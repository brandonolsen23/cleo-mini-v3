"""Esso and Mobil Canada scraper via Sitecore WEP2 Retail Locator API.

Both brands share the same backend API. The `Brand` field distinguishes them.
The API caps at 250 results per request, so we tile Ontario into overlapping
bounding boxes to capture all stations.
"""

from __future__ import annotations

from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

API_URL = "https://www.esso.ca/en-ca/api/locator/Locations"

# Ontario bounding boxes to ensure we capture all stations (overlapping)
ON_TILES = [
    # Southern Ontario - East (Ottawa region)
    (44.0, 46.0, -77.0, -74.0),
    # Southern Ontario - Central (GTA)
    (43.0, 44.5, -80.5, -78.5),
    # Southern Ontario - West (Hamilton/London)
    (42.0, 44.0, -82.5, -79.5),
    # Southern Ontario - Southwest (Windsor)
    (41.5, 43.0, -84.0, -81.5),
    # Central Ontario (Muskoka/Barrie)
    (44.0, 46.5, -81.0, -78.5),
    # Northern Ontario - South (Sudbury)
    (46.0, 48.5, -82.0, -79.0),
    # Northern Ontario - East (North Bay)
    (46.0, 48.0, -80.0, -77.0),
    # Northern Ontario - West (Thunder Bay)
    (47.5, 50.0, -91.0, -84.0),
    # Far Northern Ontario
    (48.0, 52.0, -85.0, -79.0),
    # Northwestern Ontario
    (48.0, 52.0, -95.0, -85.0),
    # Niagara / South shore
    (42.5, 44.0, -80.0, -78.5),
    # Eastern Ontario (Kingston)
    (44.0, 45.5, -78.5, -75.5),
]


def _fetch_all() -> list[dict]:
    """Fetch all stations across Ontario tiles, deduped by LocationID."""
    client = make_client()
    seen_ids: set[str] = set()
    all_locations: list[dict] = []

    for lat1, lat2, lng1, lng2 in ON_TILES:
        resp = client.get(
            API_URL,
            params={
                "Latitude1": str(lat1),
                "Latitude2": str(lat2),
                "Longitude1": str(lng1),
                "Longitude2": str(lng2),
                "DataSource": "RetailGasStations",
                "Country": "CA",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        for loc in data.get("Locations", []):
            if loc.get("StateProvince") != "ON":
                continue
            loc_id = loc.get("LocationID", "")
            if loc_id in seen_ids:
                continue
            seen_ids.add(loc_id)
            all_locations.append(loc)

    return all_locations


def _to_record(loc: dict, brand: str, ts: str) -> StoreRecord:
    name = loc.get("DisplayName", "").strip()
    if not name:
        name = loc.get("LocationName", brand)

    return StoreRecord(
        brand=brand,
        store_name=name,
        address=loc.get("AddressLine1", ""),
        city=loc.get("City", ""),
        province="ON",
        postal_code=loc.get("PostalCode"),
        phone=loc.get("Telephone"),
        lat=loc.get("Latitude"),
        lng=loc.get("Longitude"),
        source_url=f"https://www.esso.ca/en-ca/find-station",
        scraped_at=ts,
    )


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Esso stations in Ontario (excludes Mobil)."""
    ts = now_iso()
    all_locations = _fetch_all()
    records = [
        _to_record(loc, "Esso", ts)
        for loc in all_locations
        if loc.get("Brand", "Esso") == "Esso"
    ]
    path = write_brand_json("esso", records)
    return records, path


def scrape_mobil() -> tuple[list[StoreRecord], Path]:
    """Scrape all Mobil stations in Ontario."""
    ts = now_iso()
    all_locations = _fetch_all()
    records = [
        _to_record(loc, "Mobil", ts)
        for loc in all_locations
        if loc.get("Brand") == "Mobil"
    ]
    path = write_brand_json("mobil", records)
    return records, path


def scrape_all() -> list[tuple[str, int, Path]]:
    """Scrape both Esso and Mobil in a single pass."""
    ts = now_iso()
    all_locations = _fetch_all()

    esso_records = []
    mobil_records = []
    for loc in all_locations:
        brand = loc.get("Brand", "Esso")
        if brand == "Mobil":
            mobil_records.append(_to_record(loc, "Mobil", ts))
        else:
            esso_records.append(_to_record(loc, "Esso", ts))

    results = []
    esso_path = write_brand_json("esso", esso_records)
    results.append(("esso", len(esso_records), esso_path))
    mobil_path = write_brand_json("mobil", mobil_records)
    results.append(("mobil", len(mobil_records), mobil_path))
    return results
