"""Parcel geometry cache — permanent on-disk store of discovered parcel boundaries.

Keyed by 20-digit ARN. Seeded from branded_parcels/*.json, grows as
RT/GW records are resolved via the provincial MapServer API.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cleo.config import PARCEL_CACHE_PATH

logger = logging.getLogger(__name__)


class ParcelCache:
    """On-disk cache of parcel geometries and attributes, keyed by 20-digit ARN."""

    def __init__(self, path: Path | None = None):
        self._path = path or PARCEL_CACHE_PATH
        self._data: Optional[dict] = None

    def _load(self) -> dict:
        if self._data is not None:
            return self._data
        if self._path.exists():
            self._data = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._data = {
                "meta": {
                    "total": 0,
                    "seeded_from_branded": 0,
                    "resolved_from_api": 0,
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                },
                "parcels": {},
            }
        return self._data

    @property
    def parcels(self) -> dict[str, dict]:
        return self._load()["parcels"]

    @property
    def total(self) -> int:
        return len(self.parcels)

    def get(self, arn_20: str) -> Optional[dict]:
        """Look up a cached parcel by 20-digit ARN. Returns parcel dict or None."""
        return self.parcels.get(arn_20)

    def has(self, arn_20: str) -> bool:
        """Check if a parcel is in the cache."""
        return arn_20 in self.parcels

    def put(
        self,
        arn_20: str,
        pin: str | None,
        geometry: dict | None,
        centroid: list[float] | None,
        attributes: dict | None,
        source: str = "api",
    ) -> None:
        """Add or update a parcel in the cache."""
        data = self._load()
        data["parcels"][arn_20] = {
            "arn": arn_20,
            "pin": pin,
            "geometry": geometry,
            "centroid": centroid,
            "attributes": attributes or {},
            "source": source,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        data["meta"]["total"] = len(data["parcels"])

    def put_batch(self, entries: list[dict], source: str = "branded_harvest") -> int:
        """Add multiple parcels. Each entry must have at least 'arn'.
        Returns count of newly added entries (not updates)."""
        data = self._load()
        added = 0
        for entry in entries:
            arn = entry.get("arn", "")
            if not arn:
                continue
            is_new = arn not in data["parcels"]
            data["parcels"][arn] = {
                "arn": arn,
                "pin": entry.get("pin"),
                "geometry": entry.get("geometry"),
                "centroid": entry.get("centroid"),
                "attributes": entry.get("attributes", {}),
                "source": source,
                "cached_at": datetime.now(timezone.utc).isoformat(),
            }
            if is_new:
                added += 1
        data["meta"]["total"] = len(data["parcels"])
        return added

    def seed_from_branded_parcels(self, branded_dir: Path) -> int:
        """Seed cache from all branded_parcels/*.json files. Returns count added."""
        if not branded_dir.exists():
            return 0
        entries = []
        for f in sorted(branded_dir.iterdir()):
            if not f.name.endswith(".json"):
                continue
            try:
                file_data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            for arn, parcel in file_data.get("parcels", {}).items():
                geom = parcel.get("geometry")
                centroid = polygon_centroid(geom) if geom else None
                entries.append({
                    "arn": arn,
                    "pin": parcel.get("pin"),
                    "geometry": geom,
                    "centroid": centroid,
                    "attributes": parcel.get("attributes", {}),
                })
        added = self.put_batch(entries, source="branded_harvest")
        self._load()["meta"]["seeded_from_branded"] = added
        logger.info("Seeded parcel cache with %d parcels from branded harvests", added)
        return added

    def save(self) -> None:
        """Write cache to disk atomically."""
        data = self._load()
        data["meta"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        tmp.rename(self._path)
        logger.info("Saved parcel cache: %d entries to %s", data["meta"]["total"], self._path)

    def stats(self) -> dict:
        """Return summary statistics."""
        data = self._load()
        with_geometry = sum(1 for p in data["parcels"].values() if p.get("geometry"))
        with_pin = sum(1 for p in data["parcels"].values() if p.get("pin"))
        by_source: dict[str, int] = {}
        for p in data["parcels"].values():
            src = p.get("source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1
        return {
            "total": data["meta"]["total"],
            "with_geometry": with_geometry,
            "with_pin": with_pin,
            "by_source": by_source,
            "last_updated": data["meta"].get("last_updated", ""),
        }


def polygon_centroid(geom: dict) -> list[float] | None:
    """Compute [lat, lng] centroid from GeoJSON polygon."""
    if not geom:
        return None
    gtype = geom.get("type", "")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon" and coords:
        ring = coords[0]
    elif gtype == "MultiPolygon" and coords:
        ring = coords[0][0]
    else:
        return None
    if not ring:
        return None
    n = len(ring)
    avg_lng = sum(c[0] for c in ring) / n
    avg_lat = sum(c[1] for c in ring) / n
    return [round(avg_lat, 7), round(avg_lng, 7)]
