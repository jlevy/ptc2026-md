"""Validate provenance bytes, artifact contracts, references, bios and contact policy."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from ptc_kb import privacy
from ptc_kb.sanitize import clean_tree
from ptc_kb.schemas import validate_kb

REF = re.compile(
    r"^(?:event|day|session|person|org|room|venue|term|experience|gh|acct|site"
    r"|profile|repo|pkg|software|page):[a-z0-9][a-z0-9._/@+-]*$"
)


def bio_input_hash(data: dict[str, Any]) -> str:
    """Hash the research facts the writer saw, excluding the resulting bio itself."""
    facts = {k: v for k, v in clean_tree(data).items() if not k.startswith("brief_bio")}
    return hashlib.sha256(
        json.dumps(facts, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def check_inputs(root: Path) -> list[str]:
    raw = root / "pipeline/raw"
    manifest_path = raw / "manifest.json"
    if not manifest_path.exists():
        return ["raw/manifest.json is missing"]
    manifest = json.loads(manifest_path.read_text()).get("files", {})
    errors = []
    actual = {
        p.relative_to(raw).as_posix()
        for p in raw.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    if actual != set(manifest):
        errors.append(
            f"raw manifest mismatch: unlisted={sorted(actual - set(manifest))}, "
            f"missing={sorted(set(manifest) - actual)}"
        )
    for rel, entry in manifest.items():
        path = raw / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        if not entry.get("url") or not entry.get("retrieved_at") or not entry.get("method"):
            errors.append(f"missing provenance for raw/{rel}")
        if entry.get("sha256") != hashlib.sha256(data).hexdigest() or entry.get("bytes") != len(
            data
        ):
            errors.append(f"raw hash or length mismatch: {rel}")
    for path, kind, _ in privacy.findings(root / "pipeline/raw", root / "pipeline/curation"):
        errors.append(f"contact data ({kind}): {Path(path).relative_to(root)}")
    return errors


def _strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [s for item in value.values() for s in _strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in _strings(item)]
    return [value] if isinstance(value, str) else []


def validate(root: Path, *, kb: Path | None = None) -> dict[str, Any]:
    kb = kb or root / "kb"
    report = validate_kb(kb)
    errors = check_inputs(root)
    nodes = [json.loads(line) for line in (kb / "_graph/nodes.jsonl").read_text().splitlines()]
    ids = {node["id"] for node in nodes}
    if len(ids) != len(nodes):
        errors.append("graph has duplicate node IDs")
    for line in (kb / "_graph/edges.jsonl").read_text().splitlines():
        edge = json.loads(line)
        if edge["source"] not in ids or edge["target"] not in ids:
            errors.append(f"dangling graph edge: {edge}")
    for path in sorted(kb.rglob("*")):
        if (
            path.suffix not in {".yaml", ".md"}
            or path.name == "README.md"
            or "_schemas" in path.parts
        ):
            continue
        content = path.read_text()
        doc = yaml.safe_load(content.split("---\n")[1] if path.suffix == ".md" else content)
        envelope = doc["softschema"]["envelope"]
        payload = doc[envelope]
        for ref in _strings(payload):
            if REF.fullmatch(ref) and ref not in ids:
                errors.append(f"dangling reference in {path.relative_to(kb)}: {ref}")
        for src in payload.get("sources", []):
            rel = src.get("snapshot")
            target = (root / "pipeline" / rel).resolve() if rel else None
            if target and (not target.is_relative_to(root / "pipeline") or not target.is_file()):
                errors.append(f"missing source snapshot: {rel}")
        bio = payload.get("brief_bio")
        if bio and bio.get("stale"):
            errors.append(f"stale bio: {payload.get('id')}")
    errors += [
        f"contact data ({kind}): {Path(path).relative_to(kb)}"
        for path, kind, _ in privacy.findings(kb)
    ]
    report["provenance_errors"] = errors[:30]
    report["ok"] = not errors and not report["invalid"]
    return report
