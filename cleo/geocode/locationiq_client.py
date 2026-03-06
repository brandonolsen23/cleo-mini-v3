"""LocationIQ Geocoding API client.

Free tier: 5,000 requests/day, 2 requests/sec.
Single-address endpoint only (no batch).
"""

import logging
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://us1.locationiq.com/v1/search"


def _extract_result(item: Dict) -> Optional[Dict]:
    """Extract relevant fields from a LocationIQ search result."""
    lat = item.get("lat")
    lon = item.get("lon")
    if lat is None or lon is None:
        return None
    try:
        lat = float(lat)
        lon = float(lon)
    except (ValueError, TypeError):
        return None

    return {
        "lat": lat,
        "lng": lon,
        "formatted_address": item.get("display_name", ""),
        "accuracy": item.get("type", ""),
        "match_code": {
            "class": item.get("class", ""),
            "type": item.get("type", ""),
            "importance": item.get("importance", 0),
            "provider": "locationiq",
        },
    }


class LocationIQClient:
    """Thin wrapper around LocationIQ forward geocoding API."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise ValueError("LOCATIONIQ_KEY is required. Add it to your .env file.")
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def forward(self, address: str) -> Optional[Dict]:
        """Geocode a single address. Returns extracted result or None."""
        resp = self.client.get(
            GEOCODE_URL,
            params={
                "key": self.api_key,
                "q": address,
                "format": "json",
                "countrycodes": "ca",
                "limit": 1,
            },
        )
        if resp.status_code == 429:
            logger.warning("LocationIQ rate limit hit (429)")
            return None
        if resp.status_code == 404:
            # LocationIQ returns 404 for "no results found"
            return None
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        return _extract_result(data[0])

    def batch_forward(
        self,
        addresses: List[str],
        delay: float = 0.5,
    ) -> List[Optional[Dict]]:
        """Geocode addresses sequentially (LocationIQ has no batch endpoint).

        Default 0.5s delay = 2 req/sec, matching their rate limit.
        Backs off on 429 responses.
        """
        results: List[Optional[Dict]] = []
        backoff = delay

        for i, addr in enumerate(addresses):
            try:
                resp = self.client.get(
                    GEOCODE_URL,
                    params={
                        "key": self.api_key,
                        "q": addr,
                        "format": "json",
                        "countrycodes": "ca",
                        "limit": 1,
                    },
                )

                if resp.status_code == 429:
                    backoff = min(backoff * 2, 10.0)
                    logger.warning("429 at address %d, backing off %.1fs", i, backoff)
                    time.sleep(backoff)
                    resp = self.client.get(
                        GEOCODE_URL,
                        params={
                            "key": self.api_key,
                            "q": addr,
                            "format": "json",
                            "countrycodes": "ca",
                            "limit": 1,
                        },
                    )
                    if resp.status_code == 429:
                        results.append(None)
                        continue

                if resp.status_code == 404:
                    results.append(None)
                    backoff = delay
                    if delay > 0:
                        time.sleep(delay)
                    continue

                resp.raise_for_status()
                data = resp.json()
                if data:
                    results.append(_extract_result(data[0]))
                    backoff = delay
                else:
                    results.append(None)

            except Exception as e:
                logger.error("LocationIQ geocode error for '%s': %s", addr[:60], e)
                results.append(None)

            if delay > 0:
                time.sleep(delay)

        return results

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
