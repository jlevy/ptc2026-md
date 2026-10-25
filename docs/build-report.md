# Build Report

The offline build contains 10 people: nine organizer-published judges and one host who
publicly reported the role.
It exports 133 graph nodes, 266 edges, and 122 search documents.
Every one of the 132 entity artifacts validates against its embedded schema.

## Coverage

| Kind | Count |
| --- | ---: |
| day | 1 |
| event | 1 |
| github_account | 7 |
| organization | 22 |
| person | 10 |
| profile | 10 |
| repository | 56 |
| social_account | 20 |
| venue | 1 |
| website | 5 |

The source snapshot holds nine sanitized LinkedIn profiles, four sanitized X profiles,
selected official event facts and the host’s public announcement, two GitHub profile and
repository snapshots, and three directly fetched repository records.
All ten raw files have checked byte counts and SHA-256 hashes in
`pipeline/raw/manifest.json`.

## Resolved Accounts

| Person | Accounts |
| --- | --- |
| Riken Shah | `acct:linkedin/in/shah-riken`, `acct:x/_rikenshah`, `acct:other/dev.to/rikenshah`, `gh:riken-shah` |
| Nitish Mane | `acct:linkedin/in/nitish-mane`, `gh:nitishmane` |
| Manpreet Singh | `acct:linkedin/in/manpoffc`, `gh:manpoffc` |
| Schezeen Fazulbhoy | `acct:linkedin/in/schezeenfazulbhoy`, `acct:x/schezfaz10`, `acct:other/medium.com/schezfaz`, `acct:youtube/schezfaz`, `acct:other/scholar.google.com/yxcz8dqaaaaj`, `acct:other/dev.to/schezfaz`, `gh:schezfaz` |
| Pooja Ravi | `acct:linkedin/in/pravi20` |
| Satyam Singh | `acct:linkedin/in/satyamsingh2003`, `acct:x/klauscodes`, `acct:youtube/satyamcodesss`, `gh:klausmikhaelson` |
| Yash Bhatia | `acct:linkedin/in/yyash-bhatia` |
| Dipen Chawla | Unresolved |
| Vivek Gopal Ramaswamy | `acct:linkedin/in/vivekgr`, `gh:vivekgr92` |
| Kunal Kushwaha | `acct:linkedin/in/kunal-kushwaha`, `acct:x/kunalstwt`, `acct:youtube/kunalkushwaha`, `gh:kunal-kushwaha` |

Seven GitHub accounts are resolved.
Manpreet’s account match is medium confidence, with its supporting ownership evidence
retained. Pooja, Yash and Dipen remain unresolved on GitHub.
An unresolved account does not affect the published judging role.

## Contracts and Shared IDs

The [contract notes](contracts.md) record two proposed additive extensions:
`Participation.role = judge` and `Organization.sponsored_events`. Other-platform account
IDs include their domain so identical handles on different services remain separate.
No person ID was reused or adjusted based on a name-only match.
Shared organization IDs include `org:adobe`, `org:meta`, `org:microsoft`, `org:openai`
and `org:oracle`, following the established normalized organization slugs.

## Validation

- `make install lint test validate` passes; the regression suite has 10 tests.
- Two consecutive builds produce identical bytes for every generated KB file.
- Validation checks every schema, graph endpoint, typed reference, source snapshot
  pointer, raw input hash, and bio freshness.
- Regression tests cover separate same-handle accounts, host/judge evidence, stale bios
  preserving the previous KB, conflicting employer claims, contributor links, repository
  metadata merging, and sensitive profile-data exclusions.
- CI installs the locked dependencies, runs the same offline checks, rebuilds, and
  requires the checked-in KB and machine-readable report to remain unchanged.

## Evidence Limits and Exclusions

Riken’s xAI/Msquare Labs observations and Pooja’s Netflix/Oracle observations retain
their separate source attribution.
Public profile snippets do not establish complete employment histories.
External talks remain cited professional work and do not imply attendance at this
hackathon or another conference.
Package registry ownership and complete contribution histories have not been verified.

Contact details, education years, credential identifiers, other people’s profile data,
bulk social-post bodies, scraper bookkeeping, sensitive structured honors, and
unresolved candidate identities are excluded.
Self-written public profile text stays verbatim apart from contact redaction.
Each generated bio records its actual writer model, capture time, cited facts and
normalized research input hash.

See [research notes](research-notes.md) for the research findings and
[build-report.json](build-report.json) for per-person enrichment counts and gaps.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
