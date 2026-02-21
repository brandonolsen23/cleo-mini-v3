"""Mapbox Geocoding v6 API client."""

import logging
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

FORWARD_URL = "https://api.mapbox.com/search/geocode/v6/forward"
BATCH_URL = "https://api.mapbox.com/search/geocode/v6/batch"


def _extract_result(feature: Dict) -> Dict:
    """Extract relevant fields from a Mapbox v6 feature response."""
    props = feature.get("properties", {})
    coords = props.get("coordinates", {})
    return {
        "lat": coords.get("latitude"),
        "lng": coords.get("longitude"),
        "formatted_address": props.get("place_formatted", ""),
        "accuracy": coords.get("accuracy", ""),
        "mapbox_id": props.get("mapbox_id", ""),
        "match_code": props.get("match_code", {}),
    }


class MapboxClient:
    """Thin wrapper around Mapbox Geocoding v6 API."""

    def __init__(self, token: str, timeout: float = 30.0):
        if not token:
            raise ValueError("MAPBOX_TOKEN is required. Add it to your .env file.")
        self.token = token
        self.client = httpx.Client(timeout=timeout)

    def forward(self, address: str) -> Optional[Dict]:
        """Geocode a single address. Returns extracted result or None."""
        resp = self.client.get(
            FORWARD_URL,
            params={
                "q": address,
                "access_token": self.token,
                "country": "ca",
                "limit": 1,
            },
        )
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
        """Geocode up to 50 addresses in a single batch POST.

        Returns list of result dicts (or None for failures), same order as input.
        """
        if len(addresses) > 50:
            raise ValueError(f"Batch limit is 50, got {len(addresses)}")
        if not addresses:
            return []

        body = [
            {
                "q": addr,
                "country": "ca",
                "limit": 1,
            }
            for addr in addresses
        ]

        resp = self.client.post(
            BATCH_URL,
            params={
                "access_token": self.token,
            },
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        results: List[Optional[Dict]] = []
        batch_items = data.get("batch", [])
        for item in batch_items:
            features = item.get("features", [])
            if features:
                results.append(_extract_result(features[0]))
            else:
                results.append(None)

        # Pad with None if response is short (shouldn't happen)
        while len(results) < len(addresses):
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
