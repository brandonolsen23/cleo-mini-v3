"""FreshCo store scraper (Ontario only).

Source: https://www.freshco.com/sitemap/stores/sitemap.xml -> individual store pages
Method: Fetch sitemap XML for store URLs, then fetch each page and extract
        JSON-LD schema.org GroceryStore structured data.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from xml.etree import ElementTree

from .base import StoreRecord, make_client, now_iso, write_brand_json

SITEMAP_URL = "https://www.freshco.com/sitemap/stores/sitemap.xml"
BRAND = "FreshCo"
SLUG = "freshco"
REQUEST_DELAY = 0.5  # seconds between store page requests


def _get_store_urls(client) -> list[str]:
    resp = client.get(SITEMAP_URL)
    resp.raise_for_status()

    root = ElementTree.fromstring(resp.text)
    # Sitemap XML namespace
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [loc.text for loc in root.findall(".//sm:loc", ns) if loc.text]
    return urls


def _extract_jsonld(html: str) -> dict | None:
    """Find and parse the GroceryStore JSON-LD block from page HTML."""
    # Look for <script type="application/ld+json"> blocks
    pattern = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL,
    )
    for m in pattern.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue

        # Could be a single object or a list
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") == "GroceryStore":
                return item
    return None


def _format_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
    return raw


def _format_postal(raw: str | None) -> str | None:
    if not raw:
        return None
    clean = raw.replace(" ", "").upper()
    if len(clean) == 6:
        return f"{clean[:3]} {clean[3:]}"
    return raw


def scrape() -> tuple[list[StoreRecord], Path]:
    client = make_client()
    urls = _get_store_urls(client)
    print(f"  FreshCo: found {len(urls)} store URLs in sitemap")

    records: list[StoreRecord] = []
    ts = now_iso()
    errors = 0

    for i, url in enumerate(urls):
        try:
            resp = client.get(url)
            if resp.status_code != 200:
                errors += 1
                continue

            store = _extract_jsonld(resp.text)
            if not store:
                errors += 1
                continue

            addr = store.get("address", {})
            province = addr.get("addressRegion", "")

            # Filter to Ontario only
            if province != "ON":
                continue

            records.append(
                StoreRecord(
                    brand=BRAND,
                    store_name=store.get("name", "FreshCo"),
                    address=addr.get("streetAddress", ""),
                    city=addr.get("addressLocality", ""),
                    province=province,
                    postal_code=_format_postal(addr.get("postalCode")),
                    phone=_format_phone(store.get("telephone")),
                    lat=None,
                    lng=None,
                    source_url=url,
                    scraped_at=ts,
                )
            )
        except Exception as e:
            print(f"  FreshCo: error on {url}: {e}")
            errors += 1

        if i < len(urls) - 1:
            time.sleep(REQUEST_DELAY)

    if errors:
        print(f"  FreshCo: {errors} pages skipped (errors/404s/no-data)")

    path = write_brand_json(SLUG, records)
    return records, path
