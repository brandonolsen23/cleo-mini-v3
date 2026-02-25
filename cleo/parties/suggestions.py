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
      {"type": "phone"|"contact"|"alias"|"address"|"chain", "value": str,
       "linked_names": [str], "rt_ids": [str], "detail": str}

    For direct reasons, each dict also includes:
      "target_rt_id", "target_role", "linked_rt_data": [{"name", "rt_id", "role"}]

    For chain reasons, each dict also includes:
      "chain": [{"name", "rt_id", "role", "link_type", "link_value"}, ...]

    If no direct link is found, traces transitive chains (BFS) through shared
    attributes across group members to explain how the name ended up in the group.
    """
    from pathlib import Path
    import json
    from collections import deque

    p = parties.get(group_id)
    if not p:
        return []

    target_norm = normalize_name(name)
    group_norms = {normalize_name(n) for n in p.get("names", [])}
    other_norms = group_norms - {target_norm}

    if not other_norms:
        return []  # Only name in the group

    # Map norm -> original name for display
    norm_to_name: dict[str, str] = {}
    for n in p.get("names", []):
        nn = normalize_name(n)
        if nn not in norm_to_name:
            norm_to_name[nn] = n

    # Collect per-name attributes from parsed data
    name_phones: dict[str, dict[str, list[str]]] = {}   # norm -> {phone: [rt_ids]}
    name_contacts: dict[str, dict[str, list[str]]] = {}  # norm -> {CONTACT: [rt_ids]}
    name_aliases: dict[str, dict[str, list[str]]] = {}   # norm -> {ALIAS: [rt_ids]}
    name_addresses: dict[str, dict[str, list[str]]] = {} # norm -> {NORM_ADDR: [rt_ids]}
    # Store raw address for display
    raw_addresses: dict[str, str] = {}  # NORM_ADDR -> original address
    # Track name roles: norm -> {rt_id: role}
    name_roles: dict[str, dict[str, str]] = {}

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

            role = "seller" if party_key == "transferor" else "buyer"
            name_roles.setdefault(norm, {})[rt_id] = role

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

            address = (party.get("address") or "").strip()
            if address and len(address) >= 10:
                norm_addr = normalize_address(address)
                name_addresses.setdefault(norm, {}).setdefault(norm_addr, []).append(rt_id)
                if norm_addr not in raw_addresses:
                    raw_addresses[norm_addr] = address

    # Helper: find RT IDs where a norm has a given attribute
    def _find_rt_for_attr(norm, attr_type, attr_val):
        if attr_type == "phone":
            return name_phones.get(norm, {}).get(attr_val, [])
        elif attr_type == "contact":
            return name_contacts.get(norm, {}).get(attr_val, [])
        elif attr_type == "address":
            na = normalize_address(attr_val)
            return name_addresses.get(norm, {}).get(na, [])
        elif attr_type == "alias":
            return name_aliases.get(norm, {}).get(attr_val, [])
        return []

    # Find direct links from target to any other group member
    target_phones = name_phones.get(target_norm, {})
    target_contacts = name_contacts.get(target_norm, {})
    target_aliases = name_aliases.get(target_norm, {})
    target_addresses = name_addresses.get(target_norm, {})

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
                "detail": "Alias matches group name",
            })

    # Shared phones with other names
    for phone, rt_ids in target_phones.items():
        linked = []
        for other_norm in other_norms:
            other_phones = name_phones.get(other_norm, {})
            if phone in other_phones:
                linked.append(norm_to_name.get(other_norm, other_norm))
        if linked:
            reasons.append({
                "type": "phone",
                "value": phone,
                "linked_names": linked[:5],
                "rt_ids": sorted(set(rt_ids)),
                "detail": f"Shared with {', '.join(linked[:3])}{'...' if len(linked) > 3 else ''}",
            })

    # Shared contacts with other names
    for contact, rt_ids in target_contacts.items():
        linked = []
        for other_norm in other_norms:
            other_contacts = name_contacts.get(other_norm, {})
            if contact in other_contacts:
                linked.append(norm_to_name.get(other_norm, other_norm))
        if linked:
            reasons.append({
                "type": "contact",
                "value": contact,
                "linked_names": linked[:5],
                "rt_ids": sorted(set(rt_ids)),
                "detail": f"Shared with {', '.join(linked[:3])}{'...' if len(linked) > 3 else ''}",
            })

    # Shared addresses with other names (Rule 4 in clustering)
    for norm_addr, rt_ids in target_addresses.items():
        linked = []
        for other_norm in other_norms:
            other_addrs = name_addresses.get(other_norm, {})
            if norm_addr in other_addrs:
                linked.append(norm_to_name.get(other_norm, other_norm))
        if linked:
            raw = raw_addresses.get(norm_addr, norm_addr)
            reasons.append({
                "type": "address",
                "value": raw,
                "linked_names": linked[:5],
                "rt_ids": sorted(set(rt_ids)),
                "detail": f"Shared party address with {', '.join(linked[:3])}{'...' if len(linked) > 3 else ''}",
            })

    # Enhance direct reasons with RT data for chain viewer
    if reasons:
        for r in reasons:
            rts = _find_rt_for_attr(target_norm, r["type"], r["value"])
            rt_id = rts[0] if rts else None
            r["target_rt_id"] = rt_id
            r["target_role"] = name_roles.get(target_norm, {}).get(rt_id)

            linked_data = []
            for ln in r.get("linked_names", []):
                ln_norm = normalize_name(ln)
                ln_rts = _find_rt_for_attr(ln_norm, r["type"], r["value"])
                ln_rt = ln_rts[0] if ln_rts else None
                ln_role = name_roles.get(ln_norm, {}).get(ln_rt)
                linked_data.append({"name": ln, "rt_id": ln_rt, "role": ln_role})
            r["linked_rt_data"] = linked_data
        return reasons

    # ---- Transitive chain tracing via BFS ----
    # Build adjacency graph: norm -> [(other_norm, link_type, link_value)]
    adj: dict[str, list[tuple[str, str, str]]] = {nn: [] for nn in group_norms}

    # Add edges for shared phones
    phone_to_norms: dict[str, list[str]] = {}
    for nn, phones in name_phones.items():
        for ph in phones:
            phone_to_norms.setdefault(ph, []).append(nn)
    for ph, norms in phone_to_norms.items():
        if len(norms) >= 2:
            for i in range(len(norms)):
                for j in range(i + 1, len(norms)):
                    adj[norms[i]].append((norms[j], "phone", ph))
                    adj[norms[j]].append((norms[i], "phone", ph))

    # Add edges for shared contacts
    contact_to_norms: dict[str, list[str]] = {}
    for nn, contacts in name_contacts.items():
        for c in contacts:
            contact_to_norms.setdefault(c, []).append(nn)
    for c, norms in contact_to_norms.items():
        if len(norms) >= 2:
            for i in range(len(norms)):
                for j in range(i + 1, len(norms)):
                    adj[norms[i]].append((norms[j], "contact", c))
                    adj[norms[j]].append((norms[i], "contact", c))

    # Add edges for shared addresses
    addr_to_norms: dict[str, list[str]] = {}
    for nn, addrs in name_addresses.items():
        for a in addrs:
            addr_to_norms.setdefault(a, []).append(nn)
    for a, norms in addr_to_norms.items():
        if len(norms) >= 2:
            raw = raw_addresses.get(a, a)
            for i in range(len(norms)):
                for j in range(i + 1, len(norms)):
                    adj[norms[i]].append((norms[j], "address", raw))
                    adj[norms[j]].append((norms[i], "address", raw))

    # BFS from target to find shortest chain to any other group member
    visited = {target_norm}
    queue: deque[tuple[str, list[tuple[str, str, str]]]] = deque()
    queue.append((target_norm, []))

    while queue:
        current, path = queue.popleft()
        for neighbor, link_type, link_val in adj.get(current, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            new_path = path + [(neighbor, link_type, link_val)]

            if neighbor in other_norms:
                # Found chain — build structured chain steps
                chain_norms = [target_norm] + [step[0] for step in new_path]
                chain_links = [(step[1], step[2]) for step in new_path]

                chain_steps = []
                for i, cn in enumerate(chain_norms):
                    out_type = chain_links[i][0] if i < len(chain_links) else None
                    out_val = chain_links[i][1] if i < len(chain_links) else None
                    in_type = chain_links[i - 1][0] if i > 0 else None
                    in_val = chain_links[i - 1][1] if i > 0 else None

                    # Pick RT: prefer outgoing link attr, then incoming, then any
                    rt_id = None
                    if out_type:
                        rts = _find_rt_for_attr(cn, out_type, out_val)
                        if rts:
                            rt_id = rts[0]
                    if not rt_id and in_type:
                        rts = _find_rt_for_attr(cn, in_type, in_val)
                        if rts:
                            rt_id = rts[0]
                    if not rt_id:
                        all_rts = list(name_roles.get(cn, {}).keys())
                        rt_id = all_rts[0] if all_rts else None

                    role = name_roles.get(cn, {}).get(rt_id)

                    chain_steps.append({
                        "name": norm_to_name.get(cn, cn),
                        "rt_id": rt_id,
                        "role": role,
                        "link_type": out_type,
                        "link_value": out_val,
                    })

                # Text format for backward compat
                steps_text = []
                prev_name = norm_to_name.get(target_norm, name)
                for step_norm, step_type, step_val in new_path:
                    sn = norm_to_name.get(step_norm, step_norm)
                    steps_text.append(f"{prev_name} --[{step_type}: {step_val}]--> {sn}")
                    prev_name = sn
                chain_detail = " | ".join(steps_text)

                reasons.append({
                    "type": "chain",
                    "value": chain_detail,
                    "linked_names": [norm_to_name.get(s[0], s[0]) for s in new_path],
                    "rt_ids": [],
                    "detail": f"Linked via {len(new_path)}-step chain: {chain_detail}",
                    "chain": chain_steps,
                })
                return reasons

            queue.append((neighbor, new_path))

    return reasons
