# Adapted from jlevy/universe2026-md at 882ea44; MIT licensed.
"""
Writing softschema artifacts: YAML style, the `softschema:` block, and where each entity
lives in `kb/`.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from strif import atomic_write_text

from ptc_kb.models import CONTRACTS

STATUS = "permissive"

# Where each ID prefix lives, relative to the knowledge base root.
_LAYOUT = {
    "event": ("events/{}", ".md"),
    "session": ("sessions/{}", ".md"),
    "person": ("people/{}", ".md"),
    "org": ("organizations/{}", ".md"),
    "room": ("rooms/{}", ".yaml"),
    "venue": ("venues/{}", ".yaml"),
    "experience": ("experiences/{}", ".yaml"),
    "gh": ("accounts/github/{}", ".yaml"),
    "acct": ("accounts/{}", ".yaml"),
    "site": ("websites/{}", ".yaml"),
    "profile": ("profiles/{}", ".yaml"),
    "page": ("pages/{}", ".md"),
    "repo": ("repositories/{}", ".yaml"),
    "pkg": ("packages/{}", ".yaml"),
    "software": ("software/{}", ".yaml"),
}


def _relative_path(value: str) -> Path:
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or "\x00" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("unsafe artifact path: expected a relative path without dot segments")
    return path


def path_for(ref: str) -> str:
    """The artifact path, relative to `kb/`, that defines the entity `ref` names."""
    prefix, _, rest = ref.partition(":")
    _relative_path(rest)
    if prefix == "term":
        return f"taxonomy/{rest.split('/', 1)[0]}.yaml"
    if prefix == "day":
        # Days live in their event's artifact: day:2026-10-28 → events/github-universe-2026.md.
        return "events/patch-the-conference-2026.md"
    template, suffix = _LAYOUT[prefix]
    return template.format(rest) + suffix


class _Dumper(yaml.SafeDumper):
    # softschema rejects anchors and aliases, so shared objects must be written out twice.
    def ignore_aliases(self, data: Any) -> bool:
        return True


# Digit strings PyYAML writes plain but a YAML 1.2 reader takes as numbers ("000438289").
_NUMERIC_LOOKING = re.compile(r"^[-+]?[0-9][0-9_]*(?:\.[0-9_]*)?(?:[eE][-+]?[0-9]+)?$")


def _str_representer(dumper: yaml.SafeDumper, value: str) -> yaml.ScalarNode:
    style = "|" if "\n" in value else "'" if _NUMERIC_LOOKING.match(value) else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str_representer)


def to_yaml(data: Any) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)


def prune(value: Any) -> Any:
    """Drop `None` and empty collections so files show only what is known."""
    if isinstance(value, dict):
        pruned = {k: prune(v) for k, v in value.items()}
        return {k: v for k, v in pruned.items() if v is not None and v != [] and v != {}}
    if isinstance(value, list):
        return [prune(v) for v in value]
    return value


def payload(model: BaseModel) -> dict[str, Any]:
    return prune(model.model_dump(mode="json"))


def write_artifact(
    kb_dir: Path,
    schema_dir: Path,
    model: BaseModel,
    *,
    envelope: str,
    rel_path: str,
    title: str | None = None,
    body: str | None = None,
) -> str:
    """
    Write one artifact and return its path relative to `kb_dir`. Markdown entities get a
    reader-facing body; the YAML payload stays the only source of structured values.
    """
    spec = CONTRACTS[envelope]
    relative = _relative_path(rel_path)
    root = kb_dir.resolve()
    target = root / relative
    if not target.resolve().is_relative_to(root):
        raise ValueError("unsafe artifact path: resolved destination leaves the knowledge base")
    schema_path = Path(os.path.relpath(schema_dir / spec.schema_file, target.parent))
    meta = {
        "contract": spec.contract_id,
        "schema": schema_path.as_posix(),
        "envelope": envelope,
        "status": STATUS,
    }
    if rel_path.endswith(".md"):
        front = {"title": title, "softschema": meta, envelope: payload(model)}
        text = f"---\n{to_yaml(front)}---\n{body or ''}"
    else:
        text = to_yaml({"softschema": meta, envelope: payload(model)})
    if not target.resolve().is_relative_to(root):
        raise ValueError("unsafe artifact path: resolved destination leaves the knowledge base")
    atomic_write_text(target, text, make_parents=True)
    return rel_path
