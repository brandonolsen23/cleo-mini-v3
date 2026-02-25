"""Track which RT IDs have already been ingested."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from cleo.config import TRACKER_PATH

logger = logging.getLogger(__name__)


class IngestTracker:
    """Manages seen_rt_ids.json — the master list of known RT IDs.

    File format (v2 — with property type):
    {
        "RT197012": {"ts": "2026-02-08T09:00:00", "type": "retail"},
        "RT43746": {"ts": "2026-02-08T09:00:00", "type": "industrial"},
        ...
    }

    Legacy format (v1 — auto-migrated on load):
    {
        "RT197012": "2026-02-08T09:00:00",
        ...
    }
    """

    def __init__(self, path: Path = TRACKER_PATH):
        self.path = path
        self.seen: Dict[str, dict] = self._load()

    def _load(self) -> Dict[str, dict]:
        """Load seen RT IDs from disk, auto-migrating v1 format."""
        if not self.path.exists():
            logger.info("No tracker file found. Starting fresh.")
            return {}

        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Auto-migrate v1 (string timestamp) -> v2 (dict with ts + type)
        migrated = 0
        result: Dict[str, dict] = {}
        for rt_id, value in data.items():
            if isinstance(value, str):
                result[rt_id] = {"ts": value, "type": "retail"}
                migrated += 1
            elif isinstance(value, dict):
                result[rt_id] = value
            else:
                result[rt_id] = {"ts": str(value), "type": "retail"}
                migrated += 1

        if migrated > 0:
            logger.info("Auto-migrated %d tracker entries to v2 format.", migrated)

        logger.info("Loaded %d known RT IDs from tracker.", len(result))
        return result

    def _save(self) -> None:
        """Save seen RT IDs to disk."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.seen, f, indent=2)

    def find_new(self, rt_ids: List[str]) -> List[str]:
        """Return RT IDs that are NOT in the master list."""
        new = [rt_id for rt_id in rt_ids if rt_id not in self.seen]
        logger.info(
            "Checked %d RT IDs: %d new, %d already known.",
            len(rt_ids),
            len(new),
            len(rt_ids) - len(new),
        )
        return new

    def mark_seen(self, rt_ids: List[str], prop_type: str = "retail") -> None:
        """Add RT IDs to the master list with current timestamp and save."""
        now = datetime.now().isoformat(timespec="seconds")
        for rt_id in rt_ids:
            self.seen[rt_id] = {"ts": now, "type": prop_type}
        self._save()
        logger.info("Marked %d RT IDs as seen (type=%s).", len(rt_ids), prop_type)

    def get_type(self, rt_id: str) -> Optional[str]:
        """Return the property type for an RT ID, or None if unknown."""
        entry = self.seen.get(rt_id)
        if entry is None:
            return None
        if isinstance(entry, dict):
            return entry.get("type")
        return "retail"  # legacy string value

    @property
    def count(self) -> int:
        """Total number of known RT IDs."""
        return len(self.seen)

    def count_by_type(self, prop_type: str) -> int:
        """Count RT IDs for a specific property type."""
        return sum(
            1 for entry in self.seen.values()
            if isinstance(entry, dict) and entry.get("type") == prop_type
        )
