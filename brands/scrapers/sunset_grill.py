"""Sunset Grill scraper via WP Store Locator AJAX API.

100 Ontario locations. The store locator page uses the WordPress WPSL plugin
which exposes a JSON endpoint at admin-ajax.php with action=store_search.
"""

from __future__ import annotations

import html
from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

AJAX_URL = "https://sunsetgrill.ca/wp-admin/admin-ajax.php"


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Sunset Grill stores in Ontario."""
    client = make_client()
    ts = now_iso()

    resp = client.get(
        AJAX_URL,
        params={
            "action": "store_search",
            "lat": "43.65",
            "lng": "-79.38",
            "max_results": "500",
            "search_radius": "50000",
            "autoload": "1",
        },
    )
    resp.raise_for_status()
    all_stores = resp.json()

    records: list[StoreRecord] = []
    for store in all_stores:
        if store.get("state", "").lower() != "ontario":
            continue

        # Build address from address + address2
        addr = store.get("address", "").strip()
        addr2 = store.get("address2", "").strip()
        if addr2:
            addr = f"{addr}, {addr2}"

        # Clean HTML entities from store name
        raw_name = store.get("store", "") or store.get("location_title", "")
        name = html.unescape(raw_name).strip()

        lat = store.get("lat")
        lng = store.get("lng")
        if lat:
            lat = float(lat)
        if lng:
            lng = float(lng)

        records.append(
            StoreRecord(
                brand="Sunset Grill",
                store_name=f"Sunset Grill - {name}" if name else f"Sunset Grill - {store.get('city', '')}",
                address=addr,
                city=store.get("city", ""),
                province="ON",
                postal_code=store.get("zip"),
                phone=store.get("phone"),
                lat=lat,
                lng=lng,
                source_url=store.get("url", "https://sunsetgrill.ca/locations/"),
                scraped_at=ts,
            )
        )

    path = write_brand_json("sunset_grill", records)
    return records, path
