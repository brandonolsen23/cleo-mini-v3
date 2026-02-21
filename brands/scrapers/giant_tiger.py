"""Giant Tiger store locator scraper (Ontario).

Two-level crawl:
1. Fetch /on/ province page to get city URLs from RLS.defaultData markers
2. Fetch each city page to get individual store markers with full address data

The RLS.defaultData JSON uses trailing commas (JS-style) and the marker
info field is an HTML-wrapped JSON object inside a <div class="tlsmap_popup">.

Source: https://stores.gianttiger.com/on/
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

BASE_URL = "https://stores.gianttiger.com"
BRAND = "Giant Tiger"


def _extract_rls_data(html: str) -> dict | None:
    """Extract RLS.defaultData using bracket-balanced parsing.

    The JSON blob has trailing commas which standard json.loads rejects,
    so we strip them before parsing.
    """
    m = re.search(r"RLS\.defaultData\s*=\s*", html)
    if not m:
        return None

    start = m.end()
    depth = 0
    end = start

    for i in range(start, len(html)):
        c = html[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0:
            end = i + 1
            break

    blob = html[start:end]
    # Fix trailing commas before } or ]
    blob = re.sub(r",\s*([}\]])", r"\1", blob)

    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def _parse_marker_info(info_html: str) -> dict:
    """Extract JSON data from the HTML-wrapped info field.

    Format: <div class="tlsmap_popup">{ "city":"...", "url":"...", ... }</div>
    """
    soup = BeautifulSoup(info_html, "lxml")
    div = soup.find("div", class_="tlsmap_popup")
    if not div:
        # Try parsing raw text as JSON
        text = soup.get_text(strip=True)
    else:
        text = div.get_text(strip=True)

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape Giant Tiger Ontario stores."""
    client = make_client()
    ts = now_iso()

    # Step 1: Get city URLs from province page
    resp = client.get(f"{BASE_URL}/on/")
    resp.raise_for_status()

    province_data = _extract_rls_data(resp.text)
    if not province_data:
        raise RuntimeError("Could not find RLS.defaultData on Giant Tiger /on/ page")

    city_urls: list[str] = []
    for marker in province_data.get("markerData", []):
        info = _parse_marker_info(marker.get("info", ""))
        url = info.get("url", "")
        if url:
            city_urls.append(url)

    print(f"  Giant Tiger: {len(city_urls)} cities found, fetching stores...", end="", flush=True)

    # Step 2: Fetch each city page for individual store data
    records: list[StoreRecord] = []
    seen_fids: set[str] = set()

    for i, url in enumerate(city_urls):
        full_url = url if url.startswith("http") else f"{BASE_URL}{url}"
        try:
            resp = client.get(full_url)
            if resp.status_code != 200:
                continue
        except Exception:
            continue

        city_data = _extract_rls_data(resp.text)
        if not city_data:
            continue

        for marker in city_data.get("markerData", []):
            info = _parse_marker_info(marker.get("info", ""))

            fid = info.get("fid", "")
            if fid in seen_fids:
                continue
            seen_fids.add(fid)

            address = info.get("address_1", "")
            if not address:
                continue

            city_name = info.get("city", "")
            location_name = info.get("location_name", f"Giant Tiger - {city_name}")

            records.append(
                StoreRecord(
                    brand=BRAND,
                    store_name=location_name,
                    address=address,
                    city=city_name,
                    province="ON",
                    postal_code=info.get("post_code"),
                    phone=None,
                    lat=float(marker["lat"]) if marker.get("lat") else None,
                    lng=float(marker["lng"]) if marker.get("lng") else None,
                    source_url=full_url,
                    scraped_at=ts,
                )
            )

        if (i + 1) % 20 == 0:
            print(f" {i + 1}...", end="", flush=True)

        time.sleep(0.2)

    print(f" done ({len(records)} stores)")

    path = write_brand_json("giant_tiger", records)
    return records, path
