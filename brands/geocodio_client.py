"""Geocodio batch geocoding client for Canadian addresses.

Uses the Geocodio v1.9 API with batch endpoint.
Free tier: 2,500 lookups/day, batch limit 10,000 per request.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BATCH_URL = "https://api.geocod.io/v1.9/geocode"
DAILY_LIMIT = 2300  # stay under 2,500 free tier


def _get_api_key() -> str:
    key = os.environ.get("GEOCODIO_KEY", "")
    if not key:
        from dotenv import load_dotenv
        load_dotenv()
        key = os.environ.get("GEOCODIO_KEY", "")
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


def batch_forward(
    addresses: list[str],
    api_key: str | None = None,
    timeout: float = 120.0,
) -> list[Optional[dict]]:
    """Geocode a batch of addresses via Geocodio.

    Args:
        addresses: List of address strings (max 10,000).
        api_key: Geocodio API key. Falls back to GEOCODIO_KEY env var.
        timeout: Request timeout in seconds.

    Returns:
        List of result dicts (same length as input). Each is either:
            {"lat": float, "lng": float, "accuracy_type": str, "accuracy": float}
        or None if geocoding failed for that address.
    """
    if not addresses:
        return []

    key = api_key or _get_api_key()
    # Ensure all addresses include CANADA to avoid Ontario, California matches
    payload = [_ensure_canada(a) for a in addresses]

    resp = httpx.post(
        BATCH_URL,
        params={"api_key": key, "country": "CA"},
        json=payload,
        timeout=timeout,
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
