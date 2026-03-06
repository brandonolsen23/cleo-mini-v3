"""Manual group operations — create, merge/split, property linking.

Every action is logged to group_link_log.jsonl for audit trail.
The lower-numbered GRP_ ID wins on merge.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from cleo.groups.registry import load_registry, save_registry, normalize_group_name, assign_group

logger = logging.getLogger(__name__)


def _append_log(log_path: Path, entry: Dict):
    """Append an audit log entry."""
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def link_names(
    registry_path: Path,
    log_path: Path,
    names: List[str],
    display_name: Optional[str] = None,
    reason: str = "",
) -> Dict:
    """Link multiple normalized names into one Group.

    If names already belong to different Groups, merges them (lower GRP_ wins).
    Returns the resulting Group record.
    """
    registry = load_registry(registry_path)
    name_index = registry["name_index"]
    groups = registry["groups"]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    # Normalize and deduplicate
    normalized = sorted(set(n for n in (normalize_group_name(n) for n in names) if n))
    if len(normalized) < 2:
        raise ValueError("At least 2 distinct normalized names required")

    # Find existing groups these names belong to
    existing_gids = set()
    for n in normalized:
        gid = name_index.get(n)
        if gid:
            existing_gids.add(gid)

    if len(existing_gids) == 0:
        # All names are new — shouldn't happen if registry was built, but handle it
        from cleo.groups.registry import assign_group
        gid = assign_group(registry, normalized[0])
        target = groups[gid]
        for n in normalized[1:]:
            if n not in name_index:
                name_index[n] = gid
                target["known_names"].append(n)
        target["known_names"] = sorted(set(target["known_names"]))
        if display_name:
            target["display_name"] = display_name
        target["updated_at"] = now

    elif len(existing_gids) == 1:
        # Extend existing group
        gid = existing_gids.pop()
        target = groups[gid]
        for n in normalized:
            if n not in name_index:
                name_index[n] = gid
                target["known_names"].append(n)
        target["known_names"] = sorted(set(target["known_names"]))
        if display_name:
            target["display_name"] = display_name
        target["updated_at"] = now

    else:
        # Merge multiple groups — lowest GRP_ ID wins
        sorted_gids = sorted(existing_gids)
        gid = sorted_gids[0]
        target = groups[gid]

        for donor_gid in sorted_gids[1:]:
            donor = groups.get(donor_gid)
            if not donor:
                continue
            # Move all names from donor to target
            for dn in donor["known_names"]:
                name_index[dn] = gid
                if dn not in target["known_names"]:
                    target["known_names"].append(dn)
            # Remove donor group (retired — ID never reused)
            del groups[donor_gid]

        # Add any new names
        for n in normalized:
            if n not in name_index:
                name_index[n] = gid
                target["known_names"].append(n)
        target["known_names"] = sorted(set(target["known_names"]))
        if display_name:
            target["display_name"] = display_name
        target["updated_at"] = now

    save_registry(registry, registry_path)
    _append_log(log_path, {
        "action": "link",
        "group_id": gid,
        "names": normalized,
        "display_name": display_name,
        "reason": reason,
    })

    return groups[gid]


def unlink_name(
    registry_path: Path,
    log_path: Path,
    name: str,
    group_id: str,
    reason: str = "",
) -> Optional[Dict]:
    """Remove a name from a Group.

    The name gets its own new GRP_ ID. If the source group has only 1 member
    left, it stays as-is (single-name groups are valid).

    Returns the updated source group.
    """
    registry = load_registry(registry_path)
    groups = registry["groups"]
    name_index = registry["name_index"]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    norm = normalize_group_name(name)

    if group_id not in groups:
        raise ValueError(f"Group {group_id} not found")

    group = groups[group_id]
    if norm not in group["known_names"]:
        raise ValueError(f"Name '{norm}' not in group {group_id}")

    if len(group["known_names"]) <= 1:
        raise ValueError(f"Cannot unlink the last name from group {group_id}")

    # Remove from source group
    group["known_names"].remove(norm)
    group["updated_at"] = now

    # Create new group for the unlinked name
    from cleo.groups.registry import assign_group
    new_gid = assign_group(registry, norm)
    # assign_group already created the group and updated name_index

    save_registry(registry, registry_path)
    _append_log(log_path, {
        "action": "unlink",
        "source_group_id": group_id,
        "new_group_id": new_gid,
        "name": norm,
        "reason": reason,
    })

    return group


def set_display_name(
    registry_path: Path,
    log_path: Path,
    group_id: str,
    display_name: str,
) -> Dict:
    """Set the display name for a Group."""
    registry = load_registry(registry_path)
    groups = registry["groups"]

    if group_id not in groups:
        raise ValueError(f"Group {group_id} not found")

    groups[group_id]["display_name"] = display_name
    groups[group_id]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    save_registry(registry, registry_path)
    _append_log(log_path, {
        "action": "rename",
        "group_id": group_id,
        "display_name": display_name,
    })

    return groups[group_id]


# ---------------------------------------------------------------------------
# Group creation (no transaction required)
# ---------------------------------------------------------------------------

def create_group(
    registry_path: Path,
    log_path: Path,
    name: str,
    display_name: Optional[str] = None,
) -> Dict:
    """Create a new Group from a name. No transaction required.

    If the normalized name already exists, returns the existing group.
    Sets display_name if provided.
    """
    registry = load_registry(registry_path)
    norm = normalize_group_name(name)
    if not norm:
        raise ValueError("Name cannot be empty")

    was_known = norm in registry["name_index"]
    gid = assign_group(registry, norm)

    if display_name:
        registry["groups"][gid]["display_name"] = display_name
    elif not was_known and not registry["groups"][gid]["display_name"]:
        # Use the original casing as display name for manually created groups
        registry["groups"][gid]["display_name"] = name.strip()

    registry["groups"][gid]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_registry(registry, registry_path)

    _append_log(log_path, {
        "action": "create",
        "group_id": gid,
        "name": norm,
        "display_name": display_name or name.strip(),
        "was_existing": was_known,
    })

    return registry["groups"][gid]


# ---------------------------------------------------------------------------
# Property linking — manual association between groups and properties
# ---------------------------------------------------------------------------

def _load_property_links(path: Path) -> List[Dict]:
    """Load the group-property links file."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return []


def _save_property_links(path: Path, links: List[Dict]) -> None:
    """Write the group-property links file."""
    path.write_text(
        json.dumps(links, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def link_property(
    links_path: Path,
    log_path: Path,
    registry_path: Path,
    group_id: str,
    arn: str,
    property_id: str = "",
) -> Dict:
    """Link a property (by ARN) to a Group. Persists across data engine rebuilds.

    Returns the created link entry.
    """
    # Verify group exists
    registry = load_registry(registry_path)
    if group_id not in registry["groups"]:
        raise ValueError(f"Group {group_id} not found")

    if not arn:
        raise ValueError("ARN is required")

    links = _load_property_links(links_path)

    # Check for duplicate
    for link in links:
        if link["group_id"] == group_id and link["arn"] == arn:
            return link  # Already linked

    entry = {
        "group_id": group_id,
        "arn": arn,
        "property_id": property_id,
        "added_at": datetime.now(timezone.utc).isoformat(),
    }
    links.append(entry)
    _save_property_links(links_path, links)

    _append_log(log_path, {
        "action": "link_property",
        "group_id": group_id,
        "arn": arn,
        "property_id": property_id,
    })

    return entry


def unlink_property(
    links_path: Path,
    log_path: Path,
    group_id: str,
    arn: str,
) -> bool:
    """Remove a property link from a Group. Returns True if a link was removed."""
    links = _load_property_links(links_path)
    before = len(links)
    links = [l for l in links if not (l["group_id"] == group_id and l["arn"] == arn)]

    if len(links) == before:
        return False

    _save_property_links(links_path, links)
    _append_log(log_path, {
        "action": "unlink_property",
        "group_id": group_id,
        "arn": arn,
    })
    return True


def get_property_links(links_path: Path, group_id: Optional[str] = None) -> List[Dict]:
    """Get property links, optionally filtered by group_id."""
    links = _load_property_links(links_path)
    if group_id:
        return [l for l in links if l["group_id"] == group_id]
    return links
