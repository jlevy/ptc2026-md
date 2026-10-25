"""Offline build, validation, and explicit bio-provenance import commands."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ptc_kb.build import build
from ptc_kb.schemas import compile_schemas
from ptc_kb.validation import bio_input_hash, validate


def import_bios(root: Path) -> int:
    records = {}
    for path in sorted((root / "pipeline/curation/people").glob("*.json")):
        data = json.loads(path.read_text())
        if not data.get("brief_bio"):
            continue
        writer = (
            "OpenAI Codex (GPT-6)"
            if data["slug"] in {"pooja-ravi", "satyam-singh", "kunal-kushwaha"}
            else "GPT-6.1 Sol (OpenAI Codex)"
        )
        records[data["slug"]] = {
            "text": data["brief_bio"],
            "cites": data.get("brief_bio_cites") or data.get("sources_consulted") or ["name"],
            "basis": "llm_synthesis",
            "written_by": data.get("brief_bio_written_by", writer),
            "written_at": data.get("brief_bio_written_at")
            or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "input_sha256": bio_input_hash(data),
            "stale": False,
        }
    path = root / "pipeline/synthesis/brief-bios.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "validate", "schemas", "bios-import"])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "build":
        result = build(root)
    elif args.command == "validate":
        result = validate(root)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(0 if result["ok"] else 1)
    elif args.command == "schemas":
        result = {"drift": compile_schemas(root / "pipeline/schemas")}
    else:
        result = {"bios_imported": import_bios(root)}
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
