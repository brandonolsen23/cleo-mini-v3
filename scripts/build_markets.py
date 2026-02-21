#!/usr/bin/env python3
"""Build data/markets.json from Wikipedia's List of population centres in Ontario.

Fetches wikitext via the Wikipedia API, parses city names and 2021 Census
populations, and writes a static lookup file.

Usage:
    python scripts/build_markets.py
"""

import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

# Add project root to path so we can import cleo modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cleo.properties.normalize import CITY_ALIASES

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MARKETS_PATH = DATA_DIR / "markets.json"

WIKI_API = (
    "https://en.wikipedia.org/w/api.php"
    "?action=parse"
    "&page=List_of_population_centres_in_Ontario"
    "&prop=wikitext"
    "&format=json"
    "&section=1"
)


def fetch_wikitext() -> str:
    req = Request(WIKI_API, headers={"User-Agent": "CleoCLI/1.0"})
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["parse"]["wikitext"]["*"]


def parse_entries(wikitext: str) -> list[tuple[str, int, list[str]]]:
    """Parse wikitext table rows into (full_name, population, [individual_cities])."""
    rows = wikitext.split("|-")
    entries = []
    for row in rows:
        # Find all [[City, Ontario|City]] links in the row
        all_names = re.findall(
            r"\[\[([^|\]]*?)(?:,\s*(?:Ontario|Quebec))?\|([^\]]+)\]\]", row
        )
        if not all_names:
            all_names = re.findall(
                r"\[\[([^|\]]*?)(?:,\s*(?:Ontario|Quebec))?\]\]", row
            )
            all_names = [(link, link.split(",")[0].strip()) for link in all_names]
        else:
            all_names = [(link, display) for link, display in all_names]

        if not all_names:
            continue

        # Extract 2021 population from {{change|POP2021|POP2016|...}}
        pop_match = re.search(r"\{\{change\|(\d+)\|(\d+)", row)
        if not pop_match:
            continue
        pop_2021 = int(pop_match.group(1))

        names = [display.strip() for _, display in all_names]
        full_name = " - ".join(names)
        entries.append((full_name, pop_2021, names))

    return entries


def build_markets(entries: list[tuple[str, int, list[str]]]) -> dict[str, dict]:
    """Build city -> {population} mapping.

    For multi-city entries like "St. Catharines - Niagara Falls", both individual
    cities get the combined population (useful for sorting by market size).
    """
    markets: dict[str, dict] = {}

    for full_name, pop, city_parts in entries:
        # Always store the combined name
        markets[full_name] = {"population": pop}

        # Also store each individual city name
        for city in city_parts:
            city = city.strip()
            if city and city != full_name:
                # Don't overwrite with a smaller combined pop
                if city not in markets or markets[city]["population"] < pop:
                    markets[city] = {"population": pop}

    return markets


# Supplemental municipality populations (Census 2021 / WPR 2026 estimates).
# These are Ontario municipalities that appear in our property data but are not
# individual "population centres" in the Wikipedia list.  Sources: Statistics
# Canada Census 2021 and worldpopulationreview.com.
SUPPLEMENTAL: dict[str, int] = {
    # GTA municipalities (separate from Toronto pop centre)
    "Mississauga": 717_961,
    "Brampton": 656_480,
    "Markham": 338_503,
    "Vaughan": 323_103,
    "Oakville": 213_759,
    "Richmond Hill": 202_022,
    "Burlington": 186_948,
    "Whitby": 138_501,
    "Ajax": 126_666,
    "Pickering": 99_186,
    "Newmarket": 87_942,
    "Aurora": 62_057,
    "Clarington": 101_427,
    "Halton Hills": 61_161,
    "Whitchurch-Stouffville": 49_864,
    "Georgina": 47_642,
    "Caledon": 76_581,
    "Milton": 132_979,
    "East Gwillimbury": 34_637,
    "Bradford West Gwillimbury": 42_880,
    "King": 27_333,
    "Uxbridge": 21_556,
    "Scugog": 21_581,
    # Waterloo Region
    "Cambridge": 138_479,
    "Waterloo": 121_436,
    # Other large municipalities
    "Greater Sudbury": 166_004,
    "Chatham-Kent": 104_316,
    "Kawartha Lakes": 78_424,
    "Brant": 39_556,
    "Norfolk County": 67_490,
    "Haldimand County": 49_139,
    "Prince Edward County": 25_704,
    "New Tecumseth": 44_194,
    # Hamilton amalgamated areas
    "Stoney Creek": 73_000,
    "Ancaster": 40_000,
    "Flamborough": 39_000,
    "Dundas": 26_000,
    "Glanbrook": 29_000,
    # Ottawa amalgamated areas
    "Nepean": 160_000,
    "Gloucester": 120_000,
    "Cumberland": 55_000,
    "Goulbourn": 30_000,
    "Kanata": 120_000,
    "Orleans": 110_000,
    # Windsor area
    "Tecumseh": 23_610,
    "LaSalle": 32_721,
    "Lakeshore": 39_816,
    "Amherstburg": 23_350,
    "Kingsville": 22_076,
    "Leamington": 29_682,
    "Essex": 20_427,
    # Niagara Region
    "Grimsby": 28_883,
    "Niagara-on-the-Lake": 19_088,
    "Lincoln": 25_857,
    "Thorold": 23_816,
    "Fort Erie": 32_311,
    "Wainfleet": 6_732,
    "West Lincoln": 15_174,
    "Port Colborne": 19_750,
    "Pelham": 18_192,
    # Other
    "Quinte West": 46_560,
    "Innisfil": 42_888,
    "Wasaga Beach": 24_001,
    "Centre Wellington": 30_753,
    "Woolwich": 27_882,
    "Clearview": 14_651,
    "Springwater": 20_032,
    "Oro-Medonte": 22_657,
    "Essa": 22_252,
    "Severn": 14_516,
    "Tay": 11_077,
    "Ramara": 10_285,
    "Tiny": 12_429,
    # More municipalities from our data
    "Mono": 10_473,
    "North Perth": 13_130,
    "North Dumfries": 11_415,
    "Wilmot": 21_429,
    "Bancroft": 4_026,
    "Penetanguishene": 9_354,
    "West Nipissing": 14_364,
    "Middlesex Centre": 18_858,
    "Selwyn": 18_657,
    "Napanee": 15_892,
    "Wellesley": 11_260,
    "East Zorra-Tavistock": 7_662,
    "North Grenville": 17_948,
    "Brock": 12_567,
    # Additional municipalities from GW/RT data gaps
    "Clarence-Rockland": 24_512,
    "Perth East": 12_658,
    "Loyalist": 17_008,
    "Temiskaming Shores": 9_920,
    "Rideau Lakes": 10_207,
    "St. Thomas": 45_732,
}

# CITY_ALIASES imported from cleo.properties.normalize (single source of truth).
# Previously maintained as a local ALIASES dict here.


def apply_supplemental(markets: dict[str, dict]) -> dict[str, dict]:
    """Add supplemental municipality populations (don't overwrite existing)."""
    for city, pop in SUPPLEMENTAL.items():
        if city not in markets:
            markets[city] = {"population": pop}
    return markets


def apply_aliases(markets: dict[str, dict]) -> dict[str, dict]:
    """Add alias entries that map our data's city names to canonical entries."""
    for alias, canonical in CITY_ALIASES.items():
        if canonical in markets and alias not in markets:
            markets[alias] = markets[canonical]
    return markets


def main():
    print("Fetching Wikipedia data...")
    wikitext = fetch_wikitext()

    print("Parsing entries...")
    entries = parse_entries(wikitext)
    print(f"  Found {len(entries)} population centres")

    print("Building markets lookup...")
    markets = build_markets(entries)
    markets = apply_supplemental(markets)
    markets = apply_aliases(markets)
    print(f"  {len(markets)} total entries (including supplemental + aliases)")

    output = {
        "meta": {
            "source": "Wikipedia / Statistics Canada Census 2021",
            "page": "List of population centres in Ontario",
            "updated": date.today().isoformat(),
            "entry_count": len(markets),
        },
        "markets": dict(sorted(markets.items())),
    }

    MARKETS_PATH.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {MARKETS_PATH}")

    # Quick stats
    pops = sorted((v["population"] for v in markets.values()), reverse=True)
    print(f"\nTop 10 markets:")
    top = sorted(markets.items(), key=lambda x: x[1]["population"], reverse=True)[:10]
    for name, info in top:
        print(f"  {name}: {info['population']:,}")


if __name__ == "__main__":
    main()
