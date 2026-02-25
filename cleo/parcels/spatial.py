"""Spatial index over parcel polygons using Shapely STRtree.

Provides point-in-parcel and bbox queries for matching brand POIs
and properties to municipal parcels.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Optional

from shapely.geometry import Point, mapping, shape
from shapely.strtree import STRtree

from cleo.config import PARCELS_PATH

logger = logging.getLogger(__name__)


class ParcelIndex:
    """R-tree spatial index over parcel polygons.

    Loads harvested parcels from disk and builds an STRtree for fast
    point-in-polygon and viewport queries.
    """

    def __init__(self, parcels_path: Path | None = None):
        self._path = parcels_path or PARCELS_PATH
        self._polys: list = []
        self._pcl_ids: list[str] = []
        self._features: dict[str, dict] = {}  # pcl_id -> feature properties
        self._tree: Optional[STRtree] = None
        self._loaded = False

    def load(self) -> None:
        if not self._path.exists():
            logger.warning("Parcels file not found: %s", self._path)
            self._loaded = True
            return

        data = json.loads(self._path.read_text(encoding="utf-8"))
        features = data.get("features", [])

        polys = []
        pcl_ids = []
        for feat in features:
            props = feat.get("properties", {})
            pcl_id = props.get("pcl_id", "")
            if not pcl_id:
                continue

            try:
                poly = shape(feat["geometry"])
                if not poly.is_valid:
                    poly = poly.buffer(0)
                if poly.is_valid and not poly.is_empty:
                    polys.append(poly)
                    pcl_ids.append(pcl_id)
                    self._features[pcl_id] = props
            except Exception:
                continue

        self._polys = polys
        self._pcl_ids = pcl_ids

        if polys:
            self._tree = STRtree(polys)

        self._loaded = True
        logger.info("Loaded %d parcels into spatial index", len(polys))

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    @property
    def count(self) -> int:
        self._ensure_loaded()
        return len(self._polys)

    def find_containing(self, lat: float, lng: float) -> list[str]:
        """Find parcel IDs whose polygon contains the given point."""
        self._ensure_loaded()
        if self._tree is None:
            return []

        point = Point(lng, lat)
        candidates = self._tree.query(point)
        results = []
        for idx in candidates:
            if self._polys[idx].contains(point):
                results.append(self._pcl_ids[idx])
        return results

    def find_nearest(self, lat: float, lng: float, max_m: float = 50) -> Optional[str]:
        """Find the nearest parcel within max_m meters."""
        self._ensure_loaded()
        if self._tree is None:
            return None

        point = Point(lng, lat)
        buffer_deg = max_m / 79_000
        search_area = point.buffer(buffer_deg)
        candidates = self._tree.query(search_area)

        best_dist = float("inf")
        best_pcl_id = None

        for idx in candidates:
            poly = self._polys[idx]
            dist_deg = poly.distance(point)
            dist_m = dist_deg * 95_000
            if dist_m < best_dist and dist_m <= max_m:
                best_dist = dist_m
                best_pcl_id = self._pcl_ids[idx]

        return best_pcl_id

    def get_feature(self, pcl_id: str) -> Optional[dict]:
        """Get the properties dict for a parcel by ID."""
        self._ensure_loaded()
        return self._features.get(pcl_id)

    def get_polygon_geojson(self, pcl_id: str) -> Optional[dict]:
        """Get the GeoJSON geometry for a parcel by ID."""
        self._ensure_loaded()
        if pcl_id not in self._features:
            return None

        try:
            idx = self._pcl_ids.index(pcl_id)
            poly = self._polys[idx]
            return mapping(poly)
        except (ValueError, IndexError):
            return None

    def get_area_sqm(self, pcl_id: str) -> Optional[float]:
        """Approximate parcel area in square meters."""
        self._ensure_loaded()
        try:
            idx = self._pcl_ids.index(pcl_id)
            poly = self._polys[idx]
        except (ValueError, IndexError):
            return None

        centroid = poly.centroid
        lat = centroid.y
        m_per_deg_lat = 111_320
        m_per_deg_lng = 111_320 * math.cos(math.radians(lat))

        coords = list(poly.exterior.coords)
        ref_lat, ref_lng = coords[0][1], coords[0][0]
        m_coords = [
            ((c[0] - ref_lng) * m_per_deg_lng, (c[1] - ref_lat) * m_per_deg_lat)
            for c in coords
        ]

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
        """Return GeoJSON features whose centroid falls within the bbox."""
        self._ensure_loaded()
        results = []
        for i, pcl_id in enumerate(self._pcl_ids):
            props = self._features.get(pcl_id, {})
            clat = props.get("centroid_lat")
            clng = props.get("centroid_lng")
            if clat is None or clng is None:
                continue
            if south <= clat <= north and west <= clng <= east:
                results.append({
                    "type": "Feature",
                    "geometry": mapping(self._polys[i]),
                    "properties": props,
                })
        return results
