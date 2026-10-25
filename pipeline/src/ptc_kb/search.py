# Adapted from jlevy/universe2026-md at 882ea44; MIT licensed.
"""
Search documents: one per entity, for a site's full-text index (Pagefind, Lunr,
Typesense, SQLite FTS and the like).

Derived from the artifacts like the graph export, so nothing here is a new fact. Each
document gathers an entity's display title, a short summary, its free text, the names of
the entities it references (a session's speakers and companies, a person's talks), its
image and the events it belongs to. Profiles fold into their person; glossary terms and
FAQ entries get documents of their own.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from strif import atomic_write_text

from ptc_kb.graph import entity_nodes
from ptc_kb.ids import slugify
from ptc_kb.models import Facet, Faq, MediaIndex, Profile

# Provenance and bookkeeping, not text anyone searches for.
SKIP_KEYS = {
    "sources",
    "evidence",
    "input_sha256",
    "cites",
    "link_basis",
    "fetch_status",
    "written_by",
    "written_at",
    "source_id",
    "source_ids",
    "stale",
    "gaps",
    "basis",
    "exhibitor_id",
    "record_id",
}
REF = re.compile(
    r"^(?:session|person|org|room|venue|term|day|event|experience|gh|acct|site"
    r"|profile|repo|pkg|software|page|facet):\S+$"
)
TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+(?:Z|[+-]\d{2}:\d{2})?)?$")
SUMMARY_KEYS = ("description", "abstract", "tagline", "bio", "headline", "summary")
IMAGE_KEYS = ("photo_url", "logo_url", "image_url", "avatar_url")
MAX_TEXT = 4000
MAX_SUMMARY = 280


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in SKIP_KEYS:
                yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)
    elif isinstance(value, str) and value.strip():
        yield value


def _document(
    entity_id: str,
    kind: str,
    title: str,
    path: str,
    data: dict[str, Any],
    names: dict[str, str],
    summary: str | None = None,
) -> dict[str, Any]:
    texts: list[str] = []
    related: list[str] = []
    events: set[str] = set()
    for text in _strings(data):
        if REF.match(text):
            if text.startswith("event:"):
                events.add(text)
            if text != entity_id and text in names:
                related.append(names[text])
        elif not text.startswith(("http://", "https://")) and not TIMESTAMP.match(text):
            texts.append(text)
    if summary is None:
        summary = next((data[k] for k in SUMMARY_KEYS if isinstance(data.get(k), str)), None)
    image = next((data[k] for k in IMAGE_KEYS if isinstance(data.get(k), str)), None)
    document = {
        "id": entity_id,
        "kind": kind,
        "title": title,
        "path": path,
        "summary": _clip(summary, MAX_SUMMARY) if summary else None,
        "text": _clip(" ".join(dict.fromkeys(texts)), MAX_TEXT),
        "related": list(dict.fromkeys(related)),
        "events": sorted(events),
        "image": image,
    }
    return {k: v for k, v in document.items() if v not in (None, [], "")}


def search_documents(models: dict[str, tuple[str, BaseModel, str | None]]) -> list[dict[str, Any]]:
    names = {
        node["id"]: node["name"]
        for rel_path, (envelope, model, _) in models.items()
        for node in entity_nodes(model, rel_path, envelope)
        if node.get("name")
    }
    profiles = {m.person: m for _, m, _ in models.values() if isinstance(m, Profile)}
    documents = []
    for rel_path, (envelope, model, _) in models.items():
        if isinstance(model, (Profile, MediaIndex)):
            continue
        if isinstance(model, Facet):
            for term in model.terms:
                documents.append(
                    _document(
                        term.id,
                        "term",
                        term.label,
                        rel_path,
                        {
                            "label": term.label,
                            "description": term.description,
                            "facet": f"facet:{model.id}",
                            "event": model.event,
                        },
                        names,
                    )
                )
            continue
        if isinstance(model, Faq):
            for entry in model.entries:
                documents.append(
                    _document(
                        f"faq:{slugify(entry.question)[:80]}",
                        "faq_entry",
                        entry.question,
                        rel_path,
                        {"answer": entry.answer, "event": model.event},
                        names,
                        summary=entry.answer,
                    )
                )
            continue
        entity_id = getattr(model, "id", None)
        if not isinstance(entity_id, str):
            continue
        data = model.model_dump(mode="json", exclude_none=True)
        summary = None
        profile = profiles.get(entity_id)
        if profile:
            profile_data = profile.model_dump(mode="json", exclude_none=True)
            data["profile"] = {k: v for k, v in profile_data.items() if k not in {"id", "person"}}
            summary = profile.brief_bio.text if profile.brief_bio else None
        title = names.get(entity_id) or entity_id
        documents.append(_document(entity_id, envelope, title, rel_path, data, names, summary))
    documents.sort(key=lambda d: d["id"])
    return documents


def write_search(
    kb_dir: Path, models: dict[str, tuple[str, BaseModel, str | None]]
) -> dict[str, int]:
    documents = search_documents(models)
    atomic_write_text(
        kb_dir / "_search" / "documents.jsonl",
        "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in documents),
        make_parents=True,
    )
    return dict(sorted(Counter(d["kind"] for d in documents).items()))
