# Patch the Conference Knowledge Base

Public professional records for the Patch the Conference Hackathon on October 24, 2026
in San Francisco. The dataset records the organizer’s published judges, event schedule,
sponsors, affiliations, linked accounts, and cited professional work.
An organizer listing establishes a judging role; it does not establish attendance at any
other event.

Every person links to `event:patch-the-conference-2026` through an evidenced
`participations` record, a `participates_in` graph relationship, and the search
document’s `events` field.
Judges retain their published judging role; the host retains a self-reported host role.

- [Knowledge base](kb/README.md): generated records, graph exports and search documents
- [Pipeline](pipeline/README.md): installation, offline build and validation
- [Data policy](docs/data-policy.md): inclusion, privacy and removal rules
- [Contracts](docs/contracts.md): shared formats and proposed extensions
- [Build report](docs/build-report.md): coverage and unresolved evidence
- [Research notes](docs/research-notes.md): account resolution and evidence limits

Source code is MIT licensed.
Quoted public source material retains its original rights.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
