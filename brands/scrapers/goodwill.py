"""Goodwill Industries store scraper (Ontario).

Source: https://www.goodwillindustries.ca/find-a-goodwill/
Method: Single HTTP GET, parse TBK_HYDRATE_COMPONENTS JSON blob embedded in page.
Locations in `defaultLocations` array with address, phone, lat/lng.
"""

from __future__ import annotations

import json
import re

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://www.goodwillindustries.ca/find-a-goodwill/"
BRAND = "Goodwill"
SLUG = "goodwill"

# Match start of the hydration assignment
HYDRATE_START_RE = re.compile(r"TBK_HYDRATE_COMPONENTS\s*=\s*\{")


def _parse_address(addr_str: str) -> dict:
    """Parse 'street,\\ncity, ON postal' into components."""
    # Replace literal newlines
    addr_str = addr_str.replace("\\n", "\n")
    lines = [l.strip() for l in addr_str.split("\n") if l.strip()]

    result = {"address": "", "city": "", "province": "ON", "postal_code": None}

    if not lines:
        return result

    result["address"] = lines[0].rstrip(",")

    if len(lines) > 1:
        # Second line: "City, ON PostalCode"
        city_line = lines[1]
        # Try to extract postal code
        pm = re.search(r"([A-Z]\d[A-Z]\s*\d[A-Z]\d)", city_line)
        if pm:
            result["postal_code"] = pm.group(1)
            city_line = city_line[: pm.start()].strip().rstrip(",")
        # Remove province
        city_line = re.sub(r",?\s*ON\s*$", "", city_line).strip().rstrip(",")
        result["city"] = city_line

    return result


def scrape() -> tuple[list[StoreRecord], "Path"]:
    client = make_client()
    resp = client.get(SOURCE_URL)
    resp.raise_for_status()

    m = HYDRATE_START_RE.search(resp.text)
    if not m:
        raise RuntimeError("Could not find TBK_HYDRATE_COMPONENTS in page")

    # Find matching closing brace using bracket balancing
    start = m.end() - 1  # include the opening {
    depth = 0
    end = start
    for i, c in enumerate(resp.text[start:]):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0:
            end = start + i + 1
            break

    hydrate = json.loads(resp.text[start:end])

    records: list[StoreRecord] = []
    ts = now_iso()

    # Walk the hydration object (keyed by UUIDs) to find defaultLocations
    # defaultLocations is at the top level of each component (not under "props")
    seen_titles: set[str] = set()

    for key, component in hydrate.items():
        if not isinstance(component, dict):
            continue

        locations = component.get("defaultLocations", [])
        if not locations:
            continue

        for loc in locations:
            # Only use entries that have marker data (lat/lng)
            marker = loc.get("marker")
            if not marker:
                continue

            title = loc.get("title", "")
            if title in seen_titles:
                continue
            seen_titles.add(title)

            addr_raw = loc.get("address", "")
            phone = loc.get("phone")
            pos = marker.get("position", {})
            lat = pos.get("lat")
            lng = pos.get("lng")

            fields = _parse_address(addr_raw)

            records.append(
                StoreRecord(
                    brand=BRAND,
                    store_name=title,
                    address=fields["address"],
                    city=fields["city"],
                    province=fields["province"],
                    postal_code=fields["postal_code"],
                    phone=phone,
                    lat=lat,
                    lng=lng,
                    source_url=SOURCE_URL,
                    scraped_at=ts,
                )
            )

    path = write_brand_json(SLUG, records)
    return records, path
