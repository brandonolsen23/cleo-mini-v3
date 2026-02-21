"""Longo's store scraper (Ontario).

Source: https://www.longos.com/store-finder
Method: Single HTTP GET, parse `markersData` JavaScript array embedded in page.
Each entry: {id, name, lat, lng, address, phone, url}
"""

from __future__ import annotations

import html
import re

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://www.longos.com/store-finder"
BRAND = "Longo's"
SLUG = "longos"

# Match start of the markersData array
MARKERS_START_RE = re.compile(r"markersData\s*=\s*\[")

# Field extractors for JS object literals (unquoted keys, quoted string values)
def _js_field(obj: str, key: str) -> str | None:
    m = re.search(rf'{key}\s*:\s*"((?:[^"\\]|\\.)*)"', obj)
    return m.group(1) if m else None


def _js_float(obj: str, key: str) -> float | None:
    m = re.search(rf"{key}\s*:\s*([-\d.]+)", obj)
    return float(m.group(1)) if m else None


def scrape() -> tuple[list[StoreRecord], "Path"]:
    client = make_client()
    resp = client.get(SOURCE_URL)
    resp.raise_for_status()

    m = MARKERS_START_RE.search(resp.text)
    if not m:
        raise RuntimeError("Could not find markersData array in page")

    # Find the matching closing bracket
    start = m.end() - 1  # include the [
    depth = 0
    end = start
    for i, c in enumerate(resp.text[start:]):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        if depth == 0:
            end = start + i + 1
            break

    raw_array = resp.text[start:end]
    records: list[StoreRecord] = []
    ts = now_iso()

    for entry in re.finditer(r"\{[^}]+\}", raw_array):
        obj = entry.group(0)

        name = _js_field(obj, "name")
        if not name:
            continue
        name = html.unescape(name)

        lat = _js_float(obj, "lat")
        lng = _js_float(obj, "lng")

        addr_raw = _js_field(obj, "address") or ""
        phone = _js_field(obj, "phone")

        # Address format: "1 Rossland Rd East, Ajax, , L1Z1Z2"
        parts = [p.strip() for p in addr_raw.split(",")]
        # Remove empty parts (the double-comma gap)
        parts = [p for p in parts if p]

        address = parts[0] if parts else addr_raw
        city = parts[1] if len(parts) > 1 else ""
        postal_code = parts[-1] if len(parts) > 2 else None

        records.append(
            StoreRecord(
                brand=BRAND,
                store_name=name,
                address=address,
                city=city,
                province="ON",
                postal_code=postal_code,
                phone=phone,
                lat=lat,
                lng=lng,
                source_url=SOURCE_URL,
                scraped_at=ts,
            )
        )

    path = write_brand_json(SLUG, records)
    return records, path
