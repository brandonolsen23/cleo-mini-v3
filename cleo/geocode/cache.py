"""Geocode cache: address string -> geocode result, stored as JSON on disk."""

import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class GeocodeCache:
    """JSON file-based cache mapping normalized address keys to geocode results.

    Cache structure:
    {
        "123 MAIN ST, TORONTO, ONTARIO": {
            "lat": 43.6532,
            "lng": -79.3832,
            "formatted_address": "123 Main Street, Toronto, Ontario, Canada",
            "accuracy": "rooftop",
            "mapbox_id": "dXJuOm1ieC...",
            "match_code": {...},
            "geocoded_at": "2026-02-15T10:30:00",
            "failed": false
        }
    }
    """

    def __init__(self, path: Path):
        self.path = path
        self._data: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
                logger.info("Loaded geocode cache: %d entries", len(self._data))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load cache, starting fresh: %s", e)
                self._data = {}
        else:
            self._data = {}

    @staticmethod
    def _normalize_key(address: str) -> str:
        return address.strip().upper()

    def get(self, address: str) -> Optional[Dict]:
        """Look up a cached result. Returns None if not cached."""
        key = self._normalize_key(address)
        return self._data.get(key)

    def put(self, address: str, result: Dict) -> None:
        """Store a geocode result (success or failure)."""
        key = self._normalize_key(address)
        result["geocoded_at"] = datetime.now().isoformat(timespec="seconds")
        self._data[key] = result

    def put_success(self, address: str, geocode_result: Dict) -> None:
        """Store a successful geocode result."""
        entry = {
            "lat": geocode_result["lat"],
            "lng": geocode_result["lng"],
            "formatted_address": geocode_result.get("formatted_address", ""),
            "accuracy": geocode_result.get("accuracy", ""),
            "mapbox_id": geocode_result.get("mapbox_id", ""),
            "match_code": geocode_result.get("match_code", {}),
            "failed": False,
        }
        self.put(address, entry)

    def put_failure(self, address: str, reason: str = "no_results") -> None:
        """Store a failed geocode attempt."""
        self.put(address, {"failed": True, "fail_reason": reason})

    def put_batch(self, items: List[Tuple[str, Optional[Dict]]]) -> None:
        """Store multiple results. Each item is (address, geocode_result_or_None)."""
        for address, result in items:
            if result is not None:
                self.put_success(address, result)
            else:
                self.put_failure(address)

    def save(self) -> None:
        """Write cache to disk atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._data, indent=2, ensure_ascii=False)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".geocache_"
        )
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            os.replace(tmp_path, self.path)
        except Exception:
            os.close(fd) if not os.get_inheritable(fd) else None
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise
        logger.info("Saved geocode cache: %d entries", len(self._data))

    def stats(self) -> Dict:
        """Return cache statistics."""
        total = len(self._data)
        failures = sum(1 for v in self._data.values() if v.get("failed"))
        successes = total - failures
        return {
            "total": total,
            "successes": successes,
            "failures": failures,
        }

    def uncached_from(self, addresses: Set[str]) -> Set[str]:
        """Return addresses from the input set that are not yet in cache."""
        return {a for a in addresses if self._normalize_key(a) not in self._data}

    def failures(self) -> Set[str]:
        """Return address keys that previously failed."""
        return {k for k, v in self._data.items() if v.get("failed")}

    def clear_failures(self) -> int:
        """Remove all failed entries from cache. Returns count removed."""
        to_remove = [k for k, v in self._data.items() if v.get("failed")]
        for k in to_remove:
            del self._data[k]
        if to_remove:
            logger.info("Cleared %d failed cache entries", len(to_remove))
        return len(to_remove)
