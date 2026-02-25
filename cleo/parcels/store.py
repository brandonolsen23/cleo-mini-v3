"""ParcelStore: on-disk cache for harvested parcel polygons and attributes.

Stores parcel features as GeoJSON with stable PCL_NNNNN IDs.
Deduplicates by (municipality, pin_or_arn) where available,
falling back to geometry overlap.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from cleo.config import PARCELS_PATH

logger = logging.getLogger(__name__)


class ParcelStore:
    """Manage the parcels.json cache file.

    Structure:
    {
        "meta": {"total": N, "by_municipality": {...}},
        "features": [
            {
                "type": "Feature",
                "geometry": {...},  # GeoJSON polygon in WGS84
                "properties": {
                    "pcl_id": "PCL00001",
                    "municipality": "grey",
                    "pin": "...",
                    "arn": "...",
                    "address": "...",
                    "city": "...",
                    "zone_code": "...",
                    "zone_desc": "...",
                    "area_sqm": ...,
                    "assessment": ...,
                    "property_use": "...",
                    "legal_desc": "...",
                    "centroid_lat": ...,
                    "centroid_lng": ...,
                }
            }
        ],
        "property_to_parcel": {"P00001": "PCL00001", ...},
        "no_coverage": ["P00002", ...]
    }
    """

    def __init__(self, path: Path | None = None):
        self._path = path or PARCELS_PATH
        self._data: Optional[dict] = None

    def _load(self) -> dict:
        if self._data is not None:
            return self._data

        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._data = {
                "meta": {"total": 0, "by_municipality": {}},
                "features": [],
                "property_to_parcel": {},
                "no_coverage": [],
            }
        return self._data

    @property
    def features(self) -> list[dict]:
        return self._load()["features"]

    @property
    def property_to_parcel(self) -> dict[str, str]:
        return self._load()["property_to_parcel"]

    @property
    def no_coverage(self) -> list[str]:
        return self._load()["no_coverage"]

    def _next_pcl_id(self) -> str:
        """Generate the next PCL_NNNNN ID."""
        existing = self._load()["features"]
        if not existing:
            return "PCL00001"
        max_num = 0
        for feat in existing:
            pcl_id = feat.get("properties", {}).get("pcl_id", "")
            if pcl_id.startswith("PCL"):
                try:
                    num = int(pcl_id[3:])
                    max_num = max(max_num, num)
                except ValueError:
                    pass
        return f"PCL{max_num + 1:05d}"

    def _dedup_key(self, municipality: str, props: dict) -> Optional[str]:
        """Build dedup key from municipality + pin/arn."""
        pin = props.get("pin") or props.get("arn")
        if pin:
            return f"{municipality}:{pin}"
        return None

    def _existing_keys(self) -> set[str]:
        """Build set of existing dedup keys."""
        keys = set()
        for feat in self.features:
            p = feat.get("properties", {})
            key = self._dedup_key(p.get("municipality", ""), p)
            if key:
                keys.add(key)
        return keys

    def add_parcels(
        self,
        municipality: str,
        new_features: list[dict],
    ) -> dict:
        """Add new parcel features, deduplicating by (municipality, pin/arn).

        Each feature dict should have:
        - geometry: GeoJSON polygon (WGS84)
        - properties: dict with extracted attributes

        Returns summary dict.
        """
        data = self._load()
        existing_keys = self._existing_keys()
        added = 0
        skipped = 0

        for feat in new_features:
            props = feat.get("properties", {})
            props["municipality"] = municipality
            key = self._dedup_key(municipality, props)

            if key and key in existing_keys:
                skipped += 1
                continue

            pcl_id = self._next_pcl_id()
            props["pcl_id"] = pcl_id

            # Compute centroid from geometry
            geom = feat.get("geometry", {})
            centroid = _polygon_centroid(geom)
            if centroid:
                props["centroid_lat"] = round(centroid[1], 7)
                props["centroid_lng"] = round(centroid[0], 7)

            data["features"].append({
                "type": "Feature",
                "geometry": geom,
                "properties": props,
            })

            if key:
                existing_keys.add(key)
            added += 1

        # Update meta
        data["meta"]["total"] = len(data["features"])
        by_muni: dict[str, int] = {}
        for f in data["features"]:
            m = f.get("properties", {}).get("municipality", "unknown")
            by_muni[m] = by_muni.get(m, 0) + 1
        data["meta"]["by_municipality"] = by_muni

        return {"added": added, "skipped_dups": skipped}

    def set_property_mapping(self, prop_id: str, pcl_id: str) -> None:
        """Link a property to a parcel."""
        self._load()["property_to_parcel"][prop_id] = pcl_id

    def mark_no_coverage(self, prop_id: str) -> None:
        """Mark a property as having no parcel coverage."""
        data = self._load()
        if prop_id not in data["no_coverage"]:
            data["no_coverage"].append(prop_id)

    def get_parcel(self, pcl_id: str) -> Optional[dict]:
        """Look up a parcel feature by PCL ID."""
        for feat in self.features:
            if feat.get("properties", {}).get("pcl_id") == pcl_id:
                return feat
        return None

    def get_parcel_for_property(self, prop_id: str) -> Optional[dict]:
        """Look up the parcel feature linked to a property."""
        pcl_id = self.property_to_parcel.get(prop_id)
        if pcl_id:
            return self.get_parcel(pcl_id)
        return None

    def save(self) -> None:
        """Write parcels.json atomically."""
        data = self._load()
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.rename(self._path)
        logger.info("Saved %d parcels to %s", data["meta"]["total"], self._path)

    def status(self) -> dict:
        """Return summary statistics."""
        data = self._load()
        return {
            "total_parcels": data["meta"]["total"],
            "by_municipality": data["meta"].get("by_municipality", {}),
            "properties_mapped": len(data["property_to_parcel"]),
            "no_coverage": len(data["no_coverage"]),
            "file_exists": self._path.exists(),
        }


def _polygon_centroid(geom: dict) -> Optional[tuple[float, float]]:
    """Compute centroid of a GeoJSON polygon as (lng, lat).

    Simple average of exterior ring coordinates.
    """
    if not geom:
        return None
    gtype = geom.get("type", "")
    rings = geom.get("coordinates", [])

    if gtype == "Polygon" and rings:
        coords = rings[0]  # exterior ring
    elif gtype == "MultiPolygon" and rings:
        coords = rings[0][0]  # first polygon exterior ring
    else:
        return None

    if not coords:
        return None

    n = len(coords)
    avg_x = sum(c[0] for c in coords) / n
    avg_y = sum(c[1] for c in coords) / n
    return (round(avg_x, 7), round(avg_y, 7))
