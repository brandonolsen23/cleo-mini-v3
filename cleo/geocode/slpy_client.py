"""SLPY Geocoding API client.

Free tier: 50K credits/month (hard cap, pauses at limit), 60 req/min.
Single-address endpoint only.
"""

import logging
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://api.slpy.com/v1/search"


def _extract_result(data: Dict) -> Optional[Dict]:
    """Extract relevant fields from a SLPY geocode response."""
    status = data.get("status", "")
    if status != "OK":
        return None

    lat = data.get("lat")
    lon = data.get("lon")
    if lat is None or lon is None:
        return None

    props = data.get("properties", {})
    accuracy = data.get("accuracy", "")
    level = data.get("level", 0)

    return {
        "lat": lat,
        "lng": lon,
        "formatted_address": props.get("address", ""),
        "accuracy": accuracy,
        "match_code": {
            "level": level,
            "accuracy": accuracy,
            "provider": "slpy",
        },
    }


class SlpyClient:
    """Thin wrapper around SLPY geocoding API."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise ValueError("SLPY_API_KEY is required. Add it to your .env file.")
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def forward(self, address: str) -> Optional[Dict]:
        """Geocode a single address. Returns extracted result or None."""
        resp = self.client.get(
            GEOCODE_URL,
            params={
                "key": self.api_key,
                "query": address,
                "country": "CA",
            },
        )
        if resp.status_code == 429:
            logger.warning("SLPY rate limit hit (429)")
            return None
        resp.raise_for_status()
        data = resp.json()
        return _extract_result(data)

    def batch_forward(
        self,
        addresses: List[str],
        delay: float = 1.0,
    ) -> List[Optional[Dict]]:
        """Geocode addresses sequentially (SLPY has no batch endpoint).

        Default 1.0s delay = 60 req/min, matching their rate limit.
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
                        "query": addr,
                        "country": "CA",
                    },
                )

                if resp.status_code == 429:
                    backoff = min(backoff * 2, 15.0)
                    logger.warning("429 at address %d, backing off %.1fs", i, backoff)
                    time.sleep(backoff)
                    resp = self.client.get(
                        GEOCODE_URL,
                        params={
                            "key": self.api_key,
                            "query": addr,
                            "country": "CA",
                        },
                    )
                    if resp.status_code == 429:
                        results.append(None)
                        continue

                resp.raise_for_status()
                data = resp.json()
                result = _extract_result(data)
                results.append(result)
                if result is not None:
                    backoff = delay

            except Exception as e:
                logger.error("SLPY geocode error for '%s': %s", addr[:60], e)
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
