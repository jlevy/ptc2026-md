# Adapted from jlevy/universe2026-md at 882ea44; MIT licensed.
"""
The knowledge graph view: every entity as a node and every reference as an edge.

`kb/_graph/nodes.jsonl` and `kb/_graph/edges.jsonl` are derived from the artifacts on
each build, so graph tools (a property-graph loader, DuckDB, `jq`) can read the whole
conference without parsing YAML. Edges run only along forward references; backlink
lists in the artifacts are the same edges seen from the other end.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from strif import atomic_write_text

from ptc_kb.models import (
    Event,
    Experience,
    Facet,
    GitHubAccount,
    Organization,
    Package,
    Person,
    Profile,
    Repository,
    Room,
    Session,
    SocialAccount,
    Software,
    Venue,
    Website,
)

Edge = tuple[str, str, str, dict[str, Any]]


def _edges(model: BaseModel) -> Iterator[Edge]:
    match model:
        case Session():
            yield model.id, "part_of", model.event, {}
            for slot in model.slots:
                yield model.id, "scheduled_on", slot.day, {"start": slot.start}
                if slot.room:
                    yield model.id, "held_in", slot.room, {"start": slot.start}
            for speaker in model.speakers:
                yield speaker.person, "presents", model.id, {"role": speaker.role}
            facets = model.facets
            yield model.id, "has_type", facets.session_type, {}
            if facets.level:
                yield model.id, "has_level", facets.level, {}
            for relation, terms in (
                ("in_track", facets.tracks),
                ("about_topic", facets.topics),
                ("features_product", facets.products),
                ("for_audience", facets.audiences),
                ("for_industry", facets.industries),
                ("delivered_as", facets.delivery_formats),
                ("in_curated_agenda", facets.curated_agendas),
            ):
                for term in terms:
                    yield model.id, relation, term, {}
            for host in model.hosts:
                yield host, "hosts", model.id, {}
            for related in model.related:
                yield model.id, "related_to", related, {}
            for mention in model.mentions:
                yield model.id, "mentions", mention.target, {"field": mention.field}
        case Person():
            for affiliation in model.affiliations:
                yield (
                    model.id,
                    "affiliated_with",
                    affiliation.organization,
                    {
                        "basis": affiliation.basis,
                        "current": affiliation.current,
                        "title": affiliation.title,
                    },
                )
            for participation in model.participations:
                yield (
                    model.id,
                    "participates_in",
                    participation.event,
                    {"role": participation.role, "status": participation.status},
                )
            for account in model.accounts:
                match = model.github_match if account == model.github else None
                yield model.id, "has_account", account, {"match": match}
            for website in model.websites:
                yield model.id, "has_website", website, {}
            for mention in model.mentions:
                yield model.id, "mentions", mention.target, {"field": mention.field}
        case Profile():
            yield model.id, "describes", model.person, {}
            for claim in model.expertise:
                if claim.target:
                    yield model.person, "expert_in", claim.target, {"basis": claim.basis}
            for claim in model.technologies:
                if claim.target:
                    yield model.person, "works_with", claim.target, {"basis": claim.basis}
            relations = {"owner": "maintains", "pinned": "pins", "contributor": "contributes_to"}
            for work in model.open_source:
                yield model.person, relations[work.relation], work.repository, {}
        case SocialAccount() | Website():
            for account in getattr(model, "linked_accounts", []):
                yield model.id, "links_to", account, {}
        case Organization():
            for account in model.accounts:
                yield model.id, "has_account", account, {}
            for related in model.related_organizations:
                yield model.id, "related_to", related, {}
            for event in model.sponsored_events:
                yield (
                    model.id,
                    "sponsors",
                    event,
                    ({"tier": model.sponsorship.tier} if model.sponsorship else {}),
                )
        case Event():
            yield model.organizer, "organizes", model.id, {}
            if model.venue:
                yield model.id, "located_at", model.venue, {}
            for day in model.days:
                yield model.id, "has_day", day.id, {"date": day.date}
            for person in model.featured_speakers:
                yield model.id, "features", person, {}
        case Room():
            if model.venue:
                yield model.id, "located_in", model.venue, {}
        case Venue():
            if model.parent:
                yield model.id, "part_of", model.parent, {}
        case Experience():
            if model.venue:
                yield model.id, "located_in", model.venue, {}
        case Facet():
            for term in model.terms:
                yield f"facet:{model.id}", "has_term", term.id, {}
        case GitHubAccount():
            for repo in model.contributed_to:
                yield model.id, "contributes_to", repo, {}
            for account in model.linked_accounts:
                yield model.id, "links_to", account, {}
            for website in model.websites:
                yield model.id, "links_to", website, {}
            for repo in model.pinned:
                yield model.id, "pinned", repo, {}
            for repo in model.top_repositories:
                yield model.id, "top_repository", repo, {}
        case Repository():
            if model.owner:
                yield model.owner, "owns", model.id, {}
            if model.software:
                yield model.id, "source_of", model.software, {}
        case Package():
            if model.software:
                yield model.id, "distributes", model.software, {}
            if model.repository:
                yield model.id, "published_from", model.repository, {}
            for publisher in model.publishers:
                yield publisher, "publishes", model.id, {}
        case Software():
            if model.vendor:
                yield model.vendor, "makes", model.id, {}
            if model.product_term:
                yield model.id, "catalog_term", model.product_term, {}
        case _:
            return


def entity_nodes(model: BaseModel, rel_path: str, envelope: str) -> Iterator[dict[str, Any]]:
    if isinstance(model, Facet):
        yield {"id": f"facet:{model.id}", "kind": "facet", "name": model.label, "path": rel_path}
        for term in model.terms:
            yield {"id": term.id, "kind": "term", "name": term.label, "path": rel_path}
        return
    entity_id = getattr(model, "id", None)
    if not isinstance(entity_id, str):
        return
    name = (
        getattr(model, "name", None)
        or getattr(model, "title", None)
        or getattr(model, "full_name", None)
        or getattr(model, "login", None)
        or getattr(model, "handle", None)
        or getattr(model, "url", None)
    )
    yield {"id": entity_id, "kind": envelope, "name": name, "path": rel_path}
    if isinstance(model, Event):
        for day in model.days:
            yield {
                "id": day.id,
                "kind": "day",
                "name": f"{day.label} ({day.date})",
                "path": rel_path,
            }


def write_graph(
    kb_dir: Path, models: dict[str, tuple[str, BaseModel, str | None]]
) -> dict[str, Any]:
    nodes = [
        node
        for rel_path, (envelope, model, _) in models.items()
        for node in entity_nodes(model, rel_path, envelope)
    ]
    node_ids = {n["id"] for n in nodes}
    edges = []
    dangling = []
    for _, model, _ in models.values():
        for source, relation, target, attrs in _edges(model):
            edge = {
                "source": source,
                "relation": relation,
                "target": target,
                **{k: v for k, v in attrs.items() if v is not None},
            }
            edges.append(edge)
            if source not in node_ids or target not in node_ids:
                dangling.append(edge)
    if dangling:
        summary = Counter((e["relation"], e["target"].split("/")[0]) for e in dangling)
        raise ValueError(
            f"{len(dangling)} edges point at missing entities: "
            f"{summary.most_common(10)}; first: {dangling[:3]}"
        )
    edges.sort(key=lambda e: (e["source"], e["relation"], e["target"]))
    nodes.sort(key=lambda n: n["id"])
    stats = {
        "nodes": dict(sorted(Counter(n["kind"] for n in nodes).items())),
        "edges": dict(sorted(Counter(e["relation"] for e in edges).items())),
        "node_total": len(nodes),
        "edge_total": len(edges),
    }
    graph_dir = kb_dir / "_graph"
    atomic_write_text(
        graph_dir / "nodes.jsonl",
        "".join(json.dumps(n, ensure_ascii=False) + "\n" for n in nodes),
        make_parents=True,
    )
    atomic_write_text(
        graph_dir / "edges.jsonl", "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in edges)
    )
    atomic_write_text(graph_dir / "stats.json", json.dumps(stats, indent=2) + "\n")
    atomic_write_text(
        graph_dir / "coverage.json", json.dumps(field_coverage(models), indent=2) + "\n"
    )
    return stats


def field_coverage(
    models: dict[str, tuple[str, BaseModel, str | None]],
) -> dict[str, dict[str, Any]]:
    """
    Per entity kind, how many artifacts there are and the percentage that fill each
    field, so a site builder can see which fields to rely on.
    """
    totals: Counter[str] = Counter()
    filled: dict[str, Counter[str]] = {}
    for envelope, model, _ in models.values():
        totals[envelope] += 1
        counts = filled.setdefault(envelope, Counter())
        for key, value in model.model_dump(exclude_none=True).items():
            if value not in ([], {}, ""):
                counts[key] += 1
    return {
        envelope: {
            "count": total,
            "fields": {
                key: round(100 * count / total)
                for key, count in sorted(filled[envelope].items(), key=lambda kv: -kv[1])
            },
        }
        for envelope, total in sorted(totals.items())
    }
