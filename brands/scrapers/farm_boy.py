"""Farm Boy scraper via WordPress REST API + individual store page parsing.

~51 Ontario stores. Uses the WP REST API to discover store URLs,
then scrapes each page for address, phone, and store name.
No lat/lng available from the site — geocoding pipeline handles that.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

REST_URL = "https://www.farmboy.ca/wp-json/wp/v2/stores"
PHONE_RE = re.compile(r"\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
POSTAL_RE = re.compile(r"[A-Z]\d[A-Z]\s?\d[A-Z]\d")


def _parse_store_page(client, url: str) -> dict | None:
    """Fetch and parse a single Farm Boy store page."""
    resp = client.get(url)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Store name from <h1>
    h1 = soup.find("h1")
    name = h1.get_text(strip=True) if h1 else ""

    # Address from class="address"
    addr_el = soup.find(class_="address")
    raw_address = addr_el.get_text(strip=True) if addr_el else ""

    # Phone from tel: links
    phone = None
    for a in soup.find_all("a", href=re.compile(r"^tel:")):
        phone_text = a.get_text(strip=True)
        m = PHONE_RE.search(phone_text)
        if m:
            phone = m.group()
            break

    if not raw_address:
        return None

    # Parse "700 Terry Fox Drive, Ottawa, ON, K2L 4H4" format
    parts = [p.strip() for p in raw_address.split(",")]

    address = parts[0] if parts else ""
    city = parts[1] if len(parts) > 1 else ""
    province = "ON"
    postal_code = None

    # Find province and postal code in remaining parts
    for part in parts[2:]:
        part_clean = part.strip()
        if POSTAL_RE.search(part_clean):
            postal_code = POSTAL_RE.search(part_clean).group()
        elif part_clean.upper() in ("ON", "ONTARIO"):
            province = "ON"

    return {
        "name": name,
        "address": address,
        "city": city,
        "province": province,
        "postal_code": postal_code,
        "phone": phone,
    }


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Farm Boy stores in Ontario."""
    client = make_client()
    ts = now_iso()

    # Step 1: Get all store URLs from WP REST API
    resp = client.get(REST_URL, params={"per_page": 100})
    resp.raise_for_status()
    stores_api = resp.json()

    records: list[StoreRecord] = []

    # Step 2: Scrape each individual store page
    for i, store in enumerate(stores_api):
        url = store.get("link", "")
        if not url:
            continue

        fields = _parse_store_page(client, url)
        if not fields or not fields["address"]:
            continue

        records.append(
            StoreRecord(
                brand="Farm Boy",
                store_name=fields["name"] or f"Farm Boy - {fields['city']}",
                address=fields["address"],
                city=fields["city"],
                province=fields["province"],
                postal_code=fields["postal_code"],
                phone=fields["phone"],
                lat=None,
                lng=None,
                source_url=url,
                scraped_at=ts,
            )
        )

        # Polite delay between requests
        if i < len(stores_api) - 1:
            time.sleep(0.3)

    path = write_brand_json("farm_boy", records)
    return records, path
