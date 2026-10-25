# Adapted from jlevy/universe2026-md at 882ea44; MIT licensed.
"""
Entity IDs and the normalizers that make names from different sources line up.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal
from urllib.parse import urlparse

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# "& Co." is part of a name ("Levi Strauss & Co."), not a legal suffix.
_ORG_SUFFIX = re.compile(
    r"(?<!&)[,\s]+(inc|llc|ltd|limited|corp|corporation|co|gmbh|plc|ag|sa|s\.a)\.?$",
    re.IGNORECASE,
)
_GITHUB_LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
# Enterprise Managed Users have logins like `jdoe_acme` that public lookups never resolve.
_EMU_LOGIN = re.compile(r"^[A-Za-z0-9-]+_[A-Za-z0-9]+$")
_EMPTY_VALUES = {"", "n/a", "na", "none", "-", "no", "null"}
# `@login` mentions in a GitHub profile's company field.
COMPANY_LOGIN = re.compile(r"@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))")

HandleStatus = Literal["candidate", "absent", "invalid", "enterprise_managed"]


def slugify(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _NON_ALNUM.sub("-", folded.lower()).strip("-") or "x"


def normalize_org_name(name: str) -> str:
    """
    Strip legal suffixes so "Postman, Inc." and "Postman" become the same organization.
    Trailing parentheticals stay: "Advanced Micro Devices (AMD)" is resolved by curation.
    """
    cleaned = " ".join(name.split())
    while True:
        stripped = _ORG_SUFFIX.sub("", cleaned).strip(" ,")
        if stripped == cleaned or not stripped:
            return cleaned
        cleaned = stripped


def org_key(name: str) -> str:
    return slugify(normalize_org_name(name))


def parse_github_handle(raw: str | None) -> tuple[str | None, HandleStatus]:
    """
    Turn a free-text "GitHub handle" answer into a login. Speakers typed URLs, `@`
    prefixes and "N/A"; managed enterprise logins are kept but flagged, since they
    cannot be looked up publicly.
    """
    if raw is None:
        return None, "absent"
    value = raw.strip().lstrip("@").strip()
    if value.lower() in _EMPTY_VALUES:
        return None, "absent"
    if "github.com" in value.lower():
        path = urlparse(value if "://" in value else f"https://{value}").path
        value = next((part for part in path.split("/") if part), "")
    value = value.strip().rstrip("/")
    if _GITHUB_LOGIN.match(value):
        return value, "candidate"
    if _EMU_LOGIN.match(value):
        return value, "enterprise_managed"
    return None, "invalid"


def social_url(kind: Literal["x", "bluesky", "linkedin"], raw: str | None) -> str | None:
    """Normalize a social handle or URL to a canonical profile URL."""
    if not raw or raw.strip().lower() in _EMPTY_VALUES:
        return None
    value = raw.strip()
    if value.startswith(("http://", "https://")):
        return value
    handle = value.lstrip("@").strip("/")
    if kind == "x":
        handle = re.sub(r"^(www\.)?(twitter|x)\.com/", "", handle)
        return f"https://x.com/{handle}"
    if kind == "bluesky":
        handle = re.sub(r"^(www\.)?bsky\.app/profile/", "", handle)
        return f"https://bsky.app/profile/{handle}"
    if handle.startswith(("linkedin.com", "www.linkedin.com")):
        return f"https://{handle}"
    return f"https://www.linkedin.com/in/{handle}"


def registrable_domain(url: str | None) -> str | None:
    """
    The host without `www.` and without subdomains beyond the registrable pair, close
    enough to match a sponsor link against a GitHub organization's website.
    """
    if not url:
        return None
    url = url.strip()
    host = urlparse(url if "://" in url else f"https://{url}").hostname or ""
    parts = host.lower().removeprefix("www.").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else None


def repo_id(full_name: str) -> str:
    return f"repo:{full_name.lower()}"


def account_id(login: str) -> str:
    return f"gh:{login.lower()}"


def package_id(ecosystem: str, name: str) -> str:
    return f"pkg:{ecosystem}/{name.lower()}"
