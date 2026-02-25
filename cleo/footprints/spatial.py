"""Spatial index over building footprint polygons using Shapely STRtree.

Provides point-in-polygon and nearest-footprint queries for matching
properties and brand POIs to building footprints.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Optional

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from cleo.config import FOOTPRINTS_PATH

logger = logging.getLogger(__name__)


class FootprintIndex:
    """R-tree spatial index over building footprint polygons.

    Loads filtered footprints from disk and builds an STRtree for fast
    point-in-polygon and nearest-footprint queries.
    """

    def __init__(self, footprints_path: Path | None = None):
        self._path = footprints_path or FOOTPRINTS_PATH
        self._polys: list = []
        self._fp_ids: list[str] = []
        self._features: dict[str, dict] = {}  # fp_id -> feature properties
        self._tree: Optional[STRtree] = None
        self._loaded = False

    def load(self) -> None:
        """Load footprints and build spatial index."""
        if not self._path.exists():
            logger.warning("Footprints file not found: %s", self._path)
            self._loaded = True
            return

        data = json.loads(self._path.read_text(encoding="utf-8"))
        features = data.get("features", [])

        polys = []
        fp_ids = []
        for feat in features:
            props = feat.get("properties", {})
            fp_id = props.get("fp_id", "")
            if not fp_id:
                continue

            try:
                poly = shape(feat["geometry"])
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_valid and not poly.is_empty:
                    polys.append(poly)
                    fp_ids.append(fp_id)
                    self._features[fp_id] = props
            except Exception:
                continue

        self._polys = polys
        self._fp_ids = fp_ids

        if polys:
            self._tree = STRtree(polys)

        self._loaded = True
        logger.info("Loaded %d building footprints into spatial index", len(polys))

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    @property
    def count(self) -> int:
        self._ensure_loaded()
        return len(self._polys)

    def find_containing(self, lat: float, lng: float) -> list[str]:
        """Find footprint IDs whose polygon contains the given point.

        Returns list of fp_ids (usually 0 or 1, but could be multiple
        for overlapping buildings).
        """
        self._ensure_loaded()
        if self._tree is None:
            return []

        point = Point(lng, lat)
        candidates = self._tree.query(point)
        results = []
        for idx in candidates:
            if self._polys[idx].contains(point):
                results.append(self._fp_ids[idx])
        return results

    def find_nearest(self, lat: float, lng: float, max_m: float = 30) -> Optional[str]:
        """Find the nearest footprint within max_m meters.

        Falls back for cases where the geocoded point doesn't land
        exactly inside a building polygon (coordinate drift).
        """
        self._ensure_loaded()
        if self._tree is None:
            return None

        point = Point(lng, lat)

        # Query with a buffer (~max_m in degrees, rough approximation)
        # At 44N latitude: 1 deg lat = ~111km, 1 deg lng = ~79km
        buffer_deg = max_m / 79_000  # conservative: use smaller lng scale
        search_area = point.buffer(buffer_deg)
        candidates = self._tree.query(search_area)

        best_dist = float("inf")
        best_fp_id = None

        for idx in candidates:
            poly = self._polys[idx]
            # Distance in degrees — convert to approximate meters
            dist_deg = poly.distance(point)
            # Rough conversion at Ontario latitudes
            dist_m = dist_deg * 95_000  # average of lat/lng scales
            if dist_m < best_dist and dist_m <= max_m:
                best_dist = dist_m
                best_fp_id = self._fp_ids[idx]

        return best_fp_id

    def get_feature(self, fp_id: str) -> Optional[dict]:
        """Get the properties dict for a footprint by ID."""
        self._ensure_loaded()
        return self._features.get(fp_id)

    def get_polygon_geojson(self, fp_id: str) -> Optional[dict]:
        """Get the GeoJSON geometry for a footprint by ID."""
        self._ensure_loaded()
        if fp_id not in self._features:
            return None

        try:
            idx = self._fp_ids.index(fp_id)
            poly = self._polys[idx]
            from shapely.geometry import mapping
            return mapping(poly)
        except (ValueError, IndexError):
            return None

    def get_area_sqm(self, fp_id: str) -> Optional[float]:
        """Approximate building footprint area in square meters.

        Uses a simplified projection at Ontario latitudes.
        """
        self._ensure_loaded()
        try:
            idx = self._fp_ids.index(fp_id)
            poly = self._polys[idx]
        except (ValueError, IndexError):
            return None

        # Get centroid for projection scale
        centroid = poly.centroid
        lat = centroid.y
        # At this latitude, degrees to meters conversion
        m_per_deg_lat = 111_320
        m_per_deg_lng = 111_320 * math.cos(math.radians(lat))

        # Scale polygon coords to meters and compute area
        coords = list(poly.exterior.coords)
        ref_lat, ref_lng = coords[0][1], coords[0][0]
        m_coords = [
            ((c[0] - ref_lng) * m_per_deg_lng, (c[1] - ref_lat) * m_per_deg_lat)
            for c in coords
        ]

        # Shoelace formula
        n = len(m_coords)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += m_coords[i][0] * m_coords[j][1]
            area -= m_coords[j][0] * m_coords[i][1]

        return round(abs(area) / 2, 1)

    def features_in_bbox(
        self, south: float, west: float, north: float, east: float
    ) -> list[dict]:
        """Return GeoJSON features whose centroid falls within the bbox.

        Used by the viewport API endpoint.
        """
        self._ensure_loaded()
        results = []
        for i, fp_id in enumerate(self._fp_ids):
            props = self._features.get(fp_id, {})
            clat = props.get("centroid_lat")
            clng = props.get("centroid_lng")
            if clat is None or clng is None:
                continue
            if south <= clat <= north and west <= clng <= east:
                from shapely.geometry import mapping
                results.append({
                    "type": "Feature",
                    "geometry": mapping(self._polys[i]),
                    "properties": props,
                })
        return results
