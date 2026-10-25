"""Regression tests for repository facts and qualified GitHub identity links."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from ptc_kb.artifacts import path_for, write_artifact
from ptc_kb.build import EVENT_ID, Builder, source
from ptc_kb.graph import write_graph
from ptc_kb.models import GitHubAccount, Participation, Person, Profile, Repository

ROOT = Path(__file__).resolve().parents[2]


def export(builder: Builder, output: Path, ref: str) -> dict:
    path = path_for(ref)
    envelope, model, body = builder.models[path]
    write_artifact(
        output,
        output / "_schemas",
        model,
        envelope=envelope,
        rel_path=path,
        body=body,
    )
    content = (output / path).read_text()
    if path.endswith(".md"):
        content = content.split("---\n")[1]
    return yaml.safe_load(content)[envelope]


def edges(builder: Builder, output: Path) -> list[dict]:
    write_graph(output, builder.models)
    return [json.loads(line) for line in (output / "_graph/edges.jsonl").read_text().splitlines()]


def test_sparse_pins_preserve_unknown_facts_and_do_not_claim_maintenance(tmp_path: Path) -> None:
    builder = Builder(ROOT)
    builder.prepare()
    zulip = export(builder, tmp_path, "repo:riken-shah/zulip")
    cal = export(builder, tmp_path, "repo:calcom/cal.diy")
    for repo in (zulip, cal):
        assert not {"stars", "forks", "fork", "archived"} & repo.keys()
    graph = edges(builder, tmp_path)
    assert {
        "source": "gh:riken-shah",
        "relation": "pinned",
        "target": "repo:riken-shah/zulip",
    } in graph
    assert not any(
        edge["relation"] == "maintains" and edge["target"] == "repo:riken-shah/zulip"
        for edge in graph
    )
    spot = export(builder, tmp_path, "repo:schezfaz/spot")
    assert (spot["stars"], spot["forks"], spot["fork"]) == (14, 3, False)


def github_case(
    root: Path, github: dict, builder: Builder | None = None
) -> tuple[Builder, Person, Profile]:
    curation = root / "pipeline/curation"
    curation.mkdir(parents=True, exist_ok=True)
    (curation / "event.json").write_text('{"url": "https://example.com/conference"}')
    (curation / "organizations.json").write_text("[]")
    slug = github["login"]
    src = source(f"curation/people/{slug}.json", "https://example.com/conference")
    person = Person(
        id=f"person:{slug}",
        name="Example Engineer",
        inclusion_basis="published_by_event",
        github_resolution="unverified",
        participations=[Participation(event=EVENT_ID, role="judge", status="confirmed")],
        sources=[src],
    )
    profile = Profile(id=f"profile:{slug}", person=person.id, sources=[src])
    builder = builder or Builder(root)
    builder.github(person, profile, {"github": github}, src)
    return builder, person, profile


def test_full_observations_survive_sparse_pins_and_partial_repository_cache(tmp_path: Path) -> None:
    cache_dir = tmp_path / "pipeline/raw/github"
    cache_dir.mkdir(parents=True)
    (cache_dir / "repositories.json").write_text(
        json.dumps({"example-engineer/tool": {"record": {"archived": False}}})
    )
    builder, _, profile = github_case(
        tmp_path,
        {
            "login": "example-engineer",
            "resolution": "resolved",
            "top_repositories": [
                {
                    "full_name": "example-engineer/tool",
                    "stars": 0,
                    "forks": 2,
                    "fork": False,
                    "primary_language": "Python",
                }
            ],
            "pinned": [{"full_name": "example-engineer/tool", "stars": None}],
        },
    )
    repo = export(builder, tmp_path / "output", "repo:example-engineer/tool")
    assert (repo["stars"], repo["forks"], repo["fork"], repo["archived"]) == (0, 2, False, False)
    assert repo["primary_language"] == "Python"
    assert [(work.relation, work.stars) for work in profile.open_source] == [("owner", 0)]
    account = builder.models[path_for("gh:example-engineer")][1]
    assert isinstance(account, GitHubAccount)
    assert account.pinned == account.top_repositories == ["repo:example-engineer/tool"]


def test_medium_confidence_identity_survives_artifacts_and_graph(tmp_path: Path) -> None:
    builder = Builder(ROOT)
    builder.prepare()
    research = json.loads((ROOT / "pipeline/curation/people/manpreet-singh.json").read_text())
    curated = next(account for account in research["accounts"] if account["platform"] == "github")
    account = export(builder, tmp_path, "gh:manpoffc")
    assert account["identity_confidence"] == "medium"
    assert account["identity_link_basis"] == curated["link_basis"]
    assert set(account["link_basis"]) == {"curated"}
    assert all(
        any(
            evidence["url"] == original["url"]
            and evidence["observed_at"] == original["observed_at"]
            for evidence in account["identity_evidence"]
        )
        for original in curated["evidence"]
    )
    person = export(builder, tmp_path, "person:manpreet-singh")
    assert person["github_resolution"] == "unverified"
    assert person["github_match"] == "unconfirmed"
    assert {
        "source": "person:manpreet-singh",
        "relation": "has_account",
        "target": "gh:manpoffc",
        "match": "unconfirmed",
    } in edges(builder, tmp_path)


def test_unresolved_github_identity_is_not_promoted(tmp_path: Path) -> None:
    builder, person, profile = github_case(
        tmp_path,
        {"login": "example-engineer", "resolution": "unresolved", "identity_confidence": "high"},
    )
    assert person.github is None
    assert person.github_resolution == "unverified"
    assert not any(
        isinstance(model, (GitHubAccount, Repository)) for _, model, _ in builder.models.values()
    )
    assert not profile.open_source


def test_shared_repositories_merge_sparse_and_full_observations_in_either_order(
    tmp_path: Path,
) -> None:
    sparse = {
        "login": "example-pinner",
        "resolution": "resolved",
        "pinned": [{"full_name": "example-engineer/tool"}],
    }
    full = {
        "login": "example-engineer",
        "resolution": "resolved",
        "top_repositories": [
            {"full_name": "example-engineer/tool", "stars": 4, "forks": 2, "fork": False}
        ],
    }
    exported = []
    for index, observations in enumerate(((sparse, full), (full, sparse))):
        root = tmp_path / str(index)
        builder = None
        for observation in observations:
            builder, _, _ = github_case(root, observation, builder)
        assert builder is not None
        exported.append(export(builder, root / "output", "repo:example-engineer/tool"))
    assert exported[0] == exported[1]
    assert (exported[0]["stars"], exported[0]["forks"], exported[0]["fork"]) == (4, 2, False)
    assert exported[0]["owner"] == "gh:example-engineer"
