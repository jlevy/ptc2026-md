"""Regression tests for public-data boundaries and reproducible artifact generation."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import yaml

from ptc_kb.build import Builder, build
from ptc_kb.cli import import_bios
from ptc_kb.models import Person, Profile, Repository, SocialAccount
from ptc_kb.sanitize import sanitize
from ptc_kb.validation import check_inputs, validate

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def dataset(tmp_path: Path) -> Path:
    for folder in ("curation", "raw", "synthesis"):
        shutil.copytree(ROOT / "pipeline" / folder, tmp_path / "pipeline" / folder)
    (tmp_path / "docs").mkdir()
    return tmp_path


def fingerprints(path: Path) -> dict[str, str]:
    return {
        p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in path.rglob("*")
        if p.is_file()
    }


def test_build_is_reproducible_and_all_artifacts_validate(dataset: Path) -> None:
    build(dataset)
    before = fingerprints(dataset / "kb")
    build(dataset)
    assert fingerprints(dataset / "kb") == before
    report = validate(dataset)
    assert report["ok"], report
    assert report["artifacts"] > 100


def test_event_links_survive_artifact_graph_and_search_exports(dataset: Path) -> None:
    build(dataset)
    event_id = "event:patch-the-conference-2026"
    roster = json.loads((dataset / "pipeline/curation/event.json").read_text())
    expected = {f"person:{judge['slug']}": ("judge", "confirmed") for judge in roster["judges"]}
    expected["person:kunal-kushwaha"] = ("host", "self_reported")
    people = {}
    for path in (dataset / "kb/people").glob("*.md"):
        person = yaml.safe_load(path.read_text().split("---\n")[1])["person"]
        people[person["id"]] = person
    assert people.keys() == expected.keys()
    for person_id, person in people.items():
        assert [
            (part["event"], part["role"], part["status"]) for part in person["participations"]
        ] == [(event_id, *expected[person_id])]
        assert all(part["evidence"] for part in person["participations"])
    edges = [
        json.loads(line) for line in (dataset / "kb/_graph/edges.jsonl").read_text().splitlines()
    ]
    links = [edge for edge in edges if edge["relation"] == "participates_in"]
    assert len(links) == len(expected)
    assert {(edge["source"], edge["target"], edge["role"], edge["status"]) for edge in links} == {
        (person_id, event_id, *role) for person_id, role in expected.items()
    }
    documents = [
        json.loads(line)
        for line in (dataset / "kb/_search/documents.jsonl").read_text().splitlines()
    ]
    people_docs = {doc["id"]: doc for doc in documents if doc["kind"] == "person"}
    assert people_docs.keys() == expected.keys()
    assert all(doc["events"] == [event_id] for doc in people_docs.values())


def test_host_is_self_reported_and_judges_are_organizer_listed() -> None:
    builder = Builder(ROOT)
    builder.prepare()
    people = {m.id: m for env, m, _ in builder.models.values() if isinstance(m, Person)}
    host = people["person:kunal-kushwaha"]
    assert host.inclusion_basis == "public_self_report"
    assert [(p.role, p.status) for p in host.participations] == [("host", "self_reported")]
    assert (
        sum(
            any(p.role == "judge" and p.status == "confirmed" for p in person.participations)
            for person in people.values()
        )
        == 9
    )


def test_other_platform_handles_remain_distinct() -> None:
    builder = Builder(ROOT)
    builder.prepare()
    ids = {m.id for env, m, _ in builder.models.values() if isinstance(m, SocialAccount)}
    assert "acct:other/dev.to/schezfaz" in ids
    assert "acct:other/medium.com/schezfaz" in ids


def test_raw_timelines_cannot_publish_personal_posts() -> None:
    raw = {
        "id": "example",
        "biography": "Software engineer",
        "posts": [
            {
                "description": "My family paid for my scholarship and my credit score improved.",
                "post_url": "https://x.com/example/status/1",
            },
            {
                "description": "I shipped a Python tool",
                "post_url": "https://x.com/example/status/2",
            },
        ],
    }
    assert "posts" not in sanitize("x_profiles", raw)


def test_nested_profile_allowlists_exclude_finances_visas_and_other_people() -> None:
    payload = {
        "id": "example",
        "name": "Example Engineer",
        "people_also_viewed": [{"name": "X"}],
        "education": [{"title": "Example University", "start_year": "2001", "friend": "X"}],
        "honors_and_awards": [
            {"title": "Professional software award"},
            {"title": "Conference scholarship"},
            {"title": "Global Talent Visa (UK)", "description": "Work authorization"},
        ],
        "projects": [{"title": "Compiler", "description": "A compiler", "tagged_people": ["X"]}],
    }
    result = sanitize("linkedin_profiles", payload)
    assert "people_also_viewed" not in result
    assert result["education"] == [{"title": "Example University"}]
    assert [item["title"] for item in result["honors_and_awards"]] == [
        "Professional software award"
    ]
    assert "tagged_people" not in result["projects"][0]


def test_manifest_detects_changed_evidence(dataset: Path) -> None:
    path = next((dataset / "pipeline/raw/event").glob("*.json"))
    path.write_text(path.read_text() + "\n")
    assert any("hash or length mismatch" in error for error in check_inputs(dataset))


def test_stale_bio_prevents_replacing_valid_kb(dataset: Path) -> None:
    build(dataset)
    before = fingerprints(dataset / "kb")
    path = dataset / "pipeline/curation/people/pooja-ravi.json"
    research = json.loads(path.read_text())
    research["profile"]["headline"] = "Changed professional headline"
    path.write_text(json.dumps(research))
    with pytest.raises(ValueError, match="stale bio"):
        build(dataset)
    assert fingerprints(dataset / "kb") == before
    import_bios(dataset)
    build(dataset)
    assert validate(dataset)["ok"]


def test_conflicting_employers_retain_source_attribution(dataset: Path) -> None:
    build(dataset)
    text = (dataset / "kb/people/pooja-ravi.md").read_text()
    payload = yaml.safe_load(text.split("---\n")[1])["person"]
    affiliations = {(a["organization"], a["basis"]) for a in payload["affiliations"]}
    assert ("org:netflix", "event_listing") in affiliations
    assert ("org:oracle", "linkedin") in affiliations


def test_sparse_pinned_metadata_does_not_erase_top_repository_statistics() -> None:
    builder = Builder(ROOT)
    builder.prepare()
    record = next(
        m
        for _, m, _ in builder.models.values()
        if isinstance(m, Repository) and m.id == "repo:schezfaz/spot"
    )
    assert record.stars == 14
    assert record.forks == 3
    assert record.description


def test_curated_contributor_work_keeps_relation_and_evidence() -> None:
    builder = Builder(ROOT)
    builder.prepare()
    profile = next(
        m
        for _, m, _ in builder.models.values()
        if isinstance(m, Profile) and m.person == "person:riken-shah"
    )
    assert any(
        w.repository == "repo:zulip/zulip" and w.relation == "contributor"
        for w in profile.open_source
    )
    assert (profile.model_extra or {})["open_source_evidence"]["repo:zulip/zulip"]
