"""Unified multi-provider coordinate store.

Central registry mapping addresses to geocode results from multiple providers
(Mapbox, Geocodio, HERE, scraper). Supports consensus detection, outlier
flagging, and best-coordinate selection.

Store format (data/coordinates.json):
{
  "meta": {"version": 1, "updated_at": "...", "providers": [...], "total_addresses": N},
  "addresses": {
    "NORMALIZED ADDRESS": {
      "mapbox":   {"lat": ..., "lng": ..., "accuracy": ..., "geocoded_at": ...},
      "geocodio": {"lat": ..., "lng": ..., "accuracy_type": ..., "accuracy": ..., "geocoded_at": ...},
      "scraper":  {"lat": ..., "lng": ..., "source": ..., "scraped_at": ...}
    }
  }
}
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COORDINATES_PATH = DATA_DIR / "coordinates.json"
GEOCODE_CACHE_PATH = DATA_DIR / "geocode_cache.json"
BRANDS_DATA_DIR = Path(__file__).resolve().parent / "data"


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two lat/lng points."""
    R = 6_371_000  # Earth radius in meters
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class CoordinateStore:
    """Multi-provider coordinate store backed by data/coordinates.json."""

    def __init__(self, path: Path = COORDINATES_PATH):
        self.path = path
        self._data: dict = {"meta": {}, "addresses": {}}
        if path.exists():
            self._data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def addresses(self) -> dict:
        return self._data["addresses"]

    @staticmethod
    def normalize_key(address: str) -> str:
        return address.strip().upper()

    def get(self, address: str) -> dict | None:
        """Get all provider entries for an address."""
        return self.addresses.get(self.normalize_key(address))

    def set_provider(self, address: str, provider: str, entry: dict) -> None:
        """Set a single provider's result for an address."""
        key = self.normalize_key(address)
        self.addresses.setdefault(key, {})[provider] = entry

    def best_coords(self, address: str) -> tuple[float, float] | None:
        """Return (lat, lng) using best available data.

        Priority: geocodio > mapbox > here > scraper.
        If multiple non-scraper providers exist, use median.
        """
        entry = self.get(address)
        if not entry:
            return None

        # Collect all valid coordinates
        provider_order = ["geocodio", "mapbox", "here", "scraper"]
        coords = []
        for p in provider_order:
            if p in entry and entry[p].get("lat") is not None:
                coords.append((entry[p]["lat"], entry[p]["lng"], p))

        if not coords:
            return None

        # If only one provider, use it
        if len(coords) == 1:
            return (coords[0][0], coords[0][1])

        # Multiple providers: use median of non-scraper coords
        non_scraper = [(lat, lng) for lat, lng, p in coords if p != "scraper"]
        if not non_scraper:
            return (coords[0][0], coords[0][1])

        lats = sorted(c[0] for c in non_scraper)
        lngs = sorted(c[1] for c in non_scraper)
        mid = len(lats) // 2
        return (lats[mid], lngs[mid])

    def save(self) -> None:
        """Write store to disk atomically."""
        self._data["meta"] = {
            "version": 1,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "providers": self._list_providers(),
            "total_addresses": len(self.addresses),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._data, indent=2, ensure_ascii=False)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".coords_"
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

    def _list_providers(self) -> list[str]:
        """List all providers present in the store."""
        providers: set[str] = set()
        for entry in self.addresses.values():
            providers.update(entry.keys())
        return sorted(providers)

    # --- Seed functions ---

    def seed_from_geocode_cache(self) -> int:
        """Import existing Mapbox results from data/geocode_cache.json.

        Returns count of entries imported.
        """
        if not GEOCODE_CACHE_PATH.exists():
            print("No geocode_cache.json found.")
            return 0

        cache = json.loads(GEOCODE_CACHE_PATH.read_text(encoding="utf-8"))
        imported = 0
        for addr_key, result in cache.items():
            if result.get("failed"):
                continue
            lat = result.get("lat")
            lng = result.get("lng")
            if lat is None or lng is None:
                continue

            entry = {
                "lat": lat,
                "lng": lng,
                "accuracy": result.get("accuracy", ""),
                "geocoded_at": result.get("geocoded_at", ""),
            }
            # Preserve match_code if present
            mc = result.get("match_code")
            if mc:
                entry["match_code"] = mc

            self.set_provider(addr_key, "mapbox", entry)
            imported += 1

        return imported

    def seed_scraper_coords(self) -> int:
        """Import lat/lng from brand store JSON files as 'scraper' provider.

        Returns count of entries imported.
        """
        imported = 0
        for path in sorted(BRANDS_DATA_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for store in data:
                lat = store.get("lat")
                lng = store.get("lng")
                if lat is None or lng is None:
                    continue
                addr = store.get("address", "")
                city = store.get("city", "")
                province = store.get("province", "ON")
                if not addr or not city:
                    continue
                # Build address key matching the format used by brand stores
                addr_key = f"{addr}, {city}, {province}".strip().upper()
                # Only set if we don't already have scraper data for this address
                existing = self.addresses.get(self.normalize_key(addr_key))
                if existing and "scraper" in existing:
                    continue
                entry = {
                    "lat": lat,
                    "lng": lng,
                    "source": store.get("brand", ""),
                    "scraped_at": store.get("scraped_at", ""),
                }
                self.set_provider(addr_key, "scraper", entry)
                imported += 1

        return imported

    def add_geocodio_batch(
        self, addresses: list[str], results: list[Optional[dict]]
    ) -> int:
        """Merge a batch of Geocodio results into the store.

        Returns count of successful results added.
        """
        added = 0
        now = datetime.now().isoformat(timespec="seconds")
        for addr, result in zip(addresses, results):
            if result is None:
                continue
            entry = {
                "lat": result["lat"],
                "lng": result["lng"],
                "accuracy_type": result.get("accuracy_type", ""),
                "accuracy": result.get("accuracy", 0.0),
                "geocoded_at": now,
            }
            self.set_provider(addr, "geocodio", entry)
            added += 1
        return added

    # --- Reporting ---

    def stats(self) -> dict:
        """Return coverage statistics by provider."""
        provider_counts: dict[str, int] = {}
        multi_provider = 0
        for entry in self.addresses.values():
            providers = [p for p in entry if entry[p].get("lat") is not None]
            for p in providers:
                provider_counts[p] = provider_counts.get(p, 0) + 1
            if len(providers) > 1:
                multi_provider += 1
        return {
            "total_addresses": len(self.addresses),
            "by_provider": provider_counts,
            "multi_provider": multi_provider,
        }

    def divergence_report(self, threshold_m: float = 500) -> list[dict]:
        """Find addresses where providers disagree by more than threshold_m meters.

        Returns list of dicts with address, providers, distances.
        """
        divergences: list[dict] = []
        for addr_key, entry in self.addresses.items():
            # Collect valid coordinates per provider
            coords = {}
            for provider, data in entry.items():
                if data.get("lat") is not None and data.get("lng") is not None:
                    coords[provider] = (data["lat"], data["lng"])

            if len(coords) < 2:
                continue

            # Check all pairs
            providers = list(coords.keys())
            max_dist = 0.0
            worst_pair = ("", "")
            for i in range(len(providers)):
                for j in range(i + 1, len(providers)):
                    p1, p2 = providers[i], providers[j]
                    d = _haversine_m(
                        coords[p1][0], coords[p1][1],
                        coords[p2][0], coords[p2][1],
                    )
                    if d > max_dist:
                        max_dist = d
                        worst_pair = (p1, p2)

            if max_dist >= threshold_m:
                divergences.append({
                    "address": addr_key,
                    "max_distance_m": round(max_dist, 1),
                    "providers": {p: {"lat": c[0], "lng": c[1]} for p, c in coords.items()},
                    "worst_pair": worst_pair,
                })

        divergences.sort(key=lambda x: -x["max_distance_m"])
        return divergences

    def pending_geocodio(self) -> list[str]:
        """Return addresses that don't yet have a Geocodio result."""
        pending = []
        for addr_key, entry in self.addresses.items():
            if "geocodio" not in entry:
                pending.append(addr_key)
        return pending

    def all_unique_addresses(self) -> set[str]:
        """Return all address keys in the store."""
        return set(self.addresses.keys())
