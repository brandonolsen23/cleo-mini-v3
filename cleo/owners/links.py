"""Manual owner linking — confirmed pairs stored in owner_links.json.

Every link/unlink action is logged to owner_link_log.jsonl for
audit trail and future AI pattern analysis.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from cleo.config import OWNER_LINKS_PATH, OWNER_LINK_LOG_PATH

logger = logging.getLogger(__name__)


def _load_links() -> Dict:
    """Load owner links file, creating empty structure if missing."""
    if OWNER_LINKS_PATH.exists():
        return json.loads(OWNER_LINKS_PATH.read_text(encoding="utf-8"))
    return {"links": [], "name_to_link": {}}


def _save_links(data: Dict):
    """Write owner links file."""
    OWNER_LINKS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _append_log(entry: Dict):
    """Append an audit log entry to owner_link_log.jsonl."""
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(OWNER_LINK_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _next_link_id(data: Dict) -> str:
    """Generate the next LNK_NNNNN ID."""
    existing_ids = [lg["id"] for lg in data.get("links", [])]
    max_num = 0
    for lid in existing_ids:
        if lid.startswith("LNK_"):
            try:
                num = int(lid[4:])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"LNK_{max_num + 1:05d}"


def link_owners(
    names: List[str],
    display_name: Optional[str] = None,
    reason: str = "",
) -> Dict:
    """Link multiple normalized owner names into a group.

    If any name is already in a group, extends that group.
    If names span multiple groups, merges them.
    Returns the resulting link group.
    """
    data = _load_links()
    name_to_link = data.get("name_to_link", {})
    links_by_id: Dict[str, Dict] = {lg["id"]: lg for lg in data.get("links", [])}

    # Find existing groups that these names belong to
    existing_groups = set()
    for n in names:
        lid = name_to_link.get(n)
        if lid:
            existing_groups.add(lid)

    if len(existing_groups) == 0:
        # Create new group
        link_id = _next_link_id(data)
        group = {
            "id": link_id,
            "display_name": display_name or "",
            "members": sorted(set(names)),
            "notes": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        data["links"].append(group)
        for n in names:
            name_to_link[n] = link_id

    elif len(existing_groups) == 1:
        # Extend existing group
        link_id = existing_groups.pop()
        group = links_by_id[link_id]
        new_members = set(group["members"])
        for n in names:
            new_members.add(n)
        group["members"] = sorted(new_members)
        if display_name:
            group["display_name"] = display_name
        group["updated_at"] = datetime.now(timezone.utc).isoformat()
        for n in names:
            name_to_link[n] = link_id

    else:
        # Merge multiple groups
        sorted_groups = sorted(existing_groups)
        link_id = sorted_groups[0]  # keep the lowest ID
        target = links_by_id[link_id]

        all_members = set(target["members"])
        for gid in sorted_groups[1:]:
            donor = links_by_id[gid]
            all_members.update(donor["members"])
            # Remove donor group
            data["links"] = [lg for lg in data["links"] if lg["id"] != gid]

        for n in names:
            all_members.add(n)

        target["members"] = sorted(all_members)
        if display_name:
            target["display_name"] = display_name
        target["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Update all name mappings
        for m in target["members"]:
            name_to_link[m] = link_id

        group = target

    data["name_to_link"] = name_to_link
    _save_links(data)

    _append_log({
        "action": "link",
        "link_id": group["id"],
        "names": names,
        "display_name": display_name,
        "reason": reason,
    })

    return group


def unlink_owner(name: str, link_id: str, reason: str = "") -> Optional[Dict]:
    """Remove a name from a link group.

    If the group has only 1 member after removal, dissolves the group.
    Returns the updated group, or None if dissolved.
    """
    data = _load_links()
    name_to_link = data.get("name_to_link", {})

    # Find the group
    group = None
    for lg in data["links"]:
        if lg["id"] == link_id:
            group = lg
            break

    if not group:
        raise ValueError(f"Link group {link_id} not found")

    if name not in group["members"]:
        raise ValueError(f"Name '{name}' not in group {link_id}")

    group["members"].remove(name)
    name_to_link.pop(name, None)
    group["updated_at"] = datetime.now(timezone.utc).isoformat()

    result = group
    if len(group["members"]) <= 1:
        # Dissolve group — single member doesn't need a link
        for m in group["members"]:
            name_to_link.pop(m, None)
        data["links"] = [lg for lg in data["links"] if lg["id"] != link_id]
        result = None

    data["name_to_link"] = name_to_link
    _save_links(data)

    _append_log({
        "action": "unlink",
        "link_id": link_id,
        "name": name,
        "reason": reason,
    })

    return result


def set_display_name(owner_id: str, display_name: str, normalized_name: str = "") -> Dict:
    """Set the display name for a link group or individual entity.

    For link groups (LNK_NNNNN), updates the group record.
    For individual entities, stores in a display_names dict keyed by normalized name.
    """
    data = _load_links()

    # Link group
    if owner_id.startswith("LNK_"):
        for lg in data["links"]:
            if lg["id"] == owner_id:
                lg["display_name"] = display_name
                lg["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save_links(data)
                _append_log({
                    "action": "rename",
                    "link_id": owner_id,
                    "display_name": display_name,
                })
                return lg
        raise ValueError(f"Link group {owner_id} not found")

    # Individual entity — store in display_names dict
    if not normalized_name:
        raise ValueError("normalized_name required for non-link entities")

    display_names = data.get("display_names", {})
    display_names[normalized_name] = display_name
    data["display_names"] = display_names
    _save_links(data)

    _append_log({
        "action": "rename",
        "owner_id": owner_id,
        "normalized_name": normalized_name,
        "display_name": display_name,
    })
    return {"id": owner_id, "display_name": display_name}


def get_all_links() -> List[Dict]:
    """Return all link groups."""
    data = _load_links()
    return data.get("links", [])
