"""Suggestion engine for affiliate matching between party groups.

Builds inverted indexes on phone, contact, and address fields to find
groups that share attributes with a target group.
"""

from cleo.parties.normalize import normalize_name, normalize_address

# Module-level cache
_index_cache: dict | None = None
_index_cache_mtime: float = 0


def _build_indexes(parties: dict) -> dict:
    """Build inverted indexes: attribute -> set of group_ids."""
    phone_idx: dict[str, set[str]] = {}
    contact_idx: dict[str, set[str]] = {}
    address_idx: dict[str, set[str]] = {}

    for gid, p in parties.items():
        for phone in p.get("phones", []):
            phone = phone.strip()
            if phone:
                phone_idx.setdefault(phone, set()).add(gid)

        for contact in p.get("contacts", []):
            norm = normalize_name(contact)
            if norm:
                contact_idx.setdefault(norm, set()).add(gid)

        for addr in p.get("addresses", []):
            norm = normalize_address(addr)
            if len(norm) >= 10:
                address_idx.setdefault(norm, set()).add(gid)

    return {
        "phone": phone_idx,
        "contact": contact_idx,
        "address": address_idx,
    }


def _get_indexes(parties: dict, mtime: float) -> dict:
    """Return cached indexes, rebuilding if mtime changed."""
    global _index_cache, _index_cache_mtime
    if _index_cache is not None and _index_cache_mtime == mtime:
        return _index_cache
    _index_cache = _build_indexes(parties)
    _index_cache_mtime = mtime
    return _index_cache


def get_suggestions(
    group_id: str,
    parties: dict,
    dismissed: list[str],
    mtime: float,
) -> list[dict]:
    """Find groups that share attributes with the target group.

    Returns a ranked list of suggestion dicts sorted by evidence_score desc.
    """
    if group_id not in parties:
        return []

    target = parties[group_id]
    indexes = _get_indexes(parties, mtime)
    dismissed_set = set(dismissed)

    # Collect candidates with their shared attributes
    candidates: dict[str, dict] = {}  # gid -> {shared_phones, shared_contacts, shared_addresses}

    # Phones
    for phone in target.get("phones", []):
        phone = phone.strip()
        if not phone:
            continue
        for gid in indexes["phone"].get(phone, set()):
            if gid == group_id or gid in dismissed_set:
                continue
            c = candidates.setdefault(gid, {
                "shared_phones": [],
                "shared_contacts": [],
                "shared_addresses": [],
            })
            if phone not in c["shared_phones"]:
                c["shared_phones"].append(phone)

    # Contacts
    for contact in target.get("contacts", []):
        norm = normalize_name(contact)
        if not norm:
            continue
        for gid in indexes["contact"].get(norm, set()):
            if gid == group_id or gid in dismissed_set:
                continue
            c = candidates.setdefault(gid, {
                "shared_phones": [],
                "shared_contacts": [],
                "shared_addresses": [],
            })
            if contact not in c["shared_contacts"]:
                c["shared_contacts"].append(contact)

    # Addresses
    for addr in target.get("addresses", []):
        norm = normalize_address(addr)
        if len(norm) < 10:
            continue
        for gid in indexes["address"].get(norm, set()):
            if gid == group_id or gid in dismissed_set:
                continue
            c = candidates.setdefault(gid, {
                "shared_phones": [],
                "shared_contacts": [],
                "shared_addresses": [],
            })
            if addr not in c["shared_addresses"]:
                c["shared_addresses"].append(addr)

    # Score and build results
    results = []
    for gid, shared in candidates.items():
        p = parties.get(gid)
        if not p:
            continue
        score = (
            len(shared["shared_phones"]) * 3
            + len(shared["shared_contacts"]) * 2
            + len(shared["shared_addresses"]) * 1
        )
        results.append({
            "group_id": gid,
            "display_name": p.get("display_name_override") or p.get("display_name", ""),
            "is_company": p.get("is_company", True),
            "transaction_count": p.get("transaction_count", 0),
            "names": p.get("names", [])[:5],
            "shared_phones": shared["shared_phones"],
            "shared_contacts": shared["shared_contacts"],
            "shared_addresses": shared["shared_addresses"],
            "evidence_score": score,
        })

    results.sort(key=lambda r: r["evidence_score"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Known-attributes: confirmed group attributes → display names
# ---------------------------------------------------------------------------

_known_cache: dict | None = None
_known_cache_mtime: float = 0


def build_known_attributes(parties: dict, overrides: dict, mtime: float) -> dict:
    """Build lookup from confirmed groups' attributes to their display names.

    Only includes groups with at least one confirmed name.
    Returns {phones: {phone: [names]}, contacts: {NORM: [names]}, addresses: {NORM: [names]}}.
    """
    global _known_cache, _known_cache_mtime
    if _known_cache is not None and _known_cache_mtime == mtime:
        return _known_cache

    confirmed = overrides.get("confirmed", {})
    confirmed_gids = {gid for gid, names in confirmed.items() if names}

    phones: dict[str, list[str]] = {}
    contacts: dict[str, list[str]] = {}
    addresses: dict[str, list[str]] = {}

    for gid in confirmed_gids:
        p = parties.get(gid)
        if not p:
            continue
        display = p.get("display_name_override") or p.get("display_name", "")
        if not display:
            continue

        for phone in p.get("phones", []):
            phone = phone.strip()
            if phone:
                phones.setdefault(phone, [])
                if display not in phones[phone]:
                    phones[phone].append(display)

        for contact in p.get("contacts", []):
            norm = normalize_name(contact)
            if norm:
                contacts.setdefault(norm, [])
                if display not in contacts[norm]:
                    contacts[norm].append(display)

        for addr in p.get("addresses", []):
            norm = normalize_address(addr)
            if len(norm) >= 10:
                addresses.setdefault(norm, [])
                if display not in addresses[norm]:
                    addresses[norm].append(display)

    _known_cache = {"phones": phones, "contacts": contacts, "addresses": addresses}
    _known_cache_mtime = mtime
    return _known_cache


# ---------------------------------------------------------------------------
# Grouping reason: why is a specific name in this group?
# ---------------------------------------------------------------------------

def get_grouping_reason(
    group_id: str,
    name: str,
    parties: dict,
    parsed_dir: "Path",
) -> list[dict]:
    """Explain why a name is in a group by finding shared attributes with other group names.

    Scans parsed transaction data for the target name and all other names in
    the group. Returns a list of linkage evidence dicts:
      {"type": "phone"|"contact"|"alias", "value": str, "linked_names": [str], "rt_ids": [str]}
    """
    from pathlib import Path
    import json

    p = parties.get(group_id)
    if not p:
        return []

    target_norm = normalize_name(name)
    group_norms = {normalize_name(n) for n in p.get("names", [])}
    other_norms = group_norms - {target_norm}

    if not other_norms:
        return []  # Only name in the group

    # Collect per-name attributes from parsed data
    name_phones: dict[str, dict[str, list[str]]] = {}  # norm -> {phone: [rt_ids]}
    name_contacts: dict[str, dict[str, list[str]]] = {}  # norm -> {CONTACT: [rt_ids]}
    name_aliases: dict[str, dict[str, list[str]]] = {}  # norm -> {ALIAS: [rt_ids]}

    for rt_id in p.get("rt_ids", []):
        f = parsed_dir / f"{rt_id}.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))

        for party_key in ("transferor", "transferee"):
            party = data.get(party_key, {})
            if not party:
                continue
            pname = party.get("name", "")
            norm = normalize_name(pname)
            if norm not in group_norms:
                continue

            phone = (party.get("phone") or "").strip()
            if phone:
                name_phones.setdefault(norm, {}).setdefault(phone, []).append(rt_id)

            contact = (party.get("contact") or "").strip().upper()
            if contact:
                name_contacts.setdefault(norm, {}).setdefault(contact, []).append(rt_id)

            for alias in party.get("aliases", []):
                a = alias.upper()
                if a:
                    name_aliases.setdefault(norm, {}).setdefault(a, []).append(rt_id)

    # Find shared phones
    target_phones = name_phones.get(target_norm, {})
    target_contacts = name_contacts.get(target_norm, {})
    target_aliases = name_aliases.get(target_norm, {})

    reasons: list[dict] = []

    # Check alias match to display name
    display = (p.get("display_name_override") or p.get("display_name", "")).upper()
    for alias, rt_ids in target_aliases.items():
        if display and (alias in display or display in alias):
            reasons.append({
                "type": "alias",
                "value": alias,
                "linked_names": [],
                "rt_ids": sorted(set(rt_ids)),
                "detail": f"Alias matches group name",
            })

    # Shared phones with other names
    for phone, rt_ids in target_phones.items():
        linked = []
        linked_rts = []
        for other_norm in other_norms:
            other_phones = name_phones.get(other_norm, {})
            if phone in other_phones:
                # Find original name string
                for n in p["names"]:
                    if normalize_name(n) == other_norm:
                        linked.append(n)
                        break
                linked_rts.extend(other_phones[phone])
        if linked:
            reasons.append({
                "type": "phone",
                "value": phone,
                "linked_names": linked,
                "rt_ids": sorted(set(rt_ids)),
                "detail": f"Shared with {', '.join(linked)}",
            })

    # Shared contacts with other names
    for contact, rt_ids in target_contacts.items():
        linked = []
        linked_rts = []
        for other_norm in other_norms:
            other_contacts = name_contacts.get(other_norm, {})
            if contact in other_contacts:
                for n in p["names"]:
                    if normalize_name(n) == other_norm:
                        linked.append(n)
                        break
                linked_rts.extend(other_contacts[contact])
        if linked:
            reasons.append({
                "type": "contact",
                "value": contact,
                "linked_names": linked[:5],
                "rt_ids": sorted(set(rt_ids)),
                "detail": f"Shared with {', '.join(linked[:3])}{'...' if len(linked) > 3 else ''}",
            })

    return reasons
