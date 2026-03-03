"""Shared address and city normalization for property dedup.

Provides canonical normalization functions used by both the property
registry (dedup) and the markets builder (city alias resolution).
"""

import re


# Saint names commonly found in Ontario street names.
# Used to disambiguate "ST" (Saint) from "ST" (Street).
_SAINT_NAMES: set[str] = {
    "CLAIR", "PAUL", "GEORGE", "ANDREW", "DAVID", "LAWRENCE", "THOMAS",
    "JOSEPH", "JAMES", "JOHN", "MICHAEL", "MIKE", "PETER", "PATRICK",
    "CATHERINE", "CATHARINE",  # St. Catharines, ON
    "ANNE", "MARY", "MARIE", "CHARLES", "LAURENT", "DENIS", "HYACINTHE",
    "ALPHONSE",
}

# Pre-compiled pattern: "ST" or "STE" followed by a known saint name
# (with optional possessive/plural trailing S, e.g. "ST PAULS", "ST CATHARINES").
# Must run BEFORE the general abbreviation expansion.
_SAINT_PATTERN = re.compile(
    r"\bSTE?\s+((?:" + "|".join(sorted(_SAINT_NAMES, key=len, reverse=True)) + r")S?)\b"
)

# Street type abbreviations → canonical long form.
# Order matters: longer abbreviations checked first to avoid partial matches.
_STREET_TYPE_MAP: dict[str, str] = {
    "BLVD": "BOULEVARD",
    "BOUL": "BOULEVARD",   # French: boulevard
    "PKWY": "PARKWAY",
    "PKY": "PARKWAY",      # GW/MPAC abbreviation
    "CRES": "CRESCENT",
    "TERR": "TERRACE",
    "AV": "AVENUE",
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
    "Niagara On The Lake": "Niagara-on-the-Lake",
    "Niagara on the Lake": "Niagara-on-the-Lake",
    "NOTL": "Niagara-on-the-Lake",
    "Blue Mountains": "The Blue Mountains",
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
    # Other
    "Oro": "Oro-Medonte",
    "Napanee": "Greater Napanee",
    "Smith": "Selwyn",
    # Abbreviation/alternate forms found in data
    "St Thomas": "St. Thomas",
    "Prince Edward": "Prince Edward County",
    "Trenton": "Quinte West",
    "Stittsville": "Ottawa",
    "Waterdown": "Hamilton",
    "Amherstview": "Loyalist",
    "Ottawa-Nepean": "Ottawa",
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
    # Community → official municipality (missing from earlier)
    "Bradford": "Bradford West Gwillimbury",
    "Walkerton": "Brockton",
    "Port Elgin": "Saugeen Shores",
    "Southampton": "Saugeen Shores",
    "Strathroy": "Strathroy-Caradoc",
    "Smithville": "West Lincoln",
    "Waterford": "Norfolk County",
    "Delhi": "Norfolk County",
    "Port Dover": "Norfolk County",
    "Port Rowan": "Norfolk County",
    "Hagersville": "Haldimand County",
    "Jarvis": "Haldimand County",
    "Campbellford": "Trent Hills",
    "Ayr": "North Dumfries",
    "New Hamburg": "Wilmot",
    "Baden": "Wilmot",
    "St. Jacobs": "Woolwich",
    "St Jacobs": "Woolwich",
    "Tavistock": "East Zorra-Tavistock",
    "Dorchester": "Thames Centre",
    "Komoka": "Middlesex Centre",
    "Ilderton": "Middlesex Centre",
    "Harriston": "Minto",
    "Palmerston": "Minto",
    "Mount Forest": "Wellington North",
    "Arthur": "Wellington North",
    "Drayton": "Mapleton",
    "Wiarton": "South Bruce Peninsula",
    "Penetang": "Penetanguishene",
    "Glencoe": "Southwest Middlesex",
    "Lindsay": "Kawartha Lakes",
    "Paris": "Brant",
    "Bobcaygeon": "Kawartha Lakes",
    "Fenelon Falls": "Kawartha Lakes",
    "Coboconk": "Kawartha Lakes",
    "Omemee": "Kawartha Lakes",
    "Minden": "Minden Hills",
    "Haliburton": "Dysart et al",
    # Ottawa amalgamated (additional)
    "Cumberland": "Ottawa",
    "Goulbourn": "Ottawa",
    "W. Carleton": "Ottawa",
    "West Carleton": "Ottawa",
    "Rideau": "Ottawa",
    # Realtrack directional abbreviations
    "N. Bay": "North Bay",
    "N Bay": "North Bay",
    "N. Perth": "North Perth",
    "N. Dumfries": "North Dumfries",
    "N. Huron": "North Huron",
    "N. Dorchester": "North Middlesex",
    "N. Kawartha": "North Kawartha",
    "N. Monaghan": "Otonabee-South Monaghan",
    "N. Frontenac": "North Frontenac",
    "N. Middlesex": "North Middlesex",
    "E. Gwillimbury": "East Gwillimbury",
    "E. Zorra-Tavistock": "East Zorra-Tavistock",
    "W. Nipissing": "West Nipissing",
    "W. Perth": "West Perth",
    "W. Elgin": "West Elgin",
    "W. Lincoln": "West Lincoln",
    "W. Grey": "West Grey",
    "S. Monaghan": "Otonabee-South Monaghan",
    "S. Dumfries": "North Dumfries",
    "S. Huron": "South Huron",
    "S. Stormont": "South Stormont",
    "S. Frontenac": "South Frontenac",
    "S. Dundas": "South Dundas",
    "S. Glengarry": "South Glengarry",
    "S. Bruce": "South Bruce",
    "SW Middlesex": "Southwest Middlesex",
    "SW Oxford": "South-West Oxford",
    "Quinte W": "Quinte West",
    "Perth E": "Perth East",
    "Perth S": "Perth South",
    "Wellington N": "Wellington North",
    "Huron E": "Huron East",
    "Huron E.": "Huron East",
    # St. variants
    "St Marys": "St. Marys",
    "St. Mary's": "St. Marys",
    "St Mary's": "St. Marys",
    "SSM": "Sault Ste. Marie",
    "Sault Ste Marie": "Sault Ste. Marie",
    # Pre-amalgamation township / community names found in RT data
    "Eramosa": "Guelph-Eramosa",
    "Adjala": "Adjala-Tosorontio",
    "Marmora": "Marmora and Lake",
    "Almonte": "Mississippi Mills",
    "Grand Bend": "Lambton Shores",
    "Dysart": "Dysart et al",
    "Lakefield": "Selwyn",
    "Lucan": "Lucan Biddulph",
    "Exeter": "South Huron",
    "Forest": "Lambton Shores",
    "Oakland": "Brant",
    "Cavan-Monaghan": "Cavan Monaghan",
    "Caradoc": "Strathroy-Caradoc",
    "Townsend": "Norfolk County",
    "Havelock": "Havelock-Belmont-Methuen",
    "Colborne": "Cramahe",
    "Elgin-Rideau Lakes": "Rideau Lakes",
    "Ashfield": "Ashfield-Colborne-Wawanosh",
    "Middleton": "Norfolk County",
    "Spencerville": "Edwardsburgh/Cardinal",
    "Portland": "Rideau Lakes",
    "Embrun": "Russell",
    "Elderslie": "Arran Elderslie",
    "Stirling": "Stirling-Rawdon",
    "Norwood": "Asphodel-Norwood",
    "Raglan": "Oshawa",
    "Plympton": "Plympton-Wyoming",
    "Brooke": "Brooke-Alvinston",
    "Timiskaming": "Temiskaming Shores",
    "Eganville": "Bonnechere Valley",
    "Limoges": "The Nation",
    "Gilmour": "Tudor and Cashel",
    "St Isidore": "The Nation",
    "Ekfrid": "Southwest Middlesex",
    "Mallorytown": "Front of Yonge",
    "Alnwick": "Alnwick/Haldimand",
    "Madawaska": "Madawaska Valley",
    "Barrys Bay": "Madawaska Valley",
    "Barry's Bay": "Madawaska Valley",
    "Whitewater": "Whitewater Region",
    "Burford": "Brant",
    "Bosanquet": "Lambton Shores",
    "Port Carling": "Muskoka Lakes",
    "Charlotteville": "Norfolk County",
    "Hallowell": "Prince Edward County",
    "Lobo": "Middlesex Centre",
    "The Nation Municipality": "The Nation",
    "Alfred & Plantagenet": "Alfred and Plantagenet",
    "Killaloe": "Killaloe Hagarty and Richards",
    "Glencoe Village": "Southwest Middlesex",
    "Tobermory": "Northern Bruce Peninsula",
    "Alexandria": "North Glengarry",
    "Haldimand": "Haldimand County",
    "Hastings": "Trent Hills",
    "Dutton-Dunwich": "Dutton/Dunwich",
    # ── Brand scraper city aliases (Feb 2026) ──
    # Sudbury region communities
    "Chelmsford": "Greater Sudbury",
    "Val Caron": "Greater Sudbury",
    "Hanmer": "Greater Sudbury",
    "Capreol": "Greater Sudbury",
    "Garson": "Greater Sudbury",
    "Lively": "Greater Sudbury",
    "Dowling": "Greater Sudbury",
    "Azilda": "Greater Sudbury",
    "Coniston": "Greater Sudbury",
    # Chatham-Kent communities
    "Wallaceburg": "Chatham-Kent",
    "Tilbury": "Chatham-Kent",
    "Blenheim": "Chatham-Kent",
    "Dresden": "Chatham-Kent",
    "Ridgetown": "Chatham-Kent",
    "Thamesville": "Chatham-Kent",
    # Eastern Ontario communities
    "Kemptville": "North Grenville",
    "Morrisburg": "South Dundas",
    "Winchester": "North Dundas",
    "Ingleside": "South Stormont",
    "Long Sault": "South Stormont",
    "Lancaster": "South Glengarry",
    "Alfred": "Alfred and Plantagenet",
    # Ottawa/prescott-russell area
    "Rockland": "Clarence-Rockland",
    "Ottawa-Orleans": "Ottawa",
    "Ottawa-Kanata": "Ottawa",
    # York Region communities
    "King City": "King",
    "Nobleton": "King",
    "Schomberg": "King",
    "Sharon": "East Gwillimbury",
    "Sutton West": "Georgina",
    "Mount Hope": "Hamilton",
    # Simcoe County / Georgian Bay
    "Elmvale": "Springwater",
    "Thornbury": "The Blue Mountains",
    "Brechin": "Ramara",
    "Waubaushene": "Tay",
    "Port Severn": "Severn",
    "Victoria Harbour": "Tay",
    # Huron/Perth/Middlesex communities
    "Wingham": "North Huron",
    "Seaforth": "Huron East",
    "Clinton": "Central Huron",
    "Bayfield": "Bluewater",
    "Parkhill": "North Middlesex",
    "Wyoming": "Plympton-Wyoming",
    "Watford": "Warwick",
    # Lambton/Sarnia area
    "Corunna": "St. Clair",
    "Belle River": "Lakeshore",
    # Other communities
    "Sturgeon Falls": "West Nipissing",
    "Little Current": "Northeastern Manitoulin and the Islands",
    "Dutton": "Dutton/Dunwich",
    "West Lorne": "West Elgin",
    "Odessa": "Loyalist",
    "Burks Falls": "Armour",
    "Smith Falls": "Smiths Falls",
    "Dundalk": "Southgate",
    "Cobden": "Whitewater Region",
    "Markdale": "Grey Highlands",
    "South Porcupine": "Timmins",
    "Geraldton": "Greenstone",
    "Port Stanley": "Central Elgin",
    "Belmont": "Malahide",
    "Sydenham": "South Frontenac",
    "Durham": "West Grey",
    "Mildmay": "South Bruce",
    "Lucknow": "Huron-Kinloss",
    "Frankford": "Quinte West",
    "Wellington": "Prince Edward County",
    "Millbrook": "Cavan Monaghan",
    "Sauble Beach": "South Bruce Peninsula",
    "Bridgenorth": "Smith-Ennismore-Lakefield",
    "Harrow": "Essex",
    "Hannon": "Hamilton",
    # Toronto sub-areas from Pizza Pizza
    "Toronto - Scarborough": "Toronto",
    "Toronto - North York": "Toronto",
    "Toronto - Etobicoke": "Toronto",
    "Toronto - Thornhill": "Vaughan",
    # More small communities
    "Verona": "South Frontenac",
    "Vankleek Hill": "Champlain",
    "Northbrook": "Addington Highlands",
    "Wilberforce": "Highlands East",
    "McKeRrow": "Baldwin",
    "Mount Brydges": "Strathroy-Caradoc",
    "Rodney": "West Elgin",
    "Hornby": "Halton Hills",
    "Gormley": "Whitchurch-Stouffville",
    "Iroquois": "South Dundas",
    "Bothwell": "Chatham-Kent",
    "Drumbo": "Blandford-Blenheim",
    "Sharbot Lake": "Central Frontenac",
    "Noelville": "French River",
    "Dorset": "Algonquin Highlands",
    "Rama": "Ramara",
    "Brussels": "Huron East",
    "Mount Albert": "East Gwillimbury",
    "Thornton": "Essa",
    "South Lancaster": "South Glengarry",
    "Thamesford": "Zorra",
    "Mactier": "Georgian Bay",
    "Porcupine": "Timmins",
    "Flesherton": "Grey Highlands",
    "Brights Grove": "St. Clair",
    "Creemore": "Clearview",
    "Comber": "Lakeshore",
    "Onaping": "Greater Sudbury",
    "Buckhorn": "Trent Lakes",
    "Orono": "Clarington",
    "Maidstone": "Lakeshore",
    "Matheson": "Black River-Matheson",
    "Lanark": "Lanark Highlands",
    "Inglewood": "Caledon",
    "Apsley": "North Kawartha",
    "Pefferlaw": "Georgina",
    "Oak Ridges": "Richmond Hill",
    "Kinmount": "Kawartha Lakes",
    "Baysville": "Lake of Bays",
    "Lions Head": "Northern Bruce Peninsula",
    "Port Burwell": "Bayham",
    "Kaladar": "Addington Highlands",
    "Monkland": "North Stormont",
    "Spragge": "The North Shore",
    # Toronto sub-areas
    "Toronto - East York": "Toronto",
    "Gloucester - Ottawa": "Ottawa",
    # Typos and variants
    "St. Catherines": "St. Catharines",
    "St-Catharines": "St. Catharines",
    "Catharines": "St. Catharines",
    "Smiths Fall": "Smiths Falls",
    "Smith Falls": "Smiths Falls",
    "Sault Sainte Marie": "Sault Ste. Marie",
    "Niagara On Lake": "Niagara-on-the-Lake",
    "Niagara On The Lake": "Niagara-on-the-Lake",
    "Brooklynn": "Whitby",
    "Orleans": "Ottawa",
    "Orléans": "Ottawa",
    "Etobicoke": "Toronto",
    "Shannonville": "Tyendinaga",
    "Delta": "Rideau Lakes",
    "Dunvegan": "North Glengarry",
    "Courtright": "St. Clair",
    "Dwight": "Lake of Bays",
    "St. George": "Brant",
    "Borden": "Essa",
    "Mindemoya": "Central Manitoulin",
    "Melbourne": "Strathroy-Caradoc",
    "Kingston Centre": "Kingston",
    "Toronto Islands": "Toronto",
    "Vermilion Bay": "Machin",
    # ── Small communities missing from alias table (Feb 2026 audit) ──
    "Ailsa Craig": "North Middlesex",
    "Bala": "Muskoka Lakes",
    "Bloomfield": "Prince Edward County",
    "Chalk River": "Laurentian Hills",
    "Lambeth": "London",
    "Paisley": "Arran-Elderslie",
    "Washago": "Severn",
    "Zurich": "Bluewater",
    "Ennismore": "Selwyn",
    "Alvinston": "Brooke-Alvinston",
    "Oldcastle": "Tecumseh",
    "Ridgeville": "Pelham",
    "Gorrie": "Howick",
    "Valley East": "Greater Sudbury",
    # ── Brand scraper misspellings (Feb 2026 audit) ──
    "Etiboicoke": "Toronto",
    "Etobiocke": "Toronto",
    "Glouester": "Ottawa",
    "Hunstville": "Huntsville",
    "Missassauga": "Mississauga",
    "Orilla": "Orillia",
    "Owne Sound": "Owen Sound",
    "Oronto": "Toronto",
    "Carelton Place": "Carleton Place",
    "Whitchurch-Stouffvile": "Whitchurch-Stouffville",
    "ThunderBay": "Thunder Bay",
    "Thunderbay": "Thunder Bay",
    "Sault St Marie": "Sault Ste. Marie",
    "Peterbrough": "Peterborough",
    # ── Brand scraper compound/qualified city names ──
    "Brampton-Bramalea": "Brampton",
    "Cambridge-Preston": "Cambridge",
    "Fort Erie-Ridgeway": "Fort Erie",
    "Windsor East": "Windsor",
    "Guelph North": "Guelph",
    "OAK RIDGES/RICHMOND HILL": "Richmond Hill",
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
