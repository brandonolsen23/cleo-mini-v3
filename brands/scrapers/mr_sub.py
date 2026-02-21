"""Mr. Sub scraper via Yext Pages embedded directory data.

~150 locations in Ontario across 84 cities.
The Yext Pages directory embeds store data (address, phone) as
URL-encoded JSON in city-level pages. No lat/lng at city level.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import unquote

from .base import StoreRecord, make_client, now_iso, write_brand_json

BASE_URL = "https://locations.mrsub.ca"
PROVINCE_URL = f"{BASE_URL}/ca/on"

# Pattern to extract dm_directoryChildren JSON array from URL-encoded page data
CHILDREN_RE = re.compile(
    r"%22dm_directoryChildren%22%3A(%5B.*?)(?:%5D%2C%22dm_directoryManagerId|%5D%2C%22dm_directoryParents)"
)


def _extract_children(html: str) -> list[dict]:
    """Extract directory children from URL-encoded Yext Pages data."""
    m = CHILDREN_RE.search(html)
    if not m:
        return []
    raw = unquote(m.group(1) + "]")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Mr. Sub stores in Ontario."""
    client = make_client()
    ts = now_iso()

    # Step 1: Get city slugs from ON province page
    resp = client.get(PROVINCE_URL)
    resp.raise_for_status()
    cities = _extract_children(resp.text)
    print(f"  Mr. Sub: {len(cities)} Ontario cities")

    # Step 2: Get store data from each city page
    records: list[StoreRecord] = []
    for city_info in cities:
        slug = city_info.get("slug", "")
        if not slug:
            continue

        time.sleep(0.15)
        resp = client.get(f"{BASE_URL}/{slug}")
        if resp.status_code != 200:
            continue

        stores = _extract_children(resp.text)
        for store in stores:
            addr = store.get("address", {})
            if not addr.get("line1"):
                continue

            city = addr.get("city", city_info.get("name", ""))
            phone = store.get("mainPhone")

            records.append(
                StoreRecord(
                    brand="Mr. Sub",
                    store_name=f"Mr. Sub - {city}",
                    address=addr["line1"],
                    city=city,
                    province=addr.get("region", "ON"),
                    postal_code=addr.get("postalCode"),
                    phone=phone,
                    lat=None,
                    lng=None,
                    source_url=f"{BASE_URL}/{store.get('slug', slug)}",
                    scraped_at=ts,
                )
            )

    path = write_brand_json("mr_sub", records)
    return records, path
