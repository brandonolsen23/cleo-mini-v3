"""Recipe Unlimited brand scraper (Ontario).

Covers: Harvey's, Swiss Chalet, Kelseys, Montana's, East Side Mario's.
All share one Yext account (ID 1247882420862196446) with a public API key.
Each brand is separated by meta.folderId.

Source: Yext Live API geosearch endpoint
Method: Paginated API calls with offset, filter by folderId per brand.
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

YEXT_API_KEY = "13a5875d18fe490377fc4bf35de52851"
YEXT_BASE = "https://liveapi.yext.com/v2/accounts/me/entities/geosearch"

# Center of Ontario, large radius to capture all locations
SEARCH_LAT = 43.65
SEARCH_LNG = -79.38
SEARCH_RADIUS = 1000  # km

PAGE_SIZE = 50

BRANDS = {
    "harveys": {"folder_id": "415848", "brand_name": "Harvey's"},
    "swiss_chalet": {"folder_id": "415850", "brand_name": "Swiss Chalet"},
    "kelseys": {"folder_id": "416273", "brand_name": "Kelseys"},
    "montanas": {"folder_id": "415846", "brand_name": "Montana's"},
    "east_side_marios": {"folder_id": "415849", "brand_name": "East Side Mario's"},
}


def _fetch_all_entities(client: httpx.Client) -> list[dict]:
    """Fetch all entities from the Yext account via paginated geosearch."""
    all_entities: list[dict] = []
    offset = 0

    while True:
        resp = client.get(
            YEXT_BASE,
            params={
                "radius": SEARCH_RADIUS,
                "location": f"{SEARCH_LAT},{SEARCH_LNG}",
                "limit": PAGE_SIZE,
                "offset": offset,
                "api_key": YEXT_API_KEY,
                "v": "20220101",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        entities = data.get("response", {}).get("entities", [])
        if not entities:
            break

        all_entities.extend(entities)
        total = data.get("response", {}).get("count", 0)

        if len(all_entities) >= total or len(entities) < PAGE_SIZE:
            break

        offset += PAGE_SIZE
        time.sleep(0.3)

    return all_entities


def _entity_to_record(
    entity: dict, brand_name: str, ts: str
) -> StoreRecord | None:
    """Convert a Yext entity dict to a StoreRecord."""
    addr = entity.get("address", {})
    region = addr.get("region", "")

    # Ontario only
    if region != "ON":
        return None

    coords = entity.get("yextDisplayCoordinate", {})
    phone_raw = entity.get("mainPhone", "")

    # Format phone from +14169998888 to (416) 999-8888
    phone = None
    if phone_raw and len(phone_raw) >= 11:
        digits = phone_raw.lstrip("+").lstrip("1")
        if len(digits) == 10:
            phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

    return StoreRecord(
        brand=brand_name,
        store_name=entity.get("name", ""),
        address=addr.get("line1", ""),
        city=addr.get("city", ""),
        province="ON",
        postal_code=addr.get("postalCode"),
        phone=phone,
        lat=coords.get("latitude"),
        lng=coords.get("longitude"),
        source_url=f"https://liveapi.yext.com (folderId={entity.get('meta', {}).get('folderId')})",
        scraped_at=ts,
    )


def scrape_brand(slug: str) -> tuple[list[StoreRecord], Path]:
    """Scrape a single Recipe Unlimited brand."""
    cfg = BRANDS[slug]
    client = httpx.Client(timeout=30, follow_redirects=True)
    ts = now_iso()

    all_entities = _fetch_all_entities(client)

    records = []
    for entity in all_entities:
        folder = entity.get("meta", {}).get("folderId", "")
        if folder != cfg["folder_id"]:
            continue

        rec = _entity_to_record(entity, cfg["brand_name"], ts)
        if rec:
            records.append(rec)

    path = write_brand_json(slug, records)
    return records, path


def scrape_all() -> list[tuple[str, int, Path]]:
    """Scrape all Recipe Unlimited brands in one API pass."""
    client = httpx.Client(timeout=30, follow_redirects=True)
    ts = now_iso()

    all_entities = _fetch_all_entities(client)
    results = []

    for slug, cfg in BRANDS.items():
        records = []
        for entity in all_entities:
            folder = entity.get("meta", {}).get("folderId", "")
            if folder != cfg["folder_id"]:
                continue
            rec = _entity_to_record(entity, cfg["brand_name"], ts)
            if rec:
                records.append(rec)

        path = write_brand_json(slug, records)
        results.append((slug, len(records), path))

    return results


# Individual brand scrape functions for run.py registration
def scrape_harveys() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("harveys")

def scrape_swiss_chalet() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("swiss_chalet")

def scrape_kelseys() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("kelseys")

def scrape_montanas() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("montanas")

def scrape_east_side_marios() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("east_side_marios")
