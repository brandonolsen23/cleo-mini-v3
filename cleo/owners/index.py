"""Entity index: every unique buyer/seller name from all transactions.

Scans ALL transactions on ALL properties — not just the current owner.
Every unique normalized buyer or seller name becomes an entity entry.

No persistent file — computed on-the-fly from properties.json + owner_links.json.
Cached in memory, invalidated when source files change.
"""

import hashlib
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from cleo.config import PROPERTIES_PATH, OWNER_LINKS_PATH

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Name normalization (conservative — uppercase, collapse whitespace, strip
# trailing punctuation, strip legal suffixes for grouping)
# ---------------------------------------------------------------------------

_SUFFIX_RE = re.compile(
    r"\s*\b(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|LLC|LLP|LP|ULC)\b\.?\s*$",
    re.IGNORECASE,
)


def normalize_owner_name(name: str) -> str:
    """Normalize a buyer/seller name for entity grouping.

    Uppercase, collapse whitespace, strip trailing punctuation,
    strip legal suffixes (Inc/Ltd/Corp) so that "ABC Holdings Inc"
    and "ABC Holdings Ltd" group together.
    """
    s = name.upper().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:")
    # Strip legal suffixes (up to 2 passes for stacked)
    for _ in range(2):
        prev = s
        s = _SUFFIX_RE.sub("", s).rstrip(".,;: ")
        if s == prev:
            break
    return s


def owner_id_from_name(normalized_name: str) -> str:
    """Deterministic hash-based ID from a normalized owner name."""
    return hashlib.md5(normalized_name.encode("utf-8")).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Entity index
# ---------------------------------------------------------------------------

class OwnerIndex:
    """In-memory entity index built from properties.json + owner_links.json.

    Scans ALL transactions on ALL properties. Every unique buyer and seller
    name becomes an entity entry. Manual link groups merge multiple names.
    """

    def __init__(self):
        self._owners: Dict[str, Dict] = {}       # owner_id -> entity record
        self._name_to_id: Dict[str, str] = {}    # normalized_name -> owner_id
        self._links: Dict = {}                    # raw owner_links data
        self._props_mtime: float = 0
        self._links_mtime: float = 0
        self._built = False

    def _needs_rebuild(self) -> bool:
        if not self._built:
            return True
        if PROPERTIES_PATH.exists():
            mt = PROPERTIES_PATH.stat().st_mtime
            if mt != self._props_mtime:
                return True
        if OWNER_LINKS_PATH.exists():
            mt = OWNER_LINKS_PATH.stat().st_mtime
            if mt != self._links_mtime:
                return True
        elif self._links_mtime != 0:
            return True
        return False

    def _build(self):
        start = time.time()
        logger.info("Building owner index...")

        if not PROPERTIES_PATH.exists():
            logger.warning("No properties.json — owner index empty")
            self._owners = {}
            self._name_to_id = {}
            self._built = True
            return

        props_data = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
        self._props_mtime = PROPERTIES_PATH.stat().st_mtime
        properties = props_data.get("properties", {})

        # Load manual links
        self._links = {}
        name_to_link: Dict[str, str] = {}
        if OWNER_LINKS_PATH.exists():
            self._links = json.loads(OWNER_LINKS_PATH.read_text(encoding="utf-8"))
            self._links_mtime = OWNER_LINKS_PATH.stat().st_mtime
            name_to_link = self._links.get("name_to_link", {})
        else:
            self._links_mtime = 0

        link_groups: Dict[str, Dict] = {}
        for lg in self._links.get("links", []):
            link_groups[lg["id"]] = lg

        # Phase 1: Scan ALL transactions on ALL properties
        raw_entities: Dict[str, Dict] = {}

        def ensure(norm: str) -> Dict:
            if norm not in raw_entities:
                raw_entities[norm] = {
                    "raw_names": set(),
                    "buy_txns": [],         # all buy appearances
                    "sell_txns": [],        # all sell appearances
                    "owned_pids": set(),    # property IDs currently owned
                    "contacts": {},         # uppercase_name -> {name, phone, source_ids}
                    "corp_addresses": {},   # canonical -> address dict
                    "phones": set(),
                    "cities": set(),
                    "aliases": {},          # alias_value -> set(rt_ids)
                    "company_lines": {},    # cl_value -> set(rt_ids)
                    "total_buy_value": 0,
                    "total_sell_value": 0,
                    "latest_date": "",
                    "earliest_date": "",
                    "seen_buy_rtids": set(),   # for dedup
                    "seen_sell_rtids": set(),   # for dedup
                }
            return raw_entities[norm]

        for pid, prop in properties.items():
            prop_addr = prop.get("primary_address", "")
            prop_city = prop.get("city", "").strip()

            for txn in prop.get("transactions", []):
                rt_id = txn.get("rt_id", "")
                sale_date = txn.get("sale_date", "")
                sale_price = txn.get("sale_price") or 0

                # Shared base fields for transaction summary
                txn_base = {
                    "property_id": pid,
                    "address": prop_addr,
                    "city": prop_city,
                    "sale_price": txn.get("sale_price"),
                    "sale_date": sale_date,
                    "rt_id": rt_id,
                }

                # --- BUYER side ---
                b_name = txn.get("buyer_name", "").strip()
                if b_name:
                    b_norm = normalize_owner_name(b_name)
                    if b_norm:
                        e = ensure(b_norm)
                        e["raw_names"].add(b_name)
                        # Dedup by rt_id (multi-parcel txns appear on multiple properties)
                        if rt_id not in e["seen_buy_rtids"]:
                            b_cl = txn.get("buyer_company_lines", [])
                            e["buy_txns"].append({
                                **txn_base,
                                "entity_name": b_name,
                                "alternate_names": [c for c in b_cl if c != b_name],
                                "contact": txn.get("buyer_contact", ""),
                                "phone": txn.get("buyer_phone", ""),
                                "phones": txn.get("buyer_phones", []),
                                "corp_address": txn.get("buyer_address"),
                                "attention": txn.get("buyer_attention", ""),
                            })
                            e["total_buy_value"] += sale_price
                            e["seen_buy_rtids"].add(rt_id)
                        if prop_city:
                            e["cities"].add(prop_city)
                        _update_dates(e, sale_date)
                        _collect_party_data(e, txn, "buyer", rt_id)

                # --- SELLER side ---
                s_name = txn.get("seller_name", "").strip()
                if s_name:
                    s_norm = normalize_owner_name(s_name)
                    if s_norm:
                        e = ensure(s_norm)
                        e["raw_names"].add(s_name)
                        if rt_id not in e["seen_sell_rtids"]:
                            s_cl = txn.get("seller_company_lines", [])
                            e["sell_txns"].append({
                                **txn_base,
                                "entity_name": s_name,
                                "alternate_names": [c for c in s_cl if c != s_name],
                                "contact": txn.get("seller_contact", ""),
                                "phone": txn.get("seller_phone", ""),
                                "phones": txn.get("seller_phones", []),
                                "corp_address": txn.get("seller_address"),
                                "attention": txn.get("seller_attention", ""),
                            })
                            e["total_sell_value"] += sale_price
                            e["seen_sell_rtids"].add(rt_id)
                        if prop_city:
                            e["cities"].add(prop_city)
                        _update_dates(e, sale_date)
                        _collect_party_data(e, txn, "seller", rt_id)

        # Phase 2: Mark owned properties (current_owner on each property)
        for pid, prop in properties.items():
            owner = prop.get("current_owner")
            if not owner or not owner.get("name"):
                continue
            norm = normalize_owner_name(owner["name"])
            if norm and norm in raw_entities:
                raw_entities[norm]["owned_pids"].add(pid)

        # Phase 3: Merge link groups
        merged: Dict[str, List[str]] = {}  # link_id -> [normalized names]
        for norm_name, link_id in name_to_link.items():
            if link_id not in merged:
                merged[link_id] = []
            if norm_name in raw_entities:
                merged[link_id].append(norm_name)

        # Build final records
        owners: Dict[str, Dict] = {}
        name_to_id: Dict[str, str] = {}
        processed: Set[str] = set()

        # Linked groups first
        for link_id, member_names in merged.items():
            if not member_names:
                continue
            lg = link_groups.get(link_id, {})
            combined = _merge_entities([raw_entities[n] for n in member_names])
            for m in lg.get("members", []):
                combined["raw_names"].add(m)

            owner = _build_entity_record(link_id, combined, lg.get("display_name"), link_id, properties)
            owners[link_id] = owner
            for n in member_names:
                name_to_id[n] = link_id
                processed.add(n)
            for m in lg.get("members", []):
                name_to_id[m] = link_id

        # Unlinked entities (check for custom display names)
        custom_names = self._links.get("display_names", {})
        for norm, entity in raw_entities.items():
            if norm in processed:
                continue
            oid = owner_id_from_name(norm)
            display = custom_names.get(norm)
            owner = _build_entity_record(oid, entity, display, None, properties)
            owners[oid] = owner
            name_to_id[norm] = oid

        self._owners = owners
        self._name_to_id = name_to_id
        self._built = True

        elapsed = time.time() - start
        logger.info("Owner index: %d owners in %.1fs", len(owners), elapsed)

    def ensure_built(self):
        if self._needs_rebuild():
            self._build()

    # --- Public API ---

    def browse(
        self,
        name: str = "",
        contact: str = "",
        phone: str = "",
        address: str = "",
        city: str = "",
        min_properties: int = 0,
        sort: str = "property_count",
        order: str = "desc",
        page: int = 1,
        per_page: int = 25,
    ) -> Dict:
        """Browse entities with layered filtering, sorting, and pagination."""
        self.ensure_built()

        name_q = name.upper().strip() if name else ""
        contact_q = contact.upper().strip() if contact else ""
        phone_q = re.sub(r"\D", "", phone) if phone else ""
        address_q = address.upper().strip() if address else ""
        city_q = city.upper().strip() if city else ""

        filtered: List[Dict] = []
        for owner in self._owners.values():
            if min_properties and owner["property_count"] < min_properties:
                continue

            # Name search: matches entity names, aliases, and company lines
            if name_q:
                matched = False
                if any(name_q in n.upper() for n in owner["all_names"]):
                    matched = True
                if not matched:
                    for a in owner["aliases"]:
                        if name_q in a["value"].upper():
                            matched = True
                            break
                if not matched:
                    for cl in owner["company_lines"]:
                        if name_q in cl["value"].upper():
                            matched = True
                            break
                if not matched:
                    continue

            if contact_q:
                if not any(contact_q in c["name"].upper() for c in owner["contacts"]):
                    continue

            if phone_q:
                if not any(phone_q in p for p in owner["phones"]):
                    continue

            if address_q:
                if not any(address_q in a.get("canonical", "").upper()
                           for a in owner["corp_addresses"]):
                    continue

            if city_q:
                if not any(city_q in c.upper() for c in owner["cities"]):
                    continue

            filtered.append(owner)

        # Sort
        def _sort_key(o: Dict):
            if sort == "total_value":
                return o.get("total_value", 0)
            if sort == "latest_date":
                return o.get("latest_date", "")
            if sort == "name":
                return o.get("display_name") or o.get("name", "")
            if sort == "buy_count":
                return o.get("buy_count", 0)
            if sort == "sell_count":
                return o.get("sell_count", 0)
            return o.get("property_count", 0)

        reverse = order == "desc"
        filtered.sort(key=_sort_key, reverse=reverse)

        total = len(filtered)
        start_idx = (page - 1) * per_page
        page_items = filtered[start_idx:start_idx + per_page]

        results = []
        for o in page_items:
            # Collect unique alternate name groups from transactions
            seen_groups: Set[tuple] = set()
            alt_name_groups: List[List[str]] = []
            for txn_key in ("buy_transactions", "seller_transactions"):
                for t in o.get(txn_key, []):
                    alts = tuple(t.get("alternate_names", []))
                    if alts and alts not in seen_groups:
                        seen_groups.add(alts)
                        alt_name_groups.append(list(alts))

            results.append({
                "id": o["id"],
                "name": o["name"],
                "display_name": o.get("display_name"),
                "link_id": o.get("link_id"),
                "property_count": o["property_count"],
                "buy_count": o["buy_count"],
                "sell_count": o["sell_count"],
                "cities": o["cities"][:5],
                "total_value": o["total_value"],
                "total_sell_value": o["total_sell_value"],
                "owned_value": o["owned_value"],
                "latest_date": o["latest_date"],
                "contacts": [c["name"] for c in o["contacts"][:3]],
                "corp_address_cities": list({
                    a.get("city", "") for a in o["corp_addresses"] if a.get("city")
                })[:3],
                "phones": o["phones"][:3],
                "all_names": o["all_names"][:5],
                "alt_name_groups": alt_name_groups,
            })

        return {
            "results": results,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def detail(self, owner_id: str) -> Optional[Dict]:
        """Full entity detail by ID (hash or LNK_NNNNN)."""
        self.ensure_built()
        return self._owners.get(owner_id)

    def resolve(self, normalized_name: str) -> Optional[str]:
        """Resolve a normalized name to its entity ID."""
        self.ensure_built()
        return self._name_to_id.get(normalized_name)

    def filters(self) -> Dict:
        """Return available filter values."""
        self.ensure_built()
        cities: Set[str] = set()
        max_props = 0
        for o in self._owners.values():
            for c in o["cities"]:
                cities.add(c)
            if o["property_count"] > max_props:
                max_props = o["property_count"]
        return {
            "cities": sorted(cities),
            "max_property_count": max_props,
            "total_owners": len(self._owners),
        }

    def search(self, q: str, limit: int = 20) -> List[Dict]:
        """Quick search across all fields including aliases and company lines."""
        self.ensure_built()
        q_upper = q.upper().strip()
        if not q_upper:
            return []

        q_digits = re.sub(r"\D", "", q)
        results: List[Tuple[int, Dict]] = []

        for owner in self._owners.values():
            score = 0

            # Name match (highest priority)
            for n in owner["all_names"]:
                if q_upper in n.upper():
                    score += 10
                    if n.upper().startswith(q_upper):
                        score += 5
                    break

            # Alias match
            for a in owner["aliases"]:
                if q_upper in a["value"].upper():
                    score += 8
                    break

            # Company line match
            for cl in owner["company_lines"]:
                if q_upper in cl["value"].upper():
                    score += 8
                    break

            # Contact match
            for c in owner["contacts"]:
                if q_upper in c["name"].upper():
                    score += 5
                    break

            # Phone match
            if q_digits and len(q_digits) >= 3:
                for p in owner["phones"]:
                    if q_digits in p:
                        score += 5
                        break

            # Address match
            for a in owner["corp_addresses"]:
                if q_upper in a.get("canonical", "").upper():
                    score += 3
                    break

            if score > 0:
                results.append((score, {
                    "id": owner["id"],
                    "name": owner.get("display_name") or owner["name"],
                    "property_count": owner["property_count"],
                    "score": score,
                }))

        results.sort(key=lambda x: (-x[0], x[1]["name"]))
        return [r[1] for r in results[:limit]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_dates(entity: Dict, sale_date: str):
    """Update earliest/latest date on entity."""
    if not sale_date:
        return
    if not entity["latest_date"] or sale_date > entity["latest_date"]:
        entity["latest_date"] = sale_date
    if not entity["earliest_date"] or sale_date < entity["earliest_date"]:
        entity["earliest_date"] = sale_date


def _collect_party_data(entity: Dict, txn: Dict, role: str, rt_id: str):
    """Collect contact, address, aliases, company_lines from a transaction for one role."""
    contact = txn.get(f"{role}_contact", "").strip()
    phone = txn.get(f"{role}_phone", "").strip()

    if contact:
        ckey = contact.upper()
        if ckey not in entity["contacts"]:
            entity["contacts"][ckey] = {"name": contact, "phone": phone, "source_ids": []}
        if rt_id not in entity["contacts"][ckey]["source_ids"]:
            entity["contacts"][ckey]["source_ids"].append(rt_id)

    if phone:
        entity["phones"].add(re.sub(r"\D", "", phone))
    for p in txn.get(f"{role}_phones", []):
        if p:
            entity["phones"].add(re.sub(r"\D", "", p))

    # Address with provenance
    addr = txn.get(f"{role}_address")
    ent_name = txn.get(f"{role}_name", "").strip()
    if addr and addr.get("canonical"):
        akey = addr["canonical"]
        if akey not in entity["corp_addresses"]:
            entity["corp_addresses"][akey] = {**addr, "rt_ids": set(), "entity_names": set()}
        entity["corp_addresses"][akey]["rt_ids"].add(rt_id)
        if ent_name:
            entity["corp_addresses"][akey]["entity_names"].add(ent_name)

    # Aliases with provenance
    for a in txn.get(f"{role}_aliases", []):
        if a:
            if a not in entity["aliases"]:
                entity["aliases"][a] = set()
            entity["aliases"][a].add(rt_id)

    # Company lines with provenance
    for cl in txn.get(f"{role}_company_lines", []):
        if cl:
            if cl not in entity["company_lines"]:
                entity["company_lines"][cl] = set()
            entity["company_lines"][cl].add(rt_id)


def _merge_entities(entities: List[Dict]) -> Dict:
    """Merge multiple raw entity groups into one (for link groups)."""
    combined: Dict[str, Any] = {
        "raw_names": set(),
        "buy_txns": [],
        "sell_txns": [],
        "owned_pids": set(),
        "contacts": {},
        "corp_addresses": {},
        "phones": set(),
        "cities": set(),
        "aliases": {},
        "company_lines": {},
        "total_buy_value": 0,
        "total_sell_value": 0,
        "latest_date": "",
        "earliest_date": "",
        "seen_buy_rtids": set(),
        "seen_sell_rtids": set(),
    }
    # Track added rt_ids separately for proper dedup during merge
    added_buy_rtids: Set[str] = set()
    added_sell_rtids: Set[str] = set()

    for e in entities:
        combined["raw_names"].update(e["raw_names"])
        combined["owned_pids"].update(e["owned_pids"])
        combined["phones"].update(e["phones"])
        combined["cities"].update(e["cities"])
        combined["total_buy_value"] += e["total_buy_value"]
        combined["total_sell_value"] += e["total_sell_value"]

        # Dedup txns by rt_id when merging
        for bt in e["buy_txns"]:
            if bt["rt_id"] not in added_buy_rtids:
                combined["buy_txns"].append(bt)
                added_buy_rtids.add(bt["rt_id"])
        for st in e["sell_txns"]:
            if st["rt_id"] not in added_sell_rtids:
                combined["sell_txns"].append(st)
                added_sell_rtids.add(st["rt_id"])

        for ckey, cval in e["contacts"].items():
            if ckey not in combined["contacts"]:
                combined["contacts"][ckey] = {
                    "name": cval["name"],
                    "phone": cval["phone"],
                    "source_ids": list(cval["source_ids"]),
                }
            else:
                for sid in cval["source_ids"]:
                    if sid not in combined["contacts"][ckey]["source_ids"]:
                        combined["contacts"][ckey]["source_ids"].append(sid)

        for akey, aval in e["corp_addresses"].items():
            if akey not in combined["corp_addresses"]:
                combined["corp_addresses"][akey] = {**aval, "rt_ids": set(aval.get("rt_ids", set())), "entity_names": set(aval.get("entity_names", set()))}
            else:
                combined["corp_addresses"][akey]["rt_ids"].update(aval.get("rt_ids", set()))
                combined["corp_addresses"][akey]["entity_names"].update(aval.get("entity_names", set()))

        for alias, rt_ids in e["aliases"].items():
            if alias not in combined["aliases"]:
                combined["aliases"][alias] = set()
            combined["aliases"][alias].update(rt_ids)

        for cl, rt_ids in e["company_lines"].items():
            if cl not in combined["company_lines"]:
                combined["company_lines"][cl] = set()
            combined["company_lines"][cl].update(rt_ids)

        if e["latest_date"]:
            if not combined["latest_date"] or e["latest_date"] > combined["latest_date"]:
                combined["latest_date"] = e["latest_date"]
        if e["earliest_date"]:
            if not combined["earliest_date"] or e["earliest_date"] < combined["earliest_date"]:
                combined["earliest_date"] = e["earliest_date"]

    combined["seen_buy_rtids"] = added_buy_rtids
    combined["seen_sell_rtids"] = added_sell_rtids

    return combined


def _build_entity_record(
    owner_id: str,
    entity: Dict,
    display_name: Optional[str],
    link_id: Optional[str],
    properties: Dict,
) -> Dict:
    """Build a final entity record from a raw entity group."""
    raw_names = sorted(entity["raw_names"])

    # Pick the best display name (prefer properly cased, longest)
    best_name = raw_names[0] if raw_names else ""
    if len(raw_names) > 1:
        for n in raw_names:
            if n != n.upper() and len(n) >= len(best_name):
                best_name = n

    contacts = sorted(entity["contacts"].values(), key=lambda c: -len(c["source_ids"]))
    corp_addresses = []
    for aval in entity["corp_addresses"].values():
        corp_addresses.append({
            "canonical": aval.get("canonical", ""),
            "city": aval.get("city"),
            "lat": aval.get("lat"),
            "lng": aval.get("lng"),
            "rt_ids": sorted(aval.get("rt_ids", set())),
            "entity_names": sorted(aval.get("entity_names", set())),
        })

    # Owned properties (current_owner)
    owned_props = []
    for pid in sorted(entity["owned_pids"]):
        prop = properties.get(pid)
        if not prop:
            continue
        latest = prop.get("latest_transaction") or {}
        owned_props.append({
            "property_id": pid,
            "address": prop.get("primary_address", ""),
            "city": prop.get("city", ""),
            "sale_price": latest.get("sale_price"),
            "sale_date": latest.get("sale_date", ""),
            "rt_id": latest.get("rt_id", ""),
        })
    owned_props.sort(key=lambda p: p.get("sale_date") or "", reverse=True)

    # Buy transactions (all, sorted by date desc, with is_owned flag)
    buy_txns = entity["buy_txns"]
    owned_pids = entity["owned_pids"]
    for bt in buy_txns:
        bt["is_owned"] = bt["property_id"] in owned_pids
    buy_txns.sort(key=lambda t: t.get("sale_date") or "", reverse=True)

    # Sell transactions (all, sorted by date desc)
    sell_txns = entity["sell_txns"]
    sell_txns.sort(key=lambda t: t.get("sale_date") or "", reverse=True)

    # Aliases with provenance (list of {value, rt_ids})
    aliases_with_prov = []
    for alias_val, rt_ids in sorted(entity["aliases"].items()):
        aliases_with_prov.append({
            "value": alias_val,
            "rt_ids": sorted(rt_ids),
        })

    # Company lines with provenance
    company_lines_with_prov = []
    for cl_val, rt_ids in sorted(entity["company_lines"].items()):
        company_lines_with_prov.append({
            "value": cl_val,
            "rt_ids": sorted(rt_ids),
        })

    return {
        "id": owner_id,
        "name": best_name,
        "display_name": display_name,
        "link_id": link_id,
        "normalized_names": sorted(set(normalize_owner_name(n) for n in raw_names)),
        "all_names": raw_names,
        "aliases": aliases_with_prov,
        "company_lines": company_lines_with_prov,
        "contacts": contacts,
        "corp_addresses": corp_addresses,
        "phones": sorted(entity["phones"]),
        "properties": owned_props,
        "property_count": len(owned_props),
        "owned_value": sum(p.get("sale_price") or 0 for p in owned_props),
        "buy_transactions": buy_txns,
        "buy_count": len(buy_txns),
        "seller_transactions": sell_txns,
        "sell_count": len(sell_txns),
        "cities": sorted(entity["cities"]),
        "total_value": entity["total_buy_value"],
        "total_sell_value": entity["total_sell_value"],
        "latest_date": entity["latest_date"],
        "earliest_date": entity["earliest_date"],
    }
