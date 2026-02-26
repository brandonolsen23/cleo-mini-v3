"""Shared address and city normalization for property dedup.

Provides canonical normalization functions used by both the property
registry (dedup) and the markets builder (city alias resolution).
"""

import re


# Saint names commonly found in Ontario street names.
# Used to disambiguate "ST" (Saint) from "ST" (Street).
_SAINT_NAMES: set[str] = {
    "CLAIR", "PAUL", "GEORGE", "ANDREW", "DAVID", "LAWRENCE", "THOMAS",
    "JOSEPH", "JAMES", "JOHN", "MICHAEL", "PETER", "PATRICK", "CATHERINE",
    "ANNE", "MARY", "CHARLES", "LAURENT", "DENIS", "HYACINTHE", "ALPHONSE",
}

# Pre-compiled pattern: "ST" or "STE" followed by a known saint name.
# Must run BEFORE the general abbreviation expansion.
_SAINT_PATTERN = re.compile(
    r"\bSTE?\s+(" + "|".join(sorted(_SAINT_NAMES, key=len, reverse=True)) + r")\b"
)

# Street type abbreviations → canonical long form.
# Order matters: longer abbreviations checked first to avoid partial matches.
_STREET_TYPE_MAP: dict[str, str] = {
    "BLVD": "BOULEVARD",
    "PKWY": "PARKWAY",
    "CRES": "CRESCENT",
    "TERR": "TERRACE",
    "AVE": "AVENUE",
    "CRT": "COURT",
    "HWY": "HIGHWAY",
    "CIR": "CIRCLE",
    "CT": "COURT",
    "DR": "DRIVE",
    "LN": "LANE",
    "PL": "PLACE",
    "RD": "ROAD",
    "ST": "STREET",
}

# Directional abbreviations → canonical long form.
_DIRECTION_MAP: dict[str, str] = {
    "E": "EAST",
    "W": "WEST",
    "N": "NORTH",
    "S": "SOUTH",
    "NE": "NORTHEAST",
    "NW": "NORTHWEST",
    "SE": "SOUTHEAST",
    "SW": "SOUTHWEST",
}

# Combined abbreviation map for single-pass replacement.
_ALL_ABBREVS: dict[str, str] = {**_STREET_TYPE_MAP, **_DIRECTION_MAP}

# Pre-compiled pattern: match abbreviations as whole words.
# Sort by length descending so "BLVD" matches before "BL" etc.
_ABBREV_PATTERN = re.compile(
    r"\b(" + "|".join(sorted(_ALL_ABBREVS, key=len, reverse=True)) + r")\b"
)


# Community → municipality aliases.  Single source of truth — imported by
# both registry.py (dedup) and scripts/build_markets.py (market lookup).
CITY_ALIASES: dict[str, str] = {
    # Abbreviation variants
    "Sault Ste Marie": "Sault Ste. Marie",
    "St Catharines": "St. Catharines",
    "N. York": "Toronto",
    "North York": "Toronto",
    "E. York": "Toronto",
    "East York": "Toronto",
    "Scarborough": "Toronto",
    "Etobicoke": "Toronto",
    "York": "Toronto",
    "Downsview": "Toronto",
    "Willowdale": "Toronto",
    "Don Mills": "Toronto",
    "Agincourt": "Toronto",
    "Weston": "Toronto",
    "Rexdale": "Toronto",
    "Leaside": "Toronto",
    "Woodbridge": "Vaughan",
    "Maple": "Vaughan",
    "Concord": "Vaughan",
    "Kleinburg": "Vaughan",
    "Thornhill": "Vaughan",
    "Unionville": "Markham",
    "Stouffville": "Whitchurch-Stouffville",
    "N. Bay": "North Bay",
    "N Bay": "North Bay",
    "Niagara On The Lake": "Niagara-on-the-Lake",
    "Niagara on the Lake": "Niagara-on-the-Lake",
    "NOTL": "Niagara-on-the-Lake",
    "Quinte W": "Quinte West",
    "The Blue Mountains": "Collingwood",
    "Blue Mountains": "Collingwood",
    "Sault Ste. Marie": "Sault Ste. Marie",
    "Sudbury": "Greater Sudbury",
    "Chatham": "Chatham-Kent",
    "Kent": "Chatham-Kent",
    "Bowmanville": "Clarington",
    "Newcastle": "Clarington",
    "Courtice": "Clarington",
    "Alliston": "New Tecumseth",
    "Tottenham": "New Tecumseth",
    "Beeton": "New Tecumseth",
    "Simcoe": "Norfolk County",
    "Cayuga": "Haldimand County",
    "Dunnville": "Haldimand County",
    "Caledonia": "Haldimand County",
    "Picton": "Prince Edward County",
    "Fergus": "Centre Wellington",
    "Elora": "Centre Wellington",
    "Elmira": "Woolwich",
    "Stayner": "Clearview",
    "Keswick": "Georgina",
    "Sutton": "Georgina",
    "Erin Mills": "Mississauga",
    "Port Credit": "Mississauga",
    "Streetsville": "Mississauga",
    # Hyphenated Toronto variants
    "Toronto-North York": "Toronto",
    "Toronto-Etobicoke": "Toronto",
    "Toronto-Scarborough": "Toronto",
    "Toronto-East York": "Toronto",
    "Toronto-York": "Toronto",
    # Ottawa area
    "Vanier": "Ottawa",
    "Rockcliffe Park": "Ottawa",
    "Bells Corners": "Ottawa",
    # Niagara communities → municipalities
    "Fonthill": "Pelham",
    "Fenwick": "Pelham",
    "Vineland": "Lincoln",
    "Beamsville": "Lincoln",
    "Jordan": "Lincoln",
    "Crystal Beach": "Fort Erie",
    "Ridgeway": "Fort Erie",
    "Stevensville": "Fort Erie",
    "Port Dalhousie": "St. Catharines",
    "Virgil": "Niagara-on-the-Lake",
    # Halton / Peel communities
    "Georgetown": "Halton Hills",
    "Acton": "Halton Hills",
    "Bolton": "Caledon",
    # Durham communities
    "Port Perry": "Scugog",
    "Cannington": "Brock",
    "Sunderland": "Brock",
    "Beaverton": "Brock",
    # Simcoe communities
    "Cookstown": "Innisfil",
    "Angus": "Essa",
    "Midhurst": "Springwater",
    "Coldwater": "Severn",
    "Orillia": "Orillia",
    # Other
    "Oro": "Oro-Medonte",
    "N. Perth": "North Perth",
    "N. Dumfries": "North Dumfries",
    "W. Nipissing": "West Nipissing",
    "Greater Napanee": "Napanee",
    "Smith": "Selwyn",
    "Smiths Falls": "Smiths Falls",
    # Abbreviation/alternate forms found in data
    "St Thomas": "St. Thomas",
    "St. Thomas": "St. Thomas",
    "Prince Edward": "Prince Edward County",
    "Trenton": "Quinte West",
    "Clarence-Rockland": "Clarence-Rockland",
    "Perth E": "Perth East",
    "E. Gwillimbury": "East Gwillimbury",
    "Stittsville": "Ottawa",
    "Waterdown": "Hamilton",
    "Amherstview": "Loyalist",
    "Ottawa-Nepean": "Ottawa",
    "Temiskaming Shores": "Temiskaming Shores",
    "Westport": "Rideau Lakes",
    "New Liskeard": "Temiskaming Shores",
    # Perth County communities → lower-tier municipalities
    "Listowel": "North Perth",
    "Mitchell": "West Perth",
    "Milverton": "Perth East",
    "Atwood": "North Perth",
    "Monkton": "North Perth",
    "Millbank": "Perth East",
    "Rostock": "Perth East",
    # Ottawa amalgamated communities (2001)
    "Nepean": "Ottawa",
    "Gloucester": "Ottawa",
    "Kanata": "Ottawa",
    "Barrhaven": "Ottawa",
    "Orléans": "Ottawa",
    "Orleans": "Ottawa",
    "Manotick": "Ottawa",
    "Richmond": "Ottawa",
    "Carp": "Ottawa",
    "Greely": "Ottawa",
    "Osgoode": "Ottawa",
    "Navan": "Ottawa",
    # Hamilton amalgamated communities (2001)
    "Stoney Creek": "Hamilton",
    "Dundas": "Hamilton",
    "Ancaster": "Hamilton",
    "Flamborough": "Hamilton",
    "Glanbrook": "Hamilton",
    "Binbrook": "Hamilton",
    # Brampton/Mississauga communities
    "Bramalea": "Brampton",
    "Malton": "Mississauga",
    "Cooksville": "Mississauga",
    "Clarkson": "Mississauga",
    "Lorne Park": "Mississauga",
    # Welland / Niagara Falls communities
    "Crowland": "Welland",
    "Chippawa": "Niagara Falls",
    # Barrie / Innisfil
    "Alcona": "Innisfil",
    "Lefroy": "Innisfil",
    # Whitby / Oshawa communities
    "Brooklin": "Whitby",
    # Common abbreviations/typos
    "S.S. Marie": "Sault Ste. Marie",
    "S.S.Marie": "Sault Ste. Marie",
}

# Build uppercase lookup for fast matching.
_CITY_ALIAS_UPPER: dict[str, str] = {k.upper(): v for k, v in CITY_ALIASES.items()}


def normalize_address_for_dedup(address: str) -> str:
    """Normalize an address for dedup matching.

    - Uppercase
    - Strip periods (Rd. → RD → ROAD)
    - Expand "ST/STE <saint name>" → "SAINT <name>" before general expansion
    - Expand abbreviations to long form (ST → STREET, HWY → HIGHWAY, etc.)
    - Collapse whitespace
    """
    s = address.upper().strip()
    # Replace period immediately followed by a letter with a space ("Ave.North" → "Ave North")
    # so it doesn't get concatenated into "AVENORTH" when periods are stripped.
    s = re.sub(r"\.(?=[A-Z])", " ", s)
    s = s.replace(".", "")
    s = re.sub(r"\s+", " ", s)
    # Protect saint names before ST → STREET expansion
    s = _SAINT_PATTERN.sub(lambda m: f"SAINT {m.group(1)}", s)
    s = _ABBREV_PATTERN.sub(lambda m: _ALL_ABBREVS[m.group(1)], s)
    return s


def normalize_city_for_dedup(city: str) -> str:
    """Normalize a city name for dedup matching.

    - Uppercase + strip
    - Apply community → municipality alias table
    - Collapse whitespace
    """
    s = city.strip()
    s = re.sub(r"\s+", " ", s)
    # Check alias table (case-insensitive)
    canonical = _CITY_ALIAS_UPPER.get(s.upper())
    if canonical:
        return canonical.upper()
    return s.upper()


def make_dedup_key(address: str, city: str) -> str:
    """Create a dedup key from normalized address + city."""
    return f"{normalize_address_for_dedup(address)}|{normalize_city_for_dedup(city)}"


# Strips trailing cardinal directionals from a normalized address.
_TRAILING_DIRECTIONAL = re.compile(
    r"\s+(NORTH|SOUTH|EAST|WEST|NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST)$"
)


def make_loose_dedup_key(address: str, city: str) -> str:
    """Dedup key with any trailing directional stripped from the address part.

    Used as a secondary merge key to handle brand/POI data that omits trailing
    directionals (e.g. '975 WALLACE AVE' vs '975 WALLACE AVE N').
    A loose match is accepted only when exactly one side has a trailing
    directional — see registry.py for how this is applied.
    """
    addr_norm = normalize_address_for_dedup(address)
    city_norm = normalize_city_for_dedup(city)
    addr_loose = _TRAILING_DIRECTIONAL.sub("", addr_norm).rstrip()
    return f"{addr_loose}|{city_norm}"
