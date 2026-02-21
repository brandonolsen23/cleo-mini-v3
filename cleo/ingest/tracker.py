"""Track which RT IDs have already been ingested."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from cleo.config import TRACKER_PATH

logger = logging.getLogger(__name__)


class IngestTracker:
    """Manages seen_rt_ids.json — the master list of known RT IDs.

    File format:
    {
        "RT197012": "2026-02-08T09:00:00",
        "RT43746": "2026-02-08T09:00:00",
        ...
    }
    """

    def __init__(self, path: Path = TRACKER_PATH):
        self.path = path
        self.seen: Dict[str, str] = self._load()

    def _load(self) -> Dict[str, str]:
        """Load seen RT IDs from disk."""
        if not self.path.exists():
            logger.info("No tracker file found. Starting fresh.")
            return {}

        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info("Loaded %d known RT IDs from tracker.", len(data))
        return data

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

    def mark_seen(self, rt_ids: List[str]) -> None:
        """Add RT IDs to the master list with current timestamp and save."""
        now = datetime.now().isoformat(timespec="seconds")
        for rt_id in rt_ids:
            self.seen[rt_id] = now
        self._save()
        logger.info("Marked %d RT IDs as seen.", len(rt_ids))

    @property
    def count(self) -> int:
        """Total number of known RT IDs."""
        return len(self.seen)
