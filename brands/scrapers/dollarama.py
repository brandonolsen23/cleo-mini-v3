"""Dollarama store scraper (Ontario).

Source: https://www.storelocate.ca/dollarama/ontario.html
Method: Single HTTP GET, parse JavaScript `stores` array embedded in page.
Each entry: [city_name, html_popup, latitude, longitude]
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://www.storelocate.ca/dollarama/ontario.html"
BRAND = "Dollarama"
SLUG = "dollarama"

# Match: var stores = [...];
STORES_ARRAY_RE = re.compile(r"var\s+stores\s*=\s*(\[.+?\])\s*;", re.DOTALL)


def _parse_popup_html(html: str) -> dict:
    """Extract address fields from the info window HTML.

    Format: <p>street<br> [shopping_center<br>] city<br> province<br> postal</p>
    """
    soup = BeautifulSoup(html, "lxml")
    p = soup.find("p")
    if not p:
        return {}

    # Split on <br> tags to get individual lines
    parts = [t.strip() for t in p.stripped_strings]

    if len(parts) < 3:
        return {}

    # Last part is always postal code, second-to-last is province, before that is city
    postal_code = parts[-1]
    province = parts[-2]
    city = parts[-3]
    address = parts[0]

    return {
        "address": address,
        "city": city,
        "province": province,
        "postal_code": postal_code,
    }


def scrape() -> tuple[list[StoreRecord], Path]:
    client = make_client()
    resp = client.get(SOURCE_URL)
    resp.raise_for_status()

    m = STORES_ARRAY_RE.search(resp.text)
    if not m:
        raise RuntimeError("Could not find 'var stores = [...]' in page")

    # The JS array contains single-quoted strings and escaped quotes.
    # Convert to valid JSON: replace single quotes with double quotes,
    # but handle escaped single quotes in HTML content.
    raw = m.group(1)

    # Strategy: use a JS-compatible parser approach.
    # The array is: [['name', '<html>...', lat, lng], ...]
    # We'll manually parse by evaluating the structure.
    records: list[StoreRecord] = []
    ts = now_iso()

    # Split into individual store entries by finding each sub-array
    # Pattern: ['city', 'html', lat, lng]
    entry_re = re.compile(
        r"\[\s*'([^']*)'\s*,\s*'((?:[^'\\]|\\.)*)'\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\]"
    )

    for match in entry_re.finditer(raw):
        city_label = match.group(1)
        popup_html = match.group(2).replace("\\'", "'")
        lat = float(match.group(3))
        lng = float(match.group(4))

        fields = _parse_popup_html(popup_html)
        if not fields.get("address"):
            continue

        records.append(
            StoreRecord(
                brand=BRAND,
                store_name=f"Dollarama - {fields.get('city', city_label)}",
                address=fields["address"],
                city=fields.get("city", city_label),
                province=fields.get("province", "ON"),
                postal_code=fields.get("postal_code"),
                phone=None,
                lat=lat,
                lng=lng,
                source_url=SOURCE_URL,
                scraped_at=ts,
            )
        )

    path = write_brand_json(SLUG, records)
    return records, path
