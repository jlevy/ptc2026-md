# Offline Dataset Pipeline

Run from this directory with Python 3.11 or later and uv:

```bash
make install
make lint test
make build validate
```

`ptc-kb build` reads `curation/` and checked, sanitized snapshots in `raw/`, then
replaces the generated `../kb/` tree.
It compiles the shared Pydantic contracts, writes self-describing softschema artifacts,
checks references, and exports `_graph/{nodes,edges}.jsonl`, `_graph/stats.json`,
`_graph/coverage.json` and `_search/documents.jsonl`. Builds contain no network calls or
current-time fields.
`ptc-kb bios-import` explicitly captures the authored research bios and their provenance
in `synthesis/brief-bios.json`; run it after a writer updates the research and rechecks
the bio. Builds flag changed evidence as stale.
`ptc-kb validate` checks each artifact through its own schema, graph endpoints, source
snapshot pointers and input hashes, and scans committed data for contact details.

The build accepts one JSON research record per person in `curation/people/`. Required
fields are `slug` and `name`; optional sections include `listed_as`, `affiliations`,
`accounts`, `websites`, `github`, `profile`, `brief_bio` and `gaps`. Unknown input
fields are retained in source research but do not become asserted structured facts
automatically. Low-confidence accounts remain unresolved.
Every account must carry evidence of ownership.
The organizer’s public judge listing supplies the baseline judging role and affiliation,
independently of enrichment.

`raw/manifest.json` describes the sanitized bytes actually stored, so redaction does not
break provenance hashes.
Research facts are cited as curation with source URLs and excerpts.
Rebuild after changing inputs; generated bios hash their exact inputs.

The models and general artifact, privacy, graph and search helpers are adapted from
[jlevy/universe2026-md](https://github.com/jlevy/universe2026-md), commit `882ea44`,
under the MIT license.
Event-specific acquisition and mapping code lives here.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
