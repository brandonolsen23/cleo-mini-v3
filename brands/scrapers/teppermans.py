"""Tepperman's store scraper (Ontario).

Source: https://www.teppermans.com/our-locations
Method: Single HTTP GET, parse static HTML list of ~7 stores.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://www.teppermans.com/our-locations"
BRAND = "Tepperman's"
SLUG = "teppermans"

# Phone pattern: (519) 672-6500 or similar
PHONE_RE = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")

# Ontario postal code: L1Z 1Z2
POSTAL_RE = re.compile(r"[A-Z]\d[A-Z]\s*\d[A-Z]\d")


def scrape() -> tuple[list[StoreRecord], "Path"]:
    client = make_client()
    resp = client.get(SOURCE_URL)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    records: list[StoreRecord] = []
    ts = now_iso()

    # Find store entries — they're in <li> elements with <h3> headings
    for li in soup.find_all("li"):
        h3 = li.find("h3")
        if not h3:
            continue

        name = h3.get_text(strip=True).lstrip("#").strip()
        if not name or name.lower() in ("store details", "get directions"):
            continue

        text = li.get_text("\n", strip=True)
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        # Extract phone from tel: link
        phone_link = li.find("a", href=re.compile(r"^tel:"))
        phone = phone_link.get_text(strip=True) if phone_link else None

        # Extract directions link for address
        maps_link = li.find("a", href=re.compile(r"google\.com/maps"))

        # Parse address lines (between name and phone/links)
        addr_lines = []
        for line in lines:
            if line == name:
                continue
            if "Store Details" in line or "Get Directions" in line:
                continue
            if phone and line == phone:
                continue
            addr_lines.append(line)

        if not addr_lines:
            continue

        address = addr_lines[0]
        city = ""
        postal_code = None

        # Second line typically: "City, ON PostalCode"
        if len(addr_lines) > 1:
            city_line = addr_lines[1]
            pm = POSTAL_RE.search(city_line)
            if pm:
                postal_code = pm.group(0)
                city_line = city_line[: pm.start()].strip().rstrip(",")
            # Remove province
            city_line = re.sub(r",?\s*ON\s*$", "", city_line).strip().rstrip(",")
            city = city_line

        records.append(
            StoreRecord(
                brand=BRAND,
                store_name=f"Tepperman's {name}",
                address=address,
                city=city,
                province="ON",
                postal_code=postal_code,
                phone=phone,
                lat=None,
                lng=None,
                source_url=SOURCE_URL,
                scraped_at=ts,
            )
        )

    path = write_brand_json(SLUG, records)
    return records, path
