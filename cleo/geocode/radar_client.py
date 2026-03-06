"""Radar Geocoding API client.

Free tier: 100K API requests/month, 10 req/sec.
Single-address endpoint only (no batch).
"""

import logging
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://api.radar.io/v1/geocode/forward"


def _extract_result(data: Dict) -> Optional[Dict]:
    """Extract relevant fields from a Radar geocode response."""
    addresses = data.get("addresses", [])
    if not addresses:
        return None

    best = addresses[0]
    lat = best.get("latitude")
    lng = best.get("longitude")
    if lat is None or lng is None:
        return None

    return {
        "lat": lat,
        "lng": lng,
        "formatted_address": best.get("formattedAddress", ""),
        "accuracy": best.get("confidence", ""),
        "match_code": {
            "confidence": best.get("confidence", ""),
            "provider": "radar",
        },
    }


class RadarClient:
    """Thin wrapper around Radar geocoding API."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise ValueError("RADAR_API_KEY is required. Add it to your .env file.")
        self.api_key = api_key
        self.client = httpx.Client(
            timeout=timeout,
            headers={"Authorization": api_key},
        )

    def forward(self, address: str) -> Optional[Dict]:
        """Geocode a single address. Returns extracted result or None."""
        resp = self.client.get(
            GEOCODE_URL,
            params={"query": address, "country": "CA"},
        )
        if resp.status_code == 429:
            logger.warning("Radar rate limit hit (429)")
            return None
        resp.raise_for_status()
        return _extract_result(resp.json())

    def batch_forward(
        self,
        addresses: List[str],
        delay: float = 0.1,
    ) -> List[Optional[Dict]]:
        """Geocode addresses sequentially (Radar has no batch endpoint).

        Default 0.1s delay = 10 req/sec, matching their rate limit.
        """
        results: List[Optional[Dict]] = []
        backoff = delay

        for i, addr in enumerate(addresses):
            try:
                resp = self.client.get(
                    GEOCODE_URL,
                    params={"query": addr, "country": "CA"},
                )

                if resp.status_code == 429:
                    backoff = min(backoff * 2, 10.0)
                    logger.warning("Radar 429 at address %d, backing off %.1fs", i, backoff)
                    time.sleep(backoff)
                    resp = self.client.get(
                        GEOCODE_URL,
                        params={"query": addr, "country": "CA"},
                    )
                    if resp.status_code == 429:
                        results.append(None)
                        continue

                resp.raise_for_status()
                result = _extract_result(resp.json())
                results.append(result)
                if result is not None:
                    backoff = delay

            except Exception as e:
                logger.error("Radar geocode error for '%s': %s", addr[:60], e)
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
