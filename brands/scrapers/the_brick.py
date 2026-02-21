"""The Brick scraper via static HTML stores listing page.

~70 Ontario stores. The Brick's Shopify-powered site has a full store directory
page with all addresses and phone numbers in static HTML.
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://www.thebrick.com/pages/stores-listing"
POSTAL_RE = re.compile(r"([A-Z]\d[A-Z]\s?\d[A-Z]\d)")
PHONE_RE = re.compile(r"\d{3}[-.]?\d{3}[-.]?\d{4}")


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all The Brick stores in Ontario."""
    client = make_client()
    ts = now_iso()

    resp = client.get(SOURCE_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    records: list[StoreRecord] = []
    for div in soup.find_all("div", class_="store-info-cont"):
        # Get address text
        addr_p = div.select_one(".upper-store-grid p")
        if not addr_p:
            continue

        raw = addr_p.get_text(separator="|").strip()
        parts = [p.strip() for p in raw.split("|") if p.strip()]

        # Filter to Ontario only
        full_text = " ".join(parts)
        if ", ON " not in full_text and ", ON\n" not in full_text:
            # Check if ON is in the joined text
            if " ON " not in full_text:
                continue

        # Parse address: first part is street, second is "City, ON PostalCode"
        address = parts[0] if parts else ""
        city = ""
        postal_code = None

        if len(parts) > 1:
            city_line = parts[1]
            # Pattern: "City, ON L1Z1G1" or "City, ON L1Z 1G1"
            m = re.match(r"(.+?),\s*ON\s+(.*)", city_line)
            if m:
                city = m.group(1).strip()
                postal_raw = m.group(2).strip()
                pm = POSTAL_RE.search(postal_raw)
                if pm:
                    postal_code = pm.group(1)
            else:
                city = city_line.strip()

        # Store name
        h4 = div.find("h4")
        name = h4.get_text(strip=True) if h4 else city

        # Skip distribution centres
        if "distribution" in name.lower():
            continue

        # Phone number
        phone = None
        phone_el = div.find("a", class_="store-phone")
        if phone_el:
            phone = phone_el.get_text(strip=True)

        # Store page URL
        link_el = div.find("a", class_="location-button")
        store_url = SOURCE_URL
        if link_el and link_el.get("href"):
            store_url = f"https://www.thebrick.com{link_el['href']}"

        records.append(
            StoreRecord(
                brand="The Brick",
                store_name=f"The Brick - {name}",
                address=address,
                city=city,
                province="ON",
                postal_code=postal_code,
                phone=phone,
                lat=None,
                lng=None,
                source_url=store_url,
                scraped_at=ts,
            )
        )

    path = write_brand_json("the_brick", records)
    return records, path
