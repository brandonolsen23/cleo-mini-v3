"""Party group registry — clusters related companies via union-find.

Scans parsed transaction data, clusters by normalized name and
company address, assigns stable group IDs, and maintains a
persistent JSON registry with manual override support.
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from .normalize import normalize_name, normalize_address, normalize_phone, make_alias


# ---------------------------------------------------------------------------
# Company detection heuristic
# ---------------------------------------------------------------------------

_COMPANY_INDICATORS = re.compile(
    r"\b(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|LLC|LLP|LP|ULC"
    r"|TRUST|REIT|HOLDINGS|PROPERTIES|REAL ESTATE|INVESTMENTS|MANAGEMENT"
    r"|DEVELOPMENT|DEVELOPMENTS|ENTERPRISES|ASSOCIATES|PARTNERSHIP|PARTNERS"
    r"|GROUP|CAPITAL|REALTY|CONSTRUCTION|SERVICES|SOLUTIONS|CONSULTING"
    r"|VENTURES|BUILDERS|FINANCIAL|MORTGAGE|BANK|CREDIT UNION"
    r"|ONTARIO|CANADA|NAMED INDIVIDUAL)\b",
    re.IGNORECASE,
)

_NUMBER_COMPANY_RE = re.compile(r"^\d{4,}")

_NUMBERED_CO_RE = re.compile(
    r"^\d+\s+Ontario\s+(Inc|Ltd|Limited|Incorporated)\.?\s*$", re.I
)

_BRAND_PAREN_RE = re.compile(
    r"^(.+?)\s*\(.*?\)\s*(Inc|Ltd|Limited|Incorporated|Corp|Corporation)\.?\s*$", re.I
)

_ALIAS_BLACKLIST = {
    "PROFESSIONAL CORPORATION", "PROFESSIONAL", "REAL ESTATE",
    "BARRISTER & SOLICITOR", "BARRISTER", "SOLICITOR",
    "BARRISTERS & SOLICITORS",
    "IN TRUST", "TRUSTEE", "EXECUTOR", "ESTATE OF",
}

# Law firm indicators — aliases matching these are excluded from clustering
_LAW_FIRM_RE = re.compile(
    r"\bLLP\b|BARRISTER|SOLICITOR|LAW OFFICE|LAW FIRM|AVOCATS?\b",
    re.I,
)

# Office building / address aliases — connecting entities that share an office
_BUILDING_ADDR_RE = re.compile(
    r"\b(TOWER|PLACE|PLAZA|FLOOR|SUITE)\b.*\d|\d.*\b(TOWER|PLACE|PLAZA|FLOOR|SUITE)\b"
    r"|^BCE\b|^TD\s",
    re.I,
)


def _is_numbered_company(name: str) -> bool:
    """Is this a numbered Ontario company like '1195117 Ontario Ltd'?"""
    return bool(_NUMBERED_CO_RE.match(name.strip()))


def _clean_alias(alias: str, entity_name: str) -> str | None:
    """Return cleaned alias or None if it should be excluded."""
    norm = alias.upper().strip()
    if len(norm) < 4:
        return None
    if norm in _ALIAS_BLACKLIST:
        return None
    # Skip law firm names
    if _LAW_FIRM_RE.search(norm):
        return None
    # Skip office building / address aliases
    if _BUILDING_ADDR_RE.search(norm):
        return None
    # Skip trivial aliases (just the entity name with suffix stripped)
    if norm == make_alias(entity_name).upper().strip():
        return None
    # Skip purely numeric aliases (just the number from "1195117 Ontario")
    if re.match(r"^\d+\s*(ONTARIO)?$", norm):
        return None
    return norm


def _is_company_name(name: str) -> bool:
    """Heuristic: is this name a company rather than a person?"""
    if not name:
        return True
    if _COMPANY_INDICATORS.search(name):
        return True
    if _NUMBER_COMPANY_RE.match(name):
        return True  # e.g. "8809143 Canada Inc" or numbered companies
    # Person names: 2-3 words, all alpha, no digits
    words = name.split()
    if len(words) < 2 or len(words) > 3:
        return True  # single word or 4+ words = likely company
    if any(c.isdigit() for c in name):
        return True
    return False


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------

class _UnionFind:
    """Simple union-find / disjoint set data structure."""

    def __init__(self):
        self._parent: dict[int, int] = {}
        self._rank: dict[int, int] = {}

    def find(self, x: int) -> int:
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]  # path compression
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1

    def components(self, ids: list[int]) -> dict[int, list[int]]:
        """Return {root: [member_ids]} for all given ids."""
        groups: dict[int, list[int]] = defaultdict(list)
        for i in ids:
            groups[self.find(i)].append(i)
        return dict(groups)


# ---------------------------------------------------------------------------
# Appearance scanning
# ---------------------------------------------------------------------------

def _scan_appearances(parsed_dir: Path) -> list[dict]:
    """Read all parsed JSONs and extract buyer+seller appearances."""
    appearances = []

    for f in sorted(parsed_dir.glob("*.json")):
        if f.stem == "_meta":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        rt_id = data.get("rt_id", f.stem)
        tx = data.get("transaction", {})
        sale_date_iso = tx.get("sale_date_iso", "")
        sale_price = tx.get("sale_price", "")
        addr = tx.get("address", {})
        prop_address = addr.get("address", "")
        prop_city = addr.get("city", "")

        for role, key in [("seller", "transferor"), ("buyer", "transferee")]:
            party = data.get(key, {})
            name = (party.get("name") or "").strip()
            if not name:
                continue

            is_company = _is_company_name(name)
            contact = (party.get("contact") or "").strip()
            phone = (party.get("phone") or "").strip()
            address = (party.get("address") or "").strip()
            aliases = party.get("aliases", [])
            alternate_names = [a for a in party.get("alternate_names", []) if a]
            phones = party.get("phones", [])

            # Collect all phones
            all_phones = list(phones) if phones else []
            if phone and phone not in all_phones:
                all_phones.insert(0, phone)

            # Brand extraction from parenthetical names
            m = _BRAND_PAREN_RE.match(name)
            if m:
                brand = m.group(1).strip().upper()
                existing_upper = {(a.upper() if isinstance(a, str) else a) for a in aliases}
                if brand and len(brand) >= 4 and brand not in existing_upper:
                    aliases = list(aliases) + [brand]

            appearances.append({
                "rt_id": rt_id,
                "role": role,
                "name": name,
                "is_company": is_company,
                "contact": contact,
                "phone": phone,
                "address": address,
                "aliases": aliases,
                "alternate_names": alternate_names,
                "phones": all_phones,
                "sale_date_iso": sale_date_iso,
                "sale_price": sale_price,
                "prop_address": prop_address,
                "prop_city": prop_city,
            })

    return appearances


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def _cluster_appearances(
    appearances: list[dict],
    overrides: dict,
) -> list[list[int]]:
    """Union-find clustering on appearance indices.

    Rules:
    1. Same normalized name (non-numbered companies only)
    2. Same phone number (with dynamic blacklist for high-fan-out phones)
    3. Same filtered alias / alternate name
    4. Same normalized address (companies only, min 10 chars)
    5. Numbered company + same contact
    All transitive via union-find.
    """
    uf = _UnionFind()
    n = len(appearances)

    # --- Rule 1: Name matching (non-numbered companies only) ---
    by_name: dict[str, list[int]] = defaultdict(list)
    for i, app in enumerate(appearances):
        if _is_numbered_company(app["name"]):
            continue
        norm = normalize_name(app["name"])
        by_name[norm].append(i)

    for indices in by_name.values():
        if len(indices) > 1:
            for j in range(1, len(indices)):
                uf.union(indices[0], indices[j])

    # --- Build phone index and detect high-fan-out phones ---
    phone_to_appearances: dict[str, list[int]] = defaultdict(list)
    phone_name_groups: dict[str, set[str]] = defaultdict(set)
    for i, app in enumerate(appearances):
        phones: set[str] = set()
        if app.get("phone"):
            phones.add(normalize_phone(app["phone"]))
        for ph in app.get("phones", []):
            phones.add(normalize_phone(ph))
        for ph in phones:
            if ph and len(ph) >= 7:
                phone_to_appearances[ph].append(i)
                phone_name_groups[ph].add(normalize_name(app["name"]))
    high_fanout_phones = {
        ph for ph, names in phone_name_groups.items() if len(names) >= 15
    }

    # --- Rule 2: Phone matching ---
    # Low fan-out phones: union all appearances unconditionally
    # High fan-out phones: only union appearances that share the same contact
    for ph, indices in phone_to_appearances.items():
        if len(indices) < 2:
            continue
        if ph not in high_fanout_phones:
            for j in range(1, len(indices)):
                uf.union(indices[0], indices[j])
        else:
            # Group by contact, only union within same contact
            by_contact: dict[str, list[int]] = defaultdict(list)
            for i in indices:
                contact = appearances[i].get("contact", "").upper().strip()
                if contact:
                    by_contact[contact].append(i)
            for contact_indices in by_contact.values():
                if len(contact_indices) > 1:
                    for j in range(1, len(contact_indices)):
                        uf.union(contact_indices[0], contact_indices[j])

    # --- Rule 3: Alias matching (filtered) ---
    by_alias: dict[str, list[int]] = defaultdict(list)
    for i, app in enumerate(appearances):
        seen: set[str] = set()
        for alias in list(app.get("aliases", [])) + list(app.get("alternate_names", [])):
            cleaned = _clean_alias(alias, app["name"])
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                by_alias[cleaned].append(i)

    for indices in by_alias.values():
        if len(indices) > 1:
            for j in range(1, len(indices)):
                uf.union(indices[0], indices[j])

    # --- Rule 4: Company address matching ---
    by_addr: dict[str, list[int]] = defaultdict(list)
    for i, app in enumerate(appearances):
        if not app["is_company"]:
            continue
        addr = app["address"]
        if len(addr) < 10:
            continue
        norm_addr = normalize_address(addr)
        by_addr[norm_addr].append(i)

    for indices in by_addr.values():
        if len(indices) > 1:
            for j in range(1, len(indices)):
                uf.union(indices[0], indices[j])

    # --- Rule 5: Numbered company + same contact ---
    numbered_by_name: dict[str, list[int]] = defaultdict(list)
    for i, app in enumerate(appearances):
        if _is_numbered_company(app["name"]):
            numbered_by_name[normalize_name(app["name"])].append(i)

    for norm_name, indices in numbered_by_name.items():
        by_contact: dict[str, list[int]] = defaultdict(list)
        for i in indices:
            contact = appearances[i].get("contact", "").upper().strip()
            if contact:
                by_contact[contact].append(i)
        for contact_indices in by_contact.values():
            if len(contact_indices) > 1:
                for j in range(1, len(contact_indices)):
                    uf.union(contact_indices[0], contact_indices[j])

    # Collect components
    all_indices = list(range(n))
    components = uf.components(all_indices)
    return list(components.values())


# ---------------------------------------------------------------------------
# Display name selection
# ---------------------------------------------------------------------------

def _choose_display_name(apps: list[dict]) -> str:
    """Pick the most frequent name, preferring company names."""
    name_counts: dict[str, int] = defaultdict(int)
    company_names: set[str] = set()
    for app in apps:
        name_counts[app["name"]] += 1
        if app.get("is_company", _is_company_name(app["name"])):
            company_names.add(app["name"])

    # Prefer company names
    if company_names:
        candidates = {n: c for n, c in name_counts.items() if n in company_names}
    else:
        candidates = dict(name_counts)

    return max(candidates, key=lambda n: candidates[n])


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _next_group_id(existing_ids: set[str]) -> str:
    """Generate the next G-prefixed ID (G00001, G00002, ...)."""
    max_num = 0
    for gid in existing_ids:
        if gid.startswith("G") and gid[1:].isdigit():
            max_num = max(max_num, int(gid[1:]))
    return f"G{max_num + 1:05d}"


# ---------------------------------------------------------------------------
# Build registry
# ---------------------------------------------------------------------------

def build_registry(
    parsed_dir: Path,
    existing_registry_path: Path | None = None,
) -> dict:
    """Build or update the party group registry.

    Args:
        parsed_dir: Active parsed JSON directory.
        existing_registry_path: Path to existing parties.json to merge with.

    Returns:
        Registry dict: {"parties": {...}, "overrides": {...}, "meta": {...}}
    """
    # Load existing registry
    existing: dict[str, dict] = {}
    overrides: dict = {"merge": [], "display_name": {}}
    if existing_registry_path and existing_registry_path.exists():
        data = json.loads(existing_registry_path.read_text(encoding="utf-8"))
        existing = data.get("parties", {})
        overrides = data.get("overrides", {"merge": [], "display_name": {}})

    # Build reverse index: normalized name -> existing group ID
    name_to_gid: dict[str, str] = {}
    for gid, group in existing.items():
        for norm_name in group.get("normalized_names", []):
            name_to_gid[norm_name] = gid

    # Scan appearances
    appearances = _scan_appearances(parsed_dir)

    # Cluster
    groups = _cluster_appearances(appearances, overrides)

    # Build party groups
    today = datetime.now().strftime("%Y-%m-%d")
    used_ids = set(existing.keys())
    parties: dict[str, dict] = {}

    for member_indices in groups:
        apps = [appearances[i] for i in member_indices]

        # Collect normalized names for this group
        norm_names = sorted(set(normalize_name(a["name"]) for a in apps))

        # Try to match to existing group by name overlap
        matched_gid = None
        for nn in norm_names:
            if nn in name_to_gid:
                matched_gid = name_to_gid[nn]
                break

        if matched_gid and matched_gid not in parties:
            gid = matched_gid
        else:
            gid = _next_group_id(used_ids)

        used_ids.add(gid)

        # Determine is_company for group
        is_company = any(a["is_company"] for a in apps)

        # Display name
        display_name = _choose_display_name(apps)
        display_name_override = overrides.get("display_name", {}).get(gid, "")

        # Collect unique values
        names = sorted(set(a["name"] for a in apps))
        addresses = sorted(set(
            a["address"] for a in apps if a["address"]
        ))
        contacts = sorted(set(
            a["contact"] for a in apps if a["contact"]
        ))
        all_phones: list[str] = []
        seen_phones: set[str] = set()
        for a in apps:
            for p in a["phones"]:
                if p and p not in seen_phones:
                    all_phones.append(p)
                    seen_phones.add(p)
        aliases = sorted(set(
            alias for a in apps for alias in a.get("aliases", [])
        ))
        alternate_names = sorted(set(
            alt for a in apps for alt in a.get("alternate_names", [])
        ))

        # Add make_alias variants
        for name in names:
            alias = make_alias(name)
            if alias and alias.upper() not in {a.upper() for a in aliases}:
                aliases.append(alias)
        aliases = sorted(set(aliases))

        # Build appearances list
        appearance_list = []
        seen_appearances: set[tuple[str, str]] = set()
        for a in apps:
            key = (a["rt_id"], a["role"])
            if key in seen_appearances:
                continue
            seen_appearances.add(key)
            appearance_list.append({
                "rt_id": a["rt_id"],
                "role": a["role"],
                "name": a["name"],
                "sale_date_iso": a["sale_date_iso"],
                "sale_price": a["sale_price"],
                "prop_address": a["prop_address"],
                "prop_city": a["prop_city"],
            })

        # Sort appearances newest first
        appearance_list.sort(
            key=lambda x: x.get("sale_date_iso", ""),
            reverse=True,
        )

        # Stats
        rt_ids = sorted(set(a["rt_id"] for a in apps))
        buy_count = sum(1 for a in appearance_list if a["role"] == "buyer")
        sell_count = sum(1 for a in appearance_list if a["role"] == "seller")
        dates = [a["sale_date_iso"] for a in apps if a["sale_date_iso"]]

        # Preserve created date from existing
        created = existing.get(gid, {}).get("created", today)

        parties[gid] = {
            "display_name": display_name,
            "display_name_override": display_name_override,
            "is_company": is_company,
            "names": names,
            "normalized_names": norm_names,
            "addresses": addresses,
            "contacts": contacts,
            "phones": all_phones,
            "aliases": aliases,
            "alternate_names": alternate_names,
            "appearances": appearance_list,
            "transaction_count": len(rt_ids),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "first_active_iso": min(dates) if dates else "",
            "last_active_iso": max(dates) if dates else "",
            "rt_ids": rt_ids,
            "created": created,
            "updated": today,
        }

    # Apply split overrides — disconnect names that were manually separated
    for split in overrides.get("splits", []):
        split_norm = split.get("normalized_name", "")
        target_gid = split.get("target", "")
        if not split_norm:
            continue

        # Find which group currently contains this normalized name
        source_gid = None
        for gid, p in parties.items():
            if split_norm in p.get("normalized_names", []):
                source_gid = gid
                break

        if not source_gid:
            continue

        # If the target already contains this name, the algorithm separated it
        if target_gid and target_gid in parties and target_gid == source_gid:
            continue
        # If the name is alone in its group, already separated correctly
        source_p = parties[source_gid]
        # Split matching appearances out
        matching = [a for a in source_p["appearances"] if normalize_name(a["name"]) == split_norm]
        remaining = [a for a in source_p["appearances"] if normalize_name(a["name"]) != split_norm]

        if not matching or not remaining:
            continue  # nothing to split, or would empty the group

        # Update source group
        source_p["appearances"] = remaining
        source_p["names"] = sorted(set(a["name"] for a in remaining))
        source_p["normalized_names"] = sorted(set(normalize_name(a["name"]) for a in remaining))
        source_p["rt_ids"] = sorted(set(a["rt_id"] for a in remaining))
        source_p["transaction_count"] = len(source_p["rt_ids"])
        source_p["buy_count"] = sum(1 for a in remaining if a["role"] == "buyer")
        source_p["sell_count"] = sum(1 for a in remaining if a["role"] == "seller")
        remaining_dates = [a["sale_date_iso"] for a in remaining if a.get("sale_date_iso")]
        source_p["first_active_iso"] = min(remaining_dates) if remaining_dates else ""
        source_p["last_active_iso"] = max(remaining_dates) if remaining_dates else ""

        # Determine target group ID
        if target_gid and target_gid in parties and target_gid != source_gid:
            # Merge into existing target
            tgt = parties[target_gid]
            seen_app = {(a["rt_id"], a["role"]) for a in tgt["appearances"]}
            for a in matching:
                if (a["rt_id"], a["role"]) not in seen_app:
                    tgt["appearances"].append(a)
            tgt["appearances"].sort(key=lambda x: x.get("sale_date_iso", ""), reverse=True)
            tgt["names"] = sorted(set(tgt["names"] + [a["name"] for a in matching]))
            tgt["normalized_names"] = sorted(set(tgt["normalized_names"] + [normalize_name(a["name"]) for a in matching]))
            tgt["rt_ids"] = sorted(set(tgt["rt_ids"] + [a["rt_id"] for a in matching]))
            tgt["transaction_count"] = len(tgt["rt_ids"])
            tgt["buy_count"] = sum(1 for a in tgt["appearances"] if a["role"] == "buyer")
            tgt["sell_count"] = sum(1 for a in tgt["appearances"] if a["role"] == "seller")
            all_dates = [a["sale_date_iso"] for a in tgt["appearances"] if a.get("sale_date_iso")]
            tgt["first_active_iso"] = min(all_dates) if all_dates else ""
            tgt["last_active_iso"] = max(all_dates) if all_dates else ""
        else:
            # Create new group with target_gid or auto-generate
            new_gid = target_gid if target_gid and target_gid not in parties else _next_group_id(used_ids)
            used_ids.add(new_gid)
            m_names = sorted(set(a["name"] for a in matching))
            m_norm = sorted(set(normalize_name(a["name"]) for a in matching))
            m_aliases = sorted(set(alias for a in matching for alias in a.get("aliases", [])))
            for n in m_names:
                alias = make_alias(n)
                if alias and alias.upper() not in {a.upper() for a in m_aliases}:
                    m_aliases.append(alias)
            m_aliases = sorted(set(m_aliases))
            m_dates = [a["sale_date_iso"] for a in matching if a.get("sale_date_iso")]

            parties[new_gid] = {
                "display_name": _choose_display_name(matching),
                "display_name_override": overrides.get("display_name", {}).get(new_gid, ""),
                "is_company": any(_is_company_name(n) for n in m_names),
                "names": m_names,
                "normalized_names": m_norm,
                "addresses": sorted(set(a.get("address", "") for a in matching if (a.get("address") or "").strip())),
                "contacts": sorted(set(a.get("contact", "") for a in matching if (a.get("contact") or "").strip())),
                "phones": list(dict.fromkeys(p for a in matching for p in a.get("phones", []) if p)),
                "aliases": m_aliases,
                "alternate_names": sorted(set(
                    alt for a in matching for alt in a.get("alternate_names", [])
                )),
                "appearances": sorted(matching, key=lambda x: x.get("sale_date_iso", ""), reverse=True),
                "transaction_count": len(set(a["rt_id"] for a in matching)),
                "buy_count": sum(1 for a in matching if a["role"] == "buyer"),
                "sell_count": sum(1 for a in matching if a["role"] == "seller"),
                "first_active_iso": min(m_dates) if m_dates else "",
                "last_active_iso": max(m_dates) if m_dates else "",
                "rt_ids": sorted(set(a["rt_id"] for a in matching)),
                "created": existing.get(new_gid, {}).get("created", today),
                "updated": today,
            }

    # Apply merge overrides — merge groups by their IDs
    for merge_entry in overrides.get("merge", []):
        if not isinstance(merge_entry, list) or len(merge_entry) < 2:
            continue
        target_gid = merge_entry[0]
        if target_gid not in parties:
            continue
        for source_gid in merge_entry[1:]:
            if source_gid not in parties or source_gid == target_gid:
                continue
            src = parties.pop(source_gid)
            tgt = parties[target_gid]
            # Merge all fields
            tgt["names"] = sorted(set(tgt["names"] + src["names"]))
            tgt["normalized_names"] = sorted(set(tgt["normalized_names"] + src["normalized_names"]))
            tgt["addresses"] = sorted(set(tgt["addresses"] + src["addresses"]))
            tgt["contacts"] = sorted(set(tgt["contacts"] + src["contacts"]))
            seen_p = set(tgt["phones"])
            for p in src["phones"]:
                if p not in seen_p:
                    tgt["phones"].append(p)
                    seen_p.add(p)
            tgt["aliases"] = sorted(set(tgt["aliases"] + src["aliases"]))
            tgt["alternate_names"] = sorted(set(tgt.get("alternate_names", []) + src.get("alternate_names", [])))
            seen_app = {(a["rt_id"], a["role"]) for a in tgt["appearances"]}
            for a in src["appearances"]:
                if (a["rt_id"], a["role"]) not in seen_app:
                    tgt["appearances"].append(a)
            tgt["appearances"].sort(key=lambda x: x.get("sale_date_iso", ""), reverse=True)
            tgt["rt_ids"] = sorted(set(tgt["rt_ids"] + src["rt_ids"]))
            tgt["transaction_count"] = len(tgt["rt_ids"])
            tgt["buy_count"] = sum(1 for a in tgt["appearances"] if a["role"] == "buyer")
            tgt["sell_count"] = sum(1 for a in tgt["appearances"] if a["role"] == "seller")
            all_dates = [a["sale_date_iso"] for a in tgt["appearances"] if a.get("sale_date_iso")]
            tgt["first_active_iso"] = min(all_dates) if all_dates else ""
            tgt["last_active_iso"] = max(all_dates) if all_dates else ""
            tgt["is_company"] = tgt["is_company"] or src["is_company"]

    # Sort by group ID
    parties = dict(sorted(parties.items()))

    # Meta
    total_groups = len(parties)
    company_groups = sum(1 for p in parties.values() if p["is_company"])
    person_groups = total_groups - company_groups

    meta = {
        "built": datetime.now().isoformat(timespec="seconds"),
        "source_dir": parsed_dir.name,
        "total_groups": total_groups,
        "total_company_groups": company_groups,
        "total_person_groups": person_groups,
        "total_appearances": sum(len(p["appearances"]) for p in parties.values()),
    }

    return {"parties": parties, "overrides": overrides, "meta": meta}


def save_registry(registry: dict, path: Path) -> None:
    """Atomically save the party registry to disk."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def load_registry(path: Path) -> dict:
    """Load the party registry from disk."""
    if not path.exists():
        return {"parties": {}, "overrides": {}, "meta": {}}
    return json.loads(path.read_text(encoding="utf-8"))
