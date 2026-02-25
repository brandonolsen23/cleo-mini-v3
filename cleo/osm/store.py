"""TenantStore — JSON-backed cache for OSM tenant discovery results.

data/osm_tenants.json structure:
{
  "meta": {"updated_at": "...", "properties_checked": N, "total_tenants": N},
  "properties": {
    "P00001": {
      "checked_at": "2026-03-01T10:00:00",
      "radius": 150,
      "tenants": [
        {
          "osm_id": "node/12345",
          "name": "Giant Tiger",
          "brand": "Giant Tiger",
          "category": "shop=department_store",
          "lat": 42.779,
          "lng": -81.167,
          ...
        }
      ]
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

from cleo.config import DATA_DIR

OSM_TENANTS_PATH = DATA_DIR / "osm_tenants.json"


class TenantStore:
    """JSON-backed store for OSM tenant discovery results."""

    def __init__(self, path: Path = OSM_TENANTS_PATH):
        self.path = path
        self._data: dict = {"meta": {}, "properties": {}}
        if path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def properties(self) -> dict:
        return self._data.setdefault("properties", {})

    def get(self, prop_id: str) -> dict | None:
        return self.properties.get(prop_id)

    def get_tenants(self, prop_id: str) -> list[dict]:
        entry = self.properties.get(prop_id)
        if not entry:
            return []
        return entry.get("tenants", [])

    def set_tenants(self, prop_id: str, tenants: list[dict], radius: int) -> None:
        self.properties[prop_id] = {
            "checked_at": datetime.now().isoformat(timespec="seconds"),
            "radius": radius,
            "tenant_count": len(tenants),
            "tenants": tenants,
        }

    def has_data(self, prop_id: str) -> bool:
        return prop_id in self.properties

    def pending(self, prop_ids: list[str]) -> list[str]:
        """Return prop_ids that haven't been checked yet."""
        return [pid for pid in prop_ids if not self.has_data(pid)]

    def stats(self) -> dict:
        total_checked = len(self.properties)
        with_tenants = sum(
            1 for p in self.properties.values()
            if p.get("tenant_count", 0) > 0
        )
        total_tenants = sum(
            p.get("tenant_count", 0) for p in self.properties.values()
        )
        empty = total_checked - with_tenants
        return {
            "properties_checked": total_checked,
            "with_tenants": with_tenants,
            "empty": empty,
            "total_tenants": total_tenants,
        }

    def save(self) -> None:
        stats = self.stats()
        self._data["meta"] = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            **stats,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._data, indent=2, ensure_ascii=False)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".osm_tenants_"
        )
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
