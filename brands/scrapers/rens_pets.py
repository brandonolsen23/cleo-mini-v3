"""Rens Pets scraper via Demandware Stores-FindStores API.

~61 stores across Canada. Rens Pets uses Salesforce Commerce Cloud (Demandware)
which exposes a JSON API for store search.
"""

from __future__ import annotations

from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

API_URL = "https://www.renspets.com/on/demandware.store/Sites-CA-Site/en_CA/Stores-FindStores"


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Rens Pets stores in Ontario."""
    client = make_client()
    ts = now_iso()

    resp = client.get(
        API_URL,
        params={
            "showMap": "false",
            "lat": "44.0",
            "long": "-79.5",
            "radius": "5000",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    all_stores = data.get("stores", [])

    records: list[StoreRecord] = []
    for store in all_stores:
        if store.get("stateCode") != "ON":
            continue

        records.append(
            StoreRecord(
                brand="Rens Pets",
                store_name=f"Rens Pets - {store.get('name', '')}",
                address=store.get("address1", ""),
                city=store.get("city", ""),
                province="ON",
                postal_code=store.get("postalCode"),
                phone=store.get("phone"),
                lat=store.get("latitude"),
                lng=store.get("longitude"),
                source_url="https://www.renspets.com/store-locator",
                scraped_at=ts,
            )
        )

    path = write_brand_json("rens_pets", records)
    return records, path
