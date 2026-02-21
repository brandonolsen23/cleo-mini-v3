"""Generic scraper for Yext-powered directory sites.

Covers brands that use the Yext directory pattern:
  province page -> city links -> store pages

Supports two parsing modes:
  - Classic Yext: `c-address-*` CSS classes + `meta[itemprop=latitude/longitude]`
  - Modern Yext / JSON-LD: `application/ld+json` structured data

Tested on: Wendy's, Subway, Five Guys, Tim Hortons, Chipotle, Mucho Burrito, Papa John's.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

# ── Brand configs ──────────────────────────────────────────────────────


@dataclass
class BrandConfig:
    province_url: str
    brand_name: str
    # Optional: base path for store detail links when different from province path.
    # e.g. Tim Hortons lists at /en/locations-list/on/ but stores at /en/on/
    store_base: str | None = None
    # If True, accept store links anywhere on the same domain (e.g. Five Guys
    # where stores live at the root like /329-yonge-street)
    root_level_stores: bool = False


BRANDS: dict[str, BrandConfig] = {
    "wendys": BrandConfig(
        "https://locations.wendys.com/canada/on",
        "Wendy's",
    ),
    "subway": BrandConfig(
        "https://restaurants.subway.com/canada/on",
        "Subway",
    ),
    "five_guys": BrandConfig(
        "https://restaurants.fiveguys.ca/on",
        "Five Guys",
        root_level_stores=True,
    ),
    "tim_hortons": BrandConfig(
        "https://locations.timhortons.ca/en/locations-list/on",
        "Tim Hortons",
        store_base="/en/on",
    ),
    "chipotle": BrandConfig(
        "https://locations.chipotle.ca/on",
        "Chipotle",
    ),
    "mucho_burrito": BrandConfig(
        "https://locations.muchoburrito.com/en-ca/locations-list/on",
        "Mucho Burrito",
        store_base="/en-ca/on",
    ),
    "papa_johns": BrandConfig(
        "https://locations.papajohns.com/canada/on",
        "Papa John's",
    ),
}


def _is_store_link(path: str, province_path: str) -> bool:
    """True if the link goes to a store page (has address slug after city)."""
    after = path.split(province_path)[-1].strip("/")
    return after.count("/") >= 1


def _extract_links(
    soup: BeautifulSoup,
    province_url: str,
    cfg: BrandConfig,
) -> tuple[list[str], list[str]]:
    """Extract city links and store links from a directory page.

    Returns (city_urls, store_urls).
    """
    parsed_base = urlparse(province_url)
    province_path = parsed_base.path.rstrip("/")
    store_base = cfg.store_base.rstrip("/") if cfg.store_base else None

    city_urls: list[str] = []
    store_urls: list[str] = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(province_url, href)
        parsed = urlparse(full)

        # Must be same host
        if parsed.hostname != parsed_base.hostname:
            continue

        path = parsed.path.rstrip("/")
        if not path or path in seen:
            continue

        # Check if it's a store link under the alternate store_base path
        if store_base and path.startswith(store_base + "/"):
            if path not in seen:
                seen.add(path)
                url = f"{parsed_base.scheme}://{parsed_base.hostname}{path}"
                store_urls.append(url)
            continue

        # For root-level store brands (e.g. Five Guys), any link with 1+
        # path segments that isn't the province page is a potential store link
        if cfg.root_level_stores:
            segments = path.strip("/").split("/")
            if path.startswith(province_path + "/"):
                # Under province path — city or store
                if path == province_path:
                    continue
                if path in seen:
                    continue
                seen.add(path)
                url = f"{parsed_base.scheme}://{parsed_base.hostname}{path}"
                if _is_store_link(path, province_path):
                    store_urls.append(url)
                else:
                    city_urls.append(url)
            elif len(segments) >= 1 and not path.startswith("/assets"):
                # Root-level store link (outside province path)
                if path in seen:
                    continue
                seen.add(path)
                url = f"{parsed_base.scheme}://{parsed_base.hostname}{path}"
                store_urls.append(url)
            continue

        # Standard: must be under province path
        if not path.startswith(province_path + "/"):
            continue
        if path == province_path:
            continue
        if path in seen:
            continue
        seen.add(path)

        url = f"{parsed_base.scheme}://{parsed_base.hostname}{path}"
        if _is_store_link(path, province_path):
            store_urls.append(url)
        else:
            city_urls.append(url)

    return city_urls, store_urls


def _parse_json_ld(soup: BeautifulSoup) -> dict | None:
    """Extract address and coordinates from JSON-LD structured data."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue

        # Handle direct objects, plain arrays, and @graph arrays
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and "@graph" in data:
            items = data["@graph"]
        else:
            items = [data]
        for item in items:
            addr = item.get("address", {})
            if not addr.get("streetAddress"):
                continue

            street_raw = addr["streetAddress"]
            # Some sites embed full address "123 Main St, City, ON, K1A0B1"
            # in streetAddress — take just the street portion
            street = street_raw.split(",")[0].strip()

            fields: dict[str, str | float | None] = {
                "address": street,
                "city": addr.get("addressLocality", ""),
                "province": addr.get("addressRegion", "ON"),
                "postal_code": addr.get("postalCode"),
            }

            # Coordinates from JSON-LD GeoCoordinates
            geo = item.get("geo", {})
            if geo.get("latitude"):
                try:
                    fields["lat"] = float(geo["latitude"])
                except (ValueError, TypeError):
                    pass
            if geo.get("longitude"):
                try:
                    fields["lng"] = float(geo["longitude"])
                except (ValueError, TypeError):
                    pass

            # Phone
            if item.get("telephone"):
                fields["phone"] = item["telephone"]

            return fields

    return None


def _parse_yext_blob_coords(soup: BeautifulSoup) -> tuple[float | None, float | None]:
    """Extract coordinates from URL-encoded Yext data blob in the page source."""
    html_str = str(soup)
    # Look for yextDisplayCoordinate in URL-encoded JSON
    m = re.search(
        r'%22yextDisplayCoordinate%22%3A%7B%22latitude%22%3A([\d.-]+)%2C%22longitude%22%3A([\d.-]+)',
        html_str,
    )
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            pass

    # Also try decoded JSON pattern
    m = re.search(
        r'"yextDisplayCoordinate"\s*:\s*\{\s*"latitude"\s*:\s*([\d.-]+)\s*,\s*"longitude"\s*:\s*([\d.-]+)',
        html_str,
    )
    if m:
        try:
            return float(m.group(1)), float(m.group(2))
        except ValueError:
            pass

    return None, None


def _parse_store_page(soup: BeautifulSoup) -> dict | None:
    """Extract store data from a Yext directory store page.

    Tries three extraction methods in order:
    1. Classic Yext CSS classes (c-address-*) + itemprop meta tags
    2. JSON-LD structured data
    3. Yext URL-encoded data blob (coordinates only)
    """
    fields: dict[str, str | float | None] = {}

    # Method 1: Classic Yext CSS classes
    for css_class, key in [
        ("c-address-street-1", "street"),
        ("c-address-street-2", "street2"),
        ("c-address-city", "city"),
        ("c-address-state", "province"),
        ("c-address-postal-code", "postal_code"),
    ]:
        el = soup.find(class_=css_class)
        if el:
            fields[key] = el.get_text(strip=True)

    # Coordinates — itemprop meta tags
    for prop, key in [("latitude", "lat"), ("longitude", "lng")]:
        el = soup.find("meta", itemprop=prop)
        if el and el.get("content"):
            try:
                fields[key] = float(el["content"])
            except ValueError:
                pass

    # Phone
    el = soup.find(itemprop="telephone")
    if el:
        fields["phone"] = el.get_text(strip=True)

    # If classic CSS classes found a street address, use them
    if fields.get("street"):
        address = fields["street"]
        if fields.get("street2"):
            address += f", {fields['street2']}"
        return {
            "address": address,
            "city": fields.get("city", ""),
            "province": fields.get("province", "ON"),
            "postal_code": fields.get("postal_code"),
            "phone": fields.get("phone"),
            "lat": fields.get("lat"),
            "lng": fields.get("lng"),
        }

    # Method 2: JSON-LD fallback
    ld_fields = _parse_json_ld(soup)
    if ld_fields:
        # Carry forward phone from itemprop if JSON-LD didn't have one
        if not ld_fields.get("phone") and fields.get("phone"):
            ld_fields["phone"] = fields["phone"]

        # Method 3: If JSON-LD didn't have coordinates, try Yext blob
        if not ld_fields.get("lat"):
            lat, lng = _parse_yext_blob_coords(soup)
            if lat is not None:
                ld_fields["lat"] = lat
                ld_fields["lng"] = lng

        return ld_fields

    return None


def scrape_brand(slug: str) -> tuple[list[StoreRecord], Path]:
    """Scrape a single brand from its Yext directory."""
    cfg = BRANDS[slug]
    province_url = cfg.province_url
    brand_name = cfg.brand_name
    client = make_client()
    ts = now_iso()

    # Step 1: Fetch province page
    resp = client.get(province_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    city_urls, store_urls = _extract_links(soup, province_url, cfg)
    print(f"  {brand_name}: {len(city_urls)} cities, {len(store_urls)} direct stores")

    # Step 2: Crawl city pages to discover remaining store URLs
    for city_url in city_urls:
        time.sleep(0.2)
        resp = client.get(city_url)
        if resp.status_code != 200:
            continue
        city_soup = BeautifulSoup(resp.text, "lxml")
        _, city_store_urls = _extract_links(city_soup, province_url, cfg)
        for url in city_store_urls:
            if url not in store_urls:
                store_urls.append(url)

    print(f"  {brand_name}: {len(store_urls)} total stores to scrape")

    # Step 3: Scrape each store page
    records: list[StoreRecord] = []
    for store_url in store_urls:
        time.sleep(0.2)
        resp = client.get(store_url)
        if resp.status_code != 200:
            continue
        store_soup = BeautifulSoup(resp.text, "lxml")
        fields = _parse_store_page(store_soup)
        if not fields:
            continue

        records.append(
            StoreRecord(
                brand=brand_name,
                store_name=f"{brand_name} - {fields['city']}",
                address=fields["address"],
                city=fields["city"],
                province=fields["province"],
                postal_code=fields["postal_code"],
                phone=fields.get("phone"),
                lat=fields.get("lat"),
                lng=fields.get("lng"),
                source_url=store_url,
                scraped_at=ts,
            )
        )

    path = write_brand_json(slug, records)
    return records, path


def scrape_all() -> list[tuple[str, int, Path]]:
    """Scrape all Yext directory brands."""
    results = []
    for slug in BRANDS:
        records, path = scrape_brand(slug)
        results.append((slug, len(records), path))
    return results


# Individual brand functions for run.py registration
def scrape_wendys() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("wendys")


def scrape_subway() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("subway")


def scrape_five_guys() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("five_guys")


def scrape_tim_hortons() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("tim_hortons")


def scrape_chipotle() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("chipotle")


def scrape_mucho_burrito() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("mucho_burrito")


def scrape_papa_johns() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("papa_johns")
