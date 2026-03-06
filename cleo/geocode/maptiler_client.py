"""MapTiler Geocoding API client.

Free tier: 100K API requests/month (pauses at limit, no surprise billing).
Batch endpoint: up to 50 queries per request (semicolon-separated).
No stated rate limit per second.
"""

import logging
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://api.maptiler.com/geocoding"


def _extract_result(feature: Dict) -> Optional[Dict]:
    """Extract relevant fields from a GeoJSON feature."""
    center = feature.get("center")
    if not center or len(center) < 2:
        return None

    lng, lat = center[0], center[1]
    if lat is None or lng is None:
        return None

    props = feature.get("properties", {})
    place_name = feature.get("place_name", "")
    relevance = feature.get("relevance", 0)
    place_type = feature.get("place_type", [])

    return {
        "lat": lat,
        "lng": lng,
        "formatted_address": place_name,
        "accuracy": place_type[0] if place_type else "",
        "match_code": {
            "relevance": relevance,
            "place_type": place_type,
            "provider": "maptiler",
        },
    }


class MapTilerClient:
    """Thin wrapper around MapTiler geocoding API with batch support."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise ValueError("MAPTILER_API_KEY is required. Add it to your .env file.")
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def forward(self, address: str) -> Optional[Dict]:
        """Geocode a single address. Returns extracted result or None."""
        resp = self.client.get(
            f"{GEOCODE_URL}/{_encode_query(address)}.json",
            params={
                "key": self.api_key,
                "country": "ca",
                "limit": 1,
            },
        )
        if resp.status_code == 429:
            logger.warning("MapTiler rate limit hit (429)")
            return None
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        return _extract_result(features[0])

    def batch_forward(
        self,
        addresses: List[str],
        delay: float = 0.1,
    ) -> List[Optional[Dict]]:
        """Geocode addresses in batches of 50 (MapTiler batch endpoint).

        Returns one result per input address (in order).
        """
        results: List[Optional[Dict]] = []
        backoff = delay

        # Dynamic batching: split addresses into URL-safe chunks
        batches = _split_batches(addresses, max_url_len=7500)

        for batch in batches:

            try:
                # Semicolon-separated queries
                query = ";".join(_encode_query(a) for a in batch)
                resp = self.client.get(
                    f"{GEOCODE_URL}/{query}.json",
                    params={
                        "key": self.api_key,
                        "country": "ca",
                        "limit": 1,
                    },
                )

                if resp.status_code == 429:
                    backoff = min(backoff * 2, 30.0)
                    logger.warning("MapTiler 429, backing off %.1fs", backoff)
                    time.sleep(backoff)
                    resp = self.client.get(
                        f"{GEOCODE_URL}/{query}.json",
                        params={
                            "key": self.api_key,
                            "country": "ca",
                            "limit": 1,
                        },
                    )
                    if resp.status_code == 429:
                        results.extend([None] * len(batch))
                        continue

                resp.raise_for_status()
                data = resp.json()

                # Batch response: a list of FeatureCollections (one per query)
                if isinstance(data, list):
                    for item in data:
                        features = item.get("features", []) if isinstance(item, dict) else []
                        if features:
                            results.append(_extract_result(features[0]))
                        else:
                            results.append(None)
                elif isinstance(data, dict):
                    # Single query fallback
                    features = data.get("features", [])
                    if features:
                        results.append(_extract_result(features[0]))
                    else:
                        results.append(None)
                    # Pad remaining if batch had more
                    results.extend([None] * (len(batch) - 1))

                backoff = delay

            except Exception as e:
                logger.error("MapTiler batch error: %s", e)
                results.extend([None] * len(batch))

            if delay > 0:
                time.sleep(delay)

        return results

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _split_batches(addresses: List[str], max_url_len: int = 1800) -> List[List[str]]:
    """Split addresses into batches that fit within URL length limits.

    Uses percent-encoded length (spaces → %20, etc.) to match actual URL size.
    MapTiler returns 404 when URL exceeds ~2KB, so we cap conservatively.
    """
    from urllib.parse import quote

    batches = []
    current: List[str] = []
    current_len = 0

    for addr in addresses:
        encoded = quote(_encode_query(addr))
        # +3 for semicolon delimiter
        entry_len = len(encoded) + 3
        if current and (current_len + entry_len > max_url_len or len(current) >= 10):
            batches.append(current)
            current = []
            current_len = 0
        current.append(addr)
        current_len += entry_len

    if current:
        batches.append(current)
    return batches


def _encode_query(address: str) -> str:
    """Encode address for use in URL path segment."""
    # MapTiler expects the query in the URL path, not as a param.
    # Semicolons are batch delimiters, so replace them.
    # Hash (#) is a URL fragment delimiter, so replace it.
    # Question mark (?) is a query delimiter, so replace it.
    return address.replace(";", ",").replace("#", "").replace("?", "").replace("/", " ")
