"""MapQuest Geocoding API client."""

import logging
import time
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://www.mapquestapi.com/geocoding/v1/batch"


def _extract_result(location: Dict) -> Optional[Dict]:
    """Extract relevant fields from a MapQuest geocode result location."""
    lat_lng = location.get("latLng", {})
    lat = lat_lng.get("lat")
    lng = lat_lng.get("lng")
    quality = location.get("geocodeQualityCode", "")
    quality_label = location.get("geocodeQuality", "")

    # MapQuest returns (39.78, -100.45) for failed US lookups — skip those
    if lat is None or lng is None:
        return None
    # Filter out low-quality results (country/state level)
    if quality_label in ("COUNTRY", "STATE"):
        return None

    return {
        "lat": lat,
        "lng": lng,
        "formatted_address": location.get("street", ""),
        "accuracy": quality_label,
        "match_code": {
            "quality_code": quality,
            "provider": "mapquest",
        },
    }


class MapQuestClient:
    """Thin wrapper around MapQuest Geocoding API v1 (batch endpoint)."""

    def __init__(self, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise ValueError("MAPQUEST_API_KEY is required. Add it to your .env file.")
        self.api_key = api_key
        self.client = httpx.Client(timeout=timeout)

    def forward(self, address: str) -> Optional[Dict]:
        """Geocode a single address. Returns extracted result or None."""
        resp = self.client.get(
            GEOCODE_URL,
            params={
                "key": self.api_key,
                "location": address,
                "maxResults": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None
        locations = results[0].get("locations", [])
        if not locations:
            return None
        return _extract_result(locations[0])

    def batch_forward(
        self,
        addresses: List[str],
        delay: float = 0.0,
    ) -> List[Optional[Dict]]:
        """Geocode addresses using MapQuest batch POST endpoint.

        MapQuest supports up to 100 locations per batch call.
        Uses POST with JSON body (GET mangles repeated params with httpx).
        """
        results: List[Optional[Dict]] = []

        for batch_start in range(0, len(addresses), 100):
            batch = addresses[batch_start:batch_start + 100]

            try:
                resp = self.client.post(
                    GEOCODE_URL,
                    params={"key": self.api_key},
                    json={
                        "locations": batch,
                        "options": {"maxResults": 1},
                    },
                )

                if resp.status_code == 403:
                    logger.warning("MapQuest 403 — quota likely exceeded")
                    results.extend([None] * len(batch))
                    break

                resp.raise_for_status()
                data = resp.json()

                for result_obj in data.get("results", []):
                    locations = result_obj.get("locations", [])
                    if locations:
                        results.append(_extract_result(locations[0]))
                    else:
                        results.append(None)

            except Exception as e:
                logger.error("MapQuest batch error at offset %d: %s", batch_start, e)
                results.extend([None] * len(batch))

            if delay > 0 and batch_start + 100 < len(addresses):
                time.sleep(delay)

        return results

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
