"""Generic storelocate.ca scraper.

Covers 20 brands — all use the same
`var stores = [['city', '<popup_html>', lat, lng], ...]` JS format.

Source: https://www.storelocate.ca/{slug}/ontario.html
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

BASE_URL = "https://www.storelocate.ca"

# Brand configs: slug on storelocate.ca -> (output slug, display name)
BRANDS = {
    # Loblaw group
    "loblaws": ("loblaws", "Loblaws"),
    "no-frills": ("no_frills", "No Frills"),
    "real-canadian-superstore": ("real_canadian_superstore", "Real Canadian Superstore"),
    "zehrs": ("zehrs", "Zehrs"),
    "fortinos": ("fortinos", "Fortinos"),
    "wholesale-club": ("wholesale_club", "Wholesale Club"),
    "shoppers-drug-mart": ("shoppers_drug_mart", "Shoppers Drug Mart"),
    # Sobeys/Empire group
    "sobeys": ("sobeys", "Sobeys"),
    "foodland": ("foodland", "Foodland"),
    "safeway": ("safeway", "Safeway"),
    # Metro
    "metro": ("metro", "Metro"),
    # Big-Box
    "walmart": ("walmart", "Walmart"),
    "canadian-tire": ("canadian_tire", "Canadian Tire"),
    "home-depot": ("home_depot", "Home Depot"),
    "costco": ("costco", "Costco"),
    # Specialty
    "homesense": ("homesense", "HomeSense"),
    "best-buy": ("best_buy", "Best Buy"),
    "staples": ("staples", "Staples"),
    "sport-chek": ("sport_chek", "Sport Chek"),
    "toys-r-us": ("toys_r_us", "Toys R Us"),
}

STORES_ARRAY_RE = re.compile(r"var\s+stores\s*=\s*(\[.+?\])\s*;", re.DOTALL)
ENTRY_RE = re.compile(
    r"\[\s*'([^']*)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\]"
)


def _parse_popup(html: str) -> dict:
    """Extract address from storelocate.ca popup HTML.

    Format: <p>street<br> city<br> province<br> postal</p>
    """
    soup = BeautifulSoup(html, "lxml")
    p = soup.find("p")
    if not p:
        return {}

    parts = [t.strip() for t in p.stripped_strings]
    if len(parts) < 3:
        return {}

    return {
        "address": parts[0],
        "city": parts[1] if len(parts) > 1 else "",
        "province": parts[2] if len(parts) > 2 else "ON",
        "postal_code": parts[3] if len(parts) > 3 else None,
    }


def scrape_brand(site_slug: str) -> tuple[list[StoreRecord], Path]:
    """Scrape a single brand from storelocate.ca."""
    out_slug, brand_name = BRANDS[site_slug]
    source_url = f"{BASE_URL}/{site_slug}/ontario.html"

    client = make_client()
    resp = client.get(source_url)
    resp.raise_for_status()

    m = STORES_ARRAY_RE.search(resp.text)
    if not m:
        raise RuntimeError(f"Could not find 'var stores' in {source_url}")

    raw = m.group(1)
    records: list[StoreRecord] = []
    ts = now_iso()

    for match in ENTRY_RE.finditer(raw):
        city_label = match.group(1)
        popup_html = match.group(2).replace("\\'", "'")
        lat = float(match.group(3))
        lng = float(match.group(4))

        fields = _parse_popup(popup_html)
        if not fields.get("address"):
            continue

        records.append(
            StoreRecord(
                brand=brand_name,
                store_name=f"{brand_name} - {fields.get('city', city_label)}",
                address=fields["address"],
                city=fields.get("city", city_label),
                province=fields.get("province", "ON"),
                postal_code=fields.get("postal_code"),
                phone=None,
                lat=lat,
                lng=lng,
                source_url=source_url,
                scraped_at=ts,
            )
        )

    path = write_brand_json(out_slug, records)
    return records, path


def scrape_all() -> list[tuple[str, int, Path]]:
    """Scrape all storelocate.ca brands."""
    results = []
    for site_slug in BRANDS:
        records, path = scrape_brand(site_slug)
        out_slug = BRANDS[site_slug][0]
        results.append((out_slug, len(records), path))
    return results


# Individual brand functions for run.py registration
def scrape_loblaws() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("loblaws")

def scrape_no_frills() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("no-frills")

def scrape_real_canadian_superstore() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("real-canadian-superstore")

def scrape_zehrs() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("zehrs")

def scrape_fortinos() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("fortinos")

def scrape_wholesale_club() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("wholesale-club")

def scrape_shoppers_drug_mart() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("shoppers-drug-mart")

def scrape_sobeys() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("sobeys")

def scrape_foodland() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("foodland")

def scrape_safeway() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("safeway")

def scrape_metro() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("metro")

def scrape_walmart() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("walmart")

def scrape_canadian_tire() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("canadian-tire")

def scrape_home_depot() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("home-depot")

def scrape_costco() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("costco")

def scrape_homesense() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("homesense")

def scrape_best_buy() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("best-buy")

def scrape_staples() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("staples")

def scrape_sport_chek() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("sport-chek")

def scrape_toys_r_us() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("toys-r-us")
