"""Allowlisted public profile snapshots, with nested and contact-data filtering.

Field choices follow universe2026-md's Bright Data sanitizer at 882ea44 (MIT).
Unknown fields are discarded, including future provider additions.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ptc_kb import privacy, sensitive

EXCLUDED = {"instagram.com", "threads.net", "threads.com", "facebook.com", "fb.com", "tiktok.com"}
PROFILE = {
    "id",
    "url",
    "name",
    "first_name",
    "last_name",
    "position",
    "about",
    "city",
    "location",
    "followers",
    "connections",
    "avatar",
    "banner_image",
    "current_company",
    "current_company_name",
    "bio_links",
    "experience",
    "education",
    "certifications",
    "honors_and_awards",
    "publications",
    "patents",
    "languages",
    "projects",
    "courses",
    "volunteer_experience",
    "organizations",
    "posts",
    "timestamp",
}
X_FIELDS = {
    "x_id",
    "url",
    "id",
    "profile_name",
    "biography",
    "is_verified",
    "profile_image_link",
    "external_link",
    "date_joined",
    "following",
    "followers",
    "location",
    "posts_count",
    "posts",
    "banner_image",
    "timestamp",
}
NESTED = {
    "current_company": {"name", "company_id", "link"},
    "bio_links": {"title", "link"},
    "experience": {"title", "company", "subtitle", "start_date", "end_date", "description"},
    "education": {"title", "url", "degree", "field"},
    "certifications": {"title", "subtitle", "meta", "credential_url"},
    "honors_and_awards": {"title", "publication", "date", "description"},
    "publications": {"title", "subtitle", "date", "description", "url", "link"},
    "patents": {"title", "patents_id", "date_issued", "description", "url"},
    "languages": {"title", "subtitle"},
    "projects": {"title", "start_date", "end_date", "description"},
    "courses": {"title", "subtitle", "description"},
    "volunteer_experience": {"title", "subtitle", "cause", "info", "duration"},
    "organizations": {"title", "subtitle", "description"},
}


def clean_url(value: Any) -> str | None:
    if not isinstance(value, str) or not value.startswith(("https://", "http://")):
        return None
    if any(c.isspace() or ord(c) < 32 for c in value) or privacy.url_findings(value):
        return None
    try:
        parts = urlsplit(value)
        if not parts.hostname or (parts.port is not None and not 0 < parts.port < 65536):
            return None
    except ValueError:
        return None
    host = (parts.hostname or "").lower().removeprefix("www.")
    if (
        parts.username
        or parts.password
        or any(host == h or host.endswith("." + h) for h in EXCLUDED)
    ):
        return None
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(("utm_", "trk"))]
    )
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, ""))


def clean_tree(value: Any, key: str = "") -> Any:
    """Sanitize contact details throughout a tree, including URL-valued fields."""
    if isinstance(value, dict):
        return {k: clean_tree(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_tree(v, key) for v in value]
    if isinstance(value, str):
        if value.lower().startswith(("http://", "https://")):
            return clean_url(value)
        if value.lower().startswith(("mailto:", "tel:")):
            return None
        if privacy.is_identifier(key, value):
            return value
        if any(privacy.url_findings(m.group(0)) for m in privacy.URL_IN_TEXT.finditer(value)):
            return None
        return privacy.redact_addresses(privacy.redact(value))
    return value


def sanitize(dataset: str, record: dict[str, Any]) -> dict[str, Any]:
    if record.get("error") or record.get("error_code"):
        return {"error_code": record.get("error_code") or "error"}
    allowed = PROFILE if dataset == "linkedin_profiles" else X_FIELDS
    if dataset not in {"linkedin_profiles", "x_profiles"}:
        raise ValueError(f"unsupported profile dataset: {dataset}")
    result = {k: v for k, v in record.items() if k in allowed}
    for field in ("city", "location"):
        if field in result:
            result[field] = sensitive.city_level(result[field])
    if dataset == "linkedin_profiles":
        for field, keys in NESTED.items():
            value = result.get(field)
            if isinstance(value, dict):
                result[field] = {k: v for k, v in value.items() if k in keys}
            elif isinstance(value, list):
                result[field] = [
                    {k: v for k, v in item.items() if k in keys}
                    for item in value
                    if isinstance(item, dict)
                ]
        for field in (
            "projects",
            "courses",
            "organizations",
            "honors_and_awards",
            "certifications",
            "volunteer_experience",
        ):
            result[field] = [
                item
                for item in result.get(field) or []
                if not sensitive.is_sensitive(" ".join(map(str, item.values())))
                and not re.search(
                    r"scholarship|\bvisa\b|immigra|work authori",
                    " ".join(map(str, item.values())),
                    re.I,
                )
                and (
                    field != "volunteer_experience"
                    or item.get("cause") in {"Education", "Science and Technology"}
                )
            ]
        for item in result.get("certifications") or []:
            item["meta"] = re.sub(r"\s*Credential ID \S+", "", item.get("meta") or "")
            if re.search(
                r"transcript|drive\.google|docs\.google|/share|sharing",
                item.get("credential_url") or "",
                re.I,
            ):
                item.pop("credential_url", None)
        # The recovered LinkedIn posts lack reliable owner attribution; exclude them.
        result.pop("posts", None)
    else:
        # Raw post bodies are unnecessary for profile enrichment. Selected professional
        # writing is separately curated with evidence, never bulk imported from timelines.
        result.pop("posts", None)
    return clean_tree(result)
