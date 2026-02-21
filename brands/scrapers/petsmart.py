"""PetSmart store locator scraper (Ontario).

Two-level crawl:
1. Fetch /on/ province page to get city URLs
2. Fetch each city page — stores are in div.col-md-6.mb-5 elements
   with address, phone, and postal code. Dedup by address since each
   physical store has separate grooming/training listings.

Source: https://stores.petsmart.ca/on/
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

BASE_URL = "https://stores.petsmart.ca"
BRAND = "PetSmart"


def _get_city_urls(client) -> list[str]:
    """Get all Ontario city page URLs from the province listing."""
    resp = client.get(f"{BASE_URL}/on/")
    resp.raise_for_status()

    urls = set()
    for match in re.finditer(r'href="(https://stores\.petsmart\.ca/on/[a-z][a-z0-9-]*)"', resp.text):
        urls.add(match.group(1))
    return sorted(urls)


def _parse_city_page(client, city_url: str, city_name: str, ts: str) -> list[StoreRecord]:
    """Extract store records from a city page, deduped by address."""
    try:
        resp = client.get(city_url)
        if resp.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    profiles = soup.find("div", class_="profiles")
    if not profiles:
        return []

    seen_addresses: set[str] = set()
    records: list[StoreRecord] = []

    for col in profiles.find_all("div", class_="col-md-6"):
        text_parts = [s.strip() for s in col.stripped_strings]
        if len(text_parts) < 4:
            continue

        # Find the street address (line with a street number)
        address = ""
        address_idx = -1
        for i, part in enumerate(text_parts):
            if re.match(r"^\d+\s", part):
                address = part
                address_idx = i
                break

        if not address:
            continue

        # Dedup by normalized address
        addr_key = address.lower().strip()
        if addr_key in seen_addresses:
            continue
        seen_addresses.add(addr_key)

        # City, Province is typically the line after address
        city = city_name.title()
        postal_code = None

        if address_idx + 1 < len(text_parts):
            city_line = text_parts[address_idx + 1]
            # Format: "Brampton, ON"
            m = re.match(r"^(.+?),\s*ON", city_line)
            if m:
                city = m.group(1).strip()

        # Postal code is typically the line after city
        if address_idx + 2 < len(text_parts):
            pc = text_parts[address_idx + 2]
            if re.match(r"^[A-Z]\d[A-Z]\s*\d[A-Z]\d$", pc):
                postal_code = pc

        # Phone from tel: link
        phone = None
        tel_link = col.find("a", href=re.compile(r"^tel:"))
        if tel_link:
            digits = re.sub(r"\D", "", tel_link["href"])
            if len(digits) == 10:
                phone = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

        records.append(
            StoreRecord(
                brand=BRAND,
                store_name=f"PetSmart - {city}",
                address=address,
                city=city,
                province="ON",
                postal_code=postal_code,
                phone=phone,
                lat=None,
                lng=None,
                source_url=city_url,
                scraped_at=ts,
            )
        )

    return records


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape PetSmart Ontario stores."""
    client = make_client()
    ts = now_iso()

    # Step 1: Get city URLs
    city_urls = _get_city_urls(client)
    print(f"  PetSmart: {len(city_urls)} cities found, fetching stores...", end="", flush=True)

    # Step 2: Fetch each city page and extract stores
    records: list[StoreRecord] = []
    seen_addresses: set[str] = set()

    for i, url in enumerate(city_urls):
        # Extract city name from URL
        city_slug = url.rstrip("/").split("/")[-1]
        city_name = city_slug.replace("-", " ")

        city_records = _parse_city_page(client, url, city_name, ts)

        # Global dedup by address
        for r in city_records:
            key = r.address.lower().strip()
            if key not in seen_addresses:
                seen_addresses.add(key)
                records.append(r)

        if (i + 1) % 15 == 0:
            print(f" {i + 1}...", end="", flush=True)

        time.sleep(0.2)

    print(f" done ({len(records)} stores)")

    path = write_brand_json("petsmart", records)
    return records, path
