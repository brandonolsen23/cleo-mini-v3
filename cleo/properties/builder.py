"""Properties builder: groups compiled records by ARN into a property master list.

Reads all compiled/active records, groups by parcel.arn (20-digit), and produces:
  - properties.json: one entry per unique ARN with denormalized data from all sources
  - properties_unresolved.json: records with no parcel or bad ARN (parked for later)
  - search_index.json: inverted index mapping tokens to property IDs

This is a read-only derived layer — rebuilt fresh from compiled data on demand.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

BAD_ARNS = {"00000000000000000000", ""}


def _best_primary_address(records: List[Dict]) -> str:
    """Pick the best primary address from a group of compiled records.

    Priority: RT property address > GW property address > Brand > OSM.
    Within RT, prefer address with highest geocode confidence.
    """
    best = ""
    best_score = -1

    confidence_scores = {"exact": 4, "high": 3, "medium": 2, "low": 1}

    for rec in records:
        source = rec.get("source", "")
        source_score = {"realtrack": 40, "geowarehouse": 30, "brand": 20, "osm": 10}.get(source, 0)

        addrs = (rec.get("addresses") or {}).get("property", [])
        for a in addrs:
            conf = confidence_scores.get(a.get("geocode_confidence", ""), 0)
            score = source_score + conf
            if score > best_score:
                best_score = score
                best = a.get("canonical", "")

        # OSM address fallback
        if source == "osm" and not addrs:
            osm_addr = rec.get("address") or {}
            parts = [osm_addr.get("housenumber", ""), osm_addr.get("street", ""),
                     osm_addr.get("city", "")]
            osm_str = " ".join(p for p in parts if p).strip()
            if osm_str and source_score > best_score:
                best_score = source_score
                best = osm_str

    return best


def _extract_city(records: List[Dict]) -> str:
    """Extract the primary city from a group of compiled records."""
    for rec in records:
        addrs = (rec.get("addresses") or {}).get("property", [])
        for a in addrs:
            city = a.get("city", "").strip()
            if city:
                return city
    # OSM fallback
    for rec in records:
        if rec.get("source") == "osm":
            city = (rec.get("address") or {}).get("city", "").strip()
            if city:
                return city
    return ""


def _collect_all_addresses(records: List[Dict]) -> List[str]:
    """Collect all unique canonical addresses from all records in a group."""
    seen: Set[str] = set()
    result: List[str] = []
    for rec in records:
        for role_addrs in (rec.get("addresses") or {}).values():
            if not isinstance(role_addrs, list):
                continue
            for a in role_addrs:
                canon = a.get("canonical", "").strip()
                if canon and canon not in seen:
                    seen.add(canon)
                    result.append(canon)
        # OSM address
        if rec.get("source") == "osm":
            osm_addr = rec.get("address") or {}
            parts = [osm_addr.get("housenumber", ""), osm_addr.get("street", ""),
                     osm_addr.get("city", "")]
            osm_str = ", ".join(p for p in parts if p).strip()
            if osm_str and osm_str not in seen:
                seen.add(osm_str)
                result.append(osm_str)
    return result


def _best_party_address(addresses: Dict, role: str) -> Optional[Dict]:
    """Extract the best address for a buyer or seller from compiled addresses.

    Returns a compact dict with canonical, city, lat, lng, or None.
    """
    role_addrs = addresses.get(role, [])
    if not role_addrs:
        return None

    # Prefer the first address with geocode data
    best = role_addrs[0]
    for a in role_addrs:
        if a.get("lat") and a.get("lng"):
            best = a
            break

    canonical = best.get("canonical", "")
    if not canonical:
        return None

    result: Dict[str, Any] = {"canonical": canonical}
    city = best.get("city", "")
    if city:
        result["city"] = city
    lat, lng = best.get("lat"), best.get("lng")
    if lat and lng:
        result["lat"] = lat
        result["lng"] = lng
    return result


def _collect_transactions(records: List[Dict]) -> List[Dict]:
    """Extract transaction summaries from RT records, sorted by date desc."""
    txns = []
    for rec in records:
        if rec.get("source") != "realtrack":
            continue
        txn = rec.get("transaction") or {}
        seller = rec.get("seller") or {}
        buyer = rec.get("buyer") or {}
        site = rec.get("site") or {}
        broker = rec.get("broker") or {}
        consid = rec.get("consideration") or {}
        addresses = rec.get("addresses") or {}

        txns.append({
            "rt_id": rec["id"],
            "sale_date": txn.get("sale_date", ""),
            "sale_price": txn.get("sale_price"),
            "sale_price_display": txn.get("sale_price_display", ""),
            "transaction_type": txn.get("transaction_type", ""),
            "property_type": rec.get("property_type", ""),
            "arn": txn.get("arn", ""),
            "pins": txn.get("pins", []),
            "seller_name": seller.get("name", ""),
            "seller_contact": seller.get("contact", ""),
            "seller_phone": seller.get("phone", ""),
            "seller_phones": seller.get("phones", []),
            "seller_attention": seller.get("attention", ""),
            "seller_aliases": seller.get("aliases", []),
            "seller_company_lines": seller.get("company_lines", []),
            "seller_address": _best_party_address(addresses, "seller"),
            "buyer_name": buyer.get("name", ""),
            "buyer_contact": buyer.get("contact", ""),
            "buyer_phone": buyer.get("phone", ""),
            "buyer_phones": buyer.get("phones", []),
            "buyer_attention": buyer.get("attention", ""),
            "buyer_aliases": buyer.get("aliases", []),
            "buyer_company_lines": buyer.get("company_lines", []),
            "buyer_address": _best_party_address(addresses, "buyer"),
            "consideration": {
                "cash": consid.get("cash"),
                "assumed_debt": consid.get("assumed_debt"),
                "chattels": consid.get("chattels", ""),
                "verbatim": consid.get("verbatim", ""),
                "chargees": consid.get("chargees", []),
            },
            "broker_name": broker.get("brokerage", ""),
            "broker_phone": broker.get("phone", ""),
            "building_sf": site.get("building_sf"),
            "site_area": site.get("site_area"),
            "site_area_units": site.get("site_area_units", ""),
            "zoning": site.get("zoning", ""),
            "legal_description": site.get("legal_description", ""),
            "description": rec.get("description", ""),
            "photos": rec.get("photos", []),
        })

    txns.sort(key=lambda t: t.get("sale_date") or "", reverse=True)
    return txns


def _current_owner(transactions: List[Dict]) -> Optional[Dict]:
    """The most recent buyer is the current owner."""
    for txn in transactions:
        if txn.get("buyer_name"):
            return {
                "name": txn["buyer_name"],
                "contact": txn.get("buyer_contact", ""),
                "phone": txn.get("buyer_phone", ""),
                "phones": txn.get("buyer_phones", []),
                "attention": txn.get("buyer_attention", ""),
                "aliases": txn.get("buyer_aliases", []),
                "company_lines": txn.get("buyer_company_lines", []),
                "address": txn.get("buyer_address"),
                "from_transaction": txn["rt_id"],
            }
    return None


def _collect_all_contacts(records: List[Dict]) -> List[Dict]:
    """Collect all contact names and phones from all records."""
    contacts: List[Dict] = []
    seen: Set[str] = set()

    for rec in records:
        if rec.get("source") != "realtrack":
            continue
        for party_key, role in [("seller", "seller"), ("buyer", "buyer")]:
            party = rec.get(party_key) or {}
            name = party.get("name", "").strip()
            contact = party.get("contact", "").strip()
            phone = party.get("phone", "").strip()

            key = f"{name}|{contact}|{role}|{rec['id']}"
            if key in seen:
                continue
            seen.add(key)

            contacts.append({
                "name": name,
                "contact": contact,
                "attention": party.get("attention", ""),
                "phone": phone,
                "phones": party.get("phones", []),
                "role": role,
                "source_id": rec["id"],
            })

    return contacts


def _collect_all_party_names(records: List[Dict]) -> List[str]:
    """Collect all unique party names and aliases for search indexing."""
    names: Set[str] = set()
    for rec in records:
        if rec.get("source") != "realtrack":
            continue
        for party_key in ("seller", "buyer"):
            party = rec.get(party_key) or {}
            for field in ("name", "contact", "attention"):
                v = party.get(field, "").strip()
                if v:
                    names.add(v)
            for arr_field in ("aliases", "alternate_names", "company_lines"):
                for v in party.get(arr_field, []):
                    if v:
                        names.add(v)
    return sorted(names)


def _collect_tenants(records: List[Dict]) -> List[Dict]:
    """Collect brand and OSM tenants on this parcel."""
    tenants = []
    for rec in records:
        src = rec.get("source", "")
        if src == "brand":
            addr = ((rec.get("addresses") or {}).get("property") or [{}])[0] if rec.get("addresses") else {}
            tenants.append({
                "source_id": rec["id"],
                "source": "brand",
                "address": addr.get("canonical", "") if isinstance(addr, dict) else "",
            })
        elif src == "osm":
            tenants.append({
                "source_id": rec["id"],
                "source": "osm",
                "name": rec.get("name", ""),
                "brand": rec.get("brand", ""),
                "category": rec.get("category", ""),
                "phone": rec.get("phone", ""),
                "website": rec.get("website", ""),
            })
    return tenants


def _best_site(transactions: List[Dict]) -> Dict:
    """Pick best site data from transactions (prefer most recent with data)."""
    for txn in transactions:
        if txn.get("building_sf") or txn.get("site_area") or txn.get("zoning"):
            return {
                "building_sf": txn.get("building_sf"),
                "site_area": txn.get("site_area"),
                "site_area_units": txn.get("site_area_units", ""),
                "zoning": txn.get("zoning", ""),
                "legal_description": txn.get("legal_description", ""),
            }
    return {}


def _check_arn_disagreement(records: List[Dict], group_arn: str) -> bool:
    """Check if any RT transaction.arn disagrees with the parcel.arn."""
    for rec in records:
        if rec.get("source") != "realtrack":
            continue
        txn_arn = (rec.get("transaction") or {}).get("arn", "")
        if txn_arn and txn_arn != group_arn:
            return True
    return False


def _collect_pins(records: List[Dict]) -> List[str]:
    """Collect all PINs from all sources."""
    pins: Set[str] = set()
    for rec in records:
        # From transaction
        for p in (rec.get("transaction") or {}).get("pins", []):
            if p:
                pins.add(p)
        # From parcel
        parcel_pin = (rec.get("parcel") or {}).get("pin", "")
        if parcel_pin:
            pins.add(parcel_pin)
    return sorted(pins)


def build_property(arn: str, records: List[Dict], property_id: str) -> Dict:
    """Build a single property record from a group of compiled records sharing an ARN."""
    transactions = _collect_transactions(records)
    owner = _current_owner(transactions)
    site = _best_site(transactions)
    parcel = records[0].get("parcel") or {}

    # Best centroid from parcel
    centroid_lat = parcel.get("centroid_lat")
    centroid_lng = parcel.get("centroid_lng")

    # Fallback to geocoded address if no parcel centroid
    if not centroid_lat or not centroid_lng:
        for rec in records:
            for addrs in (rec.get("addresses") or {}).values():
                if not isinstance(addrs, list):
                    continue
                for a in addrs:
                    if a.get("lat") and a.get("lng"):
                        centroid_lat = a["lat"]
                        centroid_lng = a["lng"]
                        break
                if centroid_lat:
                    break
            if centroid_lat:
                break

    sources = sorted(set(r.get("source", "") for r in records))
    source_records = sorted(r["id"] for r in records)

    # Collect unique property types from RT source records
    property_types = sorted(set(
        r.get("property_type", "") for r in records
        if r.get("source") == "realtrack" and r.get("property_type")
    ))

    # Most recent description and broker
    latest_desc = ""
    latest_broker = ""
    for txn in transactions:
        if not latest_desc and txn.get("description"):
            latest_desc = txn["description"]
        if not latest_broker and txn.get("broker_name"):
            latest_broker = txn["broker_name"]

    return {
        "property_id": property_id,
        "arn": arn,

        # Parcel
        "centroid_lat": centroid_lat,
        "centroid_lng": centroid_lng,
        "parcel_method": parcel.get("method", ""),
        "parcel_confidence": parcel.get("confidence", ""),

        # Addresses
        "primary_address": _best_primary_address(records),
        "city": _extract_city(records),
        "all_addresses": _collect_all_addresses(records),

        # Source records
        "source_records": source_records,
        "sources": sources,
        "property_types": property_types,

        # Current owner
        "current_owner": owner,

        # Transactions
        "transactions": transactions,
        "latest_transaction": {
            "rt_id": transactions[0]["rt_id"],
            "sale_date": transactions[0]["sale_date"],
            "sale_price": transactions[0]["sale_price"],
        } if transactions else None,

        # All contacts
        "all_contacts": _collect_all_contacts(records),
        "all_party_names": _collect_all_party_names(records),

        # Tenants
        "tenants": _collect_tenants(records),

        # Site
        "building_sf": site.get("building_sf"),
        "site_area": site.get("site_area"),
        "site_area_units": site.get("site_area_units", ""),
        "zoning": site.get("zoning", ""),
        "legal_description": site.get("legal_description", ""),

        # Broker & description
        "broker": latest_broker,
        "description": latest_desc,

        # Counts
        "transaction_count": len(transactions),
        "brand_count": sum(1 for r in records if r.get("source") == "brand"),
        "osm_count": sum(1 for r in records if r.get("source") == "osm"),

        # Flags
        "arn_disagreement": _check_arn_disagreement(records, arn),
        "pins": _collect_pins(records),
    }


def build_properties(compiled_dir: Path, id_map_path: Optional[Path] = None) -> Tuple[Dict, Dict]:
    """Build the full property master list from compiled/active.

    If id_map_path is provided, uses the persistent ID map to assign stable
    PRO_NNNNN IDs. Otherwise falls back to sequential assignment.

    Returns (properties_data, unresolved_data).
    """
    from cleo.properties.id_map import load_id_map, save_id_map, assign_id

    start = time.time()

    # Load persistent ID map (or create empty)
    id_map = None
    if id_map_path:
        id_map = load_id_map(id_map_path)

    # Phase 1: Read all compiled records and group by ARN
    logger.info("Reading compiled records from %s...", compiled_dir)
    arn_groups: Dict[str, List[Dict]] = {}
    unresolved: List[Dict] = []
    total = 0

    for f in sorted(compiled_dir.glob("*.json")):
        if f.stem == "_meta":
            continue
        total += 1

        rec = json.loads(f.read_text(encoding="utf-8"))
        parcel = rec.get("parcel")

        if not parcel or not parcel.get("arn"):
            unresolved.append({
                "id": rec["id"],
                "source": rec.get("source", ""),
                "reason": "no_parcel",
                "primary_address": _best_primary_address([rec]),
                "city": _extract_city([rec]),
            })
            continue

        arn = parcel["arn"]
        if arn in BAD_ARNS:
            unresolved.append({
                "id": rec["id"],
                "source": rec.get("source", ""),
                "reason": "bad_arn",
                "primary_address": _best_primary_address([rec]),
                "city": _extract_city([rec]),
            })
            continue

        if arn not in arn_groups:
            arn_groups[arn] = []
        arn_groups[arn].append(rec)

    read_time = time.time() - start
    logger.info("Read %d compiled records in %.1fs", total, read_time)
    logger.info("Grouped into %d unique ARNs, %d unresolved", len(arn_groups), len(unresolved))

    # Phase 2: Build property records with stable IDs
    build_start = time.time()
    properties: Dict[str, Dict] = {}
    new_ids = 0
    existing_ids = 0

    for arn in sorted(arn_groups.keys()):
        if id_map:
            was_known = arn in id_map["map"]
            pid = assign_id(id_map, arn)
            if was_known:
                existing_ids += 1
            else:
                new_ids += 1
        else:
            pid = f"PRO_{len(properties) + 1:05d}"
            new_ids += 1
        prop = build_property(arn, arn_groups[arn], pid)
        properties[pid] = prop

    # Save updated ID map
    if id_map and id_map_path:
        save_id_map(id_map, id_map_path)
        logger.info("ID map: %d existing, %d new, next_id=%d",
                     existing_ids, new_ids, id_map["meta"]["next_id"])

    build_time = time.time() - build_start
    logger.info("Built %d property records in %.1fs", len(properties), build_time)

    # Compute stats
    by_source: Dict[str, int] = {}
    multi_source = 0
    has_transactions = 0
    has_tenants = 0
    arn_disagreements = 0

    for prop in properties.values():
        for s in prop["sources"]:
            by_source[s] = by_source.get(s, 0) + 1
        if len(prop["sources"]) > 1:
            multi_source += 1
        if prop["transaction_count"] > 0:
            has_transactions += 1
        if prop["tenants"]:
            has_tenants += 1
        if prop["arn_disagreement"]:
            arn_disagreements += 1

    elapsed = time.time() - start

    properties_data = {
        "meta": {
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "compiled_dir": str(compiled_dir),
            "total_compiled_records": total,
            "total_properties": len(properties),
            "total_unresolved": len(unresolved),
            "multi_source_properties": multi_source,
            "properties_with_transactions": has_transactions,
            "properties_with_tenants": has_tenants,
            "arn_disagreements": arn_disagreements,
            "by_source": by_source,
            "id_map_existing": existing_ids,
            "id_map_new": new_ids,
            "id_map_total": id_map["meta"]["next_id"] - 1 if id_map else len(properties),
            "elapsed_seconds": round(elapsed, 1),
        },
        "properties": properties,
    }

    unresolved_data = {
        "meta": {
            "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "count": len(unresolved),
            "by_reason": {
                "no_parcel": sum(1 for u in unresolved if u["reason"] == "no_parcel"),
                "bad_arn": sum(1 for u in unresolved if u["reason"] == "bad_arn"),
            },
        },
        "records": unresolved,
    }

    return properties_data, unresolved_data
