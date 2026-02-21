"""McDonald's Canada scraper via geolocation API.

~300+ Ontario locations. The McDonald's website exposes a geolocation API
that returns nearby restaurants. We tile Ontario with multiple query points
to capture all locations, deduplicating by restaurant ID.
"""

from __future__ import annotations

from pathlib import Path

from .base import StoreRecord, make_client, now_iso, write_brand_json

API_URL = "https://www.mcdonalds.com/googleappsv2/geolocation"

# Grid of query points covering Ontario
ON_POINTS = [
    # GTA & surrounds
    (43.65, -79.38), (43.85, -79.38), (43.45, -79.38),
    (43.65, -79.80), (43.65, -78.90), (43.80, -79.70),
    # Hamilton / Niagara
    (43.25, -79.87), (43.10, -79.25), (43.15, -79.50),
    # Kitchener / Waterloo / Guelph
    (43.45, -80.49), (43.55, -80.25), (43.37, -80.98),
    # London / Windsor / Sarnia
    (42.98, -81.24), (42.30, -83.03), (42.95, -82.40),
    (43.00, -80.25), (42.78, -81.70),
    # Ottawa / Eastern Ontario
    (45.42, -75.69), (45.30, -75.90), (44.90, -75.50),
    # Kingston / Belleville
    (44.23, -76.48), (44.18, -77.38),
    # Peterborough / Lindsay
    (44.30, -78.32), (44.35, -78.74),
    # Barrie / Orillia
    (44.39, -79.69), (44.60, -79.42),
    # Sudbury / North Bay
    (46.49, -80.99), (46.30, -79.46),
    # Sault Ste Marie
    (46.52, -84.33),
    # Thunder Bay / Northern
    (48.38, -89.25), (49.77, -86.97),
    # Brampton / Mississauga
    (43.68, -79.72), (43.59, -79.64),
    # Durham / Oshawa
    (43.90, -78.86), (44.10, -78.75),
    # Brantford / Cambridge
    (43.14, -80.26), (43.36, -80.31),
    # St. Catharines
    (43.16, -79.24),
    # Cornwall
    (45.02, -74.73),
    # Timmins
    (48.47, -81.33),
    # Muskoka
    (44.77, -79.38),
]


def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all McDonald's stores in Ontario."""
    client = make_client()
    ts = now_iso()

    seen_ids: set[str] = set()
    records: list[StoreRecord] = []

    for lat, lng in ON_POINTS:
        resp = client.get(
            API_URL,
            params={
                "latitude": str(lat),
                "longitude": str(lng),
                "radius": "200",
                "maxResults": "500",
                "country": "ca",
                "language": "en-ca",
            },
        )
        if resp.status_code != 200:
            continue

        data = resp.json()
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            fid = props.get("id", "")
            if fid in seen_ids:
                continue
            seen_ids.add(fid)

            coords = feature.get("geometry", {}).get("coordinates", [None, None])
            lng_val = coords[0] if coords else None
            lat_val = coords[1] if len(coords) > 1 else None

            name = props.get("name", "")
            city = props.get("customAddress", "")
            # customAddress format: "City, PostalCode"
            postal_code = None
            if city and "," in city:
                parts = city.rsplit(",", 1)
                city = parts[0].strip()
                postal_code = parts[1].strip() if len(parts) > 1 else None
            elif props.get("postcode"):
                postal_code = props.get("postcode")

            records.append(
                StoreRecord(
                    brand="McDonald's",
                    store_name=f"McDonald's - {name}" if name else "McDonald's",
                    address=props.get("addressLine1", ""),
                    city=city,
                    province="ON",
                    postal_code=postal_code,
                    phone=props.get("telephone"),
                    lat=lat_val,
                    lng=lng_val,
                    source_url="https://www.mcdonalds.com/ca/en-ca/restaurant-locator.html",
                    scraped_at=ts,
                )
            )

    path = write_brand_json("mcdonalds", records)
    return records, path
