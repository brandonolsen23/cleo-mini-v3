"""Scraper for Pita Pit — HTML parse of pitapit.ca/find-a-restaurant/.

All ~243 Canadian stores are server-rendered in a single page using Avada/Fusion Builder.
Each store is a fusion-column-wrapper div containing the city name (h4), address text,
and phone number. No API needed — just fetch and parse the HTML.
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

URL = "https://pitapit.ca/find-a-restaurant/"

# Canadian province codes
_PROVINCES = {"AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"}

# Pattern: City PROV PostalCode (e.g. "Airdrie AB T4B 1R9")
_ADDR_LINE_RE = re.compile(
    r"^(.+?)\s+([A-Z]{2})\s+([A-Z]\d[A-Z]\s*\d[A-Z]\d)$"
)


def _parse_card(wrapper, ts: str) -> StoreRecord | None:
    """Parse a fusion-column-wrapper div into a StoreRecord."""
    # City name from h4 inside fusion-title
    h4 = wrapper.find("h4")
    if not h4:
        return None

    # Address block is in the first fusion-text div (not hidden)
    addr_div = wrapper.find("div", class_="fusion-text")
    if not addr_div:
        return None

    text = addr_div.get_text(separator="\n", strip=False)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    # Find the city/province/postal line
    street = None
    city = None
    province = None
    postal_code = None

    for i, line in enumerate(lines):
        m = _ADDR_LINE_RE.match(line)
        if m:
            city = m.group(1)
            province = m.group(2)
            postal_code = m.group(3)
            if i > 0:
                street = lines[i - 1]
            break

    if not street or not city or province not in _PROVINCES:
        return None

    # Phone: look for tel: link or plain text in a non-hidden sibling div
    phone = None
    tel_link = wrapper.find("a", href=re.compile(r"^tel:"))
    if tel_link:
        phone = tel_link.get_text(strip=True)

    return StoreRecord(
        brand="Pita Pit",
        store_name=f"Pita Pit - {city}",
        address=street,
        city=city,
        province=province,
        postal_code=postal_code,
        phone=phone,
        lat=None,
        lng=None,
        source_url=URL,
        scraped_at=ts,
    )


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Pita Pit locations from the HTML page, filter to Ontario."""
    client = make_client()
    try:
        resp = client.get(URL)
        resp.raise_for_status()
    finally:
        client.close()

    soup = BeautifulSoup(resp.text, "html.parser")
    ts = now_iso()

    records: list[StoreRecord] = []
    seen: set[tuple[str, str]] = set()
    for wrapper in soup.select("div.fusion-column-wrapper"):
        rec = _parse_card(wrapper, ts)
        if rec and rec.province == "ON":
            key = (rec.address, rec.city)
            if key not in seen:
                seen.add(key)
                records.append(rec)

    path = write_brand_json("pita_pit", records)
    print(f"  Pita Pit: {len(records)} Ontario stores")
    return records, path
