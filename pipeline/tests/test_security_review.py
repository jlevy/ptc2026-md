"""Synthetic regressions for URL privacy and artifact confinement."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest
import yaml

from ptc_kb import privacy
from ptc_kb.artifacts import path_for, write_artifact
from ptc_kb.build import Builder
from ptc_kb.models import Person, Profile, SocialAccount, Website
from ptc_kb.sanitize import clean_tree


def test_contact_and_credential_urls_are_rejected_and_detected(tmp_path: Path) -> None:
    contact = "@".join(("fictional-user", "synthetic-contact.net"))
    encoded = quote(contact, safe="")
    deep_encoded = encoded
    for _ in range(4):
        deep_encoded = quote(deep_encoded, safe="")
    urls = [
        f"https://example.org/contact?email={encoded}",
        f"https://example.org/contact?next={quote('mailto:' + encoded, safe='')}",
        f"https://example.org/contact/{encoded}",
        f"https://example.org/contact/{deep_encoded}",
        f"https://example.org/ {contact}",
        "https://example.org/contact?phone=%2B12025550123",
        "https://example.org/contact?phone=2025550123",
        "https://example.org/?access%5Ftoken=synthetic-token",
        "https://synthetic-user:synthetic-password@example.org/",
    ]
    raw = tmp_path / "raw.json"
    raw.write_text(json.dumps({"links": [{"url": url} for url in urls]}))
    detected = privacy.findings(raw)
    assert {kind for _, kind, _ in detected} == {"address", "phone", "credentials", "url"}
    assert all(contact not in match and "synthetic-token" not in match for _, _, match in detected)
    generated = tmp_path / "generated.yaml"
    generated.write_text(yaml.safe_dump({"website": {"url": urls[0]}}))
    assert privacy.findings(generated)
    assert clean_tree({"links": urls}) == {"links": [None] * len(urls)}
    raw.write_text(json.dumps(clean_tree({"links": urls})))
    assert not privacy.findings(raw)


def test_identifier_keys_and_contact_schemes_do_not_hide_contacts(tmp_path: Path) -> None:
    contact = "@".join(("fictional-user", "synthetic-contact.net"))
    values = [contact, f"mailto:{contact}", "tel:+12025550123", "123 Example Street"]
    for value in values:
        path = tmp_path / "raw.json"
        path.write_text(json.dumps({"id": value}))
        assert privacy.findings(path)
        assert value not in str(clean_tree({"id": value}))


def test_git_named_email_is_not_a_remote(tmp_path: Path) -> None:
    contact = "@".join(("git", "example.invalid"))
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"id": contact}))
    assert privacy.scan([path]) == [(str(path), "example", privacy.EMAIL_REDACTED)]
    assert clean_tree({"id": contact}) == {"id": privacy.EMAIL_REDACTED}
    prose = f"Clone git@github.com:example/project.git; contact {contact}"
    path.write_text(json.dumps({"description": prose}))
    assert privacy.scan([path]) == [(str(path), "example", privacy.EMAIL_REDACTED)]
    assert clean_tree(prose) == prose.replace(contact, privacy.EMAIL_REDACTED)


@pytest.mark.parametrize("in_prose", [False, True])
def test_git_remote_prefix_cannot_hide_adjacent_email(tmp_path: Path, in_prose: bool) -> None:
    contact = "@".join(("repo", "synthetic-contact.net"))
    remote = f"git@github.com:owner/{contact}"
    value = f"Clone {remote} for the conference." if in_prose else remote
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"description": value}))
    detected = privacy.findings(path)
    assert detected
    assert all(contact not in match for _, _, match in detected)
    assert contact not in str(clean_tree({"description": value}))


def test_git_host_email_is_not_a_remote(tmp_path: Path) -> None:
    contact = "@".join(("fictional-user", "github.com"))
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"id": contact}))
    assert privacy.findings(path) == [(str(path), "address", privacy.EMAIL_REDACTED)]
    assert clean_tree({"id": contact}) == {"id": privacy.EMAIL_REDACTED}


@pytest.mark.parametrize(
    "url",
    [
        "git+https://synthetic-access-token@github.com/owner/repo",
        "git+https://git@github.com:443/repo?token=synthetic-token",
        "Clone git+https://git@github.com:443/repo?token=synthetic-token for the conference.",
    ],
)
def test_git_https_userinfo_cannot_hide_credentials(tmp_path: Path, url: str) -> None:
    path = tmp_path / "raw.json"
    path.write_text(json.dumps({"id": url}))
    detected = privacy.findings(path)
    assert {kind for _, kind, _ in detected} == {"credentials"}
    assert all("synthetic-access-token" not in match for _, _, match in detected)
    assert clean_tree({"id": url}) == {"id": None}


def test_public_urls_and_numeric_account_ids_survive(tmp_path: Path) -> None:
    public = {
        "id": "acct:linkedin/123456789012345",
        "handle": "123456789012345",
        "url": "https://www.linkedin.com/in/123456789012345",
        "link": "https://example.org/paper/2026?author=123456789012345&view=abstract",
        "git_remote": "git@github.com:example/project.git",
        "description": "Clone git@github.com:example/project.git for the conference.",
        "git_https": "git+https://github.com/example/project.git",
        "cdn": "https://cdn.example.org/image?signature=public-image-signature",
        "mastodon": "acct:mastodon/example@mastodon.social",
    }
    assert clean_tree(public) == public
    path = tmp_path / "public.json"
    path.write_text(json.dumps(public))
    assert not privacy.findings(path)


def _website() -> Website:
    return Website(
        id="site:example.org/public",
        url="https://example.org/public",
        kind="personal",
        link_basis=["curated"],
        fetch_status="not_fetched",
        sources=[],
    )


def test_artifact_resolver_rejects_traversal_ids() -> None:
    for ref in (
        "site:example.org/../../../escaped",
        "repo:example/../../escaped",
        "site:/absolute",
        "site:example.org/./alias",
        "term:../escaped/topic",
    ):
        with pytest.raises(ValueError, match="artifact path"):
            path_for(ref)
    assert path_for("site:example.org/papers/2026") == "websites/example.org/papers/2026.yaml"
    assert path_for("acct:linkedin/123456789012345") == "accounts/linkedin/123456789012345.yaml"


def test_artifact_writer_rejects_escaping_paths_before_writing(tmp_path: Path) -> None:
    kb = tmp_path / "kb"
    kb.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (kb / "linked").symlink_to(outside, target_is_directory=True)
    (kb / "linked-file.yaml").symlink_to(outside / "file.yaml")
    for rel_path in (
        "new/../../escaped.yaml",
        (outside / "absolute.yaml").as_posix(),
        "linked/escaped.yaml",
        "linked-file.yaml",
    ):
        with pytest.raises(ValueError, match="artifact path"):
            write_artifact(kb, kb / "_schemas", _website(), envelope="website", rel_path=rel_path)
    assert not (tmp_path / "escaped.yaml").exists()
    assert not (kb / "new").exists()
    assert not list(outside.iterdir())
    rel_path = path_for(_website().id)
    assert (
        write_artifact(kb, kb / "_schemas", _website(), envelope="website", rel_path=rel_path)
        == rel_path
    )
    assert yaml.safe_load((kb / rel_path).read_text())["website"]["id"] == _website().id


def test_builder_rejects_profile_website_traversal(tmp_path: Path) -> None:
    raw = tmp_path / "pipeline/raw/brightdata/linkedin_profiles.json"
    raw.parent.mkdir(parents=True)
    url = "https://www.linkedin.com/in/example"
    raw.write_text(
        json.dumps(
            {url: {"records": [{"bio_links": [{"link": "https://example.org/../../../escaped"}]}]}}
        )
    )
    escaped = tmp_path / "escaped.yaml"
    escaped.write_text("synthetic sentinel\n")
    builder = Builder(tmp_path)
    person = Person.model_validate(
        {
            "id": "person:example",
            "name": "Example Engineer",
            "inclusion_basis": "curated",
            "participations": [{"event": "event:example", "role": "judge", "status": "confirmed"}],
            "github_resolution": "absent",
            "sources": [],
        }
    )
    account = SocialAccount(
        id="acct:linkedin/example",
        platform="linkedin",
        handle="example",
        url=url,
        link_basis=["curated"],
        sources=[],
    )
    profile = Profile(id="profile:example", person=person.id, sources=[])
    with pytest.raises(ValueError, match="artifact path"):
        builder.linkedin_details(person, profile, [account])
    assert not builder.models
    assert not person.websites
    assert escaped.read_text() == "synthetic sentinel\n"
