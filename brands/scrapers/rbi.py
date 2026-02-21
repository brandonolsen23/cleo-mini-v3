"""Scraper for Restaurant Brands International (RBI) via their GraphQL API.

Covers brands on the RBI platform:
  - Burger King (use1-prod-bk.rbictg.com)
  - Firehouse Subs (use1-prod-fhs.rbictg.com)
  - Popeyes (www.popeyeschicken.ca — proxy to use1-prod-plk-gateway.rbictg.com)

The GraphQL API returns nearby restaurants within a search radius.
Using a central Ontario coordinate with a large radius captures all ON stores.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from .base import StoreRecord, now_iso, write_brand_json

# ── Constants ─────────────────────────────────────────────────────────

# Center of southern Ontario — large radius captures the whole province
ONTARIO_CENTER_LAT = 44.0
ONTARIO_CENTER_LNG = -79.5
SEARCH_RADIUS = 1_000_000  # 1000 km — covers all of Ontario and then some

GRAPHQL_QUERY = """\
query GetRestaurants($input: RestaurantsInput) {
  restaurants(input: $input) {
    nodes {
      storeId
      name
      latitude
      longitude
      physicalAddress {
        address1
        city
        stateProvince
        postalCode
      }
    }
    totalCount
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}"""


@dataclass
class BrandConfig:
    host: str
    brand_name: str
    slug: str


BRANDS: dict[str, BrandConfig] = {
    "burger_king": BrandConfig(
        "use1-prod-bk.rbictg.com",
        "Burger King",
        "burger_king",
    ),
    "firehouse_subs": BrandConfig(
        "use1-prod-fhs.rbictg.com",
        "Firehouse Subs",
        "firehouse_subs",
    ),
    "popeyes": BrandConfig(
        "www.popeyeschicken.ca",
        "Popeyes",
        "popeyes",
    ),
}


# ── Helpers ───────────────────────────────────────────────────────────

_PROVINCE_MAP = {
    "Ontario": "ON",
    "Quebec": "QC",
    "British Columbia": "BC",
    "Alberta": "AB",
    "Manitoba": "MB",
    "Saskatchewan": "SK",
    "Nova Scotia": "NS",
    "New Brunswick": "NB",
    "Newfoundland And Labrador": "NL",
    "Newfoundland and Labrador": "NL",
    "Prince Edward Island": "PE",
    "Northwest Territories": "NT",
    "Yukon": "YT",
    "Nunavut": "NU",
}


def _normalize_province(raw: str) -> str:
    return _PROVINCE_MAP.get(raw, raw)


def _fetch_restaurants(host: str) -> list[dict]:
    """Fetch all restaurants from an RBI GraphQL endpoint."""
    client = httpx.Client(
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-ui-language": "en",
            "x-ui-region": "CA",
        },
        timeout=30,
    )
    try:
        payload = {
            "operationName": "GetRestaurants",
            "variables": {
                "input": {
                    "filter": "NEARBY",
                    "coordinates": {
                        "userLat": ONTARIO_CENTER_LAT,
                        "userLng": ONTARIO_CENTER_LNG,
                        "searchRadius": SEARCH_RADIUS,
                    },
                    "first": 5000,
                    "status": "OPEN",
                }
            },
            "query": GRAPHQL_QUERY,
        }
        resp = client.post(f"https://{host}/graphql", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("restaurants", {}).get("nodes", [])
    finally:
        client.close()


_BRAND_URLS = {
    "Burger King": "https://www.burgerking.ca/store-locator/store",
    "Firehouse Subs": "https://www.firehousesubs.ca/store-locator/store",
    "Popeyes": "https://www.popeyeschicken.ca/store-locator/store",
}


def _to_record(node: dict, brand_name: str, ts: str) -> StoreRecord | None:
    addr = node.get("physicalAddress", {})
    street = (addr.get("address1") or "").strip().rstrip(",")
    city = (addr.get("city") or "").strip()

    if not street or not city:
        return None

    base_url = _BRAND_URLS.get(brand_name, "https://www.burgerking.ca/store-locator/store")

    return StoreRecord(
        brand=brand_name,
        store_name=f"{brand_name} - {city}",
        address=street,
        city=city,
        province=_normalize_province(addr.get("stateProvince", "")),
        postal_code=addr.get("postalCode"),
        phone=None,
        lat=node.get("latitude"),
        lng=node.get("longitude"),
        source_url=f"{base_url}/{node.get('storeId', '')}",
        scraped_at=ts,
    )


# ── Public API ────────────────────────────────────────────────────────


def scrape_brand(key: str) -> tuple[list[StoreRecord], Path]:
    """Scrape a single RBI brand."""
    cfg = BRANDS[key]
    ts = now_iso()

    nodes = _fetch_restaurants(cfg.host)

    # Filter to Ontario only
    records: list[StoreRecord] = []
    for node in nodes:
        province = (node.get("physicalAddress", {}).get("stateProvince") or "")
        if province != "Ontario":
            continue
        rec = _to_record(node, cfg.brand_name, ts)
        if rec:
            records.append(rec)

    path = write_brand_json(cfg.slug, records)

    coord_count = sum(1 for r in records if r.lat is not None)
    print(f"  {cfg.brand_name}: {len(records)} Ontario stores ({coord_count}/{len(records)} have coordinates)")

    return records, path


def scrape_all() -> list[tuple[str, int, Path]]:
    """Scrape all RBI brands."""
    results = []
    for key in BRANDS:
        records, path = scrape_brand(key)
        results.append((BRANDS[key].slug, len(records), path))
    return results


def scrape_burger_king() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("burger_king")


def scrape_firehouse_subs() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("firehouse_subs")


def scrape_popeyes() -> tuple[list[StoreRecord], Path]:
    return scrape_brand("popeyes")
