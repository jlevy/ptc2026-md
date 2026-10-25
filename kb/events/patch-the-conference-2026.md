---
title: Patch the Conference Hackathon
softschema:
  contract: paraverse.conference:Event/v1
  schema: ../_schemas/event.schema.yaml
  envelope: event
  status: permissive
event:
  id: event:patch-the-conference-2026
  name: Patch the Conference Hackathon
  series: Patch the Conference
  edition: '2026'
  organizer: org:wemakedevs
  start: '2026-10-24T09:00:00-07:00'
  end: '2026-10-24T19:00:00-07:00'
  timezone: America/Los_Angeles
  attendance_modes:
  - in_person
  venue: venue:bright-data-san-francisco
  url: https://www.wemakedevs.org/hackathons/ptc
  days:
  - id: day:2026-10-24
    date: '2026-10-24'
    label: Saturday
    location: San Francisco
    agenda:
    - start: 09:00
      title: Doors open
    - start: 09:00
      end: '10:00'
      title: Breakfast, setup and hacking
    - start: '10:00'
      end: '11:00'
      title: Sponsor workshops and talks
    - start: '11:00'
      end: '14:00'
      title: Building
    - start: '14:00'
      title: Lunch
    - start: '14:00'
      end: '17:30'
      title: Hacking and project submission
    - start: '17:30'
      end: '18:30'
      title: Presentations and judging
    - start: '18:30'
      title: Winners announced
    - start: '19:00'
      title: Event wraps up
  sources:
  - system: curation
    url: https://www.wemakedevs.org/hackathons/ptc
    snapshot: curation/event.json
  - system: curation
    url: https://www.wemakedevs.org/hackathons/ptc/judges
    snapshot: curation/event.json
  - system: curation
    url: https://www.wemakedevs.org/hackathons/ptc/schedule
    snapshot: curation/event.json
  - system: curation
    url: https://www.wemakedevs.org/hackathons/ptc/resources
    snapshot: curation/event.json
---
# Patch the Conference Hackathon

October 24, 2026, San Francisco.
