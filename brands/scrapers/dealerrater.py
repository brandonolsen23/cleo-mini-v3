"""DealerRater.ca automotive dealership scraper (Ontario).

Covers 21 auto brands via dealerrater.ca/directory/Ontario/{Brand}/.
Two-step: directory pages for dealer links, then individual pages for JSON-LD.

Source: https://www.dealerrater.ca/directory/Ontario/{make}/
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

BASE_URL = "https://www.dealerrater.ca"

# Brand configs: (url_slug, output_slug, display_name)
# URL slugs match the CSV's dealerrater.ca URLs (case-sensitive as provided)
BRANDS = {
    "toyota": ("toyota", "toyota", "Toyota"),
    "lexus": ("Lexus", "lexus", "Lexus"),
    "honda": ("Honda", "honda", "Honda"),
    "acura": ("Acura", "acura", "Acura"),
    "nissan": ("Nissan", "nissan", "Nissan"),
    "infiniti": ("Infiniti", "infiniti", "Infiniti"),
    "kia": ("Kia", "kia", "Kia"),
    "hyundai": ("Hyundai", "hyundai", "Hyundai"),
    "volvo": ("Volvo", "volvo", "Volvo"),
    "chrysler": ("Chrysler", "chrysler", "Chrysler"),
    "ford": ("Ford", "ford", "Ford"),
    "gmc": ("GMC", "gmc", "GMC"),
    "mercedes_benz": ("Mercedes-Benz", "mercedes_benz", "Mercedes-Benz"),
    "porsche": ("Porsche", "porsche", "Porsche"),
    "land_rover": ("Land-Rover", "land_rover", "Land Rover"),
    "volkswagen": ("Volkswagen", "volkswagen", "Volkswagen"),
    "audi": ("Audi", "audi", "Audi"),
    "bmw": ("BMW", "bmw", "BMW"),
    "jaguar": ("Jaguar", "jaguar", "Jaguar"),
    "mazda": ("Mazda", "mazda", "Mazda"),
    "mitsubishi": ("Mitsubishi", "mitsubishi", "Mitsubishi"),
}

DEALER_LINK_RE = re.compile(r"/dealer/([^/]+)-review-(\d+)/")


def _get_dealer_links(client, url_slug: str) -> list[tuple[str, str, str]]:
    """Crawl directory pages to collect (dealer_name, dealer_href, city_province).

    Stops when a page returns only already-seen dealers (DealerRater repeats
    content on pages past the last real page).
    """
    dealers = []
    seen_hrefs: set[str] = set()
    page = 1

    while True:
        url = f"{BASE_URL}/directory/Ontario/{url_slug}/"
        if page > 1:
            url += f"page{page}/"

        resp = client.get(url)
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, "lxml")
        results = soup.find_all("div", class_="search-result")

        if not results:
            break

        new_on_page = 0
        for r in results:
            name_el = r.find("a", class_="dealer-name-link")
            if not name_el:
                continue

            href = name_el.get("href", "")
            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            new_on_page += 1

            name_span = name_el.find("span", class_="notranslate")
            name = name_span.get_text(strip=True) if name_span else name_el.get_text(strip=True)
            # Strip leading number+dot: "1.ToyotaTown" -> "ToyotaTown"
            name = re.sub(r"^\d+\.\s*", "", name)

            # Get city from the second notranslate span
            loc_spans = r.find_all("span", class_="notranslate")
            city_prov = loc_spans[1].get_text(strip=True) if len(loc_spans) > 1 else ""

            dealers.append((name, href, city_prov))

        # Stop if no new dealers found on this page (content is repeating)
        if new_on_page == 0:
            break

        page += 1
        time.sleep(0.3)

    return dealers


def _get_dealer_detail(client, href: str) -> dict | None:
    """Fetch individual dealer page and extract JSON-LD address data."""
    url = f"{BASE_URL}{href}"
    try:
        resp = client.get(url)
        if resp.status_code != 200:
            return None
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "lxml")

    # Extract JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, list):
                data = data[0]
            addr = data.get("address", {})
            if addr.get("streetAddress"):
                return {
                    "street": addr.get("streetAddress", ""),
                    "city": addr.get("addressLocality", ""),
                    "province": addr.get("addressRegion", ""),
                    "postal_code": addr.get("postalCode"),
                    "phone": data.get("telephone"),
                }
        except (json.JSONDecodeError, AttributeError):
            continue

    return None


def scrape_brand(brand_key: str) -> tuple[list[StoreRecord], Path]:
    """Scrape a single automotive brand from DealerRater."""
    url_slug, out_slug, brand_name = BRANDS[brand_key]

    client = make_client()
    # Add referer for DealerRater
    client.headers["Referer"] = f"{BASE_URL}/directory/Ontario/"

    print(f"    {brand_name}: crawling directory...", end="", flush=True)
    dealer_links = _get_dealer_links(client, url_slug)
    print(f" {len(dealer_links)} dealers found, fetching details...", end="", flush=True)

    records: list[StoreRecord] = []
    ts = now_iso()
    fetched = 0

    for name, href, city_prov in dealer_links:
        detail = _get_dealer_detail(client, href)
        fetched += 1

        if detail and detail.get("province") == "ON":
            records.append(
                StoreRecord(
                    brand=brand_name,
                    store_name=name,
                    address=detail["street"],
                    city=detail["city"],
                    province="ON",
                    postal_code=detail.get("postal_code"),
                    phone=detail.get("phone"),
                    lat=None,
                    lng=None,
                    source_url=f"{BASE_URL}{href}",
                    scraped_at=ts,
                )
            )

        if fetched % 50 == 0:
            print(f" {fetched}...", end="", flush=True)

        time.sleep(0.3)

    print(f" done ({len(records)} ON)")

    path = write_brand_json(out_slug, records)
    return records, path


def scrape_all() -> list[tuple[str, int, Path]]:
    """Scrape all automotive brands."""
    results = []
    for key in BRANDS:
        records, path = scrape_brand(key)
        out_slug = BRANDS[key][1]
        results.append((out_slug, len(records), path))
    return results
