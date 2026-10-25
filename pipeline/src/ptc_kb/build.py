"""Deterministic offline mapping of cited research into shared conference contracts."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel

from ptc_kb import sensitive
from ptc_kb.artifacts import path_for, write_artifact
from ptc_kb.graph import write_graph
from ptc_kb.ids import account_id, org_key, repo_id
from ptc_kb.models import (
    Activity,
    Affiliation,
    BriefBio,
    Claim,
    Credential,
    EducationEntry,
    Event,
    EventDay,
    Evidence,
    GitHubAccount,
    OpenSourceWork,
    Organization,
    Participation,
    Patent,
    Person,
    Position,
    Profile,
    Publication,
    Repository,
    SocialAccount,
    Source,
    Venue,
    Website,
    WritingItem,
)
from ptc_kb.sanitize import clean_tree, clean_url
from ptc_kb.schemas import compile_schemas
from ptc_kb.search import write_search

EVENT_ID = "event:patch-the-conference-2026"
BIO_WRITER = "GPT-6.1 Sol (OpenAI Codex)"
BIO_WRITTEN_AT = "2026-10-24T21:29:17Z"
LINK_BASES = {
    "event_listing",
    "github_profile",
    "website_rel_me",
    "website_link",
    "bluesky_profile",
    "mastodon_verified",
    "x_profile",
    "linkedin_profile",
    "attendance_post",
    "curated",
}
CLAIM_BASES = {
    "session_facets",
    "session_text",
    "bio",
    "github_profile",
    "github_repositories",
    "bluesky_profile",
    "mastodon_profile",
    "linkedin_profile",
    "x_profile",
    "website",
    "llm_synthesis",
    "curated",
}


def load(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text()) if path.is_file() else default


def text(value: Any) -> str | None:
    return " ".join(value.split()) if isinstance(value, str) and value.strip() else None


def items(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def source(
    file: str,
    url: str | None = None,
    *,
    system: str = "curation",
    record_id: str | None = None,
    observed: str | None = None,
) -> Source:
    return Source.model_validate(
        {
            "system": system,
            "url": clean_url(url),
            "snapshot": file,
            "record_id": record_id,
            "retrieved_at": observed,
        }
    )


def evidence(value: Any, fallback: str | None = None) -> list[Evidence]:
    values = items(value) if isinstance(value, list) else [value] if isinstance(value, dict) else []
    result = []
    for item in values:
        quote = text(item.get("quote"))
        if quote and sensitive.is_sensitive(quote):
            quote = None
        result.append(
            Evidence(
                url=clean_url(item.get("url")) or clean_url(fallback),
                quote=quote,
                observed_at=text(item.get("observed_at")),
            )
        )
    return result or ([Evidence(url=fallback)] if fallback else [])


def _basis(values: Any) -> list[str]:
    values = [values] if isinstance(values, str) else values or []
    aliases = {
        "github_profile_link": "github_profile",
        "same_name_employer": "curated",
        "direct_link": "website_link",
        "website": "website_link",
    }
    result: list[str] = []
    for value in values:
        mapped = aliases.get(value) or value
        result.append(mapped if mapped in LINK_BASES else "curated")
    return list(dict.fromkeys(result)) or ["curated"]


class Builder:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.pipeline = root / "pipeline"
        self.event_data = load(self.pipeline / "curation/event.json")
        self.models: dict[str, tuple[str, BaseModel, str | None]] = {}
        self.orgs: dict[str, Organization] = {}
        self.org_aliases: dict[str, str] = {}
        self.report: list[dict[str, Any]] = []
        self.linkedin = load(self.pipeline / "raw/brightdata/linkedin_profiles.json", {})
        self.x_data = load(self.pipeline / "raw/brightdata/x_profiles.json", {})
        for item in load(self.pipeline / "curation/organizations.json", []):
            name = item["name"]
            oid = "org:" + item["slug"]
            org = Organization(
                id=oid,
                name=name,
                website=clean_url(item.get("website")),
                aliases=item.get("aliases", []),
                roles=item.get("roles", ["mentioned"]),
                sponsored_events=[EVENT_ID] if "sponsor" in item["roles"] else [],
                sources=[source("curation/organizations.json", self.event_data["url"])],
            )
            self.orgs[oid] = org
            for alias in [name, *org.aliases]:
                self.org_aliases[org_key(alias)] = oid

    def add(self, envelope: str, model: BaseModel, body: str | None = None) -> None:
        ref = str(getattr(model, "id", None))
        path = path_for(ref)
        if path in self.models:
            previous = self.models[path][1]
            if previous != model:
                raise ValueError(f"conflicting entity {ref}")
            return
        self.models[path] = envelope, model, body

    def organization(self, name: str, src: Source) -> Organization:
        key = org_key(name)
        oid = self.org_aliases.get(key, f"org:{key}")
        if oid not in self.orgs:
            self.orgs[oid] = Organization(id=oid, name=name, roles=["affiliation"], sources=[src])
            self.org_aliases[key] = oid
        return self.orgs[oid]

    def event(self) -> None:
        data = self.event_data
        sources = [source("curation/event.json", u) for u in data["sources"]]
        venue = Venue(
            id="venue:bright-data-san-francisco",
            name=data["venue"],
            kind="external",
            sources=sources[:1],
        )
        self.add("venue", venue)
        event = Event(
            id=EVENT_ID,
            name=data["name"],
            series="Patch the Conference",
            edition="2026",
            organizer="org:wemakedevs",
            start=data["start"],
            end=data["end"],
            timezone=data["timezone"],
            attendance_modes=["in_person"],
            venue=venue.id,
            url=data["url"],
            days=[
                EventDay(
                    id="day:2026-10-24",
                    date=data["date"],
                    label="Saturday",
                    location="San Francisco",
                    agenda=data["agenda"],
                )
            ],
            sources=sources,
        )
        self.add("event", event, f"# {event.name}\n\nOctober 24, 2026, San Francisco.\n")

    def accounts(self, person: Person, data: dict[str, Any], src: Source) -> list[SocialAccount]:
        result = []
        for item in items(data.get("accounts")):
            if item.get("confidence") == "low":
                continue
            platform = item.get("platform")
            url = clean_url(item.get("url"))
            if not url or platform in {"github", "instagram", "threads", "facebook", "tiktok"}:
                continue
            if not item.get("evidence") and item.get("confidence") not in {"high", "medium"}:
                continue
            if platform not in {"x", "linkedin", "bluesky", "mastodon", "youtube", "other"}:
                platform = "other"
            handle = text(item.get("handle")) or urlsplit(url).path.strip("/")
            if platform == "linkedin" and not handle.startswith(("in/", "company/")):
                handle = urlsplit(url).path.strip("/")
            # IDs preserve the same typed, lowercase account path used by Universe.
            namespace = (
                (urlsplit(url).hostname or "").removeprefix("www.") + "/"
                if platform == "other"
                else ""
            )
            aid = f"acct:{platform}/{namespace}{handle.lower().lstrip('@')}"
            account = SocialAccount.model_validate(
                {
                    "id": aid,
                    "platform": platform,
                    "handle": handle,
                    "url": url,
                    "display_name": item.get("display_name"),
                    "headline": item.get("headline"),
                    "bio": item.get("bio"),
                    "location": sensitive.city_level(item.get("location")),
                    "followers": item.get("followers"),
                    "following": item.get("following"),
                    "avatar_url": clean_url(item.get("avatar_url")),
                    "owner": person.id,
                    "link_basis": _basis(item.get("link_basis")),
                    "sources": [src],
                    "details_fetched": bool(item.get("bio") or item.get("headline")),
                }
            )
            # Preserve ownership evidence alongside the shared permissive account contract.
            account.__pydantic_extra__ = {
                "identity_evidence": [
                    e.model_dump(exclude_none=True) for e in evidence(item.get("evidence"), url)
                ],
                "identity_confidence": item.get("confidence", "medium"),
            }
            existing = next((a for a in result if a.id == aid), None)
            if existing is None:
                result.append(account)
                person.accounts.append(aid)
        return result

    def websites(self, person: Person, data: dict[str, Any], src: Source) -> None:
        for item in items(data.get("websites")):
            url = clean_url(item.get("url"))
            if not url or item.get("confidence") == "low":
                continue
            parts = urlsplit(url)
            wid = "site:" + (parts.netloc.removeprefix("www.") + parts.path.rstrip("/")).lower()
            # Query-based pages need stable IDs without URL punctuation unsupported by the contract.
            wid = wid.replace("~", "-")
            site = Website.model_validate(
                {
                    "id": wid,
                    "url": url,
                    "kind": item.get("kind")
                    if item.get("kind") in {"personal", "blog", "company", "project", "other"}
                    else "other",
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "owner": person.id,
                    "link_basis": _basis(item.get("link_basis")),
                    "identity_links": [
                        u for u in map(clean_url, item.get("identity_links", [])) if u
                    ],
                    "fetch_status": "not_fetched",
                    "sources": [src],
                }
            )
            previous = self.models.get(path_for(site.id))
            if previous and isinstance(previous[1], Website) and previous[1].owner == person.id:
                previous[1].sources.extend(s for s in site.sources if s not in previous[1].sources)
            else:
                self.add("website", site)
            if site.id not in person.websites:
                person.websites.append(site.id)

    def github(self, person: Person, profile: Profile, data: dict[str, Any], src: Source) -> None:
        gh = data.get("github") or {}
        login = text(gh.get("login"))
        gh_account = next(
            (
                a
                for a in items(data.get("accounts"))
                if a.get("platform") == "github" and a.get("confidence") != "low"
            ),
            None,
        )
        if not login and gh_account:
            login = text(gh_account.get("handle"))
        if not login or gh.get("resolution") in {"unresolved", "unverified", "not_found"}:
            return
        if not gh_account and gh.get("resolution") != "resolved":
            return
        raw_path = self.pipeline / f"raw/github/{login.lower()}.json"
        gh_sources = [src]
        if raw_path.exists():
            snapshot = load(raw_path)
            meta = (snapshot.get("sources") or [{}])[0]
            gh_sources.append(
                source(
                    f"raw/github/{login.lower()}.json",
                    meta.get("url"),
                    system="github",
                    observed=meta.get("retrieved_at"),
                )
            )
        identity = gh_account or {}
        confidences = [
            value
            for value in (identity.get("confidence"), gh.get("identity_confidence"))
            if value in {"high", "medium", "low"}
        ]
        confidence = min(confidences, key=("low", "medium", "high").index) if confidences else None
        if confidence == "low":
            return
        identity_basis = list(
            dict.fromkeys([*identity.get("link_basis", []), *gh.get("identity_link_basis", [])])
        )
        identity_evidence = evidence(identity.get("evidence"))
        identity_evidence.extend(
            item for item in evidence(gh.get("evidence")) if item not in identity_evidence
        )
        account = GitHubAccount.model_validate(
            {
                "id": account_id(login),
                "login": login,
                "kind": "user",
                "url": f"https://github.com/{login}",
                "name": gh.get("name"),
                "bio": gh.get("bio"),
                "company": gh.get("company"),
                "location": sensitive.city_level(gh.get("location")),
                "website": clean_url(gh.get("blog")),
                "followers": gh.get("followers"),
                "created_at": gh.get("created_at"),
                "organization_logins": gh.get("organizations", []),
                "entity": person.id,
                "link_basis": _basis(identity_basis),
                "identity_link_basis": identity_basis,
                "identity_confidence": confidence,
                "identity_evidence": identity_evidence,
                "sources": gh_sources,
            }
        )
        # Merge metadata before creating any nodes: pinned listings are often sparse.
        merged: dict[str, dict[str, Any]] = {}
        for key in ("top_repositories", "pinned"):
            for repo in items(gh.get(key)):
                full = text(repo.get("full_name"))
                if full and "/" in full and not sensitive.is_sensitive(full):
                    record = merged.setdefault(full.lower(), {})
                    for name, value in repo.items():
                        if record.get(name) in (None, "", []):
                            record[name] = value
        cache = load(self.pipeline / "raw/github/repositories.json", {})
        work_evidence = {}
        explicit = items((data.get("profile") or {}).get("open_source"))
        for work in explicit:
            full = text(work.get("repo") or work.get("repository"))
            if full and "/" in full:
                merged.setdefault(full.lower(), {"full_name": full})
        for full, repo in merged.items():
            repo_sources = list(gh_sources)
            found = next((entry for key, entry in cache.items() if key.lower() == full), None)
            if found:
                record = found["record"]
                repo.update(
                    {
                        **{
                            target: record[key]
                            for key, target in (
                                ("stargazers_count", "stars"),
                                ("forks_count", "forks"),
                                ("language", "primary_language"),
                            )
                            if record.get(key) is not None
                        },
                        **{
                            k: record[k]
                            for k in (
                                "description",
                                "homepage",
                                "fork",
                                "archived",
                                "topics",
                                "pushed_at",
                            )
                            if record.get(k) is not None
                        },
                    }
                )
                repo_sources.append(
                    source(
                        "raw/github/repositories.json",
                        found.get("url"),
                        system="github",
                        observed=found.get("retrieved_at"),
                    )
                )
            rid = repo_id(full)
            owned = full.split("/")[0] == login.lower()
            model = Repository(
                id=rid,
                full_name=repo.get("full_name", full),
                url=f"https://github.com/{repo.get('full_name', full)}",
                description=repo.get("description"),
                homepage=clean_url(repo.get("homepage")),
                stars=repo.get("stars"),
                forks=repo.get("forks"),
                primary_language=repo.get("primary_language"),
                topics=repo.get("topics", []),
                archived=repo.get("archived"),
                fork=repo.get("fork"),
                owner_login=repo.get("full_name", full).split("/")[0],
                owner=account.id if owned else None,
                pushed_at=repo.get("pushed_at"),
                sources=repo_sources,
            )
            repo_path = path_for(rid)
            previous = self.models.get(repo_path)
            if previous and isinstance(previous[1], Repository):
                known = {
                    key: value
                    for key, value in previous[1].model_dump().items()
                    if value not in (None, "", [], {}) and key != "sources"
                }
                sources = list(previous[1].sources)
                sources.extend(item for item in model.sources if item not in sources)
                model = Repository.model_validate(
                    {
                        **model.model_dump(),
                        **known,
                        "sources": sorted(sources, key=lambda item: item.model_dump_json()),
                    }
                )
                self.models[repo_path] = "repository", model, None
            else:
                self.add("repository", model)
            # Preserve list order while linking to the shared, fully populated node.
            for key in ("pinned", "top_repositories"):
                if any(
                    str(item.get("full_name", "")).lower() == full for item in items(gh.get(key))
                ):
                    getattr(account, key).append(rid)
            works = [
                w for w in explicit if str(w.get("repo") or w.get("repository")).lower() == full
            ]
            relation = (
                "contributor"
                if any(w.get("role") == "contributor" for w in works)
                else "owner"
                if owned and model.fork is False
                else None
            )
            if relation:
                profile.open_source.append(
                    OpenSourceWork.model_validate(
                        {
                            "repository": rid,
                            "relation": relation,
                            "stars": model.stars,
                            "primary_language": model.primary_language,
                        }
                    )
                )
            if relation == "contributor":
                account.contributed_to.append(rid)
            if works:
                work_evidence[rid] = [
                    e.model_dump(exclude_none=True)
                    for work in works
                    for e in evidence(work.get("evidence"))
                ]
        if work_evidence:
            profile.__pydantic_extra__ = {
                **(profile.__pydantic_extra__ or {}),
                "open_source_evidence": work_evidence,
            }
        self.add("github_account", account)
        person.github = account.id
        person.accounts.append(account.id)
        person.github_resolution = "resolved" if confidence == "high" else "unverified"
        if confidence != "high":
            person.github_match = "unconfirmed"

    def fill_profile(self, profile: Profile, raw: dict[str, Any], fallback: str) -> None:
        for key in ("headline", "location"):
            value = text(raw.get(key))
            if value:
                setattr(profile, key, sensitive.city_level(value) if key == "location" else value)
        for key in (
            "expertise",
            "technologies",
            "programming_languages",
            "recognitions",
            "interests",
        ):
            for item in items(raw.get(key)):
                label = text(item.get("label"))
                ev = evidence(item.get("evidence"), fallback)
                if not label or sensitive.is_sensitive(label) or not ev:
                    continue
                basis = item.get("basis", "curated")
                basis = basis if basis in CLAIM_BASES else "curated"
                claim = Claim(
                    label=label,
                    basis=basis,
                    confidence=item.get("confidence", "medium"),
                    evidence=ev,
                )
                if not any(c.label == claim.label for c in getattr(profile, key)):
                    getattr(profile, key).append(claim)
        for item in items(raw.get("experience")):
            org = text(item.get("organization") or item.get("company"))
            if org:
                profile.experience.append(
                    Position(
                        organization=org,
                        title=item.get("title"),
                        start=item.get("start"),
                        end=item.get("end"),
                        current=item.get("current", item.get("end") is None),
                        description=item.get("summary") or item.get("description"),
                        evidence=evidence(item.get("evidence"), fallback)[0],
                    )
                )
        for item in items(raw.get("education")):
            school = text(item.get("school") or item.get("title"))
            if school:
                profile.education.append(
                    EducationEntry(
                        school=school,
                        degree=item.get("degree"),
                        field_of_study=item.get("field") or item.get("field_of_study"),
                        evidence=evidence(item.get("evidence"), fallback)[0],
                    )
                )
        for item in items(raw.get("credentials")):
            title = text(item.get("label") or item.get("title"))
            if title and not sensitive.is_sensitive(title):
                profile.credentials.append(
                    Credential(
                        kind=item.get("kind", "certification"),
                        title=title,
                        issuer=item.get("issuer"),
                        url=clean_url(item.get("url")),
                        evidence=evidence(item.get("evidence"), fallback)[0],
                    )
                )
        for item in items(raw.get("publications")):
            if text(item.get("title")):
                profile.publications.append(
                    Publication(
                        title=item["title"],
                        venue=item.get("venue"),
                        date=str(item.get("year")) if item.get("year") else item.get("date"),
                        url=clean_url(item.get("url")),
                        evidence=evidence(item.get("evidence"), fallback)[0],
                    )
                )
        for item in items(raw.get("recent_writing")):
            url = clean_url(item.get("url"))
            title = text(item.get("title"))
            channel = item.get("platform") or item.get("channel") or "blog"
            if channel not in {"blog", "linkedin", "x", "mastodon", "bluesky", "youtube"}:
                channel = "blog"
            if title and url and not sensitive.is_sensitive(title):
                profile.recent_writing.append(
                    WritingItem.model_validate(
                        {
                            "title": title,
                            "url": url,
                            "published": item.get("date") or item.get("published"),
                            "channel": channel,
                        }
                    )
                )
        profile.spoken_languages = list(
            dict.fromkeys(
                profile.spoken_languages
                + [v for v in raw.get("spoken_languages", []) if isinstance(v, str)]
            )
        )
        profile.current_roles = list(
            dict.fromkeys(profile.current_roles + raw.get("current_roles", []))
        )
        for item in items(raw.get("activities")):
            title = text(item.get("title"))
            if title and not sensitive.is_sensitive(title):
                profile.activities.append(
                    Activity.model_validate(
                        {
                            "kind": item.get("kind", "project"),
                            "title": title,
                            "detail": item.get("detail") or item.get("description"),
                            "evidence": evidence(item.get("evidence"), fallback)[0],
                        }
                    )
                )
        for item in items(raw.get("patents")):
            if text(item.get("title")):
                profile.patents.append(
                    Patent(
                        title=item["title"],
                        number=item.get("number"),
                        url=clean_url(item.get("url")),
                        evidence=evidence(item.get("evidence"), fallback)[0],
                    )
                )
        if raw.get("talks"):
            profile.__pydantic_extra__ = {
                **(profile.__pydantic_extra__ or {}),
                "external_talks": [
                    {
                        **item,
                        "evidence": [
                            e.model_dump(exclude_none=True)
                            for e in evidence(item.get("evidence"), item.get("url") or fallback)
                        ],
                    }
                    for item in items(raw["talks"])
                    if item.get("title") and clean_url(item.get("url"))
                ],
            }
        if raw.get("packages"):
            profile.__pydantic_extra__ = {
                **(profile.__pydantic_extra__ or {}),
                "unverified_package_mentions": items(raw["packages"]),
            }

    def linkedin_details(
        self, person: Person, profile: Profile, accounts: list[SocialAccount]
    ) -> None:
        for account in accounts:
            if account.platform != "linkedin":
                continue
            entry = next(
                (
                    v
                    for u, v in self.linkedin.items()
                    if u.rstrip("/").lower() == account.url.rstrip("/").lower()
                ),
                None,
            )
            if not entry or not entry.get("records"):
                continue
            record = entry["records"][0]
            src = source(
                "raw/brightdata/linkedin_profiles.json",
                account.url,
                system="brightdata",
                record_id=entry.get("snapshot_id"),
                observed=entry.get("retrieved_at"),
            )
            account.sources.append(src)
            profile.sources.append(src)
            account.display_name = record.get("name") or account.display_name
            account.headline = record.get("position") or account.headline
            account.bio = record.get("about") or account.bio
            account.location = sensitive.city_level(record.get("location") or record.get("city"))
            account.followers = record.get("followers")
            account.connections = record.get("connections")
            account.avatar_url = clean_url(record.get("avatar"))
            account.details_fetched = True
            profile.location = profile.location or account.location
            company = record.get("current_company") or {}
            name = text(company.get("name") or record.get("current_company_name"))
            if name:
                org = self.organization(name, src)
                person.affiliations.append(
                    Affiliation(
                        organization=org.id,
                        current=True,
                        basis="linkedin",
                        label=name,
                        evidence=[Evidence(url=account.url, observed_at=entry.get("retrieved_at"))],
                    )
                )
            ev = {"url": account.url, "observed_at": entry.get("retrieved_at")}
            self.fill_profile(
                profile,
                {
                    "education": [{**i, "evidence": [ev]} for i in items(record.get("education"))],
                    "publications": [
                        {**i, "evidence": [ev]} for i in items(record.get("publications"))
                    ],
                    "spoken_languages": [
                        i["title"] for i in items(record.get("languages")) if i.get("title")
                    ],
                },
                account.url,
            )
            for key, kind in (("honors_and_awards", "honor"), ("certifications", "certification")):
                for item in items(record.get(key)):
                    if item.get("title"):
                        profile.credentials.append(
                            Credential.model_validate(
                                {
                                    "kind": kind,
                                    "title": item["title"],
                                    "issuer": item.get("publication") or item.get("subtitle"),
                                    "date": item.get("date"),
                                    "url": clean_url(item.get("credential_url")),
                                    "description": item.get("description"),
                                    "evidence": ev,
                                }
                            )
                        )
            for key, kind in (
                ("projects", "project"),
                ("courses", "course"),
                ("volunteer_experience", "volunteering"),
                ("organizations", "organization"),
            ):
                for item in items(record.get(key)):
                    title = text(item.get("title"))
                    if title:
                        profile.activities.append(
                            Activity.model_validate(
                                {
                                    "kind": kind,
                                    "title": title,
                                    "detail": item.get("description") or item.get("subtitle"),
                                    "evidence": ev,
                                }
                            )
                        )
            for item in items(record.get("bio_links")):
                url = clean_url(item.get("link"))
                if url and urlsplit(url).hostname not in {"github.com", "www.github.com"}:
                    self.websites(
                        person,
                        {
                            "websites": [
                                {
                                    "url": url,
                                    "kind": "personal",
                                    "title": item.get("title"),
                                    "link_basis": ["linkedin_profile"],
                                }
                            ]
                        },
                        src,
                    )
            profile.gaps.append(
                "LinkedIn provides public snippets; the stored snapshot does not "
                "establish a complete employment history."
            )

    def person(self, listed: dict[str, Any]) -> None:
        slug = listed["slug"]
        is_judge = listed.get("is_judge", True)
        path = self.pipeline / f"curation/people/{slug}.json"
        data = clean_tree(load(path, {"slug": slug, "name": listed["name"]}))
        from ptc_kb.validation import bio_input_hash

        research_hash = bio_input_hash(data)
        src = source(
            f"curation/people/{slug}.json" if path.exists() else "curation/event.json",
            self.event_data["url"] + "/judges"
            if is_judge
            else next(
                (
                    e.get("url")
                    for part in items(data.get("participations"))
                    for e in items(part.get("evidence"))
                ),
                self.event_data["url"],
            ),
        )
        ev = evidence(listed.get("evidence"))
        org_name = listed.get("organization")
        org = self.organization(org_name, src) if org_name else None
        participations = (
            [Participation(event=EVENT_ID, role="judge", status="confirmed", evidence=ev)]
            if is_judge
            else [
                Participation.model_validate(
                    {
                        "event": EVENT_ID,
                        "role": item["role"],
                        "status": item.get("status", "self_reported"),
                        "evidence": evidence(item.get("evidence")),
                    }
                )
                for item in items(data.get("participations"))
                if item.get("status") == "self_reported" and item.get("evidence")
            ]
        )
        if not participations:
            raise ValueError(f"{slug} has no supported public participation evidence")
        person = Person(
            id=f"person:{slug}",
            name=listed["name"],
            job_title=listed.get("title") or data.get("job_title"),
            listed_for=EVENT_ID if is_judge else None,
            affiliation_label=org_name,
            inclusion_basis="published_by_event" if is_judge else "public_self_report",
            participations=participations,
            affiliations=[
                Affiliation(
                    organization=org.id,
                    title=listed.get("title"),
                    current=True,
                    basis="event_listing",
                    label=org_name,
                    evidence=ev,
                )
            ]
            if org
            else [],
            github_resolution="unverified",
            profile=f"profile:{slug}",
            sources=[src],
        )
        profile = Profile(
            id=f"profile:{slug}", person=person.id, sources=[src], gaps=data.get("gaps", [])
        )
        account_data = items(data.get("accounts"))
        if listed.get("linkedin") and not any(
            a.get("url", "").rstrip("/").lower() == listed["linkedin"].rstrip("/").lower()
            for a in account_data
        ):
            account_data.append(
                {
                    "platform": "linkedin",
                    "url": listed["linkedin"],
                    "handle": urlsplit(listed["linkedin"]).path.strip("/"),
                    "confidence": "high",
                    "link_basis": ["event_listing"],
                    "evidence": [listed["evidence"]],
                }
            )
        data["accounts"] = account_data
        accounts = self.accounts(person, data, src)
        self.websites(person, data, src)
        self.fill_profile(profile, data.get("profile") or {}, self.event_data["url"] + "/judges")
        for item in items(data.get("affiliations")):
            name = text(item.get("organization"))
            if not name:
                continue
            affiliated = self.organization(name, src)
            basis = item.get("basis", "curated")
            basis = {
                "linkedin_profile": "linkedin",
                "website": "self_reported",
                "x_profile": "self_reported",
            }.get(basis, basis)
            if basis not in {
                "event_listing",
                "github_profile",
                "linkedin",
                "self_reported",
                "curated",
            }:
                basis = "curated"
            affiliation = Affiliation.model_validate(
                {
                    "organization": affiliated.id,
                    "title": item.get("title"),
                    "current": item.get("current", True),
                    "basis": basis,
                    "label": name,
                    "evidence": evidence(item.get("evidence")),
                }
            )
            if affiliation not in person.affiliations:
                person.affiliations.append(affiliation)
        self.linkedin_details(person, profile, accounts)
        self.github(person, profile, data, src)
        # Sections duplicated between curation and snapshots retain the richer first record.
        for key, identity in (
            ("education", lambda item: item.school.lower()),
            ("credentials", lambda item: (item.kind, item.title.lower())),
            ("activities", lambda item: (item.kind, item.title.lower())),
            ("publications", lambda item: item.title.lower()),
        ):
            unique = {}
            for item in getattr(profile, key):
                unique.setdefault(identity(item), item)
            setattr(profile, key, list(unique.values()))
        for account in accounts:
            if account.platform == "x":
                entry = next(
                    (
                        v
                        for u, v in self.x_data.items()
                        if u.rstrip("/").lower() == account.url.rstrip("/").lower()
                    ),
                    None,
                )
                if entry and entry.get("records"):
                    record = entry["records"][0]
                    account.bio = record.get("biography") or account.bio
                    account.followers = record.get("followers")
                    account.following = record.get("following")
                    account.details_fetched = True
                    account.sources.append(
                        source(
                            "raw/brightdata/x_profiles.json",
                            account.url,
                            system="brightdata",
                            record_id=entry.get("snapshot_id"),
                            observed=entry.get("retrieved_at"),
                        )
                    )
            self.add("social_account", account)
        if not path.exists():
            profile.gaps.append("Detailed professional research has not yet been imported.")
        if person.github is None:
            profile.gaps.append("No GitHub account resolved with sufficient ownership evidence.")
        profile.gaps = list(dict.fromkeys(profile.gaps))
        bio_record = load(self.pipeline / "synthesis/brief-bios.json", {}).get(slug)
        if bio_record:
            profile.brief_bio = BriefBio.model_validate(
                {**bio_record, "stale": bio_record["input_sha256"] != research_hash}
            )
            bio = profile.brief_bio.text
        else:
            bio = (
                f"{person.name} is listed as a judge at the Patch the Conference Hackathon."
                if is_judge
                else f"{person.name} publicly reported hosting the Patch the Conference Hackathon."
            )
            bundle = {"name": person.name, "participation": listed}
            profile.brief_bio = BriefBio(
                text=bio,
                cites=["name", "participation"],
                written_by=BIO_WRITER,
                written_at=BIO_WRITTEN_AT,
                input_sha256=hashlib.sha256(
                    json.dumps(bundle, sort_keys=True).encode()
                ).hexdigest(),
                stale=False,
            )
        self.add("profile", profile)
        self.add("person", person, f"# {person.name}\n\n{bio}\n")
        self.report.append(
            {
                "name": person.name,
                "id": person.id,
                "accounts": person.accounts,
                "websites": person.websites,
                "github_resolution": person.github_resolution,
                "research_imported": path.exists(),
                "gaps": profile.gaps,
                "enrichment": {
                    "education": len(profile.education),
                    "credentials": len(profile.credentials),
                    "activities": len(profile.activities),
                    "publications": len(profile.publications),
                },
            }
        )

    def prepare(self) -> None:
        self.event()
        for listed in self.event_data["judges"]:
            self.person(listed)
        listed_slugs = {person["slug"] for person in self.event_data["judges"]}
        for path in sorted((self.pipeline / "curation/people").glob("*.json")):
            data = load(path)
            if data["slug"] not in listed_slugs:
                self.person({"slug": data["slug"], "name": data["name"], "is_judge": False})
        for org in self.orgs.values():
            org.people = sorted(
                {
                    p.id
                    for _, p, _ in self.models.values()
                    if isinstance(p, Person)
                    and any(a.organization == org.id and a.current for a in p.affiliations)
                }
            )
            self.add("organization", org)


def build(root: Path, output: Path | None = None) -> dict[str, Any]:
    root = root.resolve()
    output = output or root / "kb"
    from ptc_kb.validation import check_inputs

    errors = check_inputs(root)
    if errors:
        raise ValueError(f"input validation failed: {errors[:10]}")
    builder = Builder(root)
    builder.prepare()
    # Use the configured scratch volume; validation completes before replacing generated output.
    with tempfile.TemporaryDirectory(prefix="ptc-kb-") as temp:
        staged = Path(temp) / "kb"
        staged.mkdir()
        compile_schemas(staged / "_schemas")
        for path, (envelope, model, body) in sorted(builder.models.items()):
            write_artifact(
                staged,
                staged / "_schemas",
                model,
                envelope=envelope,
                rel_path=path,
                title=getattr(model, "name", None),
                body=body,
            )
        stats = write_graph(staged, builder.models)
        write_search(staged, builder.models)
        from ptc_kb.validation import validate

        validation = validate(root, kb=staged)
        if not validation["ok"]:
            raise ValueError(f"artifact validation failed: {validation}")
        (staged / "README.md").write_text(
            "# Patch the Conference Knowledge Base\n\n"
            f"{stats['node_total']} nodes and {stats['edge_total']} edges. "
            "Built offline from cited public sources.\n\n"
            "Entity records use relative schemas in `_schemas/`. Graph and search exports "
            "are under `_graph/` and `_search/`.\n"
        )
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(staged, output)
    report = {
        "graph": stats,
        "people": builder.report,
        "contract_extensions": ["Participation.role: judge", "Organization.sponsored_events"],
    }
    (root / "docs/build-report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    )
    return report
