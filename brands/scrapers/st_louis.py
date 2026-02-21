"""St. Louis Bar & Grill scraper via Next.js __NEXT_DATA__.

84 locations across Canada (~70+ in Ontario).
The locations page embeds full store data in __NEXT_DATA__.props.pageProps.locations.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://locations.stlouiswings.com/"
NEXT_DATA_RE = re.compile(
    r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all St. Louis Bar & Grill stores in Ontario."""
    client = make_client()
    ts = now_iso()

    resp = client.get(SOURCE_URL)
    resp.raise_for_status()

    m = NEXT_DATA_RE.search(resp.text)
    if not m:
        raise RuntimeError("Could not find __NEXT_DATA__")

    data = json.loads(m.group(1))
    locations = data["props"]["pageProps"]["locations"]
    records: list[StoreRecord] = []

    for loc in locations:
        # Filter to Ontario
        if loc.get("state") != "ON":
            continue

        address_lines = loc.get("addressLines", [])
        address = address_lines[0] if address_lines else ""

        postal = loc.get("postalCode", "")
        # Normalize postal code format (remove spaces then re-add)
        postal_clean = postal.replace(" ", "")
        if len(postal_clean) == 6:
            postal = f"{postal_clean[:3]} {postal_clean[3:]}"

        phones = loc.get("phoneNumbers", [])

        records.append(
            StoreRecord(
                brand="St. Louis Bar & Grill",
                store_name=f"St. Louis - {loc.get('city', '')}",
                address=address,
                city=loc.get("city", ""),
                province="ON",
                postal_code=postal or None,
                phone=phones[0] if phones else None,
                lat=loc.get("latitude"),
                lng=loc.get("longitude"),
                source_url=loc.get("websiteURL", SOURCE_URL),
                scraped_at=ts,
            )
        )

    path = write_brand_json("st_louis", records)
    return records, path
