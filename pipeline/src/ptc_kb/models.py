# Adapted from jlevy/universe2026-md at 882ea44; MIT licensed.
"""
softschema contracts for a conference knowledge base.

Each class in `CONTRACTS` is one payload contract, compiled to
`schemas/<file>.schema.yaml` by `universe-kb schemas`. The contracts are written for
conferences in general; GitHub Universe is the first one crawled into them.

Entities never nest each other. They point at one another with typed ID strings such as
`session:bld1134m` or `person:april-leonard`, so every artifact stays small, each file
has one owner, and the whole graph can be rebuilt from the files alone. Lists named
`sessions`, `people` or `mentioned_in` are backlinks that the build derives from the
forward references, so they can never disagree with them.

Top-level entities allow extra fields (`status: permissive`) because enrichment is still
growing; nested shapes are closed so a typo in a known structure fails validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

NAMESPACE = "paraverse.conference"
VERSION = "v1"


def _ref(*prefixes: str) -> str:
    """Pattern for a typed entity ID such as `session:bld1134m`."""
    return rf"^({'|'.join(prefixes)}):[a-z0-9][a-z0-9._/@+-]*$"


EventRef = Annotated[str, Field(pattern=_ref("event"))]
DayRef = Annotated[str, Field(pattern=_ref("day"))]
SessionRef = Annotated[str, Field(pattern=_ref("session"))]
PersonRef = Annotated[str, Field(pattern=_ref("person"))]
OrgRef = Annotated[str, Field(pattern=_ref("org"))]
RoomRef = Annotated[str, Field(pattern=_ref("room"))]
VenueRef = Annotated[str, Field(pattern=_ref("venue"))]
TermRef = Annotated[str, Field(pattern=_ref("term"))]
ExperienceRef = Annotated[str, Field(pattern=_ref("experience"))]
AccountRef = Annotated[str, Field(pattern=_ref("gh"))]
SocialRef = Annotated[str, Field(pattern=_ref("acct"))]
AnyAccountRef = Annotated[str, Field(pattern=_ref("gh", "acct"))]
WebsiteRef = Annotated[str, Field(pattern=_ref("site"))]
ProfileRef = Annotated[str, Field(pattern=_ref("profile"))]
PageRef = Annotated[str, Field(pattern=_ref("page"))]
RepoRef = Annotated[str, Field(pattern=_ref("repo"))]
PackageRef = Annotated[str, Field(pattern=_ref("pkg"))]
SoftwareRef = Annotated[str, Field(pattern=_ref("software"))]
MentionTarget = Annotated[str, Field(pattern=_ref("software", "org"))]
SubjectRef = Annotated[str, Field(pattern=_ref("session", "person", "org"))]
OwnerRef = Annotated[str, Field(pattern=_ref("person", "org"))]
ClaimTarget = Annotated[str, Field(pattern=_ref("term", "software", "org", "repo"))]

IsoDate = Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
IsoDateTime = Annotated[
    str, Field(pattern=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})$")
]
Url = Annotated[str, Field(pattern=r"^https?://")]

SourceSystem = Literal[
    "rainfocus",
    "githubuniverse.com",
    "github",
    "npm",
    "pypi",
    "bluesky",
    "mastodon",
    "website",
    "feed",
    "brightdata",
    "curation",
]
LinkKind = Literal[
    "website", "github", "linkedin", "x", "bluesky", "registration", "video", "image", "other"
]
SpeakerRole = Literal["speaker", "moderator", "panelist", "facilitator"]
OrgRole = Literal["organizer", "sponsor", "affiliation", "session_host", "mentioned"]
SponsorTier = Literal["platinum", "gold", "silver", "bronze", "signal"]
GitHubResolution = Literal[
    "resolved",
    "not_found",
    "enterprise_managed",
    "organization_account",
    "invalid",
    "absent",
    "unverified",
]
Platform = Literal[
    "x", "linkedin", "bluesky", "mastodon", "youtube", "instagram", "threads", "other"
]
# How an account or website was tied to its owner. More than one basis is corroboration.
LinkBasis = Literal[
    "event_listing",
    "github_profile",
    "website_rel_me",
    "website_link",
    "bluesky_profile",
    "mastodon_verified",
    "x_profile",
    "linkedin_profile",
    "attendance_post",
    "curated",
]
AffiliationBasis = Literal[
    "event_listing",
    "github_profile",
    "linkedin",
    "self_reported",
    "curated",
]
ParticipationRole = Literal[
    "speaker", "attendee", "organizer", "sponsor_representative", "host", "volunteer", "judge"
]
InclusionBasis = Literal["published_by_event", "public_self_report", "curated"]
ClaimBasis = Literal[
    "session_facets",
    "session_text",
    "bio",
    "github_profile",
    "github_repositories",
    "bluesky_profile",
    "mastodon_profile",
    "linkedin_profile",
    "x_profile",
    "website",
    "llm_synthesis",
    "curated",
]


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Entity(BaseModel):
    model_config = ConfigDict(extra="allow")


class Source(Closed):
    """Where a record came from: one raw snapshot file, or a curated list."""

    system: SourceSystem
    url: Url | None = None
    record_id: str | None = Field(default=None, description="The record's ID in that system.")
    retrieved_at: IsoDateTime | None = None
    snapshot: str | None = Field(
        default=None, description="Raw snapshot path, relative to the conference directory."
    )


class Link(Closed):
    kind: LinkKind
    url: Url
    label: str | None = None


class Mention(Closed):
    """A name found in text and resolved to a software or organization entity."""

    target: MentionTarget
    text: str = Field(description="The surface form exactly as it appears.")
    field: Literal["title", "abstract", "bio", "description"]
    method: Literal["gazetteer", "pattern"]


class Evidence(Closed):
    """Where a claim is stated, with the words that state it when they are short."""

    url: Url | None = None
    quote: str | None = None
    observed_at: str | None = Field(default=None, description="When the source said it.")
    ref: str | None = Field(default=None, description="A knowledge base entity that shows it.")


class Affiliation(Closed):
    """A person's tie to an organization, as one source states it."""

    organization: OrgRef
    title: str | None = None
    current: bool = Field(description="True when the source describes the present.")
    basis: AffiliationBasis
    label: str | None = Field(
        default=None, description="The organization text as the source wrote it."
    )
    evidence: list[Evidence] = Field(default_factory=list)


class Participation(Closed):
    """A person's part in an event, and how sure we are of it."""

    event: EventRef
    role: ParticipationRole
    status: Literal["confirmed", "self_reported", "candidate"] = Field(
        description="confirmed: published by the organizer; self_reported: the person said "
        "so publicly; candidate: inferred and unverified."
    )
    evidence: list[Evidence] = Field(default_factory=list)


# --- Event ---------------------------------------------------------------------------


class AgendaItem(Closed):
    start: str | None = Field(default=None, description="Local start time, HH:MM.")
    end: str | None = None
    title: str
    description: str | None = None


class EventDay(Closed):
    id: DayRef
    date: IsoDate
    label: str
    access: str | None = Field(default=None, description="Who may attend, when restricted.")
    location: str | None = None
    agenda: list[AgendaItem] = Field(default_factory=list)


class Offer(Closed):
    """A way to attend: a ticket tier or an application."""

    id: str
    name: str
    price: float | None = None
    currency: str | None = None
    availability: Literal["available", "sold_out", "application_required", "closed"]
    summary: str | None = None
    includes: list[str] = Field(default_factory=list)


class TourStop(Closed):
    """One city on the Universe on the road tour."""

    id: str
    city: str
    country: str
    region: Literal["americas", "asia-pacific", "emea"] | None = Field(
        default=None, description="Derived from the country; the page filters by region."
    )
    date: IsoDate
    venue_name: str
    registration: Literal["open", "closed"]
    url: Url | None = Field(default=None, description="The stop's registration page.")


class Media(Closed):
    kind: Literal["video", "image"]
    title: str
    url: Url | None = Field(default=None, description="Absent when only a player embeds it.")
    thumbnail_url: Url | None = None


class Event(Entity):
    """One edition of a conference, with its days, ways to attend and tour stops."""

    id: EventRef
    name: str
    series: str
    edition: str
    organizer: OrgRef
    start: IsoDateTime
    end: IsoDateTime
    timezone: str = Field(description="IANA time zone name.")
    attendance_modes: list[Literal["in_person", "virtual"]]
    venue: VenueRef | None = None
    url: Url
    description: str | None = None
    days: list[EventDay]
    offers: list[Offer] = Field(default_factory=list)
    tour_stops: list[TourStop] = Field(default_factory=list)
    featured_speakers: list[PersonRef] = Field(default_factory=list)
    highlights: list[Media] = Field(default_factory=list)
    testimonials: list[str] = Field(default_factory=list)
    sources: list[Source]


class FaqEntry(Closed):
    question: str
    answer: str


class Faq(Entity):
    event: EventRef
    entries: list[FaqEntry]
    sources: list[Source]


# --- Program ---------------------------------------------------------------------------


class TimeSlot(Closed):
    start: IsoDateTime
    end: IsoDateTime
    day: DayRef
    room: RoomRef | None = None
    capacity: int | None = Field(default=None, ge=0)
    in_person: bool
    virtual: bool
    source_id: str = Field(description="RainFocus session time ID.")


class SessionSpeaker(Closed):
    person: PersonRef
    role: SpeakerRole
    order: int = Field(ge=0)


class SessionFacets(Closed):
    """Catalog classifications, each a reference to a term in a taxonomy facet."""

    session_type: TermRef
    tracks: list[TermRef] = Field(default_factory=list)
    level: TermRef | None = None
    topics: list[TermRef] = Field(default_factory=list)
    products: list[TermRef] = Field(default_factory=list)
    audiences: list[TermRef] = Field(default_factory=list)
    industries: list[TermRef] = Field(default_factory=list)
    delivery_formats: list[TermRef] = Field(default_factory=list)
    curated_agendas: list[TermRef] = Field(default_factory=list)


class Session(Entity):
    """One catalog entry: a talk, demo, workshop, keynote, social or special event."""

    id: SessionRef
    event: EventRef
    code: str
    title: str
    abstract: str
    url: Url
    slots: list[TimeSlot] = Field(min_length=1)
    speakers: list[SessionSpeaker] = Field(default_factory=list)
    facets: SessionFacets
    sponsored: bool
    popular: bool = Field(description="The catalog warns that seating is not guaranteed.")
    hosts: list[OrgRef] = Field(
        default_factory=list, description="Organizations that host or sponsor the session."
    )
    registration_url: Url | None = Field(
        default=None, description="External sign-up page, for socials run by partners."
    )
    related: list[SessionRef] = Field(default_factory=list)
    mentions: list[Mention] = Field(default_factory=list)
    image_url: Url | None = None
    sources: list[Source]


class PersonSession(Closed):
    session: SessionRef
    role: SpeakerRole


class Person(Entity):
    """
    Anyone involved in the event: speakers, attendees, organizers, sponsor staff.

    `inclusion_basis` records why the person is in the knowledge base at all, and
    `participations` records each role with its own evidence, so an attendee who only
    posted "see you at Universe" is never presented like a published speaker.
    Accounts and websites are separate entities; `accounts` and `websites` point at them.
    """

    id: PersonRef
    name: str
    given_name: str | None = None
    family_name: str | None = None
    job_title: str | None = Field(default=None, description="As the primary source lists it.")
    listed_for: EventRef | None = Field(
        default=None,
        description="The event whose listing gave job_title and affiliation_label; an "
        "earlier edition's title may no longer be current.",
    )
    affiliations: list[Affiliation] = Field(
        default_factory=list,
        description="Organization ties from every source; current ones first, primary first.",
    )
    affiliation_label: str | None = Field(
        default=None, description="The company string exactly as the event lists it."
    )
    bio: str | None = None
    photo_url: Url | None = None
    inclusion_basis: InclusionBasis
    participations: list[Participation] = Field(min_length=1)
    accounts: list[AnyAccountRef] = Field(default_factory=list)
    websites: list[WebsiteRef] = Field(default_factory=list)
    links: list[Link] = Field(
        default_factory=list, description="Other links that are not modeled as accounts."
    )
    github: AccountRef | None = Field(default=None, description="The primary GitHub account.")
    github_resolution: GitHubResolution
    github_match: Literal["name", "unconfirmed"] | None = Field(
        default=None,
        description="Whether the account's profile name agrees with the person's name.",
    )
    profile: ProfileRef | None = None
    featured: bool = False
    sessions: list[PersonSession] = Field(default_factory=list)
    mentions: list[Mention] = Field(default_factory=list)
    sources: list[Source]


class Sponsorship(Closed):
    tier: SponsorTier
    summary: str | None = None
    link: Url | None = None
    logo_url: Url | None = None
    industries: list[str] = Field(default_factory=list)
    booth: str | None = None
    exhibitor_id: str


class OrgDescription(Closed):
    text: str
    basis: Literal["linkedin", "sponsor_listing", "github", "website"]


class OrgUpdate(Closed):
    """A recent post on the organization's LinkedIn page."""

    text: str
    date: IsoDateTime | None = None
    url: Url | None = None
    likes: int | None = Field(default=None, ge=0)


class AffiliatedPage(Closed):
    """A page LinkedIn lists as affiliated: a subsidiary, brand or showcase page."""

    name: str
    industry: str | None = None
    url: Url | None = None
    organization: OrgRef | None = Field(
        default=None, description="The kb organization, when the page is one we hold."
    )


class Organization(Entity):
    """A company, foundation, university or community group connected to the event."""

    id: OrgRef
    name: str
    aliases: list[str] = Field(default_factory=list)
    roles: list[OrgRole] = Field(min_length=1)
    description: str | None = Field(
        default=None, description="The best available description; all are in descriptions."
    )
    descriptions: list[OrgDescription] = Field(default_factory=list)
    tagline: str | None = None
    industry: str | None = None
    size: str | None = Field(default=None, description="Employee range, as LinkedIn states it.")
    headquarters: str | None = None
    founded: str | None = None
    specialties: list[str] = Field(default_factory=list)
    logo_url: Url | None = None
    website: Url | None = None
    github: AccountRef | None = None
    accounts: list[AnyAccountRef] = Field(default_factory=list)
    related_organizations: list[OrgRef] = Field(
        default_factory=list,
        description="Parent, subsidiary or partner, from curation or LinkedIn affiliations.",
    )
    affiliated: list[AffiliatedPage] = Field(default_factory=list)
    locations: list[str] = Field(
        default_factory=list, description="Office locations, at city level."
    )
    updates: list[OrgUpdate] = Field(
        default_factory=list, description="Recent LinkedIn posts, newest first."
    )
    sponsored_events: list[EventRef] = Field(default_factory=list)
    sponsorship: Sponsorship | None = None
    people: list[PersonRef] = Field(
        default_factory=list, description="People with a current affiliation to it."
    )
    hosted_sessions: list[SessionRef] = Field(default_factory=list)
    mentioned_in: list[SubjectRef] = Field(default_factory=list)
    sources: list[Source]


# --- Place ---------------------------------------------------------------------------


class Venue(Entity):
    """A campus, a building on it, or an outside venue used for an evening event."""

    id: VenueRef
    name: str
    kind: Literal["campus", "building", "outdoor", "external"]
    parent: VenueRef | None = None
    address: str | None = None
    sources: list[Source]


class Room(Entity):
    """A schedulable space as the catalog names it."""

    id: RoomRef
    name: str
    label: str = Field(description="The catalog's full room string.")
    venue: VenueRef | None = None
    location_note: str | None = Field(default=None, description="Floor or area detail.")
    capacity: int | None = Field(default=None, ge=0)
    source_ids: list[str]
    sessions: list[SessionRef] = Field(default_factory=list)
    sources: list[Source]


class Experience(Entity):
    """An on-site activation that is not a scheduled session."""

    id: ExperienceRef
    name: str
    description: str
    category: Literal["learn", "connect", "experiment"] | None = None
    schedule: str | None = None
    location: str | None = None
    venue: VenueRef | None = None
    action: str | None = Field(default=None, description="The call to action, as shown.")
    action_url: Url | None = None
    image_url: Url | None = None
    sources: list[Source]


# --- Taxonomy ---------------------------------------------------------------------------


class Term(Closed):
    id: TermRef
    label: str
    description: str | None = Field(default=None, description="The catalog's glossary text.")
    duration_minutes: int | None = Field(default=None, ge=0)
    source_id: str | None = None
    session_count: int = Field(ge=0)


class Facet(Entity):
    """One classification axis of the session catalog and its terms."""

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    event: EventRef | None = Field(
        default=None, description="The edition whose catalog defines these terms."
    )
    label: str
    multi_valued: bool
    terms: list[Term]
    sources: list[Source]


# --- Software and GitHub ---------------------------------------------------------------


class Contributions(Closed):
    """Public contribution counts for the last year, as GitHub reports them."""

    total: int = Field(ge=0)
    commits: int = Field(ge=0)
    pull_requests: int = Field(ge=0)
    issues: int = Field(ge=0)
    reviews: int = Field(ge=0)


class GitHubAccount(Entity):
    """A GitHub user or organization account linked to a person or organization."""

    id: AccountRef
    login: str
    kind: Literal["user", "organization"]
    url: Url
    name: str | None = None
    company: str | None = None
    bio: str | None = None
    location: str | None = None
    website: str | None = None
    followers: int | None = Field(default=None, ge=0)
    public_repositories: int | None = Field(
        default=None, ge=0, description="Public repositories the account owns, forks excluded."
    )
    created_at: IsoDateTime | None = None
    profile_readme: str | None = Field(
        default=None, description="The profile README in full, as Markdown."
    )
    contributions_last_year: Contributions | None = None
    starred_repositories: int | None = Field(default=None, ge=0)
    has_sponsors_listing: bool | None = None
    contribution_years: list[int] = Field(default_factory=list)
    github_star: bool | None = Field(default=None, description="In the GitHub Stars program.")
    campus_expert: bool | None = None
    github_employee: bool | None = None
    gists: int | None = Field(default=None, ge=0)
    contributed_to: list[RepoRef] = Field(
        default_factory=list, description="Others' repositories with their commits or PRs."
    )
    organization_logins: list[str] = Field(
        default_factory=list, description="Public organization memberships, by login."
    )
    pinned: list[RepoRef] = Field(default_factory=list)
    top_repositories: list[RepoRef] = Field(default_factory=list)
    linked_accounts: list[SocialRef] = Field(
        default_factory=list, description="Accounts the profile itself lists."
    )
    websites: list[WebsiteRef] = Field(default_factory=list)
    entity: SubjectRef | None = Field(default=None, description="The person or org it belongs to.")
    link_basis: list[LinkBasis] = Field(default_factory=list)
    identity_link_basis: list[str] = Field(
        default_factory=list,
        description="The original curated reasons for the identity association.",
    )
    identity_confidence: Literal["high", "medium", "low"] | None = None
    identity_evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source]


class SocialAccount(Entity):
    """
    An account on a social or professional platform (X, LinkedIn, Bluesky, Mastodon,
    YouTube, …). Profile details are filled only where a free public API exposes them;
    `details_fetched` says whether they were.
    """

    id: SocialRef
    platform: Platform
    handle: str = Field(description="As the platform displays it, e.g. `in/jdoe` on LinkedIn.")
    url: Url
    display_name: str | None = None
    headline: str | None = None
    bio: str | None = None
    location: str | None = None
    website: str | None = Field(default=None, description="The link the profile lists.")
    followers: int | None = Field(default=None, ge=0)
    following: int | None = Field(default=None, ge=0)
    connections: int | None = Field(default=None, ge=0)
    posts_count: int | None = Field(default=None, ge=0)
    verified: bool | None = None
    avatar_url: Url | None = None
    banner_url: Url | None = None
    created_at: IsoDateTime | None = None
    owner: OwnerRef | None = None
    link_basis: list[LinkBasis] = Field(min_length=1)
    details_fetched: bool = False
    sources: list[Source]


class Website(Entity):
    """A website someone runs: a personal site, blog or project page."""

    id: WebsiteRef
    url: Url
    kind: Literal["personal", "blog", "company", "project", "other"]
    title: str | None = None
    description: str | None = None
    owner: OwnerRef | None = None
    link_basis: list[LinkBasis] = Field(min_length=1)
    fetch_status: Literal["ok", "error", "not_fetched"]
    http_status: int | None = None
    identity_links: list[Url] = Field(
        default_factory=list, description="Links the page marks rel=me."
    )
    feeds: list[Url] = Field(default_factory=list)
    linked_accounts: list[AnyAccountRef] = Field(default_factory=list)
    sources: list[Source]


# --- Profiles ---------------------------------------------------------------------------


class Claim(Closed):
    """One thing a profile asserts about a person, with the evidence for it."""

    label: str
    target: ClaimTarget | None = Field(
        default=None, description="The term, software, organization or repository it names."
    )
    basis: ClaimBasis
    confidence: Literal["high", "medium", "low"]
    weight: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="For inferred interests: strength relative to the person's strongest one.",
    )
    sources: list[ClaimBasis] = Field(
        default_factory=list, description="Every basis that supports an inferred interest."
    )
    evidence: list[Evidence] = Field(min_length=1)


class Position(Closed):
    """A role at an organization, current or past, from a profile's experience section."""

    organization: str
    organization_ref: OrgRef | None = None
    title: str | None = None
    start: str | None = None
    end: str | None = None
    current: bool
    description: str | None = None
    evidence: Evidence


class EducationEntry(Closed):
    school: str
    school_ref: OrgRef | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_year: str | None = None
    end_year: str | None = None
    evidence: Evidence


class Publication(Closed):
    """A paper, article or book the person lists."""

    title: str
    venue: str | None = None
    date: str | None = Field(default=None, description='As listed ("May 24, 2025").')
    description: str | None = None
    url: Url | None = None
    evidence: Evidence


class Patent(Closed):
    title: str
    number: str | None = Field(default=None, description='As listed ("US 9286046").')
    date: str | None = Field(default=None, description="Date issued, as listed.")
    description: str | None = None
    url: Url | None = Field(default=None, description="Google Patents, derived from the number.")
    evidence: Evidence


class Credential(Closed):
    """An honor, award or certification as the person lists it."""

    kind: Literal["honor", "certification"]
    title: str
    issuer: str | None = None
    date: str | None = Field(default=None, description='When issued, as listed ("Nov 2023").')
    expires: str | None = None
    credential_id: str | None = None
    url: Url | None = Field(default=None, description="Where the credential can be verified.")
    description: str | None = None
    evidence: Evidence


class Activity(Closed):
    """Volunteering, projects, courses and organizations listed on a profile."""

    kind: Literal["volunteering", "project", "course", "organization"]
    title: str
    detail: str | None = None
    evidence: Evidence


class WritingItem(Closed):
    """A post, article or video the person published, newest first."""

    title: str
    url: Url
    published: str | None = None
    channel: Literal["blog", "linkedin", "x", "mastodon", "bluesky", "youtube"]
    summary: str | None = None


class OpenSourceWork(Closed):
    repository: RepoRef
    relation: Literal["owner", "pinned", "contributor"]
    stars: int | None = Field(default=None, ge=0)
    primary_language: str | None = None


class BriefBio(Closed):
    """
    One or two neutral sentences written by a model from the person's evidence
    bundle. `cites` names the bundle facts the text relies on; `stale` is true when that
    evidence has changed since the bio was written.
    """

    text: str
    cites: list[str] = Field(min_length=1)
    basis: Literal["llm_synthesis"] = "llm_synthesis"
    written_by: str
    written_at: IsoDateTime
    input_sha256: str
    stale: bool


class Profile(Entity):
    """
    The developed profile of one person: what they work on and know, built from the
    event listing, their sessions, GitHub, Bluesky, their website and imported research.
    Every claim cites evidence. `gaps` lists what is still unknown, which is the to-do
    list for the next round of profile development.
    """

    id: ProfileRef
    person: PersonRef
    brief_bio: BriefBio | None = None
    headline: str | None = None
    location: str | None = None
    current_roles: list[str] = Field(
        default_factory=list, description="Readable 'title at organization' lines."
    )
    expertise: list[Claim] = Field(default_factory=list)
    technologies: list[Claim] = Field(default_factory=list)
    programming_languages: list[Claim] = Field(default_factory=list)
    recognitions: list[Claim] = Field(default_factory=list)
    interests: list[Claim] = Field(default_factory=list)
    open_source: list[OpenSourceWork] = Field(default_factory=list)
    packages: list[PackageRef] = Field(
        default_factory=list, description="Packages published from the person's repositories."
    )
    experience: list[Position] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    credentials: list[Credential] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    patents: list[Patent] = Field(default_factory=list)
    spoken_languages: list[str] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)
    recent_writing: list[WritingItem] = Field(default_factory=list)
    talks: list[SessionRef] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    sources: list[Source]


class Repository(Entity):
    id: RepoRef
    full_name: str
    url: Url
    description: str | None = None
    homepage: str | None = None
    stars: int | None = Field(default=None, ge=0)
    forks: int | None = Field(default=None, ge=0)
    watchers: int | None = Field(default=None, ge=0)
    open_issues: int | None = Field(
        default=None, ge=0, description="Open issues, not counting pull requests."
    )
    stats_observed_at: IsoDateTime | None = Field(
        default=None,
        description="When stars and forks were read from GitHub. Unset when they came with "
        "the owner's record, whose time is not known.",
    )
    primary_language: str | None = None
    topics: list[str] = Field(default_factory=list)
    license: str | None = None
    archived: bool | None = None
    fork: bool | None = None
    created_at: IsoDateTime | None = None
    pushed_at: IsoDateTime | None = None
    owner_login: str
    owner: AccountRef | None = Field(
        default=None, description="Set when the owner has an account artifact of its own."
    )
    pinned_by: list[AccountRef] = Field(default_factory=list)
    software: SoftwareRef | None = None
    sources: list[Source]


class Package(Entity):
    """A published package, linked to its source repository when the registry agrees."""

    id: PackageRef
    ecosystem: Literal["npm", "pypi", "crates", "go"]
    name: str
    url: Url
    description: str | None = None
    latest_version: str | None = None
    license: str | None = None
    repository_url: str | None = Field(default=None, description="As the registry declares it.")
    repository: RepoRef | None = Field(
        default=None, description="The source repository, verified against the registry."
    )
    publishers: list[OwnerRef] = Field(
        default_factory=list, description="People or organizations owning that repository."
    )
    software: SoftwareRef | None = None
    sources: list[Source]


class Software(Entity):
    """A product, project, language or protocol that the program talks about."""

    id: SoftwareRef
    name: str
    aliases: list[str] = Field(default_factory=list)
    kind: Literal["github_product", "open_source", "commercial", "language", "platform", "protocol"]
    vendor: OrgRef | None = None
    homepage: Url | None = None
    product_term: TermRef | None = Field(
        default=None, description="The catalog's GitHub product term, when there is one."
    )
    repositories: list[RepoRef] = Field(default_factory=list)
    packages: list[PackageRef] = Field(default_factory=list)
    mentioned_in: list[SubjectRef] = Field(default_factory=list)
    sources: list[Source]


# --- Site content -----------------------------------------------------------------------


class Image(Closed):
    url: Url
    alt: str | None = None


class PageSection(Closed):
    """One block of a page in reading order: a heading and its text, links and images."""

    heading: str | None = None
    text: str | None = Field(default=None, description="The section's text as Markdown.")
    links: list[Link] = Field(default_factory=list)
    images: list[Image] = Field(default_factory=list)
    calls_to_action: list[Link] = Field(
        default_factory=list, description="Buttons, with their label and target."
    )


class Page(Entity):
    """
    The free text of one official web page, in reading order, so a new site can reuse the
    organizer's own copy (hero text, section intros, templates) without scraping again.
    """

    id: PageRef
    site: Literal["githubuniverse.com", "attendee-portal"]
    url: Url
    title: str
    description: str | None = None
    sections: list[PageSection] = Field(
        default_factory=list, description="Empty for pages that are only a catalog widget."
    )
    sources: list[Source]


class MediaItem(Closed):
    url: Url
    kind: Literal["photo", "logo", "tile", "banner", "thumbnail", "illustration", "avatar", "other"]
    alt: str | None = None
    used_by: list[str] = Field(description="IDs of the entities that show this image.")


class MediaIndex(Entity):
    """Every image URL in the knowledge base, what it depicts and who uses it."""

    event: EventRef
    items: list[MediaItem]
    sources: list[Source]


@dataclass(frozen=True)
class ContractSpec:
    model: type[BaseModel]
    envelope: str
    schema_file: str

    @property
    def contract_id(self) -> str:
        return f"{NAMESPACE}:{self.model.__name__}/{VERSION}"


CONTRACTS: dict[str, ContractSpec] = {
    spec.envelope: spec
    for spec in [
        ContractSpec(Event, "event", "event.schema.yaml"),
        ContractSpec(Faq, "faq", "faq.schema.yaml"),
        ContractSpec(Session, "session", "session.schema.yaml"),
        ContractSpec(Person, "person", "person.schema.yaml"),
        ContractSpec(Organization, "organization", "organization.schema.yaml"),
        ContractSpec(Venue, "venue", "venue.schema.yaml"),
        ContractSpec(Room, "room", "room.schema.yaml"),
        ContractSpec(Experience, "experience", "experience.schema.yaml"),
        ContractSpec(Facet, "facet", "facet.schema.yaml"),
        ContractSpec(GitHubAccount, "github_account", "github-account.schema.yaml"),
        ContractSpec(SocialAccount, "social_account", "social-account.schema.yaml"),
        ContractSpec(Website, "website", "website.schema.yaml"),
        ContractSpec(Profile, "profile", "profile.schema.yaml"),
        ContractSpec(Repository, "repository", "repository.schema.yaml"),
        ContractSpec(Package, "package", "package.schema.yaml"),
        ContractSpec(Software, "software", "software.schema.yaml"),
        ContractSpec(Page, "page", "page.schema.yaml"),
        ContractSpec(MediaIndex, "media", "media.schema.yaml"),
    ]
}
