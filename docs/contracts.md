# Shared Conference Contracts

Artifacts use `paraverse.conference:<Name>/v1`, typed entity IDs, the shared softschema
envelope and relative schema pointers.
Models and generated schema names follow the Universe dataset contracts at commit
`882ea44`.

Two proposed additive changes are included in the generated schema copies:

- `Participation.role` accepts `judge`. The organizer’s published judges use status
  `confirmed` and inclusion basis `published_by_event`.
- `Organization.sponsored_events` is an optional list of event IDs.
  The graph exporter writes a `sponsors` edge to each listed event.
  An event sponsor needs no invented sponsorship tier; the existing detailed
  `sponsorship` object remains optional.

The event model has no event-kind enum, so the hackathon requires no enum extension.
Shared organization IDs are reused when names are the same.
Person identities require shared public accounts; a name match alone never joins two
records.

Structured `profile.talks` points to modeled event sessions.
External talks without session records stay in curated research and may appear as linked
professional work; they do not create dangling session references.
The permissive `external_talks` field preserves their title, event, URL and evidence.
Unverified package mentions use `unverified_package_mentions` rather than a
registry-backed package entity.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
