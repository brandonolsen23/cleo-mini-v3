"""Auto-confirm party names based on high-confidence signals.

Rules:
1. Single-name groups: the name IS the group, no ambiguity.
2. Alias match: a name's transaction aliases match the group display name.
3. Shared phone: two+ names in a group share a phone across transactions.
4. Shared contact: two+ names in a group share a contact person across transactions.

Rules 3-4 use transitivity: if A shares a phone with B, and B shares a
contact with C, all three are linked.
"""

import json
from pathlib import Path

from cleo.parties.normalize import normalize_name


def auto_confirm(
    parties: dict,
    overrides: dict,
    parsed_dir: Path,
) -> dict:
    """Compute auto-confirmable names. Returns {group_id: [norm_names]}.

    Does NOT modify the registry — caller decides whether to write.
    """
    already_confirmed: dict[str, set[str]] = {}
    for gid, names in overrides.get("confirmed", {}).items():
        already_confirmed[gid] = set(names)

    result: dict[str, list[str]] = {}

    # Rule 1: single-name groups
    for gid, p in parties.items():
        names = p.get("names", [])
        if len(names) == 1:
            norm = normalize_name(names[0])
            if norm and norm not in already_confirmed.get(gid, set()):
                result.setdefault(gid, []).append(norm)

    # Rules 2-4: multi-name groups — scan parsed data
    multi_groups = {gid: p for gid, p in parties.items() if len(p.get("names", [])) > 1}

    for gid, p in multi_groups.items():
        display = (p.get("display_name_override") or p.get("display_name", "")).upper().strip()
        group_norms = {normalize_name(n) for n in p.get("names", [])}
        already = already_confirmed.get(gid, set())

        # Build per-name evidence from parsed transaction data
        name_phones: dict[str, set[str]] = {}
        name_contacts: dict[str, set[str]] = {}
        name_aliases: dict[str, set[str]] = {}

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
                if not norm or norm not in group_norms:
                    continue

                phone = (party.get("phone") or "").strip()
                if phone:
                    name_phones.setdefault(norm, set()).add(phone)

                contact = (party.get("contact") or "").strip().upper()
                if contact:
                    name_contacts.setdefault(norm, set()).add(contact)

                for alias in party.get("aliases", []):
                    name_aliases.setdefault(norm, set()).add(alias.upper())

        # Union-find for transitivity
        parent: dict[str, str] = {n: n for n in group_norms}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Rule 2: alias matches display name — link to any other name
        alias_linked: set[str] = set()
        for norm, aliases in name_aliases.items():
            for alias in aliases:
                if display and (alias in display or display in alias):
                    alias_linked.add(norm)
                    break

        # Rule 3: shared phones link names
        phone_to_norms: dict[str, set[str]] = {}
        for norm, phones in name_phones.items():
            for ph in phones:
                phone_to_norms.setdefault(ph, set()).add(norm)

        for ph, norms in phone_to_norms.items():
            norms_list = list(norms)
            for i in range(1, len(norms_list)):
                union(norms_list[0], norms_list[i])

        # Rule 4: shared contacts link names
        contact_to_norms: dict[str, set[str]] = {}
        for norm, contacts in name_contacts.items():
            for c in contacts:
                contact_to_norms.setdefault(c, set()).add(norm)

        for c, norms in contact_to_norms.items():
            norms_list = list(norms)
            for i in range(1, len(norms_list)):
                union(norms_list[0], norms_list[i])

        # Also union alias-linked names with each other
        alias_list = list(alias_linked)
        for i in range(1, len(alias_list)):
            union(alias_list[0], alias_list[i])

        # Find the largest connected component
        clusters: dict[str, set[str]] = {}
        for norm in group_norms:
            root = find(norm)
            clusters.setdefault(root, set()).add(norm)

        if not clusters:
            continue

        largest = max(clusters.values(), key=len)

        # If alias-linked names exist, the cluster containing them is the
        # "confirmed" cluster (it has brand evidence). Otherwise, use the
        # largest cluster if it has at least 2 members (linked by phone/contact).
        confirmed_cluster: set[str] | None = None
        if alias_linked:
            # Find the cluster containing alias-linked names
            for cluster in clusters.values():
                if cluster & alias_linked:
                    confirmed_cluster = cluster
                    break
        elif len(largest) >= 2:
            confirmed_cluster = largest

        if confirmed_cluster:
            for norm in confirmed_cluster:
                if norm not in already:
                    result.setdefault(gid, []).append(norm)

    return result


def apply_auto_confirm(
    registry: dict,
    confirmations: dict[str, list[str]],
) -> int:
    """Apply confirmations to registry overrides. Returns count of new names confirmed."""
    overrides = registry.setdefault("overrides", {})
    confirmed = overrides.setdefault("confirmed", {})
    count = 0

    for gid, norms in confirmations.items():
        group_confirmed = confirmed.setdefault(gid, [])
        existing = set(group_confirmed)
        for norm in norms:
            if norm not in existing:
                group_confirmed.append(norm)
                existing.add(norm)
                count += 1

    return count
