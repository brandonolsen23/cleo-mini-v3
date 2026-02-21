"""Food Basics store scraper.

Source: https://www.foodbasics.ca/find-a-grocery
Method: Single HTTP GET, parse static HTML. All ~153 stores rendered on one page.
Store data in <li class="fs--box-shop"> elements with data-store-lat/lng attributes.
"""

from __future__ import annotations

from pathlib import Path

from bs4 import BeautifulSoup

from .base import StoreRecord, make_client, now_iso, write_brand_json

SOURCE_URL = "https://www.foodbasics.ca/find-a-grocery"
BRAND = "Food Basics"
SLUG = "food_basics"


def _parse_store(li_tag, ts: str) -> StoreRecord | None:
    name = (li_tag.get("data-store-name") or "").replace("  ", " ").strip()
    if not name:
        return None

    street_el = li_tag.find("span", class_="address--street")
    city_el = li_tag.find("span", class_="address--city")
    prov_el = li_tag.find("span", class_="address--provinceCode")
    postal_el = li_tag.find("span", class_="address--postalCode")
    phone_el = li_tag.find("div", class_="store-phone")

    address = street_el.get_text(strip=True) if street_el else ""
    city = city_el.get_text(strip=True) if city_el else ""
    province = prov_el.get_text(strip=True) if prov_el else "ON"
    postal_code = postal_el.get_text(strip=True) if postal_el else None
    phone = phone_el.get_text(strip=True) if phone_el else None

    lat_raw = li_tag.get("data-store-lat")
    lng_raw = li_tag.get("data-store-lng")
    lat = float(lat_raw) if lat_raw else None
    lng = float(lng_raw) if lng_raw else None

    return StoreRecord(
        brand=BRAND,
        store_name=name,
        address=address,
        city=city,
        province=province,
        postal_code=postal_code,
        phone=phone,
        lat=lat,
        lng=lng,
        source_url=SOURCE_URL,
        scraped_at=ts,
    )


def scrape() -> tuple[list[StoreRecord], Path]:
    client = make_client()
    resp = client.get(SOURCE_URL)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    records: list[StoreRecord] = []
    ts = now_iso()

    for li in soup.find_all("li", class_="fs--box-shop"):
        rec = _parse_store(li, ts)
        if rec:
            records.append(rec)

    path = write_brand_json(SLUG, records)
    return records, path
