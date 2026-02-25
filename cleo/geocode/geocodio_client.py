"""Geocodio batch geocoding client for Canadian addresses.

Uses the Geocodio v1.9 API with batch endpoint.
Free tier: 2,500 lookups/day, batch limit 10,000 per request.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from cleo.config import GEOCODIO_KEY

logger = logging.getLogger(__name__)

BATCH_URL = "https://api.geocod.io/v1.9/geocode"
DAILY_LIMIT = 2300  # stay under 2,500 free tier


def _get_api_key() -> str:
    key = GEOCODIO_KEY
    if not key:
        raise ValueError("GEOCODIO_KEY is required. Add it to your .env file.")
    return key


def _ensure_canada(address: str) -> str:
    """Append ', CANADA' to addresses that don't already contain it.

    Geocodio interprets "ONTARIO" as Ontario, California unless
    the address explicitly contains 'CANADA'.
    """
    upper = address.upper()
    if "CANADA" in upper:
        return address
    return address + ", CANADA"


class GeocodioClient:
    """Thin wrapper around Geocodio batch geocoding API."""

    def __init__(self, api_key: str | None = None, timeout: float = 120.0):
        self.api_key = api_key or _get_api_key()
        self.timeout = timeout

    def batch_forward(
        self,
        addresses: list[str],
    ) -> list[Optional[dict]]:
        """Geocode a batch of addresses via Geocodio.

        Args:
            addresses: List of address strings (max 10,000).

        Returns:
            List of result dicts (same length as input). Each is either:
                {"lat": float, "lng": float, "accuracy_type": str, "accuracy": float}
            or None if geocoding failed for that address.
        """
        if not addresses:
            return []

        # Ensure all addresses include CANADA to avoid Ontario, California matches
        payload = [_ensure_canada(a) for a in addresses]

        resp = httpx.post(
            BATCH_URL,
            params={"api_key": self.api_key, "country": "CA"},
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()

        results: list[Optional[dict]] = []
        for item in data.get("results", []):
            response = item.get("response", {})
            geocode_results = response.get("results", [])
            if not geocode_results:
                results.append(None)
                continue
            best = geocode_results[0]
            location = best.get("location", {})
            lat = location.get("lat")
            lng = location.get("lng")
            accuracy_type = best.get("accuracy_type", "")
            if lat is None or lng is None:
                results.append(None)
                continue
            # Skip state/county-level results -- too imprecise for matching
            if accuracy_type in ("state", "county"):
                results.append(None)
                continue
            results.append({
                "lat": lat,
                "lng": lng,
                "accuracy_type": accuracy_type,
                "accuracy": best.get("accuracy", 0.0),
                "formatted_address": best.get("formatted_address", ""),
            })

        # Pad if response is shorter than input (shouldn't happen, but be safe)
        while len(results) < len(addresses):
            results.append(None)

        return results

    def close(self):
        pass  # No persistent connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
