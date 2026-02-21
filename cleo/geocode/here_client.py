"""HERE Geocoding & Search API v1 client."""

import logging
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"


def _extract_result(item: Dict) -> Dict:
    """Extract relevant fields from a HERE geocode result item."""
    position = item.get("position", {})
    address = item.get("address", {})
    scoring = item.get("scoring", {})
    return {
        "lat": position.get("lat"),
        "lng": position.get("lng"),
        "formatted_address": address.get("label", ""),
        "accuracy": item.get("resultType", ""),
        "mapbox_id": "",
        "match_code": {
            "queryScore": scoring.get("queryScore"),
            "fieldScore": scoring.get("fieldScore", {}),
            "provider": "here",
        },
    }


class HereClient:
    """Thin wrapper around HERE Geocoding & Search API v1."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise ValueError("HERE_API_KEY is required. Add it to your .env file.")
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def forward(self, address: str) -> Optional[Dict]:
        """Geocode a single address. Returns extracted result or None."""
        resp = self.client.get(
            GEOCODE_URL,
            params={
                "q": address,
                "apiKey": self.api_key,
                "in": "countryCode:CAN",
                "limit": 1,
            },
        )
        if resp.status_code == 429:
            logger.warning("HERE rate limit hit (429)")
            return None
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None
        return _extract_result(items[0])

    def batch_forward(
        self,
        addresses: List[str],
        delay: float = 0.2,
    ) -> List[Optional[Dict]]:
        """Geocode addresses sequentially (HERE has no batch endpoint).

        Respects rate limit of 5 req/sec with delay between requests.
        Backs off on 429 responses.
        """
        results: List[Optional[Dict]] = []
        backoff = delay

        for i, addr in enumerate(addresses):
            try:
                resp = self.client.get(
                    GEOCODE_URL,
                    params={
                        "q": addr,
                        "apiKey": self.api_key,
                        "in": "countryCode:CAN",
                        "limit": 1,
                    },
                )

                if resp.status_code == 429:
                    # Back off exponentially, retry once
                    backoff = min(backoff * 2, 5.0)
                    logger.warning("429 at address %d, backing off %.1fs", i, backoff)
                    time.sleep(backoff)
                    resp = self.client.get(
                        GEOCODE_URL,
                        params={
                            "q": addr,
                            "apiKey": self.api_key,
                            "in": "countryCode:CAN",
                            "limit": 1,
                        },
                    )
                    if resp.status_code == 429:
                        results.append(None)
                        continue

                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                if items:
                    results.append(_extract_result(items[0]))
                    backoff = delay  # Reset on success
                else:
                    results.append(None)

            except Exception as e:
                logger.error("HERE geocode error for '%s': %s", addr[:60], e)
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
