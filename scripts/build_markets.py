#!/usr/bin/env python3
"""Build data/markets.json from Wikipedia's List of municipalities in Ontario.

Fetches wikitext via the Wikipedia API for both local (section 5, ~414 rows)
and upper-tier (section 1, ~30 rows) municipalities, parses city names and
2021 Census populations, and writes a static lookup file.

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

WIKI_API_BASE = (
    "https://en.wikipedia.org/w/api.php"
    "?action=parse"
    "&page=List_of_municipalities_in_Ontario"
    "&prop=wikitext"
    "&format=json"
    "&section="
)

# Section 5 = local municipalities (~414 cities/towns/townships)
# Section 1 = upper-tier municipalities (~30 counties/regions)
SECTION_LOCAL = 5
SECTION_UPPER = 1


def fetch_wikitext(section: int) -> str:
    url = WIKI_API_BASE + str(section)
    req = Request(url, headers={"User-Agent": "CleoCLI/1.0"})
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["parse"]["wikitext"]["*"]


def _eval_expr(raw: str) -> int | None:
    """Evaluate a population value that may be a plain integer or a {{#expr:...}} template."""
    raw = raw.strip()
    # Plain integer
    if raw.isdigit():
        return int(raw)
    # {{#expr:696992-125}} → evaluate the arithmetic
    m = re.search(r"\{\{#expr:([^}]+)\}\}", raw)
    if m:
        expr = m.group(1).strip()
        # Only allow digits, +, -, *, spaces (safe eval)
        if re.fullmatch(r"[\d+\-* ]+", expr):
            return int(eval(expr))
    return None


def parse_section(wikitext: str) -> dict[str, int]:
    """Parse a wikitext table section into {display_name: population} dict."""
    results: dict[str, int] = {}
    rows = wikitext.split("|-")

    for row in rows:
        if 'scope="row"' not in row:
            continue

        # Extract display name from !scope="row"| [[Link|Display]] or [[Simple]]
        name_match = re.search(
            r'scope="row"\|\s*\[\[([^|\]]+?)(?:\|([^\]]+))?\]\]', row
        )
        if not name_match:
            continue
        display = (name_match.group(2) or name_match.group(1)).strip()
        # Clean up any <br /> in display names (e.g. "Stormont, Dundas<br />and Glengarry")
        display = re.sub(r"<br\s*/?>", " ", display)
        display = re.sub(r"\s+", " ", display).strip()

        # Extract population from {{change|POP2021|POP2016|...}}
        # POP2021 may be a plain integer or {{#expr:...}}
        change_match = re.search(r"\{\{change\|([^|]+)\|", row)
        if not change_match:
            continue
        pop = _eval_expr(change_match.group(1))
        if pop is None:
            continue

        # For duplicates, keep the larger population
        if display not in results or results[display] < pop:
            results[display] = pop

    return results


# Map Wikipedia display names back to the names used in our data.
# Applied after parsing so both name forms resolve to a population.
WIKI_DISPLAY_ALIASES: dict[str, str] = {
    "Norfolk County": "Norfolk",        # Wiki displays "Norfolk"
    "Haldimand County": "Haldimand",    # Wiki displays "Haldimand"
    "Prince Edward County": "Prince Edward",  # Wiki displays "Prince Edward"
    "Napanee": "Greater Napanee",        # Wiki displays "Greater Napanee"
}


def apply_display_aliases(markets: dict[str, dict]) -> dict[str, dict]:
    """Ensure both our data name and the Wikipedia display name resolve."""
    for our_name, wiki_name in WIKI_DISPLAY_ALIASES.items():
        # If wiki_name exists but our_name doesn't, add our_name
        if wiki_name in markets and our_name not in markets:
            markets[our_name] = markets[wiki_name]
        # If our_name exists but wiki_name doesn't, add wiki_name
        elif our_name in markets and wiki_name not in markets:
            markets[wiki_name] = markets[our_name]
    return markets


# Supplemental municipality populations (Census 2021 / estimates).
# Only entries NOT covered by the Wikipedia municipalities list.
# These are amalgamated communities that no longer exist as separate municipalities.
SUPPLEMENTAL: dict[str, int] = {
    # Hamilton amalgamated areas (part of City of Hamilton since 2001)
    "Stoney Creek": 73_000,
    "Ancaster": 40_000,
    "Flamborough": 39_000,
    "Dundas": 26_000,
    "Glanbrook": 29_000,
    # Ottawa amalgamated areas (part of City of Ottawa since 2001)
    "Nepean": 160_000,
    "Gloucester": 120_000,
    "Cumberland": 55_000,
    "Goulbourn": 30_000,
    "Kanata": 120_000,
    "Orleans": 110_000,
}


def build_markets(
    local: dict[str, int], upper: dict[str, int]
) -> dict[str, dict]:
    """Build city -> {population} mapping from parsed municipality data."""
    markets: dict[str, dict] = {}

    # Local municipalities first (these are the primary entries)
    for name, pop in local.items():
        markets[name] = {"population": pop}

    # Upper-tier municipalities (counties/regions) — don't overwrite locals
    for name, pop in upper.items():
        if name not in markets:
            markets[name] = {"population": pop}

    return markets


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
    print("  Section 5 (local municipalities)...")
    local_wikitext = fetch_wikitext(SECTION_LOCAL)
    print("  Section 1 (upper-tier municipalities)...")
    upper_wikitext = fetch_wikitext(SECTION_UPPER)

    print("Parsing entries...")
    local = parse_section(local_wikitext)
    upper = parse_section(upper_wikitext)
    print(f"  {len(local)} local municipalities")
    print(f"  {len(upper)} upper-tier municipalities")

    print("Building markets lookup...")
    markets = build_markets(local, upper)
    markets = apply_display_aliases(markets)
    markets = apply_supplemental(markets)
    markets = apply_aliases(markets)
    print(f"  {len(markets)} total entries (including aliases + supplemental)")

    output = {
        "meta": {
            "source": "Wikipedia / Statistics Canada Census 2021",
            "page": "List of municipalities in Ontario",
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
    print(f"\nTop 10 markets:")
    top = sorted(markets.items(), key=lambda x: x[1]["population"], reverse=True)[:10]
    for name, info in top:
        print(f"  {name}: {info['population']:,}")


if __name__ == "__main__":
    main()
