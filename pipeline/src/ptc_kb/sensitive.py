# Adapted from jlevy/universe2026-md at 882ea44; MIT licensed.
"""
Sensitive personal attributes stay out of the knowledge base.

People mention their family, health, faith, sexuality, origin or age in profile bios,
READMEs, speaker bios and posts. The data policy keeps every one of these out, stated
or inferred, so free text about a person passes through `redact`, which drops each
clause that states one; names such as starred repositories pass through `is_sensitive`;
and locations pass through `city_level`, which drops detail finer than a city.

The patterns favor removal: a clause that only looks sensitive is dropped too, which
costs a little professional text and never leaks a personal fact. Topics people work on
(accessibility, health care, security) are not attributes of the person and are left
alone, and so are a few phrases that only look personal ("dad jokes", "dog mom", the
"Catholic University of Louvain").
"""

from __future__ import annotations

import re

# Each category's markers, matched case-insensitively as whole words.
CATEGORIES: dict[str, str] = {
    "family": (
        r"husband|hubby|wife|wifey|spouse|married|newlywed|fianc[ée]e?|boyfriend|girlfriend"
        r"|(?:\d+x\s*)?(?:dad|daddy|father|mom|mommy|mum|mother|mama|papa)s?"
        r"|girl ?dad|boy ?dad|grand(?:ma|pa|mother|father|kids?|children)"
        r"|(?:my|our|two|three|four|five|six|nine|\d) (?:kids?|children|sons?|daughters?"
        r"|boys|girls|toddlers?|babies|baby|twins|little ones)"
        r"|toddlers?|\d+-year-old (?:sons?|daughters?|kids?|child|children|boys?|girls?|baby"
        r"|twins)|family (?:life|man|guy|first)|love of my life"
        r"|polyamor\w*"
    ),
    "health": (
        r"cancer|chemo\w*|tumou?r|diabet\w*|adhd|autis\w*|asperger\w*|neurodiver\w*"
        r"|dyslexi\w*|disabled|chronic(?:ally)? ill\w*|chronic illness|mental illness"
        r"|depression|anxiety disorder|bipolar|ptsd|sober|sobriety|in recovery"
        r"|alcoholi\w*|pregnan\w*|miscarr\w*|survivor|transplant|pcd"
        r"|disability (?:leadership|network|council|community|alliance|employee)"
        r"|i'?m blind|legally blind|blind (?:life|scientist|person|people|engineers?"
        r"|developers?|users?|man|woman)|visually impaired|low vision|hard of hearing|deaf"
    ),
    "religion": (
        r"catholic|protestant|evangelical|mormon|latter[- ]day saints?|lds"
        r"|muslim|islam\w*|jewish|judaism|hindu\w*|buddhis\w*|sikh|atheist|agnostic"
        r"|church|jesus|christ|god|bible|faith|pray\w*|blessed|ordained|pastor|clergy"
        r"|seminary|missionary|gospel"
    ),
    "sexuality": (
        r"gays?|lesbians?|bisexual|queers?|lgbt\w*\+?|pansexual|asexual|transgender|trans"
        r"|non[- ]?binary|enby|tech pride|pride (?:month|summit|parade|network|alliance)"
    ),
    "origin": (
        r"latin[aox]s?|latine|hispanic|chican[ao]|afro-?\w+|african[- ]american"
        r"|black (?:woman|women|girl|man|men|engineers?|developers?|founders?|in tech)"
        r"|black girls|#black\w+|asian[- ]american|\w+-american|indigenous|native american"
        r"|people of colou?r|women of colou?r|person of colou?r|bipoc"
        r"|first nations|immigra\w+|refugees?|first[- ]gen\w*|born in|born and raised"
        r"|raised in|grew up in|citizenship|green card|h-?1b"
    ),
    "politics": (
        r"democrats?|democratic party|republicans?|maga|libertarian|socialist|communist"
        r"|feminis[tm]s?|#resist\w*|blm|black lives matter|pro-?life|pro-?choice|antifa"
        r"|trump|biden|potus|nukes?|elections?|abortion|gaza|palestin\w*|zionis\w*|fascis\w*"
        r"|nazis?"
    ),
    "age": r"\d{1,3} ?(?:years|yrs) old|born (?:in|on) (?:\w+ )?\d{4}|birthday",
    "finances": r"net worth|salary|debt-free|bankrupt\w*|mortgage",
}
PATTERNS = {
    name: re.compile(rf"(?<![\w@/-])(?:{body})(?!\w)", re.IGNORECASE)
    for name, body in CATEGORIES.items()
}
# Phrases that contain a marker without stating anything about the person.
NEUTRAL = re.compile(
    r"\b(?:dog|cat|corgi|poodle|puppy|pup|plant|fur|bulldog|chicken|goat)[- ]?"
    r"(?:mom|mum|dad|mama|papa|parent)s?\b|\b(?:mom|dad)[- ](?:jokes?|shoes|bod)\b"
    r"|\bfather (?:of|to) (?:one )?four-legged child\b|\bcatholic university\b"
    r"|\buniversidad cat[oó]lica\b|\brefugee (?:council|agency)\b",
    re.IGNORECASE,
)
# Symbols that state faith, identity or disability on their own; only the symbol is
# removed.
SYMBOLS = re.compile(
    "[\u271d\u2626\u262a\u2721\U0001f549\u2638\U0001f6d0\u267f"
    "\U0001f9bd\U0001f9bc\U0001f9af\U0001f9bb]\ufe0f?"
    "|\U0001f3f3\ufe0f?\u200d(?:\U0001f308|\u26a7\ufe0f?)"
)
# Clause boundaries: line breaks, bars, bullets, semicolons, spaced dashes and sentence
# ends. Slashes are not boundaries, so URLs stay whole.
BOUNDARY = re.compile(r"(\n+|\s*[|•·;]+\s*|\s+[-–—]\s+|(?<=[.!?])\s+)")
SHORT_ITEM_WORDS = 5
LIST_ITEMS = 3


def _markers(text: str) -> set[str]:
    neutral = NEUTRAL.sub(" ", text)
    return {name for name, pattern in PATTERNS.items() if pattern.search(neutral)}


def categories(text: str | None) -> set[str]:
    """The sensitive categories `text` touches, with "symbol" for an identity symbol."""
    found = _markers(text or "")
    return found | ({"symbol"} if SYMBOLS.search(text or "") else set())


def is_sensitive(text: str | None) -> bool:
    """
    True when `text` states a sensitive attribute. Hyphens, underscores, slashes and dots
    also count as spaces, so a repository name or URL ("octo/i-have-adhd") is read as
    words.
    """
    return bool(categories(text) or categories(re.sub(r"[-_/.]", " ", text or "")))


def _clean_clause(clause: str) -> str:
    """
    Drop the sensitive part of one clause. A list of three or more short comma-separated
    items ("Husband, Dad, Developer") loses only the matching items; any other clause is
    dropped whole, since its remaining words could still imply what was removed.
    """
    if not _markers(clause):
        return clause
    items = clause.split(",")
    if len(items) >= LIST_ITEMS and all(
        len(item.split()) <= SHORT_ITEM_WORDS and item.count("(") == item.count(")")
        for item in items
    ):
        kept = [item for item in items if not _markers(item)]
        return ",".join(kept).strip(" ,") if kept else ""
    return ""


def strip_symbols(name: str | None) -> str | None:
    """
    A display name without identity symbols. Names are not redacted further: a word such
    as "Faith" or "Christian" in a name states nothing.
    """
    if name is None:
        return None
    return " ".join(SYMBOLS.sub(" ", name).split()) or None


def redact(text: str | None) -> str | None:
    """`text` without the clauses that state a sensitive attribute; None if none is left."""
    if text is None:
        return None
    cleaned = SYMBOLS.sub("", text)
    if not _markers(cleaned):
        return cleaned if cleaned.strip() else None
    parts = BOUNDARY.split(cleaned)
    out: list[str] = []
    for index in range(0, len(parts), 2):
        clause = _clean_clause(parts[index])
        separator = parts[index + 1] if index + 1 < len(parts) else ""
        if clause.strip():
            out.append(clause + separator)
    result = "".join(out).strip(" \t\n|•·;,-–—")
    return result or None


# Street-level detail: a number, a street name or a unit.
_STREET = re.compile(
    r"\d|\b(?:street|avenue|ave|road|boulevard|blvd|lane|drive|court|place|plaza|square"
    r"|rue|calle|suite|apt|apartment|unit|floor)\b"
    r"|\w(?:stra(?:ss|ß)e|straat|gasse|laan|plein|kade|gracht|weg|vej|gatan|gade|allee)\b",
    re.IGNORECASE,
)
# A postal code at the end of a part: US ZIP, Canadian, UK, Dutch and other digit codes.
_POSTCODE = re.compile(
    r"\s*\b(?:\d{3,6}(?:-\d{3,4})?|[A-Z]\d[A-Z] ?\d[A-Z]\d|[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}"
    r"|\d{4} ?[A-Z]{2})$"
)


def city_level(location: str | None) -> str | None:
    """
    A location no finer than a city or metro area: postal codes are removed, and
    comma-separated parts that name a street, a number or a unit are dropped, as is a part
    that states origin ("born in …").
    """
    if not location:
        return None
    kept = []
    for part in location.split(","):
        part = _POSTCODE.sub("", part).strip()
        if part and not _STREET.search(part) and not _markers(part):
            kept.append(part)
    return ", ".join(kept) or None


## Tests


def test_redact_drops_sensitive_clauses_and_keeps_the_rest() -> None:
    assert redact("Husband, 6x Dad, Latter-day Saint, Dev, Educator 🏹") == "Dev, Educator 🏹"
    assert redact("DevRel @ GitHub | 🇨🇴 born | BC survivor | https://ada.example/x") == (
        "DevRel @ GitHub | 🇨🇴 born | https://ada.example/x"
    )
    assert redact("Director at GitHub. Married to a dweeb and mom to two kids. She/Her ✝️ CHI") == (
        "Director at GitHub. She/Her  CHI"
    )
    assert redact("I build compilers.\nI'm 42 years old (yes, really).\nI write Rust.") == (
        "I build compilers.\nI write Rust."
    )
    assert redact("Ada lives in Oxford with her wife and two cats. Ada writes Rust.") == (
        "Ada writes Rust."
    )
    assert redact("Proud father of two") is None
    assert redact(None) is None
    # Topics, metaphors and pets are not attributes of the person.
    for kept in (
        "Head of Accessibility at GitHub, empowering people with disabilities",
        "Corgi mom, dad jokes and a PhD from the Catholic University of Louvain",
        "Staff engineer working on tech debt and democratizing ML",
    ):
        assert redact(kept) == kept


def test_categories_names_and_city_level() -> None:
    assert categories("Queer 🏳️‍🌈 Python dev, first-gen immigrant") == {
        "sexuality",
        "origin",
        "symbol",
    }
    assert is_sensitive("ayghri/i-have-adhd") and is_sensitive("Latina-Dev")
    assert not is_sensitive("octo/compiler-family")
    assert city_level("200 Berkeley St, Boston, Massachusetts 02116, US") == (
        "Boston, Massachusetts, US"
    )
    assert city_level("Vijzelstraat, 68-78, Amsterdam, North Holland 1017 HL, NL") == (
        "Amsterdam, North Holland, NL"
    )
    assert city_level("Seattle, Washington, United States") == (
        "Seattle, Washington, United States"
    )
    assert city_level("Born in Lagos, Toronto") == "Toronto"
