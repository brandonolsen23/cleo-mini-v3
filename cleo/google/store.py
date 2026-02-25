"""PlacesStore — read/write google_places.json + streetview_meta.json.

Follows the same atomic-save pattern as CoordinateStore.

google_places.json structure:
{
  "meta": {"updated_at": "...", "properties_enriched": N},
  "properties": {
    "P00001": {
      "place_id": "ChIJ...",
      "text_search_query": "1063 Talbot St, St Thomas, ON",
      "text_search_at": "2026-03-01T10:00:00",
      "essentials": { ... },
      "pro": { ... },
      "enterprise": { ... }
    }
  }
}

streetview_meta.json structure:
{
  "meta": {"updated_at": "..."},
  "properties": {
    "P00001": {
      "has_coverage": true,
      "pano_id": "...",
      "date": "2023-06",
      "checked_at": "2026-03-01T10:00:00",
      "image_fetched": true,
      "image_fetched_at": "2026-03-01T10:05:00"
    }
  }
}
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from cleo.config import GOOGLE_PLACES_PATH, STREETVIEW_META_PATH


class PlacesStore:
    """JSON-backed store for Google Places enrichment data."""

    def __init__(self, path: Path = GOOGLE_PLACES_PATH):
        self.path = path
        self._data: dict = {"meta": {}, "properties": {}}
        if path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def properties(self) -> dict:
        return self._data.setdefault("properties", {})

    def get(self, prop_id: str) -> dict | None:
        return self.properties.get(prop_id)

    def set_place_id(self, prop_id: str, place_id: str, query: str) -> None:
        entry = self.properties.setdefault(prop_id, {})
        entry["place_id"] = place_id
        entry["text_search_query"] = query
        entry["text_search_at"] = datetime.now().isoformat(timespec="seconds")

    def set_details(self, prop_id: str, tier: str, data: dict) -> None:
        entry = self.properties.setdefault(prop_id, {})
        entry[tier] = {**data, "fetched_at": datetime.now().isoformat(timespec="seconds")}

    def has_place_id(self, prop_id: str) -> bool:
        entry = self.properties.get(prop_id)
        return entry is not None and "place_id" in entry

    def has_tier(self, prop_id: str, tier: str) -> bool:
        entry = self.properties.get(prop_id)
        return entry is not None and tier in entry

    def place_id_for(self, prop_id: str) -> str | None:
        entry = self.properties.get(prop_id)
        return entry.get("place_id") if entry else None

    def pending_text_search(self, prop_ids: list[str]) -> list[str]:
        """Return prop_ids that don't yet have a place_id."""
        return [pid for pid in prop_ids if not self.has_place_id(pid)]

    def pending_details(self, prop_ids: list[str], tier: str) -> list[str]:
        """Return prop_ids that have a place_id but missing this tier."""
        return [
            pid for pid in prop_ids
            if self.has_place_id(pid) and not self.has_tier(pid, tier)
        ]

    def enrichment_stats(self) -> dict:
        """Return counts of properties at each enrichment stage."""
        total = len(self.properties)
        with_place_id = sum(1 for p in self.properties.values() if "place_id" in p)
        with_essentials = sum(1 for p in self.properties.values() if "essentials" in p)
        with_pro = sum(1 for p in self.properties.values() if "pro" in p)
        with_enterprise = sum(1 for p in self.properties.values() if "enterprise" in p)
        return {
            "total_properties": total,
            "with_place_id": with_place_id,
            "with_essentials": with_essentials,
            "with_pro": with_pro,
            "with_enterprise": with_enterprise,
        }

    def save(self) -> None:
        self._data["meta"] = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "properties_enriched": len(self.properties),
        }
        _atomic_save(self.path, self._data)


class StreetViewMetaStore:
    """JSON-backed store for Street View metadata."""

    def __init__(self, path: Path = STREETVIEW_META_PATH):
        self.path = path
        self._data: dict = {"meta": {}, "properties": {}}
        if path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def properties(self) -> dict:
        return self._data.setdefault("properties", {})

    def get(self, prop_id: str) -> dict | None:
        return self.properties.get(prop_id)

    def set_metadata(self, prop_id: str, meta: dict) -> None:
        entry = self.properties.setdefault(prop_id, {})
        entry["has_coverage"] = meta.get("has_coverage", False)
        entry["pano_id"] = meta.get("pano_id")
        entry["date"] = meta.get("date")
        entry["status"] = meta.get("status")
        entry["checked_at"] = datetime.now().isoformat(timespec="seconds")

    def set_image_fetched(self, prop_id: str) -> None:
        entry = self.properties.get(prop_id, {})
        entry["image_fetched"] = True
        entry["image_fetched_at"] = datetime.now().isoformat(timespec="seconds")
        self.properties[prop_id] = entry

    def has_metadata(self, prop_id: str) -> bool:
        return prop_id in self.properties

    def has_coverage(self, prop_id: str) -> bool:
        entry = self.properties.get(prop_id)
        return entry is not None and entry.get("has_coverage", False)

    def has_image(self, prop_id: str) -> bool:
        entry = self.properties.get(prop_id)
        return entry is not None and entry.get("image_fetched", False)

    def pending_metadata(self, prop_ids: list[str]) -> list[str]:
        """Return prop_ids that haven't had metadata checked."""
        return [pid for pid in prop_ids if not self.has_metadata(pid)]

    def pending_images(self, prop_ids: list[str]) -> list[str]:
        """Return prop_ids with coverage but no fetched image."""
        return [
            pid for pid in prop_ids
            if self.has_coverage(pid) and not self.has_image(pid)
        ]

    def stats(self) -> dict:
        total = len(self.properties)
        with_coverage = sum(1 for p in self.properties.values() if p.get("has_coverage"))
        no_coverage = sum(1 for p in self.properties.values() if not p.get("has_coverage"))
        images_fetched = sum(1 for p in self.properties.values() if p.get("image_fetched"))
        return {
            "total_checked": total,
            "with_coverage": with_coverage,
            "no_coverage": no_coverage,
            "images_fetched": images_fetched,
        }

    def save(self) -> None:
        self._data["meta"] = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "total_checked": len(self.properties),
        }
        _atomic_save(self.path, self._data)


def _atomic_save(path: Path, data: dict) -> None:
    """Write JSON to disk atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, ensure_ascii=False)
    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, suffix=".tmp", prefix=f".{path.stem}_"
    )
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
