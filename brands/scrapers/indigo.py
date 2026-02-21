"""Indigo / Chapters scraper via store locator listing + JSON-LD on detail pages.

~70 Ontario stores. Two-step scrape:
1. Fetch the store locator listing page to extract all Ontario store IDs
2. Fetch each store detail page and extract JSON-LD structured data
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

LISTING_URL = "https://www.chapters.indigo.ca/en-ca/store-locator/"
DETAIL_URL = "https://www.chapters.indigo.ca/en-ca/store-locator-store-details"


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Indigo/Chapters stores in Ontario."""
    client = make_client()
    ts = now_iso()

    # Step 1: Get all Ontario store IDs from listing page
    resp = client.get(LISTING_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    on_section = soup.find(id="ON")
    if not on_section:
        raise RuntimeError("Could not find Ontario section on store locator page")

    store_ids: list[tuple[str, str]] = []  # (store_id, store_name)
    for a in on_section.find_all("a", href=lambda x: x and "storeId=" in str(x)):
        href = a["href"]
        m = re.search(r"storeId=(\w+)", href)
        if m:
            store_ids.append((m.group(1), a.get_text(strip=True)))

    # Step 2: Fetch each detail page and extract JSON-LD
    records: list[StoreRecord] = []
    for i, (store_id, listing_name) in enumerate(store_ids):
        detail_resp = client.get(DETAIL_URL, params={"storeId": store_id})
        if detail_resp.status_code != 200:
            continue

        detail_soup = BeautifulSoup(detail_resp.text, "lxml")

        # Extract JSON-LD Store schema
        for script in detail_soup.find_all("script", type="application/ld+json"):
            try:
                ld = json.loads(script.string)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(ld, dict) or ld.get("@type") != "Store":
                continue

            addr = ld.get("address", {})
            geo = ld.get("geo", {})
            name = ld.get("name", listing_name)

            records.append(
                StoreRecord(
                    brand="Indigo",
                    store_name=name,
                    address=addr.get("streetAddress", ""),
                    city=addr.get("addressLocality", ""),
                    province=addr.get("addressRegion", "ON"),
                    postal_code=addr.get("postalCode"),
                    phone=ld.get("telephone"),
                    lat=geo.get("latitude"),
                    lng=geo.get("longitude"),
                    source_url=ld.get("url", f"{DETAIL_URL}?storeId={store_id}"),
                    scraped_at=ts,
                )
            )
            break

        if i < len(store_ids) - 1:
            time.sleep(0.2)

    path = write_brand_json("indigo", records)
    return records, path
