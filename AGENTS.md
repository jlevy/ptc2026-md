# Project Instructions

Read [the data policy](docs/data-policy.md) before changing sources or artifacts.
Public professional information only.
Never add contact details, credentials, other people’s profile data, inferred
attendance, or sensitive personal attributes.
Retain each fact’s source and distinguish conflicting attributed claims.

The self-contained Python project lives in `pipeline/`. Run its commands there through
`make` or with `UV_CONFIG_FILE=uv.toml` so user settings do not enter the lock.
Run `make install lint test build validate` before delivering changes.
`kb/` is generated; change curated inputs or source code and rebuild it.
Use the task’s approved external scratch volume for environments, caches and test
outputs. Set `TMPDIR`, `UV_CACHE_DIR`, `CARGO_TARGET_DIR` and `UV_PROJECT_ENVIRONMENT`
explicitly. Keep durable source and unique evidence here.

Person research is in `pipeline/curation/people/<slug>.json`; event and organizations
have separate curated input files.
Every raw snapshot requires a `raw/manifest.json` entry with URL, retrieval time, byte
count and SHA-256. Generated bios record the actual model, writing time and input hash.
No fetching occurs during build.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
