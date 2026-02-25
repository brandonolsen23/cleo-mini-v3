"""Municipality -> ArcGIS endpoint resolver.

Loads service definitions from data/parcels/services.json and resolves
which municipality service to use for a given city name.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from cleo.config import PARCELS_SERVICES_PATH

logger = logging.getLogger(__name__)


class ServiceConfig:
    """Parsed config for a single municipality's ArcGIS service."""

    def __init__(self, key: str, data: dict):
        self.key = key
        self.name: str = data.get("name", key)
        self.parcels_url: str = data["parcels_url"]
        self.zoning_url: Optional[str] = data.get("zoning_url")
        self.srid: int = data.get("srid", 26917)
        self.field_map: dict = data.get("field_map", {})
        self.cities: list[str] = data.get("cities", [])
        self.notes: str = data.get("notes", "")

    def __repr__(self) -> str:
        return f"ServiceConfig({self.key!r}, cities={self.cities})"


class ServiceRegistry:
    """Resolve municipality ArcGIS services from services.json."""

    def __init__(self, path: Path | None = None):
        self._path = path or PARCELS_SERVICES_PATH
        self._services: dict[str, ServiceConfig] = {}
        self._city_lookup: dict[str, str] = {}  # normalized city -> service key
        self._loaded = False

    def load(self) -> None:
        if not self._path.exists():
            logger.warning("Services file not found: %s", self._path)
            self._loaded = True
            return

        data = json.loads(self._path.read_text(encoding="utf-8"))
        services = data.get("services", {})

        for key, svc_data in services.items():
            svc = ServiceConfig(key, svc_data)
            self._services[key] = svc
            for city in svc.cities:
                self._city_lookup[city.lower().strip()] = key

        self._loaded = True
        logger.info(
            "Loaded %d municipality services covering %d cities",
            len(self._services),
            len(self._city_lookup),
        )

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def resolve(self, city: str) -> Optional[ServiceConfig]:
        """Find the ArcGIS service config for a city name.

        Tries exact normalized match first, then substring matching
        for cases like "City of Owen Sound" matching "Owen Sound".
        """
        self._ensure_loaded()
        norm = city.lower().strip()

        # Exact match
        if norm in self._city_lookup:
            return self._services[self._city_lookup[norm]]

        # Substring match: "City of Owen Sound" contains "owen sound"
        for city_key, svc_key in self._city_lookup.items():
            if city_key in norm or norm in city_key:
                return self._services[svc_key]

        return None

    def get(self, municipality_key: str) -> Optional[ServiceConfig]:
        """Get service config by municipality key (e.g. 'london', 'grey')."""
        self._ensure_loaded()
        return self._services.get(municipality_key)

    def list_municipalities(self) -> list[str]:
        """Return all registered municipality keys."""
        self._ensure_loaded()
        return list(self._services.keys())

    def all_services(self) -> dict[str, ServiceConfig]:
        """Return all service configs."""
        self._ensure_loaded()
        return dict(self._services)

    def covered_cities(self) -> dict[str, str]:
        """Return mapping of city -> municipality key."""
        self._ensure_loaded()
        return dict(self._city_lookup)
