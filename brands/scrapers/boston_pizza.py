"""Boston Pizza scraper via AEM JSON endpoint.

111 Ontario locations. Boston Pizza's AEM-powered site exposes a
JSON endpoint that returns all restaurants with full geocoded data.
"""

from __future__ import annotations

import re
from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

API_URL = "https://www.bostonpizza.com/content/bostonpizza/en/locations/jcr:content/root/container_73434033/map.getAllRestaurants.json"


def _clean_phone(raw: str) -> str | None:
    """Clean phone number from format like '0018074685597'."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    # Strip leading country code (001 or 1)
    if digits.startswith("001"):
        digits = digits[3:]
    elif digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Boston Pizza stores in Ontario."""
    client = make_client()
    ts = now_iso()

    resp = client.get(API_URL)
    resp.raise_for_status()
    data = resp.json()
    all_stores = data.get("map", {}).get("response", data.get("response", []))

    records: list[StoreRecord] = []
    for store in all_stores:
        if store.get("province") != "ON":
            continue

        lat = store.get("latitude")
        lng = store.get("longitude")
        if lat:
            lat = float(lat)
        if lng:
            lng = float(lng)

        name = store.get("restaurantName", "").strip()

        records.append(
            StoreRecord(
                brand="Boston Pizza",
                store_name=f"Boston Pizza - {name}" if name else f"Boston Pizza - {store.get('city', '')}",
                address=store.get("address", ""),
                city=store.get("city", ""),
                province="ON",
                postal_code=store.get("postalCode"),
                phone=_clean_phone(store.get("restaurantPhoneNumber")),
                lat=lat,
                lng=lng,
                source_url=f"https://bostonpizza.com{store.get('restaurantPage', '/en/locations')}",
                scraped_at=ts,
            )
        )

    path = write_brand_json("boston_pizza", records)
    return records, path
