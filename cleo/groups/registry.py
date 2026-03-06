"""Group Registry: persistent store of every company/individual in transactions.

Every unique normalized buyer/seller name gets a GRP_ ID. Manual linking
merges multiple names into one Group. The registry is append-only — IDs
are never reassigned.

Structure:
  group_registry.json = {
    meta: {created, last_updated, next_id, total_groups},
    groups: {GRP_NNNNN: {id, display_name, known_names, created_at, updated_at}},
    name_index: {NORMALIZED_NAME: GRP_NNNNN}
  }
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

_SUFFIX_RE = re.compile(
    r"\s*\b(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|LLC|LLP|LP|ULC)\b\.?\s*$",
    re.IGNORECASE,
)


def normalize_group_name(name: str) -> str:
    """Normalize a buyer/seller name for grouping.

    Uppercase, collapse whitespace, strip trailing punctuation,
    strip legal suffixes (Inc/Ltd/Corp).
    """
    s = name.upper().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:")
    for _ in range(2):
        prev = s
        s = _SUFFIX_RE.sub("", s).rstrip(".,;: ")
        if s == prev:
            break
    return s


# ---------------------------------------------------------------------------
# Registry I/O
# ---------------------------------------------------------------------------

def load_registry(path: Path) -> Dict:
    """Load the group registry from disk. Returns empty structure if not found."""
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info(
            "Loaded group registry: %d groups, %d names indexed",
            len(data.get("groups", {})),
            len(data.get("name_index", {})),
        )
        return data

    return {
        "meta": {
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "next_id": 1,
            "total_groups": 0,
        },
        "groups": {},
        "name_index": {},
    }


def save_registry(data: Dict, path: Path) -> None:
    """Write the group registry to disk."""
    data["meta"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    data["meta"]["total_groups"] = len(data["groups"])
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved group registry: %d groups", len(data["groups"]))


# ---------------------------------------------------------------------------
# ID assignment
# ---------------------------------------------------------------------------

def assign_group(registry: Dict, normalized_name: str) -> str:
    """Get or assign a GRP_ ID for a normalized name. Mutates registry in place.

    Returns the GRP_ ID.
    """
    name_index = registry["name_index"]

    # Already known?
    if normalized_name in name_index:
        return name_index[normalized_name]

    # Assign new
    next_id = registry["meta"]["next_id"]
    gid = f"GRP_{next_id:05d}"
    registry["meta"]["next_id"] = next_id + 1

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    registry["groups"][gid] = {
        "id": gid,
        "display_name": None,
        "known_names": [normalized_name],
        "created_at": now,
        "updated_at": now,
    }
    name_index[normalized_name] = gid
    return gid


# ---------------------------------------------------------------------------
# Build from properties
# ---------------------------------------------------------------------------

def build_from_properties(properties_path: Path, registry_path: Path) -> Tuple[Dict, Dict]:
    """Scan all transactions in properties.json and ensure every buyer/seller
    name has a GRP_ ID.

    Returns (registry, stats).
    """
    start = time.time()

    registry = load_registry(registry_path)
    props_data = json.loads(properties_path.read_text(encoding="utf-8"))
    properties = props_data.get("properties", {})

    existing_before = len(registry["groups"])
    new_count = 0
    existing_count = 0
    total_names = 0

    for prop in properties.values():
        for txn in prop.get("transactions", []):
            for field in ("buyer_name", "seller_name"):
                raw = txn.get(field, "").strip()
                if not raw:
                    continue
                norm = normalize_group_name(raw)
                if not norm:
                    continue
                total_names += 1

                was_known = norm in registry["name_index"]
                assign_group(registry, norm)
                if was_known:
                    existing_count += 1
                else:
                    new_count += 1

    save_registry(registry, registry_path)
    elapsed = time.time() - start

    stats = {
        "total_names_scanned": total_names,
        "existing_names": existing_count,
        "new_names": new_count,
        "groups_before": existing_before,
        "groups_after": len(registry["groups"]),
        "new_groups": len(registry["groups"]) - existing_before,
        "elapsed_seconds": round(elapsed, 1),
    }
    logger.info(
        "Group registry: %d groups (%d new) from %d names in %.1fs",
        stats["groups_after"], stats["new_groups"], total_names, elapsed,
    )
    return registry, stats
