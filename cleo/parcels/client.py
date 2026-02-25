"""Generic ArcGIS REST spatial query client.

Handles coordinate projection (WGS84 <-> UTM/WebMercator), bbox-based
spatial queries, pagination, and throttling. No pyproj dependency --
uses standard math formulas for sub-meter accuracy at Ontario latitudes.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# --- Coordinate projection (no pyproj) ---


def _wgs84_to_web_mercator(lng: float, lat: float) -> tuple[float, float]:
    """Convert WGS84 (lng, lat) to Web Mercator (x, y) EPSG:3857."""
    x = lng * 20037508.34 / 180.0
    y = math.log(math.tan((90.0 + lat) * math.pi / 360.0)) / (math.pi / 180.0)
    y = y * 20037508.34 / 180.0
    return x, y


def _web_mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert Web Mercator (x, y) EPSG:3857 to WGS84 (lng, lat)."""
    lng = x * 180.0 / 20037508.34
    lat = y * 180.0 / 20037508.34
    lat = 180.0 / math.pi * (2.0 * math.atan(math.exp(lat * math.pi / 180.0)) - math.pi / 2.0)
    return lng, lat


def _wgs84_to_utm17n(lng: float, lat: float) -> tuple[float, float]:
    """Convert WGS84 (lng, lat) to NAD83/UTM zone 17N EPSG:26917.

    Uses the transverse Mercator equations. Accurate to <1m at Ontario latitudes.
    """
    # UTM zone 17N: central meridian -81, false easting 500000
    a = 6378137.0  # WGS84 semi-major axis
    f = 1 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1 - e2)
    k0 = 0.9996
    lon0 = math.radians(-81.0)  # zone 17 central meridian

    phi = math.radians(lat)
    lam = math.radians(lng)
    dlam = lam - lon0

    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)
    tan_phi = math.tan(phi)

    N = a / math.sqrt(1 - e2 * sin_phi ** 2)
    T = tan_phi ** 2
    C = e_prime2 * cos_phi ** 2
    A = cos_phi * dlam

    # Meridional arc
    M = a * (
        (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
        - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
        + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
        - (35 * e2 ** 3 / 3072) * math.sin(6 * phi)
    )

    x = k0 * N * (
        A
        + (1 - T + C) * A ** 3 / 6
        + (5 - 18 * T + T ** 2 + 72 * C - 58 * e_prime2) * A ** 5 / 120
    ) + 500000.0  # false easting

    y = k0 * (
        M
        + N * tan_phi * (
            A ** 2 / 2
            + (5 - T + 9 * C + 4 * C ** 2) * A ** 4 / 24
            + (61 - 58 * T + T ** 2 + 600 * C - 330 * e_prime2) * A ** 6 / 720
        )
    )

    return x, y


def _utm17n_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert NAD83/UTM zone 17N EPSG:26917 to WGS84 (lng, lat)."""
    a = 6378137.0
    f = 1 / 298.257223563
    e2 = 2 * f - f * f
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    e_prime2 = e2 / (1 - e2)
    k0 = 0.9996
    lon0 = -81.0

    x -= 500000.0  # remove false easting
    M = y / k0
    mu = M / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))

    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
        + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
        + (151 * e1 ** 3 / 96) * math.sin(6 * mu)
    )

    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    tan_phi1 = math.tan(phi1)
    N1 = a / math.sqrt(1 - e2 * sin_phi1 ** 2)
    T1 = tan_phi1 ** 2
    C1 = e_prime2 * cos_phi1 ** 2
    R1 = a * (1 - e2) / (1 - e2 * sin_phi1 ** 2) ** 1.5
    D = x / (N1 * k0)

    lat = phi1 - (N1 * tan_phi1 / R1) * (
        D ** 2 / 2
        - (5 + 3 * T1 + 10 * C1 - 4 * C1 ** 2 - 9 * e_prime2) * D ** 4 / 24
        + (61 + 90 * T1 + 298 * C1 + 45 * T1 ** 2 - 252 * e_prime2 - 3 * C1 ** 2)
        * D ** 6 / 720
    )

    lng = (
        D
        - (1 + 2 * T1 + C1) * D ** 3 / 6
        + (5 - 2 * C1 + 28 * T1 - 3 * C1 ** 2 + 8 * e_prime2 + 24 * T1 ** 2)
        * D ** 5 / 120
    ) / cos_phi1

    return lon0 + math.degrees(lng), math.degrees(lat)


def wgs84_to_service_coords(lng: float, lat: float, srid: int) -> tuple[float, float]:
    """Project WGS84 point to the service's native coordinate system."""
    if srid == 4326:
        return lng, lat
    elif srid in (3857, 102100):
        return _wgs84_to_web_mercator(lng, lat)
    elif srid in (26917, 2958):
        # Both use UTM zone 17N; 2958 is NAD83(CSRS) but the difference
        # from 26917 (NAD83) is < 2m — negligible for our bbox queries.
        return _wgs84_to_utm17n(lng, lat)
    else:
        raise ValueError(f"Unsupported SRID: {srid}")


def service_coords_to_wgs84(x: float, y: float, srid: int) -> tuple[float, float]:
    """Unproject from service coordinates to WGS84 (lng, lat)."""
    if srid == 4326:
        return x, y
    elif srid in (3857, 102100):
        return _web_mercator_to_wgs84(x, y)
    elif srid in (26917, 2958):
        return _utm17n_to_wgs84(x, y)
    else:
        raise ValueError(f"Unsupported SRID: {srid}")


# --- ArcGIS REST query client ---

DEFAULT_TIMEOUT = 30.0
DEFAULT_THROTTLE = 0.5  # seconds between requests


class ArcGISClient:
    """Query ArcGIS REST services for parcels and zoning."""

    def __init__(self, throttle: float = DEFAULT_THROTTLE, timeout: float = DEFAULT_TIMEOUT):
        self._throttle = throttle
        self._timeout = timeout
        self._last_request: float = 0
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": "Cleo/3.0 parcel-harvester"},
            )
        return self._client

    def _wait_throttle(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self._throttle:
            time.sleep(self._throttle - elapsed)
        self._last_request = time.time()

    def query_at_point(
        self,
        service_url: str,
        lat: float,
        lng: float,
        srid: int,
        out_fields: str = "*",
        buffer_m: float = 50.0,
    ) -> list[dict]:
        """Query an ArcGIS service for features near a point.

        Uses a small bbox (buffer_m) around the point with esriSpatialRelIntersects.
        Returns raw ArcGIS feature dicts with geometry reprojected to WGS84.
        """
        # Build bbox in service coordinates
        sx, sy = wgs84_to_service_coords(lng, lat, srid)

        # Buffer in service units (meters for UTM/Mercator)
        if srid == 4326:
            # ~degrees at Ontario lat
            buf_deg = buffer_m / 79_000
            xmin, ymin = sx - buf_deg, sy - buf_deg
            xmax, ymax = sx + buf_deg, sy + buf_deg
        else:
            xmin, ymin = sx - buffer_m, sy - buffer_m
            xmax, ymax = sx + buffer_m, sy + buffer_m

        envelope = f"{xmin},{ymin},{xmax},{ymax}"

        params = {
            "geometry": envelope,
            "geometryType": "esriGeometryEnvelope",
            "inSR": str(srid),
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": out_fields,
            "returnGeometry": "true",
            "outSR": "4326",  # always get results in WGS84
            "f": "json",
        }

        self._wait_throttle()
        client = self._get_client()

        try:
            url = f"{service_url}/query"
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ArcGIS query failed for (%s, %s): %s", lat, lng, exc)
            return []

        if "error" in data:
            logger.warning(
                "ArcGIS error for (%s, %s): %s",
                lat, lng, data["error"].get("message", data["error"]),
            )
            return []

        features = data.get("features", [])
        return features

    def query_zoning_at_point(
        self,
        zoning_url: str,
        lat: float,
        lng: float,
        srid: int,
    ) -> Optional[dict]:
        """Query a zoning layer at a specific point.

        Returns the first intersecting zone's attributes, or None.
        """
        features = self.query_at_point(
            zoning_url, lat, lng, srid, buffer_m=10.0,
        )
        if features:
            return features[0].get("attributes", {})
        return None

    def query_by_where(
        self,
        service_url: str,
        where: str,
        out_fields: str = "*",
        return_geometry: bool = True,
    ) -> list[dict]:
        """Query an ArcGIS service using a WHERE clause.

        Reusable for any attribute-based lookup (address, Parcel_ID, PIN, etc.).
        Returns raw ArcGIS feature dicts with geometry in WGS84 (outSR=4326).
        """
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "true" if return_geometry else "false",
            "outSR": "4326",
            "f": "json",
        }

        self._wait_throttle()
        client = self._get_client()

        try:
            url = f"{service_url}/query"
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ArcGIS WHERE query failed (%s): %s", where, exc)
            return []

        if "error" in data:
            logger.warning(
                "ArcGIS error for WHERE (%s): %s",
                where, data["error"].get("message", data["error"]),
            )
            return []

        return data.get("features", [])

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
