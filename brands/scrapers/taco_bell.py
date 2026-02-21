"""Scraper for Taco Bell via the TicTuk/OpenRest API.

Two-step process:
  1. GET https://api.us.tictuk.com/v1/tenants/{chain_id}/urls?$pick=webFlowAddressURL
     -> returns a dynamic URL prefix
  2. Append &lang=en&type=getBranchesList&cust=openRest&noFilter=true to that URL
     -> returns all branches in {"msg": [...]}

Filter to Ontario by parsing province from address.formatted field.
Address formats are inconsistent — some use ", ON", some "Ontario", some "(ON)".
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

# ── Constants ─────────────────────────────────────────────────────────

CHAIN_ID = "e1f0fcc5-822e-2df4-188d-f6ced0e518c3"
URLS_ENDPOINT = f"https://api.us.tictuk.com/v1/tenants/{CHAIN_ID}/urls"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Accept": "application/json",
    "Origin": "https://www.tacobell.ca",
}


# ── Helpers ───────────────────────────────────────────────────────────

def _is_ontario(formatted: str) -> bool:
    """Check if a formatted address string is in Ontario.

    Handles varied formats:
      "1668 Bath Road, Kingston, ON"
      "293 Bay Street, Unit #ER4, Sault Ste. Marie, Ontario, Canada"
      "Fairview Mall, 1800 Sheppard Ave E Toronto Ontario (ON) M2J5A7"
      "100 Bayshore Dr fc 12, Nepean, ON K2B 8C1, Canada"
    """
    upper = formatted.upper()
    # Match ", ON" or " ON " or " ON," or ends with " ON"
    if re.search(r'[,\s]ON[\s,]', upper) or upper.endswith(" ON"):
        return True
    if "ONTARIO" in upper:
        return True
    return False


def _parse_address(formatted: str, title: str) -> tuple[str, str]:
    """Extract (street, city) from a formatted address string.

    The format is highly inconsistent. Strategy:
      - Split by comma, first part is usually street
      - City is trickier: sometimes second part, sometimes embedded

    For title-based extraction as fallback, title is like:
      "Taco Bell 1668 Bath Road" or "TB 906320 - Whitby"
    """
    parts = [p.strip() for p in formatted.split(",")]
    if not parts:
        return "", ""

    street = parts[0]

    # Try to find city from the comma-separated parts
    # Skip parts that are just province codes, postal codes, or "Canada"/"CA"
    city = ""
    for part in parts[1:]:
        part = part.strip()
        # Skip province-only parts, postal codes, country
        if re.match(r'^(ON|QC|BC|AB|MB|SK|NS|NB|NL|PE|NT|YT|NU)(\s|$)', part.upper()):
            continue
        if re.match(r'^[A-Z]\d[A-Z]\s*\d[A-Z]\d$', part.upper()):
            continue
        if part.upper() in ("CANADA", "CA"):
            continue
        # Skip if it looks like "ON K2B 8C1" (province + postal)
        if re.match(r'^(ON|QC|BC|AB)\s+[A-Z]\d[A-Z]', part.upper()):
            continue
        # Skip "Ontario" or "Ontario, Canada" trailing parts
        if part.upper() in ("ONTARIO",):
            continue
        city = part
        break

    return street, city


# ── Public API ────────────────────────────────────────────────────────

def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Taco Bell stores in Ontario."""
    ts = now_iso()
    records: list[StoreRecord] = []

    client = httpx.Client(headers=HEADERS, timeout=30)
    try:
        # Step 1: Get the dynamic URL prefix
        resp = client.get(URLS_ENDPOINT, params={"$pick": "webFlowAddressURL"})
        resp.raise_for_status()
        data = resp.json()

        base_url = data.get("webFlowAddressURL", "")
        if not base_url:
            print("  Taco Bell: ERROR — could not get webFlowAddressURL")
            return [], write_brand_json("taco_bell", [])

        # Step 2: Fetch all branches
        separator = "&" if "?" in base_url else "?"
        branches_url = f"{base_url}{separator}lang=en&type=getBranchesList&cust=openRest&noFilter=true"

        resp = client.get(branches_url)
        resp.raise_for_status()
        raw = resp.json()

        # Response wraps branches in "msg" key
        branches = raw.get("msg", []) if isinstance(raw, dict) else raw
        if not isinstance(branches, list):
            print(f"  Taco Bell: ERROR — unexpected response type: {type(branches)}")
            return [], write_brand_json("taco_bell", [])

        seen_ids: set[str] = set()

        for b in branches:
            addr_obj = b.get("address", {})
            formatted = addr_obj.get("formatted", "")

            if not _is_ontario(formatted):
                continue

            branch_id = str(b.get("id", ""))
            if not branch_id or branch_id in seen_ids:
                continue
            seen_ids.add(branch_id)

            # Title is nested: {"en_US": "Taco Bell 1668 Bath Road"}
            title_obj = b.get("title", {})
            title = title_obj.get("en_US", "") if isinstance(title_obj, dict) else str(title_obj)

            street, city = _parse_address(formatted, title)
            if not street or not city:
                continue

            # Coordinates are in address.latLng
            lat_lng = addr_obj.get("latLng", {})
            lat = lat_lng.get("lat")
            lng = lat_lng.get("lng")

            # Phone is in contact.phone
            contact = b.get("contact", {})
            phone = contact.get("phone") if isinstance(contact, dict) else None

            records.append(StoreRecord(
                brand="Taco Bell",
                store_name=f"Taco Bell - {city}",
                address=street,
                city=city,
                province="ON",
                postal_code=None,
                phone=phone,
                lat=lat,
                lng=lng,
                source_url="https://www.tacobell.ca/en/store-finder",
                scraped_at=ts,
            ))
    finally:
        client.close()

    path = write_brand_json("taco_bell", records)

    coord_count = sum(1 for r in records if r.lat is not None)
    print(f"  Taco Bell: {len(records)} Ontario stores ({coord_count}/{len(records)} have coordinates)")

    return records, path
