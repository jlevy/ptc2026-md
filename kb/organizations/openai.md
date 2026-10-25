---
title: OpenAI
softschema:
  contract: paraverse.conference:Organization/v1
  schema: ../_schemas/organization.schema.yaml
  envelope: organization
  status: permissive
organization:
  id: org:openai
  name: OpenAI
  roles:
  - sponsor
  website: https://openai.com
  sponsored_events:
  - event:patch-the-conference-2026
  sources:
  - system: curation
    url: https://www.wemakedevs.org/hackathons/ptc
    snapshot: curation/organizations.json
---
