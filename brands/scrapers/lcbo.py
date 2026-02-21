"""LCBO store locator scraper (Ontario).

Uses the Amasty Store Locator AJAX endpoint with a single center point
and large radius to cover all of Ontario. Paginates through results
(10 per page).

Source: https://www.lcbo.com/en/amlocator/index/ajax/
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

AJAX_URL = "https://www.lcbo.com/en/amlocator/index/ajax/"
BRAND = "LCBO"

# Center of Ontario with large radius to capture all stores
CENTER_LAT = 49.0
CENTER_LNG = -85.0
RADIUS = 5000
PAGE_SIZE = 10


def _parse_popup(html: str) -> dict:
    """Extract store details from Amasty popup HTML.

    Structure:
      <a class="amlocator-store-map-name">Store Name</a>
      <span class="amlocator-info-address">123 Street City</span>, ON POSTAL
      <a class="amlocator-phone-number">(XXX) XXX-XXXX</a>
      <a href="https://www.google.com/maps/dir/Your+Location/CityName...">

    The address span includes the city appended at the end.
    We extract the city from the Google Maps direction link.
    """
    soup = BeautifulSoup(html, "lxml")
    result: dict = {}

    # Store name
    name_el = soup.find("a", class_="amlocator-store-map-name")
    if name_el:
        result["name"] = name_el.get_text(strip=True)

    # Address from dedicated span
    addr_span = soup.find("span", class_="amlocator-info-address")
    if addr_span:
        result["address"] = addr_span.get_text(strip=True)

    # Postal code from info-popup text (after the span: ", ON N2G1B7")
    info = soup.find(class_="amlocator-info-popup")
    if info:
        text = info.get_text(" ", strip=True)
        m = re.search(r"[A-Z]\d[A-Z]\s*\d[A-Z]\d", text)
        if m:
            result["postal_code"] = m.group(0)

    # Phone from dedicated link
    phone_el = soup.find("a", class_="amlocator-phone-number")
    if phone_el:
        phone_text = phone_el.get_text(strip=True)
        if phone_text:
            result["phone"] = phone_text

    # City from Google Maps direction link
    maps_link = soup.find("a", class_="amlocator-link-get-direction")
    if maps_link:
        href = maps_link.get("href", "")
        # Format: .../dir/Your+Location/CityName, 123 Street...
        # or: .../dir/Your+Location/CityName\n...
        m = re.search(r"/dir/Your\+Location/([^,/\n]+)", href)
        if m:
            city = m.group(1).replace("+", " ").strip()
            # Clean up: sometimes has extra text like "Kitchener"
            result["city"] = city

    # If city found, separate it from the address
    if result.get("city") and result.get("address"):
        addr = result["address"]
        city = result["city"]
        # Address often ends with city name: "340 King Street West Kitchener"
        if addr.lower().endswith(city.lower()):
            result["address"] = addr[: -len(city)].strip()
        elif addr.lower().endswith(city.lower().replace("-", " ")):
            result["address"] = addr[: -len(city.replace("-", " "))].strip()

    return result


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape LCBO Ontario stores."""
    client = make_client()
    client.headers["X-Requested-With"] = "XMLHttpRequest"
    ts = now_iso()

    records: list[StoreRecord] = []
    seen_ids: set[int] = set()
    page = 1
    empty_pages = 0

    print("  LCBO: fetching stores...", end="", flush=True)

    while True:
        resp = client.post(
            AJAX_URL,
            data={
                "lat": str(CENTER_LAT),
                "lng": str(CENTER_LNG),
                "radius": str(RADIUS),
                "product": "0",
                "p": str(page),
            },
        )

        if resp.status_code != 200:
            break

        data = resp.json()
        items = data.get("items", [])

        if not items:
            empty_pages += 1
            if empty_pages >= 2:
                break
            page += 1
            continue

        empty_pages = 0
        new_on_page = 0

        for item in items:
            store_id = item.get("id")
            if store_id in seen_ids:
                continue
            seen_ids.add(store_id)
            new_on_page += 1

            lat = float(item["lat"]) if item.get("lat") else None
            lng = float(item["lng"]) if item.get("lng") else None

            popup_html = item.get("popup_html", "")
            details = _parse_popup(popup_html)

            address = details.get("address", "")
            if not address:
                continue

            store_num = item.get("stloc", "")
            name = details.get("name", f"LCBO #{store_num}")
            city = details.get("city", "")

            records.append(
                StoreRecord(
                    brand=BRAND,
                    store_name=name,
                    address=address,
                    city=city,
                    province="ON",
                    postal_code=details.get("postal_code"),
                    phone=details.get("phone"),
                    lat=lat,
                    lng=lng,
                    source_url=f"https://www.lcbo.com/en/stores",
                    scraped_at=ts,
                )
            )

        if new_on_page == 0:
            break

        if page % 10 == 0:
            print(f" p{page}...", end="", flush=True)

        page += 1
        time.sleep(0.3)

    print(f" done ({len(records)} stores, {page - 1} pages)")

    path = write_brand_json("lcbo", records)
    return records, path
