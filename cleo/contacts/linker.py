"""Manual contact linking — merge/split contacts, set display names.

Every action is logged to contact_link_log.jsonl for audit trail.
The lower-numbered CON_ ID wins on merge.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from cleo.contacts.registry import load_registry, save_registry, normalize_contact_name

logger = logging.getLogger(__name__)


def _append_log(log_path: Path, entry: Dict):
    """Append an audit log entry."""
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def link_contacts(
    registry_path: Path,
    log_path: Path,
    names: List[str],
    display_name: Optional[str] = None,
    reason: str = "",
) -> Dict:
    """Link multiple normalized contact names into one Contact.

    If names already belong to different Contacts, merges them (lower CON_ wins).
    Returns the resulting Contact record.
    """
    registry = load_registry(registry_path)
    name_index = registry["name_index"]
    contacts = registry["contacts"]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    normalized = sorted(set(n for n in (normalize_contact_name(n) for n in names) if n))
    if len(normalized) < 2:
        raise ValueError("At least 2 distinct normalized names required")

    existing_cids = set()
    for n in normalized:
        cid = name_index.get(n)
        if cid:
            existing_cids.add(cid)

    if len(existing_cids) == 0:
        from cleo.contacts.registry import assign_contact
        cid = assign_contact(registry, normalized[0])
        target = contacts[cid]
        for n in normalized[1:]:
            if n not in name_index:
                name_index[n] = cid
                target["known_names"].append(n)
        target["known_names"] = sorted(set(target["known_names"]))
        if display_name:
            target["display_name"] = display_name
        target["updated_at"] = now

    elif len(existing_cids) == 1:
        cid = existing_cids.pop()
        target = contacts[cid]
        for n in normalized:
            if n not in name_index:
                name_index[n] = cid
                target["known_names"].append(n)
        target["known_names"] = sorted(set(target["known_names"]))
        if display_name:
            target["display_name"] = display_name
        target["updated_at"] = now

    else:
        sorted_cids = sorted(existing_cids)
        cid = sorted_cids[0]
        target = contacts[cid]

        for donor_cid in sorted_cids[1:]:
            donor = contacts.get(donor_cid)
            if not donor:
                continue
            for dn in donor["known_names"]:
                name_index[dn] = cid
                if dn not in target["known_names"]:
                    target["known_names"].append(dn)
            # Merge phones
            for p in donor.get("phones", []):
                if p not in target.get("phones", []):
                    target.setdefault("phones", []).append(p)
            # Merge group_associations
            existing_gids = {a["group_id"] for a in target.get("group_associations", [])}
            for a in donor.get("group_associations", []):
                if a["group_id"] not in existing_gids:
                    target.setdefault("group_associations", []).append(a)
                    existing_gids.add(a["group_id"])
            del contacts[donor_cid]

        for n in normalized:
            if n not in name_index:
                name_index[n] = cid
                target["known_names"].append(n)
        target["known_names"] = sorted(set(target["known_names"]))
        if display_name:
            target["display_name"] = display_name
        target["updated_at"] = now

    save_registry(registry, registry_path)
    _append_log(log_path, {
        "action": "link",
        "contact_id": cid,
        "names": normalized,
        "display_name": display_name,
        "reason": reason,
    })

    return contacts[cid]


def unlink_contact(
    registry_path: Path,
    log_path: Path,
    name: str,
    contact_id: str,
    reason: str = "",
) -> Optional[Dict]:
    """Remove a name from a Contact. The name gets its own new CON_ ID."""
    registry = load_registry(registry_path)
    contacts = registry["contacts"]
    name_index = registry["name_index"]
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    norm = normalize_contact_name(name)

    if contact_id not in contacts:
        raise ValueError(f"Contact {contact_id} not found")

    contact = contacts[contact_id]
    if norm not in contact["known_names"]:
        raise ValueError(f"Name '{norm}' not in contact {contact_id}")

    if len(contact["known_names"]) <= 1:
        raise ValueError(f"Cannot unlink the last name from contact {contact_id}")

    contact["known_names"].remove(norm)
    contact["updated_at"] = now

    from cleo.contacts.registry import assign_contact
    new_cid = assign_contact(registry, norm)

    save_registry(registry, registry_path)
    _append_log(log_path, {
        "action": "unlink",
        "source_contact_id": contact_id,
        "new_contact_id": new_cid,
        "name": norm,
        "reason": reason,
    })

    return contact


def set_display_name(
    registry_path: Path,
    log_path: Path,
    contact_id: str,
    display_name: str,
) -> Dict:
    """Set the display name for a Contact."""
    registry = load_registry(registry_path)
    contacts = registry["contacts"]

    if contact_id not in contacts:
        raise ValueError(f"Contact {contact_id} not found")

    contacts[contact_id]["display_name"] = display_name
    contacts[contact_id]["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    save_registry(registry, registry_path)
    _append_log(log_path, {
        "action": "rename",
        "contact_id": contact_id,
        "display_name": display_name,
    })

    return contacts[contact_id]
