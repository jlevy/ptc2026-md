# Adapted from jlevy/universe2026-md at 882ea44; MIT licensed.
"""
Compile the contracts to `schemas/` and validate `kb/` against them with softschema.
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path
from typing import Any

import softschema

from ptc_kb.models import CONTRACTS


def compile_schemas(schema_dir: Path, *, check: bool = False) -> list[str]:
    """Compile every contract; with `check`, write nothing and return the drifted files."""
    drift = []
    schema_dir.mkdir(parents=True, exist_ok=True)
    for spec in CONTRACTS.values():
        result = softschema.compile_model(
            spec.model,
            schema_dir / spec.schema_file,
            contract_id=spec.contract_id,
            check_only=check,
        )
        if result.drift:
            drift.append(spec.schema_file)
    return drift


def _contract_for(path: Path) -> tuple[softschema.Contract, Any]:
    """
    Bind an artifact the way the softschema CLI does, from its own `softschema:` block,
    and add the Pydantic model so the semantic layer runs too.
    """
    if path.suffix == ".yaml":
        profile, document = softschema.SchemaProfile.pure_yaml, softschema.read_yaml_doc(path)
    else:
        profile = softschema.SchemaProfile.frontmatter_md
        _, document = softschema.read_frontmatter_doc(path)
    metadata = softschema.parse_schema_metadata((document or {}).get("softschema"))
    if metadata is None or metadata.contract_id is None or metadata.envelope is None:
        raise ValueError(f"{path} is not a self-describing artifact")
    spec = CONTRACTS[metadata.envelope]
    contract = softschema.Contract(
        id=metadata.contract_id,
        model=spec.model,
        envelope_key=metadata.envelope,
        status=metadata.status or softschema.SchemaStatus.soft,
        profile=profile,
    )
    return contract, document


def validate_kb(kb_dir: Path) -> dict[str, Any]:
    """
    Validate every artifact through its own `softschema:` block, the same path a consumer
    takes. Schema pointers are relative to each artifact and resolve to the copies in
    `<kb>/_schemas/`; softschema rejects pointers that escape the working directory, so
    this runs from the knowledge base's parent directory.
    """
    artifacts = sorted(
        p
        for p in kb_dir.rglob("*")
        if p.suffix in {".md", ".yaml"}
        and p.name != "README.md"
        and "_graph" not in p.parts
        and "_schemas" not in p.parts
    )
    previous = Path.cwd()
    os.chdir(kb_dir.parent)
    try:
        failures = []
        contracts: Counter[str] = Counter()
        for path in artifacts:
            relative = path.relative_to(kb_dir.parent)
            contract, document = _contract_for(relative)
            result = softschema.validate_artifact(relative, contract=contract, document=document)
            contracts[result.contract_id] += 1
            if not result.ok:
                errors = [*result.structural.errors, *getattr(result.semantic, "errors", [])]
                failures.append({"path": str(path.relative_to(kb_dir)), "errors": errors[:5]})
    finally:
        os.chdir(previous)
    return {
        "artifacts": len(artifacts),
        "valid": len(artifacts) - len(failures),
        "invalid": len(failures),
        "by_contract": dict(sorted(contracts.items())),
        "failures": failures[:20],
    }
