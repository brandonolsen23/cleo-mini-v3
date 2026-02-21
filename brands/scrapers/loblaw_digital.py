"""Scraper for Loblaw Digital brands via the PCX BFF API.

Covers brands that use the PCExpress/Loblaw Digital pickup-locations API:
  - Valu-Mart
  - Your Independent Grocer (YIG)

The API returns all store locations for a given banner in a single call.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

# ── Constants ─────────────────────────────────────────────────────────

API_URL = "https://api.pcexpress.ca/pcx-bff/api/v1/pickup-locations"
API_KEY = "C1xujSegT5j3ap3yexJjqhOfELwGKYvz"


@dataclass
class BrandConfig:
    banner_id: str
    brand_name: str
    slug: str


BRANDS: dict[str, BrandConfig] = {
    "valumart": BrandConfig("valumart", "Valu-Mart", "valumart"),
    "independent": BrandConfig("independent", "Your Independent Grocer", "independent_grocer"),
}


# ── Helpers ───────────────────────────────────────────────────────────


def _make_client(banner_id: str) -> httpx.Client:
    return httpx.Client(
        headers={
            "Accept": "application/json",
            "Accept-Language": "en",
            "x-apikey": API_KEY,
            "Site-Banner": banner_id,
        },
        timeout=30,
    )


def _fetch_locations(banner_id: str) -> list[dict]:
    """Fetch all pickup locations for a Loblaw banner."""
    client = _make_client(banner_id)
    try:
        resp = client.get(API_URL, params={"bannerIds": banner_id})
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        return []
    finally:
        client.close()


def _to_record(loc: dict, brand_name: str, ts: str) -> StoreRecord | None:
    """Convert a PCX location dict to a StoreRecord."""
    addr = loc.get("address", {})
    geo = loc.get("geoPoint", {})

    street = addr.get("line1", "").strip()
    city = addr.get("town", "").strip()

    if not street or not city:
        return None

    # Province: API returns full name "Ontario", normalize to "ON"
    province_raw = addr.get("region", "")
    province = _normalize_province(province_raw)

    lat = geo.get("latitude")
    lng = geo.get("longitude")

    return StoreRecord(
        brand=brand_name,
        store_name=loc.get("name", f"{brand_name} - {city}"),
        address=street,
        city=city,
        province=province,
        postal_code=addr.get("postalCode"),
        phone=loc.get("orderContactNumber"),
        lat=float(lat) if lat is not None else None,
        lng=float(lng) if lng is not None else None,
        source_url=f"https://www.pcexpress.ca/store-locator/{loc.get('storeId', '')}",
        scraped_at=ts,
    )


_PROVINCE_MAP = {
    "Ontario": "ON",
    "Quebec": "QC",
    "British Columbia": "BC",
    "Alberta": "AB",
    "Manitoba": "MB",
    "Saskatchewan": "SK",
    "Nova Scotia": "NS",
    "New Brunswick": "NB",
    "Newfoundland And Labrador": "NL",
    "Prince Edward Island": "PE",
    "Northwest Territories": "NT",
    "Yukon": "YT",
    "Nunavut": "NU",
}


def _normalize_province(raw: str) -> str:
    return _PROVINCE_MAP.get(raw, raw)


# ── Public API ────────────────────────────────────────────────────────


def scrape_brand(key: str) -> tuple[list[StoreRecord], Path]:
    """Scrape a single Loblaw Digital brand."""
    cfg = BRANDS[key]
    ts = now_iso()

    locations = _fetch_locations(cfg.banner_id)

    # Filter to Ontario only
    records: list[StoreRecord] = []
    for loc in locations:
        region = loc.get("address", {}).get("region", "")
        if region != "Ontario":
            continue
        rec = _to_record(loc, cfg.brand_name, ts)
        if rec:
            records.append(rec)

    path = write_brand_json(cfg.slug, records)

    coord_count = sum(1 for r in records if r.lat is not None)
    print(f"  {cfg.brand_name}: {len(records)} Ontario stores ({coord_count}/{len(records)} have coordinates)")

    return records, path


def scrape_all() -> list[tuple[str, int, Path]]:
    """Scrape all Loblaw Digital brands."""
    results = []
    for key in BRANDS:
        records, path = scrape_brand(key)
        results.append((BRANDS[key].slug, len(records), path))
    return results


def scrape_valumart() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("valumart")


def scrape_independent_grocer() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("independent")
