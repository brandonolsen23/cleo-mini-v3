"""Group index: query layer over the group registry + properties data.

Computed on-the-fly from group_registry.json + properties.json.
Cached in memory, invalidated when source files change.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from cleo.groups.registry import normalize_group_name

logger = logging.getLogger(__name__)


class GroupIndex:
    """In-memory query index built from group_registry.json + properties.json
    + group_property_links.json.

    Scans ALL transactions on ALL properties. Maps every buyer/seller name
    to its GRP_ ID via the registry, then aggregates transaction data per group.
    Also includes manually linked properties and groups with no transaction data.
    """

    def __init__(self, registry_path, properties_path, property_links_path=None):
        self._registry_path = registry_path
        self._properties_path = properties_path
        self._property_links_path = property_links_path
        self._groups: Dict[str, Dict] = {}
        self._reg_mtime: float = 0
        self._props_mtime: float = 0
        self._links_mtime: float = 0
        self._built = False

    def _needs_rebuild(self) -> bool:
        if not self._built:
            return True
        if self._registry_path.exists():
            if self._registry_path.stat().st_mtime != self._reg_mtime:
                return True
        if self._properties_path.exists():
            if self._properties_path.stat().st_mtime != self._props_mtime:
                return True
        if self._property_links_path and self._property_links_path.exists():
            if self._property_links_path.stat().st_mtime != self._links_mtime:
                return True
        return False

    def _build(self):
        start = time.time()
        logger.info("Building group index...")

        if not self._registry_path.exists() or not self._properties_path.exists():
            logger.warning("Missing registry or properties — group index empty")
            self._groups = {}
            self._built = True
            return

        registry = json.loads(self._registry_path.read_text(encoding="utf-8"))
        self._reg_mtime = self._registry_path.stat().st_mtime
        name_index = registry.get("name_index", {})
        reg_groups = registry.get("groups", {})

        props_data = json.loads(self._properties_path.read_text(encoding="utf-8"))
        self._props_mtime = self._properties_path.stat().st_mtime
        properties = props_data.get("properties", {})

        # Accumulate data per GRP_ ID
        accum: Dict[str, Dict] = {}

        def ensure(gid: str) -> Dict:
            if gid not in accum:
                rg = reg_groups.get(gid, {})
                accum[gid] = {
                    "id": gid,
                    "display_name": rg.get("display_name"),
                    "known_names": list(rg.get("known_names", [])),
                    "raw_names": set(),
                    "buy_txns": [],
                    "sell_txns": [],
                    "owned_pids": set(),
                    "contacts": {},
                    "corp_addresses": {},
                    "phones": set(),
                    "cities": set(),
                    "total_buy_value": 0,
                    "total_sell_value": 0,
                    "latest_date": "",
                    "earliest_date": "",
                    "seen_buy_rtids": set(),
                    "seen_sell_rtids": set(),
                }
            return accum[gid]

        # Scan all transactions
        for pid, prop in properties.items():
            prop_addr = prop.get("primary_address", "")
            prop_city = prop.get("city", "").strip()

            for txn in prop.get("transactions", []):
                rt_id = txn.get("rt_id", "")
                sale_date = txn.get("sale_date", "")
                sale_price = txn.get("sale_price") or 0

                txn_base = {
                    "property_id": pid,
                    "address": prop_addr,
                    "city": prop_city,
                    "sale_price": txn.get("sale_price"),
                    "sale_date": sale_date,
                    "rt_id": rt_id,
                }

                for role, name_field in [("buyer", "buyer_name"), ("seller", "seller_name")]:
                    raw = txn.get(name_field, "").strip()
                    if not raw:
                        continue
                    norm = normalize_group_name(raw)
                    if not norm:
                        continue
                    gid = name_index.get(norm)
                    if not gid:
                        continue

                    g = ensure(gid)
                    g["raw_names"].add(raw)
                    if prop_city:
                        g["cities"].add(prop_city)
                    _update_dates(g, sale_date)

                    if role == "buyer":
                        if rt_id not in g["seen_buy_rtids"]:
                            g["buy_txns"].append({
                                **txn_base,
                                "contact": txn.get("buyer_contact", ""),
                                "phone": txn.get("buyer_phone", ""),
                                "phones": txn.get("buyer_phones", []),
                                "corp_address": txn.get("buyer_address"),
                            })
                            g["total_buy_value"] += sale_price
                            g["seen_buy_rtids"].add(rt_id)
                        _collect_party_data(g, txn, "buyer", rt_id)
                    else:
                        if rt_id not in g["seen_sell_rtids"]:
                            g["sell_txns"].append({
                                **txn_base,
                                "contact": txn.get("seller_contact", ""),
                                "phone": txn.get("seller_phone", ""),
                                "phones": txn.get("seller_phones", []),
                                "corp_address": txn.get("seller_address"),
                            })
                            g["total_sell_value"] += sale_price
                            g["seen_sell_rtids"].add(rt_id)
                        _collect_party_data(g, txn, "seller", rt_id)

        # Mark owned properties (from transactions)
        for pid, prop in properties.items():
            owner = prop.get("current_owner")
            if not owner or not owner.get("name"):
                continue
            norm = normalize_group_name(owner["name"])
            gid = name_index.get(norm)
            if gid and gid in accum:
                accum[gid]["owned_pids"].add(pid)

        # Include ALL registry groups — even those with no transaction data
        for gid, rg in reg_groups.items():
            if gid not in accum:
                accum[gid] = {
                    "id": gid,
                    "display_name": rg.get("display_name"),
                    "known_names": list(rg.get("known_names", [])),
                    "raw_names": set(),
                    "buy_txns": [],
                    "sell_txns": [],
                    "owned_pids": set(),
                    "contacts": {},
                    "corp_addresses": {},
                    "phones": set(),
                    "cities": set(),
                    "total_buy_value": 0,
                    "total_sell_value": 0,
                    "latest_date": "",
                    "earliest_date": "",
                    "seen_buy_rtids": set(),
                    "seen_sell_rtids": set(),
                }

        # Apply manual property links
        arn_to_pid: Dict[str, str] = {}
        for pid, prop in properties.items():
            prop_arn = prop.get("arn", "")
            if prop_arn:
                arn_to_pid[prop_arn] = pid

        if self._property_links_path and self._property_links_path.exists():
            links = json.loads(self._property_links_path.read_text(encoding="utf-8"))
            self._links_mtime = self._property_links_path.stat().st_mtime
            for link in links:
                gid = link.get("group_id")
                arn = link.get("arn", "")
                if not gid or gid not in accum:
                    continue
                # Resolve ARN to property_id
                pid = link.get("property_id") or arn_to_pid.get(arn, "")
                if pid:
                    accum[gid]["owned_pids"].add(pid)
                    # Add city from property
                    prop = properties.get(pid)
                    if prop and prop.get("city"):
                        accum[gid]["cities"].add(prop["city"])

        # Build final records
        final: Dict[str, Dict] = {}
        for gid, g in accum.items():
            final[gid] = _build_group_record(gid, g, properties)

        self._groups = final
        self._built = True
        elapsed = time.time() - start
        logger.info("Group index: %d groups in %.1fs", len(final), elapsed)

    def invalidate(self):
        """Force rebuild on next access."""
        self._built = False

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
        """Browse groups with layered filtering, sorting, and pagination."""
        self.ensure_built()

        name_q = name.upper().strip() if name else ""
        contact_q = contact.upper().strip() if contact else ""
        phone_q = re.sub(r"\D", "", phone) if phone else ""
        address_q = address.upper().strip() if address else ""
        city_q = city.upper().strip() if city else ""

        filtered: List[Dict] = []
        for g in self._groups.values():
            if min_properties and g["property_count"] < min_properties:
                continue
            if name_q and not any(name_q in n.upper() for n in g["all_names"]):
                continue
            if contact_q and not any(contact_q in c["name"].upper() for c in g["contacts"]):
                continue
            if phone_q and not any(phone_q in p for p in g["phones"]):
                continue
            if address_q and not any(address_q in a.get("canonical", "").upper()
                                     for a in g["corp_addresses"]):
                continue
            if city_q and not any(city_q in c.upper() for c in g["cities"]):
                continue
            filtered.append(g)

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
        for g in page_items:
            results.append({
                "id": g["id"],
                "name": g["name"],
                "display_name": g.get("display_name"),
                "property_count": g["property_count"],
                "buy_count": g["buy_count"],
                "sell_count": g["sell_count"],
                "cities": g["cities"][:5],
                "total_value": g["total_value"],
                "total_sell_value": g["total_sell_value"],
                "owned_value": g["owned_value"],
                "latest_date": g["latest_date"],
                "contacts": [c["name"] for c in g["contacts"][:3]],
                "phones": g["phones"][:3],
                "all_names": g["all_names"][:5],
                "known_names": g.get("known_names", []),
            })

        return {
            "results": results,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def detail(self, group_id: str) -> Optional[Dict]:
        """Full group detail by GRP_ ID."""
        self.ensure_built()
        return self._groups.get(group_id)

    def filters(self) -> Dict:
        """Available filter values."""
        self.ensure_built()
        cities: Set[str] = set()
        max_props = 0
        for g in self._groups.values():
            for c in g["cities"]:
                cities.add(c)
            if g["property_count"] > max_props:
                max_props = g["property_count"]
        return {
            "cities": sorted(cities),
            "max_property_count": max_props,
            "total_groups": len(self._groups),
        }

    def search(self, q: str, limit: int = 20) -> List[Dict]:
        """Quick search across all group fields."""
        self.ensure_built()
        q_upper = q.upper().strip()
        if not q_upper:
            return []

        q_digits = re.sub(r"\D", "", q)
        results: List[Tuple[int, Dict]] = []

        for g in self._groups.values():
            score = 0

            for n in g["all_names"]:
                if q_upper in n.upper():
                    score += 10
                    if n.upper().startswith(q_upper):
                        score += 5
                    break

            for c in g["contacts"]:
                if q_upper in c["name"].upper():
                    score += 5
                    break

            if q_digits and len(q_digits) >= 3:
                for p in g["phones"]:
                    if q_digits in p:
                        score += 5
                        break

            for a in g["corp_addresses"]:
                if q_upper in a.get("canonical", "").upper():
                    score += 3
                    break

            if score > 0:
                results.append((score, {
                    "id": g["id"],
                    "name": g.get("display_name") or g["name"],
                    "property_count": g["property_count"],
                    "score": score,
                }))

        results.sort(key=lambda x: (-x[0], x[1]["name"]))
        return [r[1] for r in results[:limit]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_dates(g: Dict, sale_date: str):
    if not sale_date:
        return
    if not g["latest_date"] or sale_date > g["latest_date"]:
        g["latest_date"] = sale_date
    if not g["earliest_date"] or sale_date < g["earliest_date"]:
        g["earliest_date"] = sale_date


def _collect_party_data(g: Dict, txn: Dict, role: str, rt_id: str):
    """Collect contact, phone, address from a transaction."""
    contact = txn.get(f"{role}_contact", "").strip()
    phone = txn.get(f"{role}_phone", "").strip()

    if contact:
        ckey = contact.upper()
        if ckey not in g["contacts"]:
            g["contacts"][ckey] = {"name": contact, "phone": phone, "source_ids": []}
        if rt_id not in g["contacts"][ckey]["source_ids"]:
            g["contacts"][ckey]["source_ids"].append(rt_id)

    if phone:
        g["phones"].add(re.sub(r"\D", "", phone))
    for p in txn.get(f"{role}_phones", []):
        if p:
            g["phones"].add(re.sub(r"\D", "", p))

    addr = txn.get(f"{role}_address")
    if addr and addr.get("canonical"):
        akey = addr["canonical"]
        if akey not in g["corp_addresses"]:
            g["corp_addresses"][akey] = {**addr, "rt_ids": set()}
        g["corp_addresses"][akey]["rt_ids"].add(rt_id)


def _build_group_record(gid: str, g: Dict, properties: Dict) -> Dict:
    """Build final group record from accumulated data."""
    raw_names = sorted(g["raw_names"])

    # Best display name
    best_name = raw_names[0] if raw_names else ""
    if len(raw_names) > 1:
        for n in raw_names:
            if n != n.upper() and len(n) >= len(best_name):
                best_name = n

    contacts = sorted(g["contacts"].values(), key=lambda c: -len(c["source_ids"]))
    corp_addresses = []
    for aval in g["corp_addresses"].values():
        corp_addresses.append({
            "canonical": aval.get("canonical", ""),
            "city": aval.get("city"),
            "lat": aval.get("lat"),
            "lng": aval.get("lng"),
            "rt_ids": sorted(aval.get("rt_ids", set())),
        })

    # Owned properties
    owned_props = []
    for pid in sorted(g["owned_pids"]):
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

    buy_txns = g["buy_txns"]
    owned_pids = g["owned_pids"]
    for bt in buy_txns:
        bt["is_owned"] = bt["property_id"] in owned_pids
    buy_txns.sort(key=lambda t: t.get("sale_date") or "", reverse=True)

    sell_txns = g["sell_txns"]
    sell_txns.sort(key=lambda t: t.get("sale_date") or "", reverse=True)

    return {
        "id": gid,
        "name": best_name,
        "display_name": g["display_name"],
        "known_names": g.get("known_names", []),
        "all_names": raw_names,
        "contacts": contacts,
        "corp_addresses": corp_addresses,
        "phones": sorted(g["phones"]),
        "properties": owned_props,
        "property_count": len(owned_props),
        "owned_value": sum(p.get("sale_price") or 0 for p in owned_props),
        "buy_transactions": buy_txns,
        "buy_count": len(buy_txns),
        "seller_transactions": sell_txns,
        "sell_count": len(sell_txns),
        "cities": sorted(g["cities"]),
        "total_value": g["total_buy_value"],
        "total_sell_value": g["total_sell_value"],
        "latest_date": g["latest_date"],
        "earliest_date": g["earliest_date"],
    }
