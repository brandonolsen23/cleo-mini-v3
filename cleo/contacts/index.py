"""Contact index: query layer over the contact registry + properties data.

Computed on-the-fly from contact_registry.json + properties.json + group_registry.json.
Cached in memory, invalidated when source files change.
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from cleo.contacts.registry import normalize_contact_name

logger = logging.getLogger(__name__)


class ContactIndex:
    """In-memory query index built from contact_registry.json + properties.json.

    Enriches each contact with transaction data, group associations,
    and property references.
    """

    def __init__(self, registry_path, properties_path, group_registry_path):
        self._registry_path = registry_path
        self._properties_path = properties_path
        self._group_registry_path = group_registry_path
        self._contacts: Dict[str, Dict] = {}
        self._reg_mtime: float = 0
        self._props_mtime: float = 0
        self._greg_mtime: float = 0
        self._built = False

    def _needs_rebuild(self) -> bool:
        if not self._built:
            return True
        for path, mtime in [
            (self._registry_path, self._reg_mtime),
            (self._properties_path, self._props_mtime),
            (self._group_registry_path, self._greg_mtime),
        ]:
            if path.exists() and path.stat().st_mtime != mtime:
                return True
        return False

    def _build(self):
        start = time.time()
        logger.info("Building contact index...")

        if not self._registry_path.exists() or not self._properties_path.exists():
            logger.warning("Missing registry or properties — contact index empty")
            self._contacts = {}
            self._built = True
            return

        registry = json.loads(self._registry_path.read_text(encoding="utf-8"))
        self._reg_mtime = self._registry_path.stat().st_mtime
        name_index = registry.get("name_index", {})
        reg_contacts = registry.get("contacts", {})

        props_data = json.loads(self._properties_path.read_text(encoding="utf-8"))
        self._props_mtime = self._properties_path.stat().st_mtime
        properties = props_data.get("properties", {})

        # Load group registry for display names
        group_display: Dict[str, str] = {}
        if self._group_registry_path.exists():
            greg = json.loads(self._group_registry_path.read_text(encoding="utf-8"))
            self._greg_mtime = self._group_registry_path.stat().st_mtime
            for gid, grp in greg.get("groups", {}).items():
                group_display[gid] = grp.get("display_name") or grp.get("known_names", [""])[0]

        # Accumulate transaction data per CON_ ID
        accum: Dict[str, Dict] = {}

        def ensure(cid: str) -> Dict:
            if cid not in accum:
                rc = reg_contacts.get(cid, {})
                accum[cid] = {
                    "id": cid,
                    "display_name": rc.get("display_name"),
                    "known_names": list(rc.get("known_names", [])),
                    "raw_names": set(),
                    "phones": set(rc.get("phones", [])),
                    "group_associations": rc.get("group_associations", []),
                    "transactions": [],
                    "cities": set(),
                    "total_value": 0,
                    "latest_date": "",
                    "earliest_date": "",
                    "seen_rtids": set(),
                }
            return accum[cid]

        # Scan all transactions
        for pid, prop in properties.items():
            prop_addr = prop.get("primary_address", "")
            prop_city = prop.get("city", "").strip()

            for txn in prop.get("transactions", []):
                rt_id = txn.get("rt_id", "")
                sale_date = txn.get("sale_date", "")
                sale_price = txn.get("sale_price") or 0

                for role in ("buyer", "seller"):
                    contact_name = txn.get(f"{role}_contact", "").strip()
                    if not contact_name:
                        continue
                    norm = normalize_contact_name(contact_name)
                    if not norm:
                        continue
                    cid = name_index.get(norm)
                    if not cid:
                        continue

                    c = ensure(cid)
                    c["raw_names"].add(contact_name)

                    if prop_city:
                        c["cities"].add(prop_city)

                    # Update dates
                    if sale_date:
                        if not c["latest_date"] or sale_date > c["latest_date"]:
                            c["latest_date"] = sale_date
                        if not c["earliest_date"] or sale_date < c["earliest_date"]:
                            c["earliest_date"] = sale_date

                    if rt_id not in c["seen_rtids"]:
                        c["transactions"].append({
                            "property_id": pid,
                            "address": prop_addr,
                            "city": prop_city,
                            "sale_price": txn.get("sale_price"),
                            "sale_date": sale_date,
                            "rt_id": rt_id,
                            "role": role,
                            "group_name": txn.get(f"{role}_name", ""),
                        })
                        c["total_value"] += sale_price
                        c["seen_rtids"].add(rt_id)

                    # Collect phone
                    phone = txn.get(f"{role}_phone", "").strip()
                    if phone:
                        c["phones"].add(re.sub(r"\D", "", phone))

        # Build final records
        final: Dict[str, Dict] = {}
        for cid, c in accum.items():
            raw_names = sorted(c["raw_names"])
            # Best display name: prefer mixed case
            best_name = raw_names[0] if raw_names else ""
            if len(raw_names) > 1:
                for n in raw_names:
                    if n != n.upper() and len(n) >= len(best_name):
                        best_name = n

            txns = c["transactions"]
            txns.sort(key=lambda t: t.get("sale_date") or "", reverse=True)

            # Enrich group_associations with display names
            associations = []
            for a in c["group_associations"]:
                gid = a.get("group_id", "")
                associations.append({
                    **a,
                    "group_display_name": group_display.get(gid, a.get("group_name", "")),
                })

            final[cid] = {
                "id": cid,
                "name": best_name,
                "display_name": c["display_name"],
                "known_names": c["known_names"],
                "all_names": raw_names,
                "phones": sorted(c["phones"]),
                "group_associations": associations,
                "transactions": txns,
                "transaction_count": len(txns),
                "cities": sorted(c["cities"]),
                "total_value": c["total_value"],
                "latest_date": c["latest_date"],
                "earliest_date": c["earliest_date"],
                "group_count": len(associations),
            }

        self._contacts = final
        self._built = True
        elapsed = time.time() - start
        logger.info("Contact index: %d contacts in %.1fs", len(final), elapsed)

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
        phone: str = "",
        group: str = "",
        city: str = "",
        sort: str = "transaction_count",
        order: str = "desc",
        page: int = 1,
        per_page: int = 25,
    ) -> Dict:
        """Browse contacts with layered filtering, sorting, and pagination."""
        self.ensure_built()

        name_q = name.upper().strip() if name else ""
        phone_q = re.sub(r"\D", "", phone) if phone else ""
        group_q = group.upper().strip() if group else ""
        city_q = city.upper().strip() if city else ""

        filtered: List[Dict] = []
        for c in self._contacts.values():
            if name_q and not any(name_q in n.upper() for n in c["all_names"]):
                continue
            if phone_q and not any(phone_q in p for p in c["phones"]):
                continue
            if group_q and not any(
                group_q in a.get("group_name", "").upper()
                or group_q in a.get("group_display_name", "").upper()
                for a in c["group_associations"]
            ):
                continue
            if city_q and not any(city_q in ct.upper() for ct in c["cities"]):
                continue
            filtered.append(c)

        def _sort_key(o: Dict):
            if sort == "total_value":
                return o.get("total_value", 0)
            if sort == "latest_date":
                return o.get("latest_date", "")
            if sort == "name":
                return o.get("display_name") or o.get("name", "")
            if sort == "group_count":
                return o.get("group_count", 0)
            return o.get("transaction_count", 0)

        reverse = order == "desc"
        filtered.sort(key=_sort_key, reverse=reverse)

        total = len(filtered)
        start_idx = (page - 1) * per_page
        page_items = filtered[start_idx:start_idx + per_page]

        results = []
        for c in page_items:
            # Primary group (most recent active association)
            active_groups = [a for a in c["group_associations"] if a.get("status") == "active"]
            primary_group = active_groups[0] if active_groups else (
                c["group_associations"][0] if c["group_associations"] else None
            )

            results.append({
                "id": c["id"],
                "name": c["display_name"] or c["name"],
                "phones": c["phones"][:2],
                "primary_group": {
                    "group_id": primary_group["group_id"],
                    "name": primary_group.get("group_display_name") or primary_group.get("group_name", ""),
                } if primary_group else None,
                "group_count": c["group_count"],
                "transaction_count": c["transaction_count"],
                "total_value": c["total_value"],
                "cities": c["cities"][:3],
                "latest_date": c["latest_date"],
            })

        return {
            "results": results,
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def detail(self, contact_id: str) -> Optional[Dict]:
        """Full contact detail by CON_ ID."""
        self.ensure_built()
        return self._contacts.get(contact_id)

    def filters(self) -> Dict:
        """Available filter values."""
        self.ensure_built()
        cities: Set[str] = set()
        for c in self._contacts.values():
            for ct in c["cities"]:
                cities.add(ct)
        return {
            "cities": sorted(cities),
            "total_contacts": len(self._contacts),
        }

    def search(self, q: str, limit: int = 20) -> List[Dict]:
        """Quick search across all contact fields."""
        self.ensure_built()
        q_upper = q.upper().strip()
        if not q_upper:
            return []

        q_digits = re.sub(r"\D", "", q)
        results: List[Tuple[int, Dict]] = []

        for c in self._contacts.values():
            score = 0

            for n in c["all_names"]:
                if q_upper in n.upper():
                    score += 10
                    if n.upper().startswith(q_upper):
                        score += 5
                    break

            if q_digits and len(q_digits) >= 3:
                for p in c["phones"]:
                    if q_digits in p:
                        score += 5
                        break

            for a in c["group_associations"]:
                gname = a.get("group_name", "") or a.get("group_display_name", "")
                if q_upper in gname.upper():
                    score += 3
                    break

            if score > 0:
                results.append((score, {
                    "id": c["id"],
                    "name": c.get("display_name") or c["name"],
                    "transaction_count": c["transaction_count"],
                    "score": score,
                }))

        results.sort(key=lambda x: (-x[0], x[1]["name"]))
        return [r[1] for r in results[:limit]]
