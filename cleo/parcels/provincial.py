"""Ontario provincial Assessment Parcel client.

Queries the MPAC Assessment Parcel MapServer hosted on Ontario's LIO
infrastructure (AgMaps). This provides province-wide parcel boundaries
with ARN/PIN data, eliminating the need for municipality-specific
ArcGIS endpoints.

Service URL:
    https://ws.lioservices.lrc.gov.on.ca/arcgis4/rest/services/AIA/Assessment_Parcel_Map/MapServer/0

Authentication:
    Requires a token obtained from the AgMaps viewer. The user must:
    1. Visit https://www.gisapplication.lrc.gov.on.ca/AIA/Index.html?viewer=AIA.AIA
    2. Accept the Ontario Parcel License Agreement
    3. Copy the token from browser DevTools (Network tab, look for "token=" param)
    4. Set AGMAPS_TOKEN in .env

The token expires (typically after a few hours), so it must be refreshed
periodically by revisiting the AgMaps viewer.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Optional

import httpx

from cleo.config import AGMAPS_PARCEL_URL, AGMAPS_TOKEN

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DEFAULT_THROTTLE = 0.4  # seconds between requests


def _point_in_ring(px: float, py: float, ring: list) -> bool:
    """Ray-casting point-in-polygon test for a single ring."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


class ProvincialParcelClient:
    """Query the Ontario Assessment Parcel MapServer for parcel boundaries.

    Uses token-based auth against the provincial AIA MapServer endpoint.
    All queries request outSR=4326 (WGS84) for consistency with the rest
    of the parcel pipeline.
    """

    def __init__(
        self,
        token: str | None = None,
        throttle: float = DEFAULT_THROTTLE,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self._token = token or AGMAPS_TOKEN
        if not self._token:
            raise ValueError(
                "No AgMaps token. Set AGMAPS_TOKEN in .env or pass token= parameter.\n"
                "Get a token from: https://www.gisapplication.lrc.gov.on.ca/AIA/Index.html?viewer=AIA.AIA\n"
                "Accept the license, then grab the token from browser DevTools Network tab."
            )
        self._base_url = AGMAPS_PARCEL_URL
        self._throttle = throttle
        self._timeout = timeout
        self._last_request: float = 0
        self._client: Optional[httpx.Client] = None
        self._request_count = 0

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": "Cleo/3.0 provincial-parcel-client"},
            )
        return self._client

    def _wait_throttle(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self._throttle:
            time.sleep(self._throttle - elapsed)
        self._last_request = time.time()

    def _query(self, params: dict) -> dict:
        """Execute a query against the MapServer with token auth."""
        params["token"] = self._token
        params["f"] = "json"

        self._wait_throttle()
        client = self._get_client()
        self._request_count += 1

        url = f"{self._base_url}/query"
        try:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 498:
                raise TokenExpiredError(
                    "AgMaps token has expired. Visit AgMaps viewer to get a new one."
                ) from exc
            logger.warning("Provincial parcel query failed: %s", exc)
            return {"features": [], "error": str(exc)}
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Provincial parcel query failed: %s", exc)
            return {"features": [], "error": str(exc)}

        if "error" in data:
            err_msg = data["error"].get("message", str(data["error"]))
            if "token" in err_msg.lower() or "invalid" in err_msg.lower():
                raise TokenExpiredError(f"AgMaps token error: {err_msg}")
            logger.warning("Provincial parcel query error: %s", err_msg)
            return {"features": [], "error": err_msg}

        return data

    def query_at_point(
        self,
        lat: float,
        lng: float,
        buffer_deg: float = 0.0002,
        out_fields: str = "*",
    ) -> list[dict]:
        """Query for parcels containing or near a point.

        Args:
            lat: WGS84 latitude
            lng: WGS84 longitude
            buffer_deg: Buffer around point in degrees (~15m at Ontario latitudes)
            out_fields: Fields to return ("*" for all)

        Returns:
            List of ArcGIS feature dicts with geometry in WGS84
        """
        xmin = lng - buffer_deg
        ymin = lat - buffer_deg
        xmax = lng + buffer_deg
        ymax = lat + buffer_deg
        envelope = f"{xmin},{ymin},{xmax},{ymax}"

        params = {
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
        }

        data = self._query(params)
        return data.get("features", [])

    def pick_containing_parcel(
        self,
        features: list[dict],
        lat: float,
        lng: float,
    ) -> dict | None:
        """Pick the feature whose polygon actually contains the point.

        Falls back to the first feature if none contain the point.
        Returns None if features is empty.
        """
        if not features:
            return None

        for feat in features:
            rings = feat.get("geometry", {}).get("rings", [])
            if not rings:
                continue
            # Rings are [[lng, lat], ...] in ArcGIS GeoJSON output
            if _point_in_ring(lng, lat, rings[0]):
                return feat

        # Fallback: closest by centroid distance
        return features[0]

    def query_by_arn(self, arn: str, out_fields: str = "*") -> list[dict]:
        """Query for a parcel by Assessment Roll Number."""
        # ASSESSMENT_ROLL_NUMBER is the correct field on the provincial layer
        for field in ["ASSESSMENT_ROLL_NUMBER", "ARN", "AssessmentRollNumber"]:
            params = {
                "where": f"{field}='{arn}'",
                "outFields": out_fields,
                "returnGeometry": "true",
                "outSR": "4326",
            }
            data = self._query(params)
            features = data.get("features", [])
            if features:
                return features
            # If query errored (wrong field name), try next
            if "error" in data:
                continue

        return []

    def query_by_pin(self, pin: str, out_fields: str = "*") -> list[dict]:
        """Query for a parcel by Property Identification Number."""
        for field in ["PIN", "PropertyIdentificationNumber"]:
            params = {
                "where": f"{field}='{pin}'",
                "outFields": out_fields,
                "returnGeometry": "true",
                "outSR": "4326",
            }
            data = self._query(params)
            features = data.get("features", [])
            if features:
                return features
            if "error" in data and "field" in str(data.get("error", "")).lower():
                continue
            break

        return []

    def query_bbox(
        self,
        south: float,
        west: float,
        north: float,
        east: float,
        out_fields: str = "*",
        max_records: int = 2000,
    ) -> list[dict]:
        """Query all parcels within a bounding box.

        Note: MapServer has MaxRecordCount of 2000. For areas with more
        parcels, use query_bbox_paginated() or subdivide the bbox.
        """
        envelope = f"{west},{south},{east},{north}"
        params = {
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",
            "resultRecordCount": str(max_records),
        }
        data = self._query(params)
        return data.get("features", [])

    def test_connection(self) -> dict:
        """Test that the token is valid by querying the service metadata.

        Returns service info dict on success, raises on failure.
        """
        client = self._get_client()
        try:
            resp = client.get(
                self._base_url,
                params={"f": "json", "token": self._token},
            )
            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                err = data["error"].get("message", str(data["error"]))
                raise TokenExpiredError(f"Token validation failed: {err}")

            return {
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "max_record_count": data.get("maxRecordCount"),
                "fields": [f.get("name") for f in data.get("fields", [])],
                "geometry_type": data.get("geometryType", ""),
            }

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 498:
                raise TokenExpiredError("Token expired") from exc
            raise

    @property
    def request_count(self) -> int:
        return self._request_count

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


class TokenExpiredError(Exception):
    """Raised when the AgMaps token has expired or is invalid."""
    pass
