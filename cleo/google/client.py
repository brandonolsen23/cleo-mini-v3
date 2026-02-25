"""Google Places API (New) client.

All methods require a BudgetGuardian and check can_use() before any request.
Tiered field masks ensure we only get billed for the tier we request.

SKU mapping:
  - Text Search (IDs Only): places.id field mask → free unlimited
  - Place Details (Essentials): types, formattedAddress, location, addressComponents
  - Place Details (Pro): businessStatus, displayName, primaryType, googleMapsUri
  - Place Details (Enterprise): rating, userRatingCount, websiteUri, internationalPhoneNumber, regularOpeningHours
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from cleo.google.budget import BudgetGuardian, BudgetExhausted

logger = logging.getLogger(__name__)

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

# Field masks organized by billing tier
FIELD_MASKS = {
    "ids_only": "places.id",
    "essentials": "types,formattedAddress,location,addressComponents",
    "pro": "businessStatus,displayName,primaryType,googleMapsUri",
    "enterprise": (
        "rating,userRatingCount,websiteUri,"
        "internationalPhoneNumber,regularOpeningHours"
    ),
}

# SKU names matching budget.py
TIER_TO_SKU = {
    "essentials": "details_essentials",
    "pro": "details_pro",
    "enterprise": "details_enterprise",
}


class GooglePlacesClient:
    """Thin wrapper around Google Places API (New), gated by BudgetGuardian."""

    def __init__(self, api_key: str, budget: BudgetGuardian, timeout: float = 30.0):
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required. Add it to your .env file.")
        self.api_key = api_key
        self.budget = budget
        self.client = httpx.Client(timeout=timeout)

    def test_connection(self) -> dict:
        """Make a single free Street View metadata call to verify the key works.

        Returns dict with status info. Does NOT use Places API (which may be
        IP-restricted), uses Street View metadata which is free and accessible.
        """
        url = "https://maps.googleapis.com/maps/api/streetview/metadata"
        resp = self.client.get(url, params={
            "location": "43.6532,-79.3832",  # Toronto
            "key": self.api_key,
        })
        resp.raise_for_status()
        data = resp.json()
        return {
            "status": data.get("status"),
            "ok": data.get("status") == "OK",
            "pano_id": data.get("pano_id"),
        }

    def text_search(self, query: str) -> Optional[str]:
        """Search for a place by text query, return place_id or None.

        Uses Text Search (IDs Only) SKU — free and unlimited.
        """
        if not self.budget.can_use("text_search_ids"):
            raise BudgetExhausted("text_search_ids budget exhausted")

        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASKS["ids_only"],
            "Content-Type": "application/json",
        }
        body = {"textQuery": query}

        try:
            resp = self.client.post(TEXT_SEARCH_URL, headers=headers, json=body)
            resp.raise_for_status()
            self.budget.record_use("text_search_ids")

            data = resp.json()
            places = data.get("places", [])
            if not places:
                return None
            # Extract place ID from resource name: "places/ChIJ..."
            name = places[0].get("id") or places[0].get("name", "")
            if name.startswith("places/"):
                return name[7:]
            return name or None
        except httpx.HTTPStatusError as e:
            logger.error("Text search failed for %r: %s", query, e)
            raise

    def place_details(self, place_id: str, tier: str) -> Optional[dict]:
        """Fetch place details for a specific billing tier.

        Args:
            place_id: Google place ID (e.g., "ChIJ...")
            tier: One of "essentials", "pro", "enterprise"

        Returns dict of fields for that tier, or None on failure.
        """
        if tier not in TIER_TO_SKU:
            raise ValueError(f"Unknown tier: {tier}. Use: essentials, pro, enterprise")

        sku = TIER_TO_SKU[tier]
        if not self.budget.can_use(sku):
            raise BudgetExhausted(f"{sku} budget exhausted")

        url = PLACE_DETAILS_URL.format(place_id=place_id)
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASKS[tier],
        }

        try:
            resp = self.client.get(url, headers=headers)
            resp.raise_for_status()
            self.budget.record_use(sku)
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Place details (%s) failed for %s: %s", tier, place_id, e)
            raise

    def text_search_batch(
        self, queries: list[str], delay: float = 0.1
    ) -> list[Optional[str]]:
        """Search multiple queries, return list of place_ids (or None).

        Note: Google Places (New) doesn't have a batch endpoint, so this
        makes sequential calls with a delay between them.
        """
        results: list[Optional[str]] = []
        for query in queries:
            try:
                place_id = self.text_search(query)
                results.append(place_id)
            except BudgetExhausted:
                logger.warning("Budget exhausted during batch text search at %d/%d", len(results), len(queries))
                break
            except Exception as e:
                logger.error("Text search failed for %r: %s", query, e)
                results.append(None)
            if delay > 0:
                time.sleep(delay)
        return results

    def place_details_batch(
        self, place_ids: list[str], tier: str, delay: float = 0.1
    ) -> list[Optional[dict]]:
        """Fetch details for multiple place IDs at a given tier.

        Sequential with delay. Stops early if budget exhausted.
        """
        results: list[Optional[dict]] = []
        for pid in place_ids:
            try:
                detail = self.place_details(pid, tier)
                results.append(detail)
            except BudgetExhausted:
                logger.warning(
                    "Budget exhausted during batch details (%s) at %d/%d",
                    tier, len(results), len(place_ids),
                )
                break
            except Exception as e:
                logger.error("Details (%s) failed for %s: %s", tier, pid, e)
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
