"""Contact Registry: persistent store of every individual person in transactions.

One person = one CON_ ID, regardless of how many transactions or Groups they
appear with. Tracks group associations with active/former status.

Structure:
  contact_registry.json = {
    meta: {created, last_updated, next_id, total_contacts},
    contacts: {CON_NNNNN: {id, display_name, phones, group_associations, ...}},
    name_index: {NORMALIZED_NAME: CON_NNNNN}
  }
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Name normalization
# ---------------------------------------------------------------------------

_TITLE_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof|Jr|Sr|Esq|CPA|P\.?Eng|MBA)\.?\s*$",
    re.IGNORECASE,
)

_INITIAL_DOT_RE = re.compile(r"\b([A-Z])\.\s*")


def normalize_contact_name(name: str) -> str:
    """Normalize a contact (individual person) name for dedup.

    Uppercase, collapse whitespace, strip trailing punctuation,
    strip titles/honorifics.
    """
    s = name.upper().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:")
    # Strip titles
    for _ in range(2):
        prev = s
        s = _TITLE_RE.sub("", s).rstrip(".,;: ")
        if s == prev:
            break
    return s


# ---------------------------------------------------------------------------
# Registry I/O
# ---------------------------------------------------------------------------

def load_registry(path: Path) -> Dict:
    """Load the contact registry from disk. Returns empty structure if not found."""
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        logger.info(
            "Loaded contact registry: %d contacts, %d names indexed",
            len(data.get("contacts", {})),
            len(data.get("name_index", {})),
        )
        return data

    return {
        "meta": {
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "next_id": 1,
            "total_contacts": 0,
        },
        "contacts": {},
        "name_index": {},
    }


def save_registry(data: Dict, path: Path) -> None:
    """Write the contact registry to disk."""
    data["meta"]["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    data["meta"]["total_contacts"] = len(data["contacts"])
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved contact registry: %d contacts", len(data["contacts"]))


# ---------------------------------------------------------------------------
# ID assignment
# ---------------------------------------------------------------------------

def assign_contact(registry: Dict, normalized_name: str) -> str:
    """Get or assign a CON_ ID for a normalized name. Mutates registry in place.

    Returns the CON_ ID.
    """
    name_index = registry["name_index"]

    if normalized_name in name_index:
        return name_index[normalized_name]

    next_id = registry["meta"]["next_id"]
    cid = f"CON_{next_id:05d}"
    registry["meta"]["next_id"] = next_id + 1

    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    registry["contacts"][cid] = {
        "id": cid,
        "display_name": None,
        "known_names": [normalized_name],
        "phones": [],
        "group_associations": [],
        "created_at": now,
        "updated_at": now,
    }
    name_index[normalized_name] = cid
    return cid


# ---------------------------------------------------------------------------
# Build from properties
# ---------------------------------------------------------------------------

def build_from_properties(properties_path: Path, registry_path: Path, group_registry_path: Path) -> Tuple[Dict, Dict]:
    """Scan all transactions in properties.json and build/update the contact registry.

    Extracts every individual from buyer_contact/seller_contact fields.
    Tracks phones, group associations, and first/last seen dates.

    Returns (registry, stats).
    """
    from cleo.groups.registry import normalize_group_name

    start = time.time()

    registry = load_registry(registry_path)
    props_data = json.loads(properties_path.read_text(encoding="utf-8"))
    properties = props_data.get("properties", {})

    # Load group registry for GRP_ ID lookups
    group_name_index = {}
    if group_registry_path.exists():
        greg = json.loads(group_registry_path.read_text(encoding="utf-8"))
        group_name_index = greg.get("name_index", {})

    existing_before = len(registry["contacts"])
    new_count = 0
    existing_count = 0
    total_contacts_scanned = 0
    assoc_changes = 0

    # Track all associations per contact for active/former calculation
    contact_txns: Dict[str, List[Dict]] = {}  # CON_ -> list of {group_id, group_name, date, rt_id, role}

    for pid, prop in properties.items():
        for txn in prop.get("transactions", []):
            rt_id = txn.get("rt_id", "")
            sale_date = txn.get("sale_date", "")

            for role in ("buyer", "seller"):
                contact_name = txn.get(f"{role}_contact", "").strip()
                if not contact_name:
                    continue

                norm = normalize_contact_name(contact_name)
                if not norm:
                    continue

                total_contacts_scanned += 1
                was_known = norm in registry["name_index"]
                cid = assign_contact(registry, norm)

                if was_known:
                    existing_count += 1
                else:
                    new_count += 1

                # Collect phone
                phone = txn.get(f"{role}_phone", "").strip()
                contact_rec = registry["contacts"][cid]
                if phone:
                    clean_phone = re.sub(r"\D", "", phone)
                    if clean_phone and clean_phone not in contact_rec["phones"]:
                        contact_rec["phones"].append(clean_phone)

                # Collect group association info
                group_raw = txn.get(f"{role}_name", "").strip()
                if group_raw:
                    group_norm = normalize_group_name(group_raw)
                    group_id = group_name_index.get(group_norm, "")
                    if cid not in contact_txns:
                        contact_txns[cid] = []
                    contact_txns[cid].append({
                        "group_id": group_id,
                        "group_name": group_raw,
                        "date": sale_date,
                        "rt_id": rt_id,
                        "role": role,
                    })

    # Build group associations per contact
    for cid, txn_list in contact_txns.items():
        contact_rec = registry["contacts"].get(cid)
        if not contact_rec:
            continue

        # Group by group_id
        by_group: Dict[str, Dict] = {}
        for t in txn_list:
            gid = t["group_id"]
            gname = t["group_name"]
            if not gid:
                continue
            if gid not in by_group:
                by_group[gid] = {
                    "group_id": gid,
                    "group_name": gname,
                    "first_seen": t["rt_id"],
                    "first_seen_date": t["date"],
                    "last_seen": t["rt_id"],
                    "last_seen_date": t["date"],
                    "transaction_count": 0,
                    "roles": set(),
                }
            bg = by_group[gid]
            bg["transaction_count"] += 1
            bg["roles"].add(t["role"])
            if t["date"] and (not bg["first_seen_date"] or t["date"] < bg["first_seen_date"]):
                bg["first_seen_date"] = t["date"]
                bg["first_seen"] = t["rt_id"]
            if t["date"] and (not bg["last_seen_date"] or t["date"] > bg["last_seen_date"]):
                bg["last_seen_date"] = t["date"]
                bg["last_seen"] = t["rt_id"]

        # Determine active/former: the group with the most recent date is active
        sorted_groups = sorted(by_group.values(), key=lambda g: g["last_seen_date"] or "", reverse=True)
        latest_date = sorted_groups[0]["last_seen_date"] if sorted_groups else ""

        associations = []
        for ga in sorted_groups:
            # Active if last_seen_date is the most recent (or within same year)
            status = "active" if ga["last_seen_date"] == latest_date else "former"
            associations.append({
                "group_id": ga["group_id"],
                "group_name": ga["group_name"],
                "status": status,
                "first_seen": ga["first_seen"],
                "first_seen_date": ga["first_seen_date"],
                "last_seen": ga["last_seen"],
                "last_seen_date": ga["last_seen_date"],
                "transaction_count": ga["transaction_count"],
                "roles": sorted(ga["roles"]),
            })

        old_assocs = contact_rec.get("group_associations", [])
        if len(associations) != len(old_assocs):
            assoc_changes += 1
        contact_rec["group_associations"] = associations
        contact_rec["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    save_registry(registry, registry_path)
    elapsed = time.time() - start

    stats = {
        "total_contacts_scanned": total_contacts_scanned,
        "existing_contacts": existing_count,
        "new_contacts": new_count,
        "contacts_before": existing_before,
        "contacts_after": len(registry["contacts"]),
        "new_contacts_added": len(registry["contacts"]) - existing_before,
        "association_changes": assoc_changes,
        "elapsed_seconds": round(elapsed, 1),
    }
    logger.info(
        "Contact registry: %d contacts (%d new) from %d appearances in %.1fs",
        stats["contacts_after"], stats["new_contacts_added"],
        total_contacts_scanned, elapsed,
    )
    return registry, stats
