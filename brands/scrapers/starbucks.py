"""Starbucks Canada scraper via public store locator API.

The API at /apiproxy/v1/locations returns up to 50 stores per request
within ~25km radius. We tile Ontario with a grid of query points and
deduplicate by store ID.

No authentication needed — only the X-Requested-With header is required.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

API_URL = "https://www.starbucks.ca/apiproxy/v1/locations"

# Grid covering Ontario — denser in GTA/Ottawa where stores are packed,
# coarser elsewhere. Spacing ~0.06 lat in dense areas, ~0.25 in suburbs/rural.
ON_GRID = [
    # === GTA core (dense: 0.06 spacing) ===
    # Downtown Toronto / Midtown / East York
    (43.64, -79.38), (43.64, -79.32), (43.64, -79.44),
    (43.70, -79.38), (43.70, -79.32), (43.70, -79.44),
    (43.76, -79.38), (43.76, -79.44),
    # Scarborough / Pickering
    (43.76, -79.25), (43.76, -79.15), (43.82, -79.18),
    (43.70, -79.20), (43.70, -79.10),
    # North York / Vaughan / Richmond Hill
    (43.82, -79.38), (43.82, -79.48), (43.82, -79.30),
    (43.88, -79.38), (43.88, -79.48), (43.88, -79.55),
    (43.94, -79.45), (43.94, -79.35),
    # Mississauga / Etobicoke
    (43.58, -79.55), (43.58, -79.65), (43.58, -79.45),
    (43.64, -79.55), (43.64, -79.65),
    (43.52, -79.60), (43.52, -79.70),
    # Brampton / Caledon
    (43.70, -79.75), (43.70, -79.65),
    (43.76, -79.70), (43.76, -79.80),
    # Oakville / Burlington
    (43.45, -79.68), (43.40, -79.80),
    # Ajax / Whitby / Oshawa
    (43.86, -79.03), (43.88, -78.87), (43.92, -78.75),
    # Markham / Stouffville
    (43.88, -79.26), (43.94, -79.25),
    (43.82, -79.08),

    # === Hamilton / Niagara ===
    (43.25, -79.85), (43.15, -79.80), (43.10, -79.25),
    (43.15, -79.50), (43.00, -79.10), (43.20, -79.25),

    # === Kitchener / Waterloo / Guelph / Cambridge ===
    (43.45, -80.50), (43.55, -80.30), (43.35, -80.30),
    (43.35, -80.55), (43.20, -80.40),

    # === London / Woodstock ===
    (42.98, -81.24), (43.00, -81.00), (43.13, -80.75),

    # === Windsor / Chatham / Sarnia ===
    (42.30, -83.03), (42.30, -82.55), (42.40, -82.20),
    (42.95, -82.40), (42.78, -81.70),

    # === Ottawa (dense) ===
    (45.42, -75.69), (45.35, -75.75), (45.35, -75.60),
    (45.28, -75.75), (45.45, -75.50),
    (45.30, -75.90), (45.48, -75.75),

    # === Kingston / Belleville ===
    (44.23, -76.48), (44.18, -77.38),

    # === Peterborough / Lindsay ===
    (44.30, -78.32),

    # === Barrie / Orillia / Collingwood ===
    (44.39, -79.69), (44.60, -79.42), (44.50, -80.22),

    # === Sudbury / North Bay ===
    (46.49, -80.99), (46.30, -79.46),

    # === Sault Ste Marie ===
    (46.52, -84.33),

    # === Thunder Bay ===
    (48.38, -89.25),

    # === Cornwall / Brockville ===
    (45.02, -74.73), (44.59, -75.68),

    # === Brantford ===
    (43.14, -80.26),

    # === St. Catharines / Welland ===
    (43.16, -79.24), (42.92, -79.25),

    # === Muskoka / Huntsville ===
    (44.77, -79.38),

    # === Orangeville / Shelburne ===
    (43.92, -80.10),

    # === Newmarket / Aurora ===
    (44.05, -79.46),

    # === Timmins ===
    (48.47, -81.33),
]


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Starbucks stores in Ontario via grid search."""
    client = httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=30,
    )
    ts = now_iso()

    seen_ids: set[str] = set()
    records: list[StoreRecord] = []

    try:
        for lat, lng in ON_GRID:
            resp = client.get(API_URL, params={"lat": lat, "lng": lng, "limit": 50})
            if resp.status_code != 200:
                continue

            data = resp.json()
            if not isinstance(data, list):
                continue

            for item in data:
                store = item.get("store", {})
                store_id = store.get("id", "")
                if not store_id or store_id in seen_ids:
                    continue

                addr = store.get("address", {})
                province = addr.get("countrySubdivisionCode", "")
                country = addr.get("countryCode", "")

                # Ontario only, Canada only
                if province != "ON" or country != "CA":
                    continue

                seen_ids.add(store_id)

                street = (addr.get("streetAddressLine1") or "").strip()
                city = (addr.get("city") or "").strip()
                if not street or not city:
                    continue

                coords = store.get("coordinates", {})

                records.append(
                    StoreRecord(
                        brand="Starbucks",
                        store_name=f"Starbucks - {store.get('name', city)}",
                        address=street,
                        city=city,
                        province="ON",
                        postal_code=addr.get("postalCode"),
                        phone=store.get("phoneNumber"),
                        lat=coords.get("latitude"),
                        lng=coords.get("longitude"),
                        source_url=f"https://www.starbucks.ca/store-locator/store/{store.get('slug', store_id)}",
                        scraped_at=ts,
                    )
                )
    finally:
        client.close()

    path = write_brand_json("starbucks", records)
    return records, path
