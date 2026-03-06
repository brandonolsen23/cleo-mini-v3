"""Property ID Map: persistent, append-only mapping from ARN to PRO_NNNNN.

Ensures the same physical property always gets the same PRO_ ID, regardless
of how many times the Data Engine rebuilds.

Rules:
  1. Append-only — once an ARN gets a PRO_ ID, that mapping never changes.
  2. Never reassign — if an ARN disappears, its PRO_ ID is retired.
  3. Monotonic counter — next_id always increments, no gaps filled.
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def load_id_map(path: Path) -> Dict:
    """Load the property ID map from disk. Returns empty structure if not found."""
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info(
            "Loaded property ID map: %d mappings, next_id=%d",
            len(data.get("map", {})),
            data.get("meta", {}).get("next_id", 1),
        )
        return data

    return {
        "meta": {
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "next_id": 1,
        },
        "map": {},
    }


def save_id_map(data: Dict, path: Path) -> None:
    """Write the property ID map to disk."""
    data["meta"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(
        "Saved property ID map: %d mappings", len(data.get("map", {}))
    )


def assign_id(id_map: Dict, arn: str) -> str:
    """Get or assign a PRO_ ID for an ARN. Mutates id_map in place."""
    mapping = id_map["map"]
    if arn in mapping:
        return mapping[arn]

    next_id = id_map["meta"]["next_id"]
    pid = f"PRO_{next_id:05d}"
    mapping[arn] = pid
    id_map["meta"]["next_id"] = next_id + 1
    return pid


def seed_from_properties(properties_path: Path, id_map_path: Path) -> Dict:
    """Seed the ID map from an existing properties.json (one-time migration).

    Maps each ARN to a PRO_ ID preserving the numeric sequence from
    old P-prefixed IDs (P00001 -> PRO_00001).

    Returns the seeded ID map.
    """
    data = json.loads(properties_path.read_text(encoding="utf-8"))
    properties = data.get("properties", {})

    id_map = {
        "meta": {
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "next_id": 1,
        },
        "map": {},
    }

    max_num = 0
    for old_pid, prop in properties.items():
        arn = prop.get("arn", "")
        if not arn:
            continue

        # Extract the numeric part from old P-prefixed ID (P00001 -> 1)
        num_str = old_pid.lstrip("P")
        try:
            num = int(num_str)
        except ValueError:
            continue

        new_pid = f"PRO_{num:05d}"
        id_map["map"][arn] = new_pid
        if num > max_num:
            max_num = num

    id_map["meta"]["next_id"] = max_num + 1

    save_id_map(id_map, id_map_path)
    logger.info(
        "Seeded ID map from %d existing properties (next_id=%d)",
        len(id_map["map"]),
        id_map["meta"]["next_id"],
    )
    return id_map
