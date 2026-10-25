# Adapted from jlevy/universe2026-md at 882ea44; MIT licensed.
"""
Contact details stay out of everything committed: the knowledge base, the raw snapshot,
the synthesis and the tests.

People and organizations publish email addresses and phone numbers in profile READMEs,
bios, company pages and posts, but the knowledge base is about what people do, not how
to reach them. The build and the raw sanitizer redact both from free text, and
`findings` scans any directory so a test can prove none slipped through.

Identifiers are left alone: a Mastodon handle (`user@host`) looks like an email but is
an account ID, and typed references and Git remotes (`git@github.com:owner/repo`)
are not free text. URL path and query components are checked after bounded decoding.
`findings` also accepts the reserved example domains tests use
(`ada@example.com`) and phone numbers reserved for fiction (`555-0123`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote, urlsplit

import yaml

# An address not preceded by "@", so "@user@host" Mastodon mentions do not match, and not
# a Git remote or an image scale suffix ("logo@2x.png").
EMAIL = re.compile(
    r"(?<![@\w.+-])(?!git@)[\w.+-]+@[\w-]+(?:\.[\w-]+)*"
    r"\.(?!(?:png|jpe?g|gif|svg|webp|avif|pdf|ya?ml|md|jsonl?)\b)[A-Za-z]{2,}(?![\w-])"
)
# An address written out to dodge scrapers: "ada at example dot com", "ada [at] example
# [dot] com", "ada(at)example.com". A bare " at " needs a spelled-out " dot " too, so
# "meet at github.com" is not an address.
OBFUSCATED_EMAIL = re.compile(
    r"(?<![\w.+-])[\w.+-]+\s*[\[({<]\s*at\s*[\])}>]\s*[\w-]+"
    r"(?:\s*(?:[\[({<]\s*dot\s*[\])}>]|\.|\s+dot\s+)\s*[\w-]+)+"
    r"|(?<![\w.+-])[\w.+-]+\s+at\s+[\w-]+(?:\s+dot\s+[\w-]+)+",
    re.IGNORECASE,
)
# North American numbers, and international ones written with a leading "+".
PHONE = re.compile(
    r"(?<![\w.])(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?![\w-]|\.\d)"
    r"|(?<![\w.+])\+\d{1,3}(?:[\s.-]?\(?\d{1,5}\)?){2,6}(?![\w-]|\.\d)"
)
MIN_PHONE_DIGITS = 7
EMAIL_REDACTED = "[email removed]"
PHONE_REDACTED = "[phone removed]"
# Only recognized identifier syntax is exempt; a field named `id` can carry contact data.
REF = re.compile(
    r"^(?:event|day|session|person|org|room|venue|term|experience|gh|acct|site|profile|page"
    r"|repo|pkg|software):[a-z0-9][a-z0-9._/@+-]*$"
)
GIT_REMOTE = re.compile(
    r"^git@[a-z0-9.-]+:[\w.-]+/[\w./-]+$",
    re.IGNORECASE,
)
MASTODON_ACCOUNT = re.compile(r"^acct:mastodon/[\w.+-]+@[a-z0-9.-]+$", re.IGNORECASE)
URL_IN_TEXT = re.compile(r"(?:https?://|mailto:|tel:)[^\s<>\"']+", re.IGNORECASE)
URL_DECODE_LIMIT = 3
URL_QUERY_LIMIT = 256
CREDENTIAL_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth_token",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "session",
    "sessionid",
    "token",
}
CONTACT_KEYS = {"email", "e-mail", "phone", "telephone", "mobile", "tel", "address"}
CREDENTIAL_REDACTED = "[credentials removed]"
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".jsonl", ".html", ".py", ".txt", ".toml"}
# Domains reserved for examples (RFC 2606 and RFC 6761); no one can be reached there.
RESERVED_DOMAIN = re.compile(
    r"(?:^|\.)(?:example|test|invalid|localhost)$"
    r"|^example\.(?:com|net|org)$",
    re.IGNORECASE,
)
# Numbers reserved for fiction: 555-0100 to 555-0199 in North America, and London's
# 020 7946 0000 to 0999.
FICTIONAL_PHONE = re.compile(r"555[\s.)-]*01\d\d|20[\s.)-]*7946[\s.-]*0\d{3}")
MASTODON_HOST = re.compile(
    r"https?://([a-z0-9.-]+\.[a-z]{2,})/@\w"
    r"|acct:mastodon/[^@\s]+@([a-z0-9.-]+\.[a-z]{2,})",
    re.IGNORECASE,
)


# A street address in free text: a number and a street name, a German-style street and
# number, or a post office box. Organizations' imprints and "contact us" blocks carry them.
STREET_ADDRESS = re.compile(
    r"\b\d{1,5}[A-Za-z]?\s+(?:[A-Z][\w'.-]*\s+){1,4}(?:Street|St|Avenue|Ave|Road|Rd"
    r"|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Place|Pl|Court|Ct|Parkway|Pkwy)\b\.?"
    r"|\b[A-ZÄÖÜ][\wäöüß-]*(?:straße|strasse|weg|gasse|platz|allee)\s+\d{1,4}[a-z]?\b"
    r"|\bP\.?\s?O\.?\s?Box\s+\d+",
)
ADDRESS_REDACTED = "[address removed]"


def redact_addresses(text: str) -> str:
    """Street addresses in free text about a person or organization; venues keep theirs."""
    return STREET_ADDRESS.sub(ADDRESS_REDACTED, text)


def _phones(text: str) -> list[str]:
    return [
        m.group(0)
        for m in PHONE.finditer(text)
        if sum(c.isdigit() for c in m.group(0)) >= MIN_PHONE_DIGITS
    ]


def redact(text: str) -> str:
    text = OBFUSCATED_EMAIL.sub(EMAIL_REDACTED, EMAIL.sub(EMAIL_REDACTED, text))
    for number in _phones(text):
        text = text.replace(number, PHONE_REDACTED)
    return text


def is_identifier(key: str | None, value: str) -> bool:
    return bool(
        GIT_REMOTE.fullmatch(value)
        or MASTODON_ACCOUNT.fullmatch(value)
        or (REF.fullmatch(value) and not EMAIL.search(value) and not _phones(value))
    )


def _decode_component(value: str) -> str:
    for _ in range(URL_DECODE_LIMIT):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    return value


def url_findings(value: str) -> list[tuple[str, str]]:
    """Inspect bounded, decoded URL components without returning contact or secret values."""
    found: list[tuple[str, str]] = []
    lowered = value.lower()
    if lowered.startswith("mailto:"):
        found.append(("address", EMAIL_REDACTED))
    elif lowered.startswith("tel:"):
        found.append(("phone", PHONE_REDACTED))
    try:
        parts = urlsplit(value)
        if parts.username is not None or parts.password is not None:
            found.append(("credentials", CREDENTIAL_REDACTED))
        query = parse_qsl(parts.query, keep_blank_values=True, max_num_fields=URL_QUERY_LIMIT)
    except ValueError:
        return [("url", "[invalid URL removed]")]
    for key, content in query:
        key = _decode_component(key).lower()
        if re.search(r"%[0-9a-f]{2}", key):
            found.append(("url", "[over-encoded URL removed]"))
        if key in CREDENTIAL_KEYS and content:
            found.append(("credentials", CREDENTIAL_REDACTED))
        elif key in CONTACT_KEYS and content:
            kind = "phone" if key in {"phone", "telephone", "mobile", "tel"} else "address"
            found.append((kind, PHONE_REDACTED if kind == "phone" else ADDRESS_REDACTED))
    # The host is an identity, while paths and query values may carry contact details.
    for component in [parts.path, parts.fragment, *(v for _, v in query)]:
        decoded = _decode_component(component)
        if re.search(r"%[0-9a-f]{2}", decoded, re.IGNORECASE):
            found.append(("url", "[over-encoded URL removed]"))
        if (
            "mailto:" in decoded.lower()
            or EMAIL.search(decoded)
            or OBFUSCATED_EMAIL.search(decoded)
        ):
            found.append(("address", EMAIL_REDACTED))
        if "tel:" in decoded.lower() or _phones(decoded):
            found.append(("phone", PHONE_REDACTED))
        if STREET_ADDRESS.search(decoded):
            found.append(("address", ADDRESS_REDACTED))
    return list(dict.fromkeys(found))


def redact_payload(value: Any, key: str | None = None) -> Any:
    """A copy of a payload with contact details removed from its free text."""
    if isinstance(value, dict):
        return {k: redact_payload(v, k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_payload(v, key) for v in value]
    if isinstance(value, str) and not is_identifier(key, value):
        if any(url_findings(m.group(0)) for m in URL_IN_TEXT.finditer(value)):
            return None
        return redact_addresses(redact(value))
    return value


# Large Mastodon servers, on top of those the scanned data itself shows to be Mastodon.
KNOWN_MASTODON = {
    "mastodon.social",
    "mastodon.online",
    "mas.to",
    "fosstodon.org",
    "hachyderm.io",
    "infosec.exchange",
    "techhub.social",
    "indieweb.social",
}
# A user name before one of these hosts is a Git remote's (`git+https://ada@github.com/…`).
GIT_HOSTS = {"github.com", "gitlab.com", "bitbucket.org"}


def email_kind(address: str, mastodon_hosts: set[str]) -> str:
    """
    "mastodon" for a handle on a Mastodon server, "git" for a Git remote's user name,
    "example" for a reserved example domain, and "address" for anything that may reach
    someone.
    """
    host = address.rsplit("@", 1)[-1].lower()
    if host in mastodon_hosts | KNOWN_MASTODON:
        return "mastodon"
    if host in GIT_HOSTS:
        return "git"
    if RESERVED_DOMAIN.search(host):
        return "example"
    return "address"


def _deobfuscate(text: str) -> str:
    """`ada at example dot com` as `ada@example.com`, so it can be classified."""
    text = re.sub(r"\s*[\[({<]\s*at\s*[\])}>]\s*|\s+at\s+", "@", text, flags=re.IGNORECASE)
    return re.sub(r"\s*[\[({<]\s*dot\s*[\])}>]\s*|\s+dot\s+", ".", text, flags=re.IGNORECASE)


def _strings(value: Any, key: str | None = None) -> Iterable[str]:
    """Strings in parsed data, excluding only precise public identifier forms."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _strings(v, k)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item, key)
    elif isinstance(value, str) and not is_identifier(key, value):
        yield value


def _file_strings(path: Path, text: str) -> Iterable[str]:
    if path.suffix == ".json":
        yield from _strings(json.loads(text))
    elif path.suffix == ".jsonl":
        for line in text.splitlines():
            yield from _strings(json.loads(line))
    elif path.suffix in {".yaml", ".yml"} or (path.suffix == ".md" and text.startswith("---\n")):
        front, _, body = text.removeprefix("---\n").partition("\n---\n")
        yield from _strings(
            yaml.load(front if path.suffix == ".md" else text, Loader=yaml.CSafeLoader)
        )
        if path.suffix == ".md":
            yield body
    else:
        yield text


def _files(roots: Iterable[Path]) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*"))
        paths += [p for p in candidates if p.is_file() and p.suffix in TEXT_SUFFIXES]
    return paths


def mastodon_hosts(texts: Iterable[str]) -> set[str]:
    """Servers that some profile URL or account ID in `texts` shows to be Mastodon."""
    hosts: set[str] = set()
    for text in texts:
        hosts.update((a or b).lower() for a, b in MASTODON_HOST.findall(text))
    return hosts


def scan(roots: Iterable[Path]) -> list[tuple[str, str, str]]:
    """(path, kind, redacted marker) for contact details and unsafe URLs under `roots`."""
    files = {path: path.read_text(errors="replace") for path in _files(roots)}
    hosts = mastodon_hosts(files.values())
    found = []
    for path, text in files.items():
        for string in _file_strings(path, text):
            found += [
                (str(path), kind, match)
                for url in URL_IN_TEXT.finditer(string)
                for kind, match in url_findings(url.group(0))
            ]
            string = URL_IN_TEXT.sub(" ", string)
            found += [
                (str(path), "address", ADDRESS_REDACTED) for _ in STREET_ADDRESS.finditer(string)
            ]
            found += [
                (str(path), email_kind(m, hosts), EMAIL_REDACTED) for m in EMAIL.findall(string)
            ]
            found += [
                (str(path), email_kind(_deobfuscate(m.group(0)), hosts), EMAIL_REDACTED)
                for m in OBFUSCATED_EMAIL.finditer(string)
            ]
            found += [
                (str(path), "example" if FICTIONAL_PHONE.search(m) else "phone", PHONE_REDACTED)
                for m in _phones(string)
            ]
    return found


def findings(*roots: Path) -> list[tuple[str, str, str]]:
    """Contact, credential and unsafe-URL findings, without echoing the matched values."""
    return [f for f in scan(roots) if f[1] in {"address", "phone", "credentials", "url"}]
