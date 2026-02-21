"""Mary Brown's scraper via embedded JavaScript locations array.

296 locations across Canada, ~118 in Ontario.
The locations page embeds a `var _locations = [...]` array with
id, name, address, phone, lat, lng for every store.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://marybrowns.com/locations/"
LOCATIONS_RE = re.compile(r"var\s+_locations\s*=\s*(\[.+?\])\s*;", re.DOTALL)
POSTAL_RE = re.compile(r"[A-Z]\d[A-Z]\s?\d[A-Z]\d")


CITY_RE = re.compile(r"(.+?),\s*(?:ON|Ontario)\b")


def _parse_address(raw: str) -> dict:
    """Parse Mary Brown's address formats.

    Handles:
      "245 Dixon Road Unit 103, Etobicoke, ON "
      "141 Spadina Avenue. Toronto, ON M5V 1X3"
      "5050 Tecumseh Road East Unit 6 Windsor, ON N8T 1C1"
    """
    postal_code = None
    m = POSTAL_RE.search(raw)
    if m:
        postal_code = m.group()

    # Extract city: the text immediately before ", ON"
    city = ""
    cm = CITY_RE.search(raw)
    if cm:
        before_on = cm.group(1).strip()
        # City is the last word(s) after the last comma or period before ON
        # Split on comma or period to find the city segment
        segments = re.split(r"[,.]", before_on)
        city = segments[-1].strip()

    # Address is everything before the city
    address = raw
    if city:
        # Find the city in the raw string and take everything before it
        idx = raw.find(city)
        if idx > 0:
            address = raw[:idx].rstrip(" .,")

    return {
        "address": address,
        "city": city,
        "province": "ON",
        "postal_code": postal_code,
    }


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Mary Brown's stores in Ontario."""
    client = make_client()
    ts = now_iso()

    resp = client.get(SOURCE_URL)
    resp.raise_for_status()

    m = LOCATIONS_RE.search(resp.text)
    if not m:
        raise RuntimeError("Could not find _locations array")

    all_stores = json.loads(m.group(1))
    records: list[StoreRecord] = []

    for store in all_stores:
        raw_addr = store.get("address", "")
        # Filter to Ontario
        if ", ON" not in raw_addr and ", Ontario" not in raw_addr:
            continue

        fields = _parse_address(raw_addr)

        records.append(
            StoreRecord(
                brand="Mary Brown's",
                store_name=f"Mary Brown's - {store.get('name', fields['city'])}",
                address=fields["address"],
                city=fields["city"],
                province=fields["province"],
                postal_code=fields["postal_code"],
                phone=store.get("phone"),
                lat=store.get("lat"),
                lng=store.get("lng"),
                source_url=SOURCE_URL,
                scraped_at=ts,
            )
        )

    path = write_brand_json("mary_browns", records)
    return records, path
