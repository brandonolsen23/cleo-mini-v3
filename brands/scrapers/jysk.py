"""JYSK store locator scraper (Ontario).

Single AJAX endpoint returns all Canadian stores; we filter to zone=ON.

Source: https://www.jysk.ca/storelocator (Magento, AJAX backend)
"""

from __future__ import annotations

from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

AJAX_URL = "https://www.jysk.ca/storelocator/ajax/stores/"
BRAND = "JYSK"


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape JYSK Ontario stores."""
    client = make_client()
    client.headers["X-Requested-With"] = "XMLHttpRequest"

    resp = client.get(AJAX_URL)
    resp.raise_for_status()
    stores = resp.json()

    records: list[StoreRecord] = []
    ts = now_iso()

    for s in stores:
        if s.get("zone") != "ON":
            continue

        records.append(
            StoreRecord(
                brand=BRAND,
                store_name=f"JYSK - {s.get('city', s.get('name', ''))}",
                address=s.get("address", ""),
                city=s.get("city", ""),
                province="ON",
                postal_code=s.get("postcode"),
                phone=s.get("phone"),
                lat=float(s["latitude"]) if s.get("latitude") else None,
                lng=float(s["longitude"]) if s.get("longitude") else None,
                source_url="https://www.jysk.ca/storelocator",
                scraped_at=ts,
            )
        )

    path = write_brand_json("jysk", records)
    return records, path
