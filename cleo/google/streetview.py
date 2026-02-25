"""Street View Static API client.

Two operations:
1. Metadata check (FREE) — returns coverage status, pano_id, date
2. Image fetch (budget-gated) — downloads JPEG to data/streetview/{prop_id}.jpg
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import httpx

from cleo.config import GOOGLE_API_KEY, STREETVIEW_DIR
from cleo.google.budget import BudgetGuardian, BudgetExhausted

logger = logging.getLogger(__name__)

METADATA_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
IMAGE_URL = "https://maps.googleapis.com/maps/api/streetview"

# Image params
DEFAULT_SIZE = "640x480"
DEFAULT_FOV = 90
DEFAULT_PITCH = 0


class StreetViewClient:
    """Street View Static API client, gated by BudgetGuardian."""

    def __init__(self, api_key: str, budget: BudgetGuardian, timeout: float = 30.0):
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required. Add it to your .env file.")
        self.api_key = api_key
        self.budget = budget
        self.client = httpx.Client(timeout=timeout)

    def check_metadata(self, lat: float, lng: float) -> dict:
        """Check Street View coverage at coordinates. FREE — no budget charge.

        Returns:
            {
                "has_coverage": bool,
                "pano_id": str | None,
                "date": str | None,       # e.g., "2023-06"
                "status": str,            # "OK", "ZERO_RESULTS", etc.
            }
        """
        # Metadata is free but we track it for observability
        if not self.budget.can_use("streetview_metadata"):
            raise BudgetExhausted("streetview_metadata budget exhausted")

        params = {
            "location": f"{lat},{lng}",
            "key": self.api_key,
        }
        resp = self.client.get(METADATA_URL, params=params)
        resp.raise_for_status()
        self.budget.record_use("streetview_metadata")

        data = resp.json()
        status = data.get("status", "UNKNOWN")
        return {
            "has_coverage": status == "OK",
            "pano_id": data.get("pano_id"),
            "date": data.get("date"),
            "status": status,
            "location": data.get("location"),
        }

    def fetch_image(
        self,
        lat: float,
        lng: float,
        prop_id: str,
        size: str = DEFAULT_SIZE,
        fov: int = DEFAULT_FOV,
        pitch: int = DEFAULT_PITCH,
    ) -> Optional[Path]:
        """Fetch a Street View image and save to data/streetview/{prop_id}.jpg.

        Returns the saved file path, or None if no coverage.
        Raises BudgetExhausted if image budget is spent.
        """
        if not self.budget.can_use("streetview_image"):
            raise BudgetExhausted("streetview_image budget exhausted")

        params = {
            "location": f"{lat},{lng}",
            "size": size,
            "fov": fov,
            "pitch": pitch,
            "key": self.api_key,
        }
        resp = self.client.get(IMAGE_URL, params=params)
        resp.raise_for_status()

        # Check content type — Google returns image/jpeg for success,
        # application/json for errors
        content_type = resp.headers.get("content-type", "")
        if "image" not in content_type:
            logger.warning("No image returned for %s (content-type: %s)", prop_id, content_type)
            return None

        self.budget.record_use("streetview_image")

        # Save atomically
        out_path = STREETVIEW_DIR / f"{prop_id}.jpg"
        STREETVIEW_DIR.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            dir=STREETVIEW_DIR, suffix=".tmp", prefix=f".sv_{prop_id}_"
        )
        try:
            os.write(fd, resp.content)
            os.close(fd)
            os.replace(tmp_path, out_path)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        return out_path

    def close(self):
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
