"""Overpass API client for querying OpenStreetMap data.

Completely free, no API key required. Rate limit: ~1 req/sec recommended.
Returns named commercial POIs (shops, restaurants, offices, etc.) near coordinates.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# OSM tags that indicate commercial/retail POIs
COMMERCIAL_FILTERS = """
  node["shop"](around:{radius},{lat},{lng});
  way["shop"](around:{radius},{lat},{lng});
  node["amenity"](around:{radius},{lat},{lng});
  way["amenity"](around:{radius},{lat},{lng});
  node["office"](around:{radius},{lat},{lng});
  way["office"](around:{radius},{lat},{lng});
  node["leisure"](around:{radius},{lat},{lng});
  way["leisure"](around:{radius},{lat},{lng});
  node["tourism"](around:{radius},{lat},{lng});
  way["tourism"](around:{radius},{lat},{lng});
  node["healthcare"](around:{radius},{lat},{lng});
  way["healthcare"](around:{radius},{lat},{lng});
  node["craft"](around:{radius},{lat},{lng});
  way["craft"](around:{radius},{lat},{lng});
"""


def _build_query(lat: float, lng: float, radius: int = 150) -> str:
    """Build an Overpass QL query for commercial POIs near coordinates."""
    filters = COMMERCIAL_FILTERS.format(radius=radius, lat=lat, lng=lng)
    return f"""
[out:json][timeout:25];
(
{filters}
);
out center tags;
"""


def _parse_element(el: dict) -> Optional[dict]:
    """Parse an Overpass element into a tenant record."""
    tags = el.get("tags", {})
    name = tags.get("name")
    if not name:
        return None

    # Get coordinates (nodes have lat/lon directly, ways have center)
    if el["type"] == "node":
        lat = el.get("lat")
        lng = el.get("lon")
    else:
        center = el.get("center", {})
        lat = center.get("lat")
        lng = center.get("lon")

    if lat is None or lng is None:
        return None

    # Determine category
    category = None
    for key in ("shop", "amenity", "office", "leisure", "tourism", "healthcare", "craft"):
        if key in tags:
            category = f"{key}={tags[key]}"
            break

    return {
        "osm_id": f"{el['type']}/{el['id']}",
        "name": name,
        "brand": tags.get("brand"),
        "brand_wikidata": tags.get("brand:wikidata"),
        "category": category,
        "lat": lat,
        "lng": lng,
        "address": tags.get("addr:street"),
        "housenumber": tags.get("addr:housenumber"),
        "phone": tags.get("phone"),
        "website": tags.get("website"),
        "opening_hours": tags.get("opening_hours"),
    }


class OverpassClient:
    """Query the Overpass API for commercial POIs near coordinates.

    Uses multiple Overpass servers with automatic failover and rate limiting.
    """

    def __init__(self, timeout: float = 30.0, delay: float = 2.0):
        self.client = httpx.Client(timeout=timeout)
        self._last_request: float = 0
        self._delay = delay
        self._server_idx = 0
        self._retries = 0
        self._max_retries = 3

    def _rate_limit(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self._delay:
            time.sleep(self._delay - elapsed)

    def _next_server(self) -> str:
        url = OVERPASS_URLS[self._server_idx % len(OVERPASS_URLS)]
        return url

    def _rotate_server(self) -> None:
        self._server_idx += 1
        logger.info("Rotating to Overpass server: %s", self._next_server())

    def query_tenants(
        self, lat: float, lng: float, radius: int = 150
    ) -> list[dict]:
        """Find all named commercial POIs within radius meters of coordinates.

        Returns list of tenant dicts with name, brand, category, lat, lng, etc.
        Automatically retries with failover across multiple Overpass servers.
        """
        self._rate_limit()
        query = _build_query(lat, lng, radius)

        for attempt in range(self._max_retries):
            url = self._next_server()
            try:
                resp = self.client.post(url, data={"data": query})
                self._last_request = time.time()
                resp.raise_for_status()
                data = resp.json()
                self._retries = 0  # reset on success
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    logger.warning("Rate limited by %s, rotating server...", url)
                    self._rotate_server()
                    time.sleep(5)
                    continue
                logger.error("Overpass query failed (%s): %s", url, e)
                raise
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                logger.warning("Connection issue with %s: %s, rotating...", url, e)
                self._rotate_server()
                time.sleep(2)
                continue
            except Exception as e:
                logger.error("Overpass query failed: %s", e)
                raise
        else:
            raise RuntimeError("All Overpass servers failed after retries")

        tenants = []
        seen_ids: set[str] = set()
        for el in data.get("elements", []):
            parsed = _parse_element(el)
            if parsed and parsed["osm_id"] not in seen_ids:
                seen_ids.add(parsed["osm_id"])
                tenants.append(parsed)

        return tenants

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
