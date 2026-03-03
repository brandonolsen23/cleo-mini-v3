"""Core address normalizer — the single normalization path for all sources.

Every address in the system (Realtrack, brands, GeoWarehouse, or any future
source) flows through this module. Source-specific parsers extract raw fields
upstream; this module normalizes and decomposes them into a canonical form.

Three entry points based on input shape:
    normalize_from_fields()  — pre-split fields (Realtrack property, brands)
    normalize_from_string()  — comma-separated string (Realtrack party addresses)
    normalize_from_mpac()    — MPAC flat format (GeoWarehouse)

All three return the same NormalizedAddress dict.
"""

import html as _html
import re
from typing import Dict, Optional

from cleo.properties.normalize import (
    CITY_ALIASES,
    _SAINT_NAMES,
    _SAINT_PATTERN,
    _STREET_TYPE_MAP,
    _DIRECTION_MAP,
    _ABBREV_PATTERN,
    _ALL_ABBREVS,
)
from cleo.normalize.municipalities import is_official, get_canonical

# ── Constants ──

# Canonical street suffixes (the expanded long forms + Ontario-specific)
_STREET_SUFFIXES: set[str] = set(_STREET_TYPE_MAP.values()) | {
    "LINE",       # Ontario concession lines: "GUELPH LINE", "10TH LINE"
    "SIDEROAD",   # rural Ontario: "ST JOHNS SIDEROAD"
    "TRAIL",      # hiking/nature-adjacent streets
    "WAY",        # common suffix not in abbreviation map
    "PATH",       # pedestrian-oriented streets
    "GATE",       # common in newer subdivisions
    "GROVE",      # less common but valid
    "CHASE",      # subdivision streets
    "COMMON",     # shared/mixed-use streets
    "CONCESSION", # rural Ontario
}

# Canonical directions (the expanded long forms)
_DIRECTIONS: set[str] = set(_DIRECTION_MAP.values())

# Province name variants → canonical form
_PROVINCE_MAP: Dict[str, str] = {
    "ON": "ONTARIO",
    "ONT": "ONTARIO",
    "ONTARIO": "ONTARIO",
}

# All Canadian provinces/territories — abbreviation/variant → canonical name
# Used for province detection in string parsing AND address_scope detection
_ALL_PROVINCE_MAP: Dict[str, str] = {
    # Ontario
    "ON": "ONTARIO", "ONT": "ONTARIO", "ONTARIO": "ONTARIO",
    # Quebec
    "QC": "QUEBEC", "QUE": "QUEBEC", "QUEBEC": "QUEBEC", "PQ": "QUEBEC",
    # British Columbia
    "BC": "BRITISH COLUMBIA", "BRITISH COLUMBIA": "BRITISH COLUMBIA",
    # Alberta
    "AB": "ALBERTA", "ALTA": "ALBERTA", "ALBERTA": "ALBERTA",
    # Manitoba
    "MB": "MANITOBA", "MAN": "MANITOBA", "MANITOBA": "MANITOBA",
    # Saskatchewan
    "SK": "SASKATCHEWAN", "SASK": "SASKATCHEWAN", "SASKATCHEWAN": "SASKATCHEWAN",
    # Nova Scotia
    "NS": "NOVA SCOTIA", "NOVA SCOTIA": "NOVA SCOTIA",
    # New Brunswick
    "NB": "NEW BRUNSWICK", "NEW BRUNSWICK": "NEW BRUNSWICK",
    # PEI
    "PE": "PRINCE EDWARD ISLAND", "PEI": "PRINCE EDWARD ISLAND",
    "PRINCE EDWARD ISLAND": "PRINCE EDWARD ISLAND",
    # Newfoundland
    "NL": "NEWFOUNDLAND AND LABRADOR", "NFLD": "NEWFOUNDLAND AND LABRADOR",
    "NEWFOUNDLAND AND LABRADOR": "NEWFOUNDLAND AND LABRADOR",
    "NEWFOUNDLAND": "NEWFOUNDLAND AND LABRADOR",
    # Territories
    "NT": "NORTHWEST TERRITORIES", "NORTHWEST TERRITORIES": "NORTHWEST TERRITORIES",
    "YT": "YUKON", "YUKON": "YUKON",
    "NU": "NUNAVUT", "NUNAVUT": "NUNAVUT",
}

_CANADIAN_PROVINCES: set[str] = set(_ALL_PROVINCE_MAP.values())

# Uppercase city alias lookup (built from properties/normalize.py source of truth)
_CITY_ALIAS_UPPER: Dict[str, str] = {k.upper(): v.upper() for k, v in CITY_ALIASES.items()}

# Postal code: A1A 1A1 or A1A1A1
_POSTAL_RE = re.compile(r"\b([A-Z]\d[A-Z])\s*(\d[A-Z]\d)\b")

# Street number: leading digits, optionally with letter suffix (620A, 373B)
# Handles ranges ("21 - 23"), comma lists ("165, 170, 180"), ampersand lists
# ("401 & 403"), slash lists ("245/251"), plus suffixes ("1255A+B"), fractions
# ("399 1/2", "84 - 88 1/2"), and combinations.
_STREET_NUM_RE = re.compile(
    r"^(\d+[A-Z]?"           # base: digits + optional letter
    r"(?:\s+\d/\d)?"         # optional fraction
    r"(?:\+[A-Z])?"          # optional plus-suffix ("A+B" after 1255A)
    r"(?:\s*[-,&/]\s*\d+[A-Z]?(?:\s+\d/\d)?)*"  # repeating: separator + more numbers
    r")\s+(.+)$"
)

# Unit/suite patterns — tried in order, each captures unit number.
# Requires comma or whitespace before keyword to avoid matching inside
# words like "STEELES" when looking for "STE".
_UNIT_TRAILING_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Ordinal floor: "2ND FLOOR", "19TH FLR", "3RD FL"
    (re.compile(r"(?:,\s*|\s+)(\d+)\s*(?:ST|ND|RD|TH)\s+(?:FLOOR|FLR|FL)\b", re.IGNORECASE), "FLOOR"),
    # FLOOR/FLR N: "FLOOR 2", "FLR #3"
    (re.compile(r"(?:,\s*|\s+)(?:FLOOR|FLR|FL)\b\s*#?\s*([^,]+)", re.IGNORECASE), "FLOOR"),
    # SUITE/STE N
    (re.compile(r"(?:,\s*|\s+)(?:SUITE|STE)\b\s+([^,]+)", re.IGNORECASE), "SUITE"),
    # UNIT/UNITS N
    (re.compile(r"(?:,\s*|\s+)UNITS?\b\s*#?\s*([^,]+)", re.IGNORECASE), "UNIT"),
    # APARTMENT/APT N
    (re.compile(r"(?:,\s*|\s+)(?:APARTMENT|APT)\s+([^,]+)", re.IGNORECASE), "APARTMENT"),
    # BUILDING/BLDG N — require unit value starts with alphanumeric (not dash/punctuation)
    (re.compile(r"(?:,\s*|\s+)(?:BUILDING|BLDG)\b\s+([A-Z0-9][^,]*)", re.IGNORECASE), "BUILDING"),
    # # N (bare hash)
    (re.compile(r"(?:,\s*|\s+)#\s*([^,]+)", re.IGNORECASE), "UNIT"),
]

# Leading unit pattern: "UNIT A4B 40 Kingston Road" → unit="A4B", street="40 Kingston Road"
_UNIT_LEADING_RE = re.compile(
    r"^(?P<type>UNITS?|SUITE|STE|APT|APARTMENT)\s+(?P<num>\S+)\s+(?P<rest>\d+.*)$",
    re.IGNORECASE,
)

# Leading unit with comma: "SUITE 2430, PO BOX 519, TD Tower, 161 Bay St"
# Captures unit number before first comma, rest is everything after.
_UNIT_LEADING_COMMA_RE = re.compile(
    r"^(?P<type>UNITS?|SUITE|STE|APT|APARTMENT)\s+(?P<num>[^,\s]+)\s*,\s*(?P<rest>.+)$",
    re.IGNORECASE,
)

# Unit type canonicalization
_UNIT_TYPE_MAP: dict[str, str] = {
    "UNIT": "UNIT", "STE": "SUITE", "SUITE": "SUITE",
    "APT": "APARTMENT", "APARTMENT": "APARTMENT",
    "FLOOR": "FLOOR", "BUILDING": "BUILDING", "BLDG": "BUILDING",
}

# Building name keywords — words that indicate a named building, tower, complex, etc.
# Used to extract building names from addresses for preservation but not geocoding.
_BUILDING_KEYWORDS = {
    "BUILDING", "TOWER", "CENTRE", "CENTER", "PLAZA", "COMPLEX",
    "PAVILION", "TERMINAL", "CHAMBERS", "GALLERIA", "MALL", "CORNERS",
    "HOSPITAL",
}

# Building name extraction — detect leading or trailing named buildings.
# Leading: "WING HANG BANK BUILDING, 161-167 QUEENS ROAD" → building="WING HANG BANK BUILDING"
# Trailing: "175 BLOOR STREET EAST, SOUTH TOWER" → building="SOUTH TOWER"
# Note: PLACE, COURT, HOUSE, HALL, SQUARE omitted — too many false positives
# (they're common street suffixes or city names).


# PO Box / mailing box number extraction (runs on normalized/cleaned string)
# Leading: "BOX 2041, EGLINGTON AVE W" or "PO BOX 1088"
_BOX_LEADING_RE = re.compile(
    r"^(?:PO\s+)?BOX\s+(\d+)\s*,?\s*(.*)$",
    re.IGNORECASE,
)
# Trailing: "231 MAIN STREET, BOX 862"
_BOX_TRAILING_RE = re.compile(
    r"(?:,\s*|\s+)(?:PO\s+)?BOX\s+(\d+)\s*$",
    re.IGNORECASE,
)

# Rural Route extraction (runs on normalized/cleaned string, after unit + PO box)
# Trailing: "1188 LAKESHORE ROAD, RR 3" → ("1188 LAKESHORE ROAD", "3")
# Leading/standalone: "RR 3" → ("", "3")
_RURAL_ROUTE_RE = re.compile(
    r"(?:,\s*|\s+)(?:RR|RURAL\s+ROUTE)\s*#?\s*(\d+)\s*$"
    r"|^(?:RR|RURAL\s+ROUTE)\s*#?\s*(\d+)\s*(?:,\s*(.*))?$",
    re.IGNORECASE,
)

# Highway route number: "Highway #7", "Hwy #50 North", "Hwy, #20", "Highway, # 17 East"
# Normalizes to "HIGHWAY 7", "HIGHWAY 50 NORTH" etc. before unit extraction sees the #.
_HIGHWAY_HASH_RE = re.compile(
    r"((?:HIGHWAY|HWY)\s*),?\s*#\s*(\d+[A-Z]?(?:\s+(?:NORTH|SOUTH|EAST|WEST|N|S|E|W))?)",
    re.IGNORECASE,
)

# Dash-joined unit-number prefix at start of address.
# Splits patterns like "B7-77 Billy Bishop Way" → unit=B7, rest="77 Billy Bishop Way"
# and "2A-5005 South Service Road" → unit=2A, rest="5005 South Service Road"
# Does NOT match pure numeric ranges like "123-125" (both sides are pure digits).
_UNIT_DASH_NUM_RE = re.compile(
    r"^([A-Z]\d+|[A-Z]+\d+[A-Z]?|\d+[A-Z]|[A-Z])"  # left side: letter+digit mix OR single letter
    r"\s*-\s*"                                          # dash separator
    r"(\d+\s+.+)$"                                      # right side: street number + rest of address
)

# Number-dash-ordinal at start of address.
# Splits "67-45th Street" → number=67, rest="45TH STREET"
_NUM_DASH_ORDINAL_RE = re.compile(
    r"^(\d+)\s*-\s*(\d+(?:ST|ND|RD|TH)\s+.+)$"
)

# PO Box / General Delivery detection
_PO_BOX_RE = re.compile(
    r"\b(P\.?O\.?\s*BOX|POST\s*OFFICE\s*BOX|GENERAL\s*DELIVERY|"
    r"STN\s+MAIN|STATION\s+MAIN)\b",
    re.IGNORECASE,
)

# Legal description detection
_LEGAL_RE = re.compile(
    r"\b(LOT|CONC|CONCESSION|PLAN|BLOCK|PART)\b", re.IGNORECASE
)

# C/O prefix pattern — "C/O COMPANY NAME 123 STREET ..."
# Accepts both C/O (letter O) and C/0 (zero) — source data has both variants
_CO_PREFIX_RE = re.compile(
    r"^C/[O0]\s+(.+?)\s+(\d+\s+.+)$",
    re.IGNORECASE,
)

# ATTN prefix — "ATTN: NAME 123 STREET ..." or "ATTN NAME 123 STREET ..."
_ATTN_PREFIX_RE = re.compile(
    r"^ATTN:?\s+(.+?)\s+(\d+\s+.+)$",
    re.IGNORECASE,
)

# Embedded ATTN within C/O text — "SOBEYS ONTARIO ATTN: JANET STROH"
_ATTN_EMBEDDED_RE = re.compile(
    r"^(.+?)\s+ATTN:?\s+(.+)$",
    re.IGNORECASE,
)

# Bare company prefix — "DGI MANAGEMENT SERVICES 2285 DUNWIN DR ..."
# Matches 2+ non-numeric words before the street number.
_BARE_PREFIX_RE = re.compile(
    r"^([A-Z][A-Z\s.&\'-]{3,}?)\s+(\d+\s+.+)$",
)

# Build a reverse-lookup set of all known city names (uppercase) for tail detection.
# Lazy-initialized on first call to _detect_city_from_tail().
_ALL_CITY_NAMES: set[str] | None = None


def _get_all_city_names() -> set[str]:
    """Return the set of all known city names (official + aliases), uppercase."""
    global _ALL_CITY_NAMES
    if _ALL_CITY_NAMES is not None:
        return _ALL_CITY_NAMES
    from cleo.normalize.municipalities import _load
    names: set[str] = set()
    names.update(_load().keys())  # official AMO names (already uppercase)
    names.update(k.upper() for k in CITY_ALIASES)  # alias names
    _ALL_CITY_NAMES = names
    return _ALL_CITY_NAMES


def _detect_city_from_tail(text: str) -> tuple[str, str]:
    """Detect a city name at the tail of a flat MPAC-format address string.

    Scans backwards trying 1-word, 2-word, ..., up to 5-word tails against the
    known municipality list + alias table.  Returns (street, city) or
    (original_text, "") if no city found.
    """
    words = text.split()
    if len(words) < 2:
        return text, ""

    all_names = _get_all_city_names()

    # Try longest tail first (up to 5 words) — prefer more specific matches
    max_tail = min(5, len(words) - 1)  # leave at least 1 word for street
    for n in range(max_tail, 0, -1):
        candidate = " ".join(words[-n:])
        if candidate in all_names:
            street = " ".join(words[:-n])
            return street, candidate

    return text, ""


# ── Internal helpers ──

def _clean(s: str) -> str:
    """Basic hygiene: strip, uppercase, collapse whitespace, strip periods."""
    s = _html.unescape(s)  # decode HTML entities before anything else
    s = s.strip().upper()
    # Normalize half-address fractions:
    #   "½" → " 1/2", "2391/2" → "239 1/2", "834-1/2" → "834 1/2"
    s = s.replace("\u00BD", " 1/2")  # ½ → 1/2
    s = re.sub(r"(\d)-1/2\b", r"\1 1/2", s)  # 834-1/2 → 834 1/2
    s = re.sub(r"(\d)1/2\b", r"\1 1/2", s)  # 2391/2 → 239 1/2
    # Period followed by letter → insert space ("Ave.North" → "AVE NORTH")
    s = re.sub(r"\.(?=[A-Z])", " ", s)
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_street(street: str) -> str:
    """Expand abbreviations in a street string (saint protection first)."""
    s = _clean(street)
    if not s:
        return ""
    # Strip descriptive preamble before "LOCATED AT" / "AT":
    # "TAXI STAND FOR DRIVERS LOCATED AT 6301 SILVER DART DRIVE" → "6301 SILVER DART DRIVE"
    m_loc = re.match(r'^.+?\bLOCATED\s+AT\s+(\d+\s+.+)$', s)
    if m_loc:
        s = m_loc.group(1)
    # Normalize highway route numbers BEFORE anything else touches the #.
    # "HIGHWAY #7" → "HIGHWAY 7", "HWY, #50 NORTH" → "HIGHWAY 50 NORTH"
    s = _HIGHWAY_HASH_RE.sub(lambda m: f"HIGHWAY {m.group(2).strip()}", s)
    # Protect saint names BEFORE possessive collapse — "ST JOHN'S" must match
    # the saint pattern while the apostrophe is still present, otherwise
    # collapsing "JOHN'S" → "JOHNS" prevents the saint match.
    s = _SAINT_PATTERN.sub(lambda m: f"SAINT {m.group(1)}", s)
    # Collapse possessive 'S / \u2019S into S before abbreviation expansion.
    # Prevents "QUEEN'S" → "QUEEN SOUTH" when \bS\b matches the isolated S.
    # Result: "QUEEN'S" → "QUEENS" (correct), "O'NEILL" stays "O'NEILL".
    s = re.sub(r"['\u2019]S\b", "S", s)
    # Protect hash-prefixed unit codes from abbreviation expansion.
    # "#E-16" has a standalone \bE\b that would become EAST. Replace # with
    # a placeholder, expand abbreviations, then restore.
    _HASH_UNIT_RE = re.compile(r"#([A-Z0-9]+-?\d*)")
    placeholders = {}
    for i, m in enumerate(_HASH_UNIT_RE.finditer(s)):
        token = m.group(0)
        ph = f"\x00HASHUNIT{i}\x00"
        placeholders[ph] = token
        s = s.replace(token, ph, 1)
    # Protect direction-letter unit codes from expansion.
    # "E-2015 PARKEDALE AVE" → E would become EAST without protection.
    _DIR_UNIT_RE = re.compile(r"\b([NSEW])-(\d+)")
    for i, m in enumerate(_DIR_UNIT_RE.finditer(s)):
        token = m.group(0)
        ph = f"\x00DIRUNIT{i}\x00"
        placeholders[ph] = token
        s = s.replace(token, ph, 1)
    # Expand all abbreviations
    s = _ABBREV_PATTERN.sub(lambda m: _ALL_ABBREVS[m.group(1)], s)
    # Restore placeholders
    for ph, token in placeholders.items():
        s = s.replace(ph, token)
    # Convert bound directions: EASTBOUND→EAST, WESTBOUND→WEST, etc.
    s = re.sub(r"\b(EAST|WEST|NORTH|SOUTH)BOUND\b", r"\1", s)
    return s


def _normalize_city(city: str) -> tuple[str, str]:
    """Normalize city: official list match, then alias resolution.

    Returns (normalized_city, city_status) where city_status is one of:
        "official"  — exact match on AMO municipality list
        "alias"     — resolved via alias table to an official municipality
        "unknown"   — not found on official list or alias table
        "empty"     — input was empty/whitespace
    """
    s = city.strip()
    # Clean up common data issues before matching
    s = s.rstrip(",")  # trailing comma ("Strathroy,")
    s = _html.unescape(s)  # HTML entities ("Orl&#233;ans" → "Orléans")
    s = re.sub(r",\s*(Ontario|ON)\s*$", "", s, flags=re.IGNORECASE)  # "Kitchener, Ontario"
    s = re.sub(r"\s+(Ontario|ON)\s*$", "", s, flags=re.IGNORECASE)  # "Etobicoke Ontario"
    s = re.sub(r"\s*\([^)]*\)", "", s)  # "Ottawa (Gloucester)" → "Ottawa"
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return "", "empty"
    upper = s.upper()

    # Step 1: strip periods for matching (N. Bay → N Bay, St. Thomas → St Thomas)
    clean = upper.replace(".", "").strip()
    clean = re.sub(r"\s+", " ", clean)

    def _clean_slash(name: str) -> str:
        """Strip slash-joined second name from composite municipalities.

        AMO uses "Dutton/Dunwich", "Edwardsburgh/Cardinal", etc. but for
        geocoding and display the first part is the usable city name.
        """
        if "/" in name:
            return name.split("/", 1)[0].strip()
        return name

    # Step 2: exact match on official municipality list
    canonical = get_canonical(upper)
    if canonical:
        return _clean_slash(canonical.upper()), "official"

    # Also try without periods
    if clean != upper:
        canonical = get_canonical(clean)
        if canonical:
            return _clean_slash(canonical.upper()), "official"

    # Step 3: alias table lookup
    alias_hit = _CITY_ALIAS_UPPER.get(upper)
    if alias_hit:
        return _clean_slash(alias_hit.upper()), "alias"

    # Also try without periods (covers "N. Bay" style)
    if clean != upper:
        alias_hit = _CITY_ALIAS_UPPER.get(clean)
        if alias_hit:
            return alias_hit.upper(), "alias"

    # Step 4: unknown — return uppercased as-is
    return upper, "unknown"


def _normalize_province(prov: str) -> str:
    """Normalize province to full canonical name."""
    s = prov.strip().upper().rstrip(".")
    return _ALL_PROVINCE_MAP.get(s, s)


def _format_postal_code(pc: str) -> str:
    """Format postal code as 'A1A 1A1'."""
    pc = pc.strip().upper().replace(" ", "")
    m = re.match(r"^([A-Z]\d[A-Z])(\d[A-Z]\d)$", pc)
    if m:
        return f"{m.group(1)} {m.group(2)}"
    return pc if pc else ""


# Compound road name prefixes — when these precede a suffix word, the suffix
# is part of the road name (e.g. "COUNTY ROAD 93") and should NOT be split.
_COMPOUND_ROAD_PREFIXES: set[str] = {
    "COUNTY", "COUNTRY", "REGIONAL", "OLD", "FIRE",
}


def _decompose_street(normalized_street: str) -> Dict[str, str]:
    """Decompose a normalized street string into components.

    Takes an already-expanded street like "1476 QUEEN STREET WEST"
    and splits into street_number, street_name, street_suffix, street_direction.
    """
    result = {
        "street_number": "",
        "street_name": "",
        "street_suffix": "",
        "street_direction": "",
    }

    s = normalized_street.strip()
    if not s:
        return result

    # Strip comma between street number and name: "133, HIGHWAY 11" → "133 HIGHWAY 11"
    # Only when the word after the comma is NOT a digit (avoids breaking "165, 170, 180 ATTWELL DR")
    s = re.sub(r"^(\d+),\s+(?=[A-Z])", r"\1 ", s)

    # Extract street number from front
    num_match = _STREET_NUM_RE.match(s)
    if num_match:
        result["street_number"] = num_match.group(1).strip()
        s = num_match.group(2).strip()
        # Strip leading dash separator ("285 - Geneva St" → remainder "- GENEVA ST")
        s = re.sub(r"^-\s*", "", s)
    # else: no street number (intersection, building name, etc.)

    # Strip trailing commas before splitting ("KING STREET," → "KING STREET")
    s = s.rstrip(",").strip()

    # Extract trailing direction (NORTH, EAST, etc.)
    # Also handle comma before direction ("KING STREET, EAST" → direction=EAST)
    words = s.split()
    if words and words[-1] in _DIRECTIONS:
        result["street_direction"] = words[-1]
        words = words[:-1]

    # Strip trailing commas from remaining words ("STREET," → "STREET")
    words = [w.rstrip(",") for w in words]

    # Extract trailing street suffix (STREET, ROAD, etc.)
    if words and words[-1] in _STREET_SUFFIXES:
        result["street_suffix"] = words[-1]
        words = words[:-1]

    # Enhanced: if no suffix at end, scan left-to-right for an embedded suffix.
    # Only splits when the trailing text is recognizably junk (known city,
    # province code, store description, etc.) — not for legitimate multi-word
    # road names like "QUEENS ROAD CENTRAL".
    #   "KENT STREET WEST LINDSAY SQ MALL" → suffix=STREET, dir=WEST, name=KENT
    #   "DIXIE ROAD STORE NO 12" → suffix=ROAD, name=DIXIE
    elif len(words) >= 2:
        _JUNK_MARKERS = {"STORE", "MALL", "PLAZA", "CENTRE", "CENTER", "INSIDE",
                         "LOCATED", "MAILBOX", "BLDG", "BUILDING", "AT", "NEAR", "SQ", "WAL-MART"}
        all_city_names = _get_all_city_names()

        for i in range(1, len(words)):
            if words[i] not in _STREET_SUFFIXES:
                continue
            # Skip compound road names: COUNTY ROAD N, REGIONAL ROAD N, etc.
            if words[i - 1] in _COMPOUND_ROAD_PREFIXES:
                continue
            # Skip if a bare number follows — likely a road number (WELLINGTON ROAD 109)
            after = words[i + 1:] if i + 1 < len(words) else []
            if after and after[0].isdigit():
                continue

            # Determine what's truly trailing (after suffix + optional direction)
            overflow = after
            has_direction = False
            if overflow and overflow[0] in _DIRECTIONS:
                has_direction = True
                overflow = overflow[1:]

            # Only split if: no overflow, or overflow is recognizable junk
            if overflow:
                overflow_text = " ".join(overflow)
                is_junk = (
                    # Overflow is a known city
                    overflow_text in all_city_names
                    # Overflow starts with a known city (city + extra text)
                    or any(" ".join(overflow[:n]) in all_city_names
                           for n in range(min(4, len(overflow)), 0, -1))
                    # Overflow contains junk markers
                    or any(w in _JUNK_MARKERS for w in overflow)
                    # Overflow contains a province code
                    or any(w in _ALL_PROVINCE_MAP for w in overflow)
                )
                if not is_junk:
                    continue

            # Accept this suffix
            result["street_suffix"] = words[i]
            if has_direction:
                result["street_direction"] = after[0]
            words = words[:i]
            break

    # What's left is the street name
    result["street_name"] = " ".join(words)

    return result


def _extract_unit(street: str) -> tuple[str, str, str]:
    """Extract unit/suite from a street string.

    Handles:
        - Leading: "UNIT A4B 40 KINGSTON ROAD"
        - Trailing keyword-first: "123 MAIN ST, SUITE 200"
        - Trailing ordinal: "2441 YONGE ST, 2ND FLOOR"

    Returns (street_without_unit, unit_number, unit_type).
    unit_type is one of: SUITE, UNIT, APARTMENT, FLOOR, BUILDING, or "".
    """
    # Leading hash-unit with following street number:
    # "#5 861 York Mills Road" → unit=5, street="861 York Mills Road"
    # "#48-40 Charles Street W." → unit=48, street="40 Charles St W." (via unit split later)
    # "#6A - 17 King St" → unit=6A, street="17 King St"
    # Does NOT match "#3 Highway 17" (no following digit → hash is civic number).
    m = re.match(r"^#\s*([A-Z0-9]+)\s*[-\s]\s*(\d+\s+.+)$", street)
    if m:
        return m.group(2).strip(), m.group(1).strip(), "UNIT"

    # Try leading pattern first: "UNIT X 123 STREET NAME"
    m = _UNIT_LEADING_RE.match(street)
    if m:
        keyword = m.group("type").upper()
        unit_type = _UNIT_TYPE_MAP.get(keyword, keyword)
        return m.group("rest").strip(), m.group("num").strip().rstrip(","), unit_type

    # Leading unit with dash-joined street number:
    # "UNIT 3-167 CHURCH STREET" → unit=3, street="167 CHURCH STREET"
    # "UNIT 210 A-240 LEIGHLAND AVENUE" → unit="210 A", street="240 LEIGHLAND AVENUE"
    m = re.match(
        r"^(?:UNITS?|SUITE|STE|APT|APARTMENT)\s+"
        r"(.+?)"          # unit value (non-greedy)
        r"\s*-\s*"        # dash separator
        r"(\d+\s+[A-Z].*)$",  # street number + street name
        street,
        re.IGNORECASE,
    )
    if m:
        unit_val = m.group(1).strip().rstrip(",").lstrip("#")
        rest = m.group(2).strip()
        return rest, unit_val, "UNIT"

    # Try leading with comma: "SUITE 2430, PO BOX 519, TD TOWER, 161 BAY ST"
    m = _UNIT_LEADING_COMMA_RE.match(street)
    if m:
        keyword = m.group("type").upper()
        unit_type = _UNIT_TYPE_MAP.get(keyword, keyword)
        return m.group("rest").strip(), m.group("num").strip().rstrip(","), unit_type

    # Try trailing patterns in order
    for pattern, unit_type in _UNIT_TRAILING_PATTERNS:
        m = pattern.search(street)
        if m:
            unit = m.group(1).strip().rstrip(",")
            # Check if the captured "unit" actually contains a street address
            # after the real unit value. E.g. "C9 1270 FISCHER HALLMAN ROAD"
            # should be unit=C9 with "1270 FISCHER HALLMAN ROAD" put back.
            overflow_text = ""
            # Case 1: unit + street-number + street words ("C9 1270 FISCHER ROAD")
            overflow_match = re.match(
                r"^(\S+)\s+(\d+\s+[A-Z].*)$", unit
            )
            if overflow_match:
                unit = overflow_match.group(1).rstrip(",")
                overflow_text = overflow_match.group(2)
            # Case 1b: unit + letter-dash-digits + street words
            # "210 A-240 LEIGHLAND AVENUE" → unit=210A, overflow="240 LEIGHLAND AVENUE"
            elif len(unit.split()) >= 3:
                parts = unit.split()
                letter_dash = re.match(r"^([A-Z])-(\d+)$", parts[1]) if len(parts) >= 2 else None
                if letter_dash:
                    unit = parts[0].rstrip(",") + letter_dash.group(1)
                    overflow_text = letter_dash.group(2) + " " + " ".join(parts[2:])
                # Case 2: unit + street-name with known suffix ("1 BANK STREET")
                elif parts[-1] in _STREET_SUFFIXES:
                    unit = parts[0].rstrip(",")
                    overflow_text = " ".join(parts[1:])
            # Keep text before AND after the match (building name may follow)
            before = street[:m.start()].strip().rstrip(",")
            after = street[m.end():].strip().lstrip(",").strip()
            # Strip orphan dash/en-dash/em-dash separators left after unit removal
            before = re.sub(r"\s*[-\u2013\u2014]\s*$", "", before)
            if overflow_text:
                # Overflow is street address extracted from unit value.
                # Strip leading dash remnants ("- 9301 BATHURST ST" → "9301 BATHURST ST")
                overflow_text = re.sub(r"^[-\u2013\u2014]\s*", "", overflow_text)
                after = (overflow_text + " " + after).strip() if after else overflow_text
                if before and after:
                    # If before is a building/place name (no leading digit), use comma
                    # so _extract_building_name can detect it downstream.
                    # If before is a street number, use space to form one address.
                    if before[0].isdigit():
                        street_clean = f"{before} {after}"
                    else:
                        street_clean = f"{before}, {after}"
                else:
                    street_clean = before or after
            else:
                # Normal case — before and after may be building name + street
                street_clean = f"{before}, {after}" if (before and after) else before or after
            return street_clean, unit, unit_type

    return street, "", ""


def _extract_po_box(street: str) -> tuple[str, str]:
    """Extract PO Box / mailing box number from a street string.

    Handles:
        "BOX 2041, EGLINGTON AVENUE WEST"  → ("EGLINGTON AVENUE WEST", "2041")
        "PO BOX 1088"                      → ("", "1088")
        "231 MAIN STREET, BOX 862"         → ("231 MAIN STREET", "862")

    Returns (street_without_box, box_number).
    """
    # Leading: "BOX 2041, ..." or "PO BOX 1088"
    m = _BOX_LEADING_RE.match(street)
    if m:
        return m.group(2).strip().lstrip(",").strip(), m.group(1).strip()

    # Trailing: "231 MAIN STREET, BOX 862"
    m = _BOX_TRAILING_RE.search(street)
    if m:
        street_clean = street[:m.start()].strip().rstrip(",")
        return street_clean, m.group(1).strip()

    return street, ""


def _extract_rural_route(street: str) -> tuple[str, str]:
    """Extract Rural Route (RR) designation from a street string.

    Handles:
        "1188 LAKESHORE ROAD, RR 3"  → ("1188 LAKESHORE ROAD", "3")
        "RR 3"                       → ("", "3")
        "RR 1, LINE 5"              → ("LINE 5", "1")

    Returns (street_without_rr, rr_number).
    """
    m = _RURAL_ROUTE_RE.search(street)
    if m:
        # Trailing match: group(1) has the number
        if m.group(1):
            rr_num = m.group(1).strip()
            street_clean = street[:m.start()].strip().rstrip(",")
            return street_clean, rr_num
        # Leading/standalone match: group(2) has the number, group(3) has remainder
        if m.group(2):
            rr_num = m.group(2).strip()
            remainder = (m.group(3) or "").strip().lstrip(",").strip()
            return remainder, rr_num
    return street, ""


def _determine_scope(
    normalized_province: str,
    city_status: str,
    category_hint: str,
) -> str:
    """Determine geographic scope of an address.

    Returns one of:
        "ontario"       — Ontario address (province is Ontario or city matches ON list)
        "canadian"      — Canadian but not Ontario (recognized non-ON province)
        "international" — non-Canadian (no recognized province + unknown city)
        "unknown"       — can't determine (no province, no city, or ambiguous)
    """
    prov = normalized_province.upper().strip() if normalized_province else ""

    if prov == "ONTARIO":
        return "ontario"

    if prov and prov in _CANADIAN_PROVINCES:
        return "canadian"

    # No province — use city_status as signal
    if city_status in ("official", "alias"):
        # City matched Ontario municipality list → ontario
        return "ontario"

    if city_status == "unknown":
        # Unknown city + no recognized province → international
        return "international"

    # Empty city or no signals
    return "unknown"


def _extract_building_name(street: str) -> tuple[str, str]:
    """Extract a named building from a street string.

    Handles:
        Leading: "WING HANG BANK BUILDING, 161-167 QUEENS ROAD"
                 → ("161-167 QUEENS ROAD", "WING HANG BANK BUILDING")
        Trailing: "175 BLOOR STREET EAST, SOUTH TOWER"
                  → ("175 BLOOR STREET EAST", "SOUTH TOWER")
        Trailing: "199 BAY STREET, COMMERCE COURT WEST"
                  → ("199 BAY STREET", "COMMERCE COURT WEST")

    Only matches when a comma-separated segment contains a building keyword
    AND a street number exists in another segment.

    Returns (street_without_building, building_name).
    """
    def _has_building_keyword(s: str) -> bool:
        words = s.split()
        return any(w in _BUILDING_KEYWORDS for w in words)

    def _starts_with_number(s: str) -> bool:
        if not s:
            return False
        if s[0].isdigit():
            return True
        # Accept unit-code prefix: "B005 - 509 ...", "FC-4 1 ...", "H7A - 777 ..."
        return bool(re.match(r'^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?[\s-]+\d', s))

    if "," not in street:
        # Check for dash-separated building/description:
        # "FIVE POINTS MALL - 275 TAUTON ROAD" (keyword)
        # "MAIN ENTRANCE - 50 CHARLTON AVENUE EAST" (no keyword, 2+ words)
        # "ALPHONSE BUILDING - LAURENTIAN UNIVERSITY - 935 RAMSEY LAKE ROAD" (double dash)
        # Use greedy match to find the LAST dash separator.
        m = re.match(r'^(.+)\s+[-\u2013\u2014]\s+(.+)$', street)
        if m:
            before, after = m.group(1).strip(), m.group(2).strip()
            if not _starts_with_number(before) and _starts_with_number(after):
                # Accept if: has a building keyword, OR description is 2+ words
                if _has_building_keyword(before) or len(before.split()) >= 2:
                    # If building name ends with digits, move them to the street.
                    # "HERITAGE MALL 50 - 4TH AVE" → building=HERITAGE MALL, street=50 4TH AVE
                    bm = re.match(r'^(.+?)\s+(\d+)$', before)
                    if bm:
                        before = bm.group(1).strip()
                        after = bm.group(2) + " " + after
                    return after, before
        # Check for building keyword followed by digits (no separator):
        # "FAIRVIEW MALL 285 GENEVA STREET" → building=FAIRVIEW MALL, street=285 GENEVA STREET
        # "SAINT CATHERINES HOSPITAL 1200 FOURTH AVENUE" → building, street
        for kw in _BUILDING_KEYWORDS:
            # Find keyword in the string, then check if digits follow
            pattern = re.compile(
                r'^(.+?\b' + re.escape(kw) + r')\s+(\d+\s+[A-Z].+)$'
            )
            km = pattern.match(street)
            if km:
                bname = km.group(1).strip()
                rest = km.group(2).strip()
                if not _starts_with_number(bname):
                    return rest, bname
        return street, ""

    # Split on first comma for leading check, last comma for trailing check
    segments = [s.strip() for s in street.split(",")]
    if len(segments) < 2:
        return street, ""

    # Leading: first segment has building keyword, second segment starts with number
    first = segments[0].strip()
    rest = ", ".join(segments[1:]).strip()
    if _has_building_keyword(first) and not _starts_with_number(first) and _starts_with_number(rest):
        return rest, first

    # Trailing: last segment has building keyword, first segment starts with number
    last = segments[-1].strip()
    front = ", ".join(segments[:-1]).strip()
    if _has_building_keyword(last) and not _starts_with_number(last) and _starts_with_number(front):
        return front, last

    # General heuristic: find the first segment starting with a digit/unit-code.
    # All preceding segments (without digits) are the building/description.
    # Handles: "ONroute Dutton, 27585 Highway 401", "Vaughan Mills, 327-1 Bass Pro",
    # "Across from Merivale Mall, Merivale Plaza, 1701 Merivale Road", etc.
    for i, seg in enumerate(segments):
        if i == 0:
            continue
        seg_s = seg.strip()
        if _starts_with_number(seg_s):
            preceding = ", ".join(s.strip() for s in segments[:i])
            if not re.search(r"\d", preceding):
                remaining = ", ".join(s.strip() for s in segments[i:])
                return remaining, preceding
            break

    return street, ""


def _strip_address_overflow(street: str, city: str = "") -> str:
    """Strip postal codes, province codes, city names, and junk from address end.

    Brand scrapers often include the full address (city/province/postal)
    in the address field. This strips the redundant parts since they're
    already available in separate fields.
    """
    s = street

    # 1. Strip postal code
    m = _POSTAL_RE.search(s)
    if m:
        s = s[:m.start()].strip()

    # 2. Strip trailing province abbreviation
    words = s.split()
    if len(words) >= 2 and words[-1].rstrip(",") in _ALL_PROVINCE_MAP:
        s = " ".join(words[:-1]).rstrip(", ").strip()

    # 3. Strip parenthetical descriptions (keep unit-related ones)
    if "(" in s:
        _UNIT_KW_IN_PAREN = re.compile(
            r"\b(UNIT|SUITE|STE|APT|APARTMENT|FLOOR|FLR)\b", re.IGNORECASE,
        )
        s = re.sub(
            r"\s*\(([^)]*)\)",
            lambda m: f" ({m.group(1)})" if _UNIT_KW_IN_PAREN.search(m.group(1)) else "",
            s,
        )
        s = re.sub(r"\s+", " ", s).strip()

    # 4. Strip trailing city name (if it matches the provided city or known cities).
    # Only strip when a recognized suffix or direction precedes the city,
    # to avoid stripping street names that happen to match a city
    # (e.g. "607 DUNDAS" — Dundas is a street, not the city here).
    all_names = _get_all_city_names()
    words = s.split()
    for n in range(min(4, len(words) - 1), 0, -1):
        tail = " ".join(words[-n:])
        if tail in all_names:
            # Check that a suffix or direction word precedes the city
            preceding = words[-(n + 1)] if len(words) > n else ""
            if preceding in _STREET_SUFFIXES or preceding in _DIRECTIONS:
                # Guard: if preceded by a direction and direction+tail is also
                # a known city (e.g. NORTH+YORK → NORTH YORK), strip both
                if preceding in _DIRECTIONS:
                    extended = preceding + " " + tail
                    if extended in all_names:
                        s = " ".join(words[:-(n + 1)]).strip()
                        break
                s = " ".join(words[:-n]).strip()
                break

    # 5. Strip trailing dash/em-dash remnants
    s = re.sub(r"\s+[-–]\s*$", "", s)

    return s


def _categorize(raw: str, street_number: str, category_hint: str = "") -> str:
    """Assign address category based on content.

    category_hint can be used by the caller to provide context
    (e.g. 'corporate_seller', 'brand') that isn't detectable from
    the address string alone.
    """
    if not raw or not raw.strip():
        return "empty"
    if _PO_BOX_RE.search(raw):
        return "po_box"
    if _LEGAL_RE.search(raw) and not raw[0].isdigit():
        return "legal_description"
    if category_hint:
        return category_hint
    if street_number:
        return "street_address"
    return "no_street_number"


# ── Public entry points ──

def normalize_from_fields(
    address: str,
    city: str,
    province: str = "",
    postal_code: str = "",
    unit: str = "",
    category_hint: str = "",
    raw_coords: Optional[Dict] = None,
) -> Dict:
    """Normalize an address from pre-split fields.

    Use for: Realtrack property addresses, brand scraper records,
    or any source where fields are already separated.

    Args:
        address: street address (e.g. "1476 QUEEN ST W" or "481 Wharncliffe Rd S")
        city: city name (e.g. "Toronto" or "London")
        province: province (e.g. "Ontario" or "ON")
        postal_code: postal code (e.g. "N6J 2N1" or "N6J2N1" or "")
        unit: suite/unit (e.g. "UNITS 8-11" or "")
        category_hint: override category (e.g. "corporate_seller", "brand")
        raw_coords: source coordinates if available, e.g. {"lat": 43.4, "lng": -80.4, "source": "brand_scraper"}

    Returns:
        NormalizedAddress dict with all decomposed fields.
    """
    raw = address.strip()

    # Normalize the street portion, strip overflow, and extract embedded unit
    norm_street = _normalize_street(raw)
    norm_street = _strip_address_overflow(norm_street, city)
    street_clean, embedded_unit, embedded_unit_type = _extract_unit(norm_street)

    # Use explicit unit if provided, otherwise use embedded
    if unit:
        final_unit = _clean(unit)
        final_unit_type = embedded_unit_type  # preserve type from embedded if available
    else:
        final_unit = embedded_unit
        final_unit_type = embedded_unit_type

    # Extract dash-joined unit-number prefix if no unit was found yet.
    # "B7-77 BILLY BISHOP WAY" → unit=B7, street="77 BILLY BISHOP WAY"
    # "2A-5005 SOUTH SERVICE ROAD" → unit=2A, street="5005 SOUTH SERVICE ROAD"
    if not final_unit:
        m = _UNIT_DASH_NUM_RE.match(street_clean)
        if m:
            final_unit = m.group(1)
            final_unit_type = "UNIT"
            street_clean = m.group(2)

    # Strip stray unit keywords from the start of the street.
    # After hash-pattern extraction, "UNIT" can be left at the front.
    street_clean = re.sub(
        r"^(?:UNITS?|SUITE|STE|APT|APARTMENT)\s*,?\s*", "", street_clean
    ).strip()

    # Split unit values that contain a dash-joined street number.
    # "4-45" from "Unit #4-45 Overlea Blvd" → unit=4, prepend 45 to street.
    # Only splits N-NNN where right side is longer (plausible street number).
    if final_unit:
        unit_split = re.match(r"^(\d+[A-Z]?)-(\d{2,}[A-Z]?)$", final_unit)
        if unit_split:
            final_unit = unit_split.group(1)
            street_clean = unit_split.group(2) + " " + street_clean

    # Extract number-dash-ordinal: "67-45TH STREET" → number=67, street="45TH STREET"
    # (not a unit — this is a street number before a numbered street name)
    m_ord = _NUM_DASH_ORDINAL_RE.match(street_clean)
    if m_ord:
        street_clean = m_ord.group(1) + " " + m_ord.group(2)

    # Extract PO Box / mailing box number
    street_clean, po_box = _extract_po_box(street_clean)

    # Extract Rural Route designation
    street_clean, rural_route = _extract_rural_route(street_clean)

    # Extract building name (must run after unit/box/RR extraction)
    street_clean, building_name = _extract_building_name(street_clean)

    # Re-check for unit-code prefix revealed by building name extraction.
    # E.g., "GEORGIAN MALL, B005 - 509 BAYFIELD STREET" → building extracted
    # → street is now "B005 - 509 BAYFIELD STREET" → extract unit B005.
    if building_name and not final_unit:
        m = re.match(
            r"^([A-Z]\d+|[A-Z]+\d+[A-Z]?|\d+[A-Z]|[A-Z]{1,3}-\d+[A-Z]?|[A-Z])[\s-]+(\d+\s+.+)$",
            street_clean,
        )
        if m:
            final_unit = m.group(1)
            final_unit_type = "UNIT"
            street_clean = m.group(2)

    # Number-dash-single-letter: "3828-A BLOOR ST" → "3828A BLOOR ST" (street num suffix)
    street_clean = re.sub(r"^(\d+)-([A-Z])\s", r"\1\2 ", street_clean)
    # Number-dash-word: "3515-HIGHWAY 89" → "3515 HIGHWAY 89" (split num from street)
    street_clean = re.sub(r"^(\d+)-\s*([A-Z]{2,})", r"\1 \2", street_clean)

    # Strip civic hash marker: "#3 HIGHWAY 17" → "3 HIGHWAY 17"
    # Only when hash+digit is at the start and no unit was extracted from it.
    if not final_unit:
        street_clean = re.sub(r"^#(\d)", r"\1", street_clean)

    # Decompose the street into number, name, suffix, direction
    parts = _decompose_street(street_clean)

    # Normalize other fields
    norm_city, city_status = _normalize_city(city) if city else ("", "empty")
    norm_province = _normalize_province(province) if province else ""
    norm_postal = _format_postal_code(postal_code) if postal_code else ""

    # Category
    category = _categorize(raw, parts["street_number"], category_hint)

    # Geographic scope
    scope = _determine_scope(norm_province, city_status, category_hint)

    result: Dict = {
        "raw_address": raw,
        "street_number": parts["street_number"],
        "street_name": parts["street_name"],
        "street_suffix": parts["street_suffix"],
        "street_direction": parts["street_direction"],
        "unit": final_unit,
        "unit_type": final_unit_type,
        "po_box": po_box,
        "rural_route": rural_route,
        "building_name": building_name,
        "normalized_city": norm_city,
        "city_status": city_status,
        "address_scope": scope,
        "category": category,
    }

    # Include non-empty optional fields
    if norm_province:
        result["normalized_province"] = norm_province
    if norm_postal:
        result["normalized_postal_code"] = norm_postal
    if raw_coords:
        result["raw_coords"] = raw_coords

    return result


def normalize_from_string(
    raw: str,
    category_hint: str = "",
) -> Dict:
    """Normalize a comma-separated address string.

    Use for: Realtrack seller/buyer addresses, or any source where
    the address is a single string with city/province/postal embedded.

    Input examples:
        "2457 Strathmore Cres, Mississauga, Ontario, L5M 5K9"
        "55 42nd St, Ste 301, Etobicoke, Ontario"
        "PO Box 1088, Stn Main, Guelph, Ontario, N1H 6N3"
    """
    if not raw or not raw.strip():
        return {
            "raw_address": "",
            "street_number": "",
            "street_name": "",
            "street_suffix": "",
            "street_direction": "",
            "unit": "",
            "unit_type": "",
            "po_box": "",
            "rural_route": "",
            "building_name": "",
            "normalized_city": "",
            "city_status": "empty",
            "address_scope": "unknown",
            "category": "empty",
        }

    text = raw.strip()

    # Strip C/O prefix — "c/o Roycom Realty Ltd., Purdy's Warf Tower 2, ..."
    # The company name after C/O is not part of the address.
    # For comma-separated strings, strip everything up to the first comma after C/O.
    co_match = re.match(r"^C/[O0]\s+[^,]+,\s*", text, re.IGNORECASE)
    if co_match:
        text = text[co_match.end():]

    # Extract postal code (if present)
    postal_code = ""
    pc_match = _POSTAL_RE.search(text.upper())
    if pc_match:
        postal_code = f"{pc_match.group(1)} {pc_match.group(2)}"
        text = text[:pc_match.start()].rstrip(", ")

    # Split on commas
    parts = [p.strip() for p in text.split(",") if p.strip()]

    province = ""
    city = ""
    street_parts = []

    # Walk backwards: province, then city, rest is street
    remaining = list(parts)

    if remaining:
        last_upper = remaining[-1].strip().upper().rstrip(".")
        if last_upper in _ALL_PROVINCE_MAP:
            province = remaining.pop()

    if len(remaining) >= 2:
        city = remaining.pop()
        street_parts = remaining
    elif len(remaining) == 1:
        if province:
            city = remaining[0]
        else:
            street_parts = remaining

    street = ", ".join(street_parts)

    return normalize_from_fields(
        address=street,
        city=city,
        province=province,
        postal_code=postal_code,
        category_hint=category_hint,
    )


def normalize_from_mpac(
    property_address: str,
    municipality: str,
    summary_address: str = "",
    category_hint: str = "",
) -> Dict:
    """Normalize an MPAC-format address from GeoWarehouse.

    Use for: GeoWarehouse records where the address is a flat string
    with municipality embedded (no commas, postal glued on).

    Input examples:
        property_address: "121 CONCESSION ST E TILLSONBURG ON N4G4W4"
        municipality: "TILLSONBURG"

        property_address: "499 NORWICH AVE WOODSTOCK ON N4S9A2"
        municipality: "WOODSTOCK"

    Also handles owner mailing addresses (no municipality hint):
        "12994 KEELE ST SUITE 6 KING CITY ON L7B 1H8"
        "C/O TAX DEPARTMENT 100 CANADIAN PL SCARBOROUGH ON M1R 4Z5"
    """
    addr = (property_address or "").strip().upper()

    # Extract name prefixes: C/O, ATTN, or bare company name before street number.
    # These are returned in _extracted_names so the caller can classify them.
    _extracted_names: list[dict] = []

    # 1) C/O prefix — "C/O GLORIA BAXTER 1016 TALBOT ST ..."
    co_match = _CO_PREFIX_RE.match(addr)
    if co_match:
        co_text = co_match.group(1).strip()
        addr = co_match.group(2).strip()
        # Check for embedded ATTN within the C/O text:
        # "SOBEYS ONTARIO ATTN: JANET STROH" → company + person
        attn_in_co = _ATTN_EMBEDDED_RE.match(co_text)
        if attn_in_co:
            _extracted_names.append({"name": attn_in_co.group(1).strip(), "source": "care_of"})
            _extracted_names.append({"name": attn_in_co.group(2).strip(), "source": "attention"})
        else:
            _extracted_names.append({"name": co_text, "source": "care_of"})

    # 2) ATTN prefix (without C/O) — "ATTN: NATHAN HINES ... 610 EAST RIVER RD ..."
    elif _ATTN_PREFIX_RE.match(addr):
        attn_match = _ATTN_PREFIX_RE.match(addr)
        attn_text = attn_match.group(1).strip()
        addr = attn_match.group(2).strip()
        # ATTN text may also have embedded company: "TSC ATTN: GEOFF BROWN" won't match
        # here because the outer ATTN regex already consumed it. Handle "COMPANY ATTN NAME":
        _extracted_names.append({"name": attn_text, "source": "attention"})

    # 3) Bare company/org prefix — "DGI MANAGEMENT SERVICES 2285 DUNWIN DR ..."
    elif not addr[0:1].isdigit() and not addr.startswith("PO "):
        bare_match = _BARE_PREFIX_RE.match(addr)
        if bare_match:
            prefix = bare_match.group(1).strip()
            # Only capture if it's 2+ words (single word could be street name)
            if len(prefix.split()) >= 2:
                _extracted_names.append({"name": prefix, "source": "prefix"})
                addr = bare_match.group(2).strip()

    # 4) Leading "COMPANY ATTN: NAME 123 STREET" (no C/O)
    #    e.g. "TSC ATTN: GEOFF BROWN 1000 CLARKE RD ..."
    #    or "COSTCO WHOLESALE CANADA LTD ATTN: TREASURY DEPT 415 ..."
    if not _extracted_names:
        # Try ATTN embedded after a company name
        m = re.match(r"^(.+?)\s+ATTN:?\s+(.+?)\s+(\d+\s+.+)$", addr, re.IGNORECASE)
        if m:
            _extracted_names.append({"name": m.group(1).strip(), "source": "prefix"})
            _extracted_names.append({"name": m.group(2).strip(), "source": "attention"})
            addr = m.group(3).strip()
        # Also try "STORE #NNN ... ATTN NAME 123 STREET"
        elif re.match(r"^STORE\s+#", addr):
            m2 = re.match(r"^.+?\s+ATTN:?\s+(.+?)\s+(\d+\s+.+)$", addr, re.IGNORECASE)
            if m2:
                _extracted_names.append({"name": m2.group(1).strip(), "source": "attention"})
                addr = m2.group(2).strip()

    # Fallback to summary_address if property_address is empty
    if not addr and summary_address:
        # Summary is comma-separated: "121 CONCESSION ST E, TILLSONBURG, N4G4W4"
        return _normalize_mpac_summary(summary_address, municipality, category_hint)

    if not addr:
        return normalize_from_fields(
            address="", city=municipality, province="ON",
            category_hint=category_hint,
        )

    # Extract postal code from end
    postal_code = ""
    m = _POSTAL_RE.search(addr)
    if m:
        postal_code = f"{m.group(1)} {m.group(2)}"
        addr = addr[:m.start()].strip()

    # Detect and strip trailing province abbreviation (ON, QC, BC, AB, etc.)
    province = "ON"  # default for GW data
    words = addr.split()
    if words:
        last = words[-1].rstrip(".")
        if last in _ALL_PROVINCE_MAP:
            province = last
            addr = " ".join(words[:-1]).strip()

    # Find municipality in remaining string
    muni = (municipality or "").strip().upper()
    street = addr
    city = municipality or ""

    if muni:
        idx = addr.rfind(muni)
        if idx > 0:
            street = addr[:idx].strip()
    else:
        # No municipality hint — detect city from tail of string
        street, city = _detect_city_from_tail(addr)

        # Fallback for non-Ontario addresses: if city detection failed,
        # split at the last known street suffix/abbreviation.
        # e.g. "106 GUN AV POINTE-CLAIRE" → street="106 GUN AV", city="POINTE-CLAIRE"
        if not city:
            _suffix_words = set(_STREET_TYPE_MAP.keys()) | _STREET_SUFFIXES
            _unit_keywords = {"SUITE", "STE", "UNIT", "APT", "APARTMENT", "FLOOR"}
            addr_words = addr.split()
            for i in range(len(addr_words) - 1, 0, -1):
                if addr_words[i] in _suffix_words and i < len(addr_words) - 1:
                    after = addr_words[i + 1:]
                    # Skip past unit keyword + number if present
                    # e.g. "RD SUITE 200 NEW GLASGOW" → skip "SUITE 200"
                    if after and after[0] in _unit_keywords and len(after) >= 2:
                        after = after[2:]  # skip keyword + unit number
                    if after:
                        street = " ".join(addr_words[:i + 1])
                        city = " ".join(after)
                    break

    # Split out embedded PO BOX from street portion
    # e.g. "571 RICHMOND ST PO BOX 507 STN MAIN" → street="571 RICHMOND ST", po_box="507"
    po_box = ""
    po_match = re.search(r"\bPO\s+BOX\s+(\d+)\b.*$", street)
    if po_match:
        po_box = po_match.group(1)
        street = street[:po_match.start()].strip()

    result = normalize_from_fields(
        address=street,
        city=city,
        province=province,
        postal_code=postal_code,
        category_hint=category_hint,
    )

    # Attach PO Box if extracted from embedded position
    if po_box and not result.get("po_box"):
        result["po_box"] = po_box

    # Attach extracted names from C/O, ATTN, or prefix patterns
    if _extracted_names:
        result["_extracted_names"] = _extracted_names

    return result


def _normalize_mpac_summary(
    summary_address: str,
    municipality: str,
    category_hint: str,
) -> Dict:
    """Parse comma-separated MPAC summary address."""
    parts = [p.strip() for p in summary_address.split(",")]
    street = parts[0] if parts else ""
    city = parts[1].strip() if len(parts) >= 2 else municipality or ""
    postal_code = ""

    if len(parts) >= 3:
        last = parts[-1].strip().upper()
        m = _POSTAL_RE.search(last)
        if m:
            postal_code = f"{m.group(1)} {m.group(2)}"
        elif re.match(r"^[A-Z]\d[A-Z]\d[A-Z]\d$", last):
            postal_code = f"{last[:3]} {last[3:]}"

    return normalize_from_fields(
        address=street,
        city=city,
        province="ON",
        postal_code=postal_code,
        category_hint=category_hint,
    )


# ── Convenience functions ──

def normalized_full_street(result: Dict) -> str:
    """Reconstruct the full normalized street from decomposed fields.

    e.g. "1476 QUEEN STREET WEST" from {street_number: "1476",
    street_name: "QUEEN", street_suffix: "STREET", street_direction: "WEST"}
    """
    parts = []
    if result.get("street_number"):
        parts.append(result["street_number"])
    if result.get("street_name"):
        parts.append(result["street_name"])
    if result.get("street_suffix"):
        parts.append(result["street_suffix"])
    if result.get("street_direction"):
        parts.append(result["street_direction"])
    return " ".join(parts)


def normalized_dedup_key(result: Dict) -> str:
    """Build a dedup key from normalized components.

    Format: "STREET_NUMBER STREET_NAME STREET_SUFFIX STREET_DIRECTION|CITY"
    """
    street = normalized_full_street(result)
    city = result.get("normalized_city", "")
    return f"{street}|{city}"
