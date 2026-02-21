"""Scraper for Dairy Queen via their Olo-powered GraphQL API.

Endpoint: https://prod-api.dairyqueen.com/graphql/
No auth required, just needs Partner-Platform: Web header.
Uses cursor-based pagination (25 per page, limit 500 per search).
Multi-center search needed to capture all Ontario stores.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

# ── Constants ─────────────────────────────────────────────────────────

GRAPHQL_URL = "https://prod-api.dairyqueen.com/graphql/"

GRAPHQL_QUERY = """\
query NearbyStores($lat: Float!, $lng: Float!, $country: String!, $searchRadius: Int!) {
  nearbyStores(
    lat: $lat, lon: $lng, country: $country, radiusMiles: $searchRadius,
    limit: 500, first: 25, order: { distance: ASC }
  ) {
    pageInfo { endCursor hasNextPage }
    nodes {
      distance
      store {
        id storeNo address3 city stateProvince postalCode country
        latitude longitude phone conceptType availabilityStatus
      }
    }
  }
}"""

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Partner-Platform": "Web",
    "Accept-Language": "en-ca",
    "Origin": "https://www.dairyqueen.com",
}

# Search centers across Ontario — the API has a ~500-result cap, so we use
# multiple centers to ensure full coverage of the province.
SEARCH_CENTERS = [
    (43.65, -79.38),   # Toronto
    (44.23, -76.48),   # Kingston
    (45.42, -75.70),   # Ottawa
    (46.49, -80.99),   # Sudbury
    (48.48, -89.25),   # Thunder Bay
    (42.98, -81.25),   # London
    (43.25, -79.87),   # Hamilton
    (44.38, -79.69),   # Barrie
    (42.32, -83.04),   # Windsor
    (46.32, -79.47),   # North Bay
    (43.45, -80.49),   # Kitchener
    (44.75, -81.18),   # Owen Sound
    (43.84, -78.87),   # Oshawa
    (44.30, -78.32),   # Peterborough
    (42.87, -80.27),   # Woodstock
    (43.17, -80.26),   # Brantford
    (44.62, -80.95),   # Collingwood
    (44.75, -77.69),   # Bancroft
    (49.77, -86.95),   # Geraldton
]

SEARCH_RADIUS_MILES = 150  # miles


# ── Helpers ───────────────────────────────────────────────────────────

def _fetch_stores(client: httpx.Client, lat: float, lng: float) -> list[dict]:
    """Fetch all stores near a center point, paginating through results."""
    all_nodes: list[dict] = []
    cursor: str | None = None

    while True:
        variables: dict = {
            "lat": lat,
            "lng": lng,
            "country": "CA",
            "searchRadius": SEARCH_RADIUS_MILES,
        }

        # Build query with cursor for pagination
        if cursor:
            query = GRAPHQL_QUERY.replace(
                "order: { distance: ASC }",
                f'after: "{cursor}", order: {{ distance: ASC }}'
            )
        else:
            query = GRAPHQL_QUERY

        payload = {"query": query, "variables": variables}
        resp = client.post(GRAPHQL_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

        nearby = data.get("data", {}).get("nearbyStores", {})
        nodes = nearby.get("nodes", [])
        all_nodes.extend(nodes)

        page_info = nearby.get("pageInfo", {})
        if page_info.get("hasNextPage") and page_info.get("endCursor"):
            cursor = page_info["endCursor"]
        else:
            break

    return all_nodes


def _to_record(node: dict, ts: str) -> StoreRecord | None:
    store = node.get("store", {})
    street = (store.get("address3") or "").strip().rstrip(",")
    city = (store.get("city") or "").strip()

    if not street or not city:
        return None

    return StoreRecord(
        brand="Dairy Queen",
        store_name=f"Dairy Queen - {city}",
        address=street,
        city=city,
        province=store.get("stateProvince", ""),
        postal_code=store.get("postalCode"),
        phone=store.get("phone"),
        lat=store.get("latitude"),
        lng=store.get("longitude"),
        source_url=f"https://www.dairyqueen.com/en-ca/locations/{store.get('storeNo', '')}",
        scraped_at=ts,
    )


# ── Public API ────────────────────────────────────────────────────────

def scrape() -> tuple[list[StoreRecord], Path]:
    """Scrape all Dairy Queen stores in Ontario."""
    ts = now_iso()
    seen_ids: set[str] = set()
    records: list[StoreRecord] = []

    client = httpx.Client(headers=HEADERS, timeout=30)
    try:
        for lat, lng in SEARCH_CENTERS:
            nodes = _fetch_stores(client, lat, lng)
            for node in nodes:
                store = node.get("store", {})
                store_no = store.get("storeNo")
                if not store_no or store_no in seen_ids:
                    continue
                seen_ids.add(store_no)

                # Filter to Ontario only
                province = (store.get("stateProvince") or "").upper()
                if province != "ON":
                    continue

                rec = _to_record(node, ts)
                if rec:
                    records.append(rec)
    finally:
        client.close()

    path = write_brand_json("dairy_queen", records)

    coord_count = sum(1 for r in records if r.lat is not None)
    print(f"  Dairy Queen: {len(records)} Ontario stores ({coord_count}/{len(records)} have coordinates)")

    return records, path
