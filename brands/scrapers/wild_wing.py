"""Wild Wing Restaurants scraper via embedded JavaScript locations array.

104 locations across Canada, ~71 in Ontario.
The locations page embeds a JSON array with title, lat, lng,
and address as HTML with phone number.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://www.wildwingrestaurants.com/locations/"
POSTAL_RE = re.compile(r"[A-Z]\d[A-Z]\s?\d[A-Z]\d")
PHONE_RE = re.compile(r"\d{3}[- ]?\d{3}[- ]?\d{4}")


def _parse_address_html(html: str) -> dict:
    """Parse Wild Wing's address HTML.

    Format: street<br>city, ON<br>postal<br>hours<br>Phone: <a>phone</a>
    """
    soup = BeautifulSoup(html, "lxml")
    parts = [t.strip() for t in soup.get_text(separator="|").split("|") if t.strip()]

    address = parts[0] if parts else ""
    city = ""
    province = "ON"
    postal_code = None
    phone = None

    for part in parts[1:]:
        # Check for phone
        m = PHONE_RE.search(part)
        if m:
            phone = m.group()
            continue

        # Check for "City, ON" or "City, ON K7G 1H4" pattern
        if ", ON" in part:
            # Extract postal code if embedded
            pm = POSTAL_RE.search(part)
            if pm:
                postal_code = pm.group()
            # City is everything before ", ON"
            city = part.split(", ON")[0].strip()
            continue

        # Standalone postal code line
        m = POSTAL_RE.search(part)
        if m:
            postal_code = m.group()
            continue

    return {
        "address": address,
        "city": city,
        "postal_code": postal_code,
        "phone": phone,
    }


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Wild Wing stores in Ontario."""
    client = make_client()
    ts = now_iso()

    resp = client.get(SOURCE_URL)
    resp.raise_for_status()

    # Find the JSON array with location data
    m = re.search(r"(\[\s*\{\"title\".*?\}\s*\])", resp.text, re.DOTALL)
    if not m:
        raise RuntimeError("Could not find locations array")

    all_stores = json.loads(m.group(1))
    records: list[StoreRecord] = []

    for store in all_stores:
        addr_html = store.get("address", "")
        # Filter to Ontario
        if ", ON" not in addr_html:
            continue

        fields = _parse_address_html(addr_html)

        records.append(
            StoreRecord(
                brand="Wild Wing",
                store_name=f"Wild Wing - {store.get('title', fields['city'])}",
                address=fields["address"],
                city=fields["city"],
                province="ON",
                postal_code=fields["postal_code"],
                phone=fields["phone"],
                lat=store.get("latitude"),
                lng=store.get("longitude"),
                source_url=store.get("view_location", SOURCE_URL),
                scraped_at=ts,
            )
        )

    path = write_brand_json("wild_wing", records)
    return records, path
