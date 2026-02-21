"""Dollar Tree Canada scraper via Yext geosearch API.

161 Ontario stores. Uses the same Yext Live API approach as recipe_unlimited.py.
API key is publicly embedded in the Dollar Tree Canada store locator page.
"""

from __future__ import annotations

from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

API_KEY = "3d24e3ce71cf3cda7fceb6b17a046ed0"
BASE_URL = "https://liveapi.yext.com/v2/accounts/me/entities/geosearch"

# Centre of Ontario, large radius to capture all stores
CENTRE = "44.0,-79.5"
RADIUS_MI = 500
PAGE_SIZE = 50


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Dollar Tree Canada stores in Ontario."""
    client = make_client()
    ts = now_iso()
    records: list[StoreRecord] = []
    offset = 0

    while True:
        params = {
            "api_key": API_KEY,
            "v": "20230101",
            "entityTypes": "location",
            "limit": PAGE_SIZE,
            "offset": offset,
            "location": CENTRE,
            "radius": RADIUS_MI,
            "filter": '{"address.region":{"$eq":"ON"}}',
        }
        resp = client.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        entities = data.get("response", {}).get("entities", [])
        if not entities:
            break

        for e in entities:
            addr = e.get("address", {})
            coords = (
                e.get("geocodedCoordinate")
                or e.get("yextDisplayCoordinate")
                or {}
            )
            phone = e.get("mainPhone")

            records.append(
                StoreRecord(
                    brand="Dollar Tree",
                    store_name=f"Dollar Tree - {addr.get('city', '')}",
                    address=addr.get("line1", ""),
                    city=addr.get("city", ""),
                    province=addr.get("region", "ON"),
                    postal_code=addr.get("postalCode"),
                    phone=phone,
                    lat=coords.get("latitude"),
                    lng=coords.get("longitude"),
                    source_url="https://locations.dollartreecanada.com/on",
                    scraped_at=ts,
                )
            )

        offset += PAGE_SIZE
        if offset >= data.get("response", {}).get("count", 0):
            break

    path = write_brand_json("dollar_tree", records)
    return records, path
