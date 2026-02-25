"""Outreach / mailing list module — build targeted owner lists, export CSV, track contacts."""

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from cleo.config import (
    OUTREACH_LISTS_PATH,
    OUTREACH_LOG_PATH,
    OUTREACH_EDITS_PATH,
    PROPERTIES_PATH,
    PARTIES_PATH,
    BRAND_MATCHES_PATH,
    CRM_DEALS_PATH,
    CRM_EDITS_PATH,
)
from cleo.parse.versioning import active_dir

router = APIRouter(prefix="/api/outreach", tags=["outreach"])

VALID_OUTCOMES = {"no_answer", "left_vm", "sent", "spoke_with", "bounced"}

# Brand category mapping — mirrors frontend BrandBadge.tsx
BRAND_CATEGORIES: dict[str, str] = {
    # Grocery
    "Loblaws": "grocery", "No Frills": "grocery", "Real Canadian Superstore": "grocery",
    "Shoppers Drug Mart": "grocery", "Zehrs": "grocery", "Fortinos": "grocery",
    "Wholesale Club": "grocery", "Sobeys": "grocery", "FreshCo": "grocery",
    "Foodland": "grocery", "Longo's": "grocery", "Safeway": "grocery",
    "Metro": "grocery", "Food Basics": "grocery", "Valu-Mart": "grocery",
    "Your Independent Grocer": "grocery", "Farm Boy": "grocery",
    # Big-Box Retail
    "Walmart": "bigbox", "Canadian Tire": "bigbox", "Home Depot": "bigbox", "Costco": "bigbox",
    # Discount Retail
    "Giant Tiger": "discount", "Dollarama": "discount", "Dollar Tree": "discount",
    "Goodwill": "discount",
    # Specialty Retail
    "Best Buy": "specialty", "Staples": "specialty", "JYSK": "specialty",
    "HomeSense": "specialty", "PetSmart": "specialty", "Sport Chek": "specialty",
    "Tepperman's": "specialty", "LCBO": "specialty", "Toys R Us": "specialty",
    "Indigo": "specialty", "Rens Pets": "specialty", "The Brick": "specialty",
    "Starbucks": "specialty",
    # QSR
    "Harvey's": "qsr", "Swiss Chalet": "qsr", "McDonald's": "qsr", "A&W": "qsr",
    "Wendy's": "qsr", "Burger King": "qsr", "Tim Hortons": "qsr",
    "Mary Brown's": "qsr", "Popeyes": "qsr", "Dairy Queen": "qsr", "Taco Bell": "qsr",
    # Full-Service
    "Kelseys": "fullservice", "Montana's": "fullservice", "East Side Mario's": "fullservice",
    "Boston Pizza": "fullservice", "Chipotle": "fullservice", "Five Guys": "fullservice",
    "St. Louis Bar & Grill": "fullservice", "Sunset Grill": "fullservice",
    "Wild Wing": "fullservice",
    # Takeout
    "Subway": "takeout", "Mr. Sub": "takeout", "Mucho Burrito": "takeout",
    "Papa John's": "takeout", "Firehouse Subs": "takeout", "Pita Pit": "takeout",
    "Domino's": "takeout", "Pizza Pizza": "takeout", "Pizza Hut": "takeout",
    # Fuel
    "Esso": "fuel", "Mobil": "fuel", "Pioneer": "fuel", "Ultramar": "fuel",
    # Automotive
    "Toyota": "automotive", "Lexus": "automotive", "Honda": "automotive",
    "Acura": "automotive", "Nissan": "automotive", "Infiniti": "automotive",
    "Kia": "automotive", "Hyundai": "automotive", "Volvo": "automotive",
    "Chrysler": "automotive", "Ford": "automotive", "GMC": "automotive",
    "Mercedes-Benz": "automotive", "Porsche": "automotive", "Land Rover": "automotive",
    "Volkswagen": "automotive", "Audi": "automotive", "BMW": "automotive",
    "Jaguar": "automotive", "Mazda": "automotive", "Mitsubishi": "automotive",
}

CATEGORY_LABELS: dict[str, str] = {
    "grocery": "Grocery",
    "bigbox": "Big-Box Retail",
    "discount": "Discount Retail",
    "specialty": "Specialty Retail",
    "qsr": "QSR",
    "fullservice": "Full-Service",
    "takeout": "Takeout",
    "fuel": "Fuel",
    "financial": "Financial",
    "automotive": "Automotive",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_lists() -> dict:
    if OUTREACH_LISTS_PATH.exists():
        return json.loads(OUTREACH_LISTS_PATH.read_text(encoding="utf-8"))
    return {"lists": {}, "next_id": 1}


def _save_lists(data: dict) -> None:
    OUTREACH_LISTS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _load_log() -> dict:
    if OUTREACH_LOG_PATH.exists():
        return json.loads(OUTREACH_LOG_PATH.read_text(encoding="utf-8"))
    return {"entries": {}, "next_id": 1}


def _save_log(data: dict) -> None:
    OUTREACH_LOG_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _next_id(data: dict, prefix: str) -> str:
    n = data["next_id"]
    data["next_id"] = n + 1
    return f"{prefix}{n:05d}"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log_edit(entry: dict) -> None:
    entry["timestamp"] = _now()
    with open(OUTREACH_EDITS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_properties() -> dict:
    if not PROPERTIES_PATH.exists():
        return {}
    raw = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    return raw.get("properties", raw) if isinstance(raw, dict) else {}


def _set_property_pipeline_status(prop_id: str, status: str) -> None:
    """Write pipeline_status to the property record on disk."""
    if not PROPERTIES_PATH.exists():
        return
    from cleo.properties.registry import load_registry, save_registry
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})
    if prop_id not in props:
        return
    props[prop_id]["pipeline_status"] = status
    save_registry(reg, PROPERTIES_PATH)


def _load_parties() -> dict:
    if not PARTIES_PATH.exists():
        return {}
    raw = json.loads(PARTIES_PATH.read_text(encoding="utf-8"))
    return raw.get("parties", raw) if isinstance(raw, dict) else {}


def _load_brand_matches() -> dict:
    if not BRAND_MATCHES_PATH.exists():
        return {}
    raw = json.loads(BRAND_MATCHES_PATH.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _brands_for_prop(matches: dict, prop_id: str) -> list[str]:
    entries = matches.get(prop_id, [])
    return sorted(set(e["brand"] for e in entries))


def _build_rt_info() -> dict[str, dict]:
    """Scan parsed files for transaction info per RT ID."""
    act = active_dir()
    rt_info: dict[str, dict] = {}
    if not act:
        return rt_info
    for f in act.glob("*.json"):
        if f.stem == "_meta":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        rt_id = data.get("rt_id", f.stem)
        tx = data.get("transaction", {})
        rt_info[rt_id] = {
            "sale_date": tx.get("sale_date", ""),
            "sale_date_iso": tx.get("sale_date_iso", ""),
            "sale_price": tx.get("sale_price", ""),
            "buyer": data.get("transferee", {}).get("name", ""),
            "buyer_contact": data.get("transferee", {}).get("contact", ""),
            "buyer_phone": data.get("transferee", {}).get("phone", ""),
        }
    return rt_info


def _resolve_owner(prop: dict, rt_info: dict) -> dict:
    """Find latest buyer for a property from its linked transactions."""
    rt_ids = prop.get("rt_ids", [])
    latest_iso = ""
    owner = ""
    owner_contact = ""
    owner_phone = ""
    sale_date = ""
    sale_price = ""
    for rt_id in rt_ids:
        info = rt_info.get(rt_id)
        if not info:
            continue
        iso = info["sale_date_iso"]
        if iso and iso > latest_iso:
            latest_iso = iso
            sale_date = info["sale_date"]
            sale_price = info["sale_price"]
            owner = info["buyer"]
            owner_contact = info["buyer_contact"]
            owner_phone = info["buyer_phone"]
    return {
        "owner": owner,
        "owner_contact": owner_contact,
        "owner_phone": owner_phone,
        "latest_sale_date": sale_date,
        "latest_sale_date_iso": latest_iso,
        "latest_sale_price": sale_price,
    }


def _build_name_to_gid(parties: dict) -> dict[str, str]:
    """Build normalized name -> group_id reverse index."""
    idx: dict[str, str] = {}
    for gid, p in parties.items():
        for name in p.get("normalized_names", []):
            idx[name] = gid
        for name in p.get("names", []):
            idx[name.upper().strip()] = gid
    return idx


def _resolve_outreach_items(
    prop_ids: list[str],
    props: dict | None = None,
    parties: dict | None = None,
    brand_matches: dict | None = None,
    rt_info: dict | None = None,
    log_data: dict | None = None,
) -> list[dict]:
    """Resolve enriched outreach items for a list of property IDs."""
    if props is None:
        props = _load_properties()
    if parties is None:
        parties = _load_parties()
    if brand_matches is None:
        brand_matches = _load_brand_matches()
    if rt_info is None:
        rt_info = _build_rt_info()
    if log_data is None:
        log_data = _load_log()

    name_to_gid = _build_name_to_gid(parties)

    # Build contact status index: prop_id -> latest log entry
    contacted_props: dict[str, dict] = {}
    for _eid, entry in log_data.get("entries", {}).items():
        pid = entry.get("prop_id", "")
        if pid:
            existing = contacted_props.get(pid)
            if not existing or entry.get("date", "") > existing.get("date", ""):
                contacted_props[pid] = entry

    items = []
    for pid in prop_ids:
        prop = props.get(pid)
        if not prop:
            continue

        owner_info = _resolve_owner(prop, rt_info)
        owner_name = owner_info["owner"]

        # Resolve party group
        owner_group_id = ""
        corporate_address = ""
        contact_names: list[str] = []
        phones: list[str] = []
        owner_type = ""
        if owner_name:
            norm = owner_name.upper().strip()
            gid = name_to_gid.get(norm, "")
            if gid and gid in parties:
                owner_group_id = gid
                group = parties[gid]
                corporate_address = group.get("addresses", [""])[0] if group.get("addresses") else ""
                contact_names = group.get("contacts", [])
                phones = group.get("phones", [])
                owner_type = "company" if group.get("is_company") else "person"

        # Contact status
        contact_entry = contacted_props.get(pid)
        contact_status = None
        if contact_entry:
            contact_status = {
                "method": contact_entry.get("method", ""),
                "outcome": contact_entry.get("outcome"),
                "date": contact_entry.get("date", ""),
            }

        outreach_status = _derive_outreach_status(pid, log_data)

        items.append({
            "prop_id": pid,
            "address": prop.get("address", ""),
            "city": prop.get("city", ""),
            "brands": _brands_for_prop(brand_matches, pid),
            "latest_sale_date": owner_info["latest_sale_date"],
            "latest_sale_date_iso": owner_info["latest_sale_date_iso"],
            "latest_sale_price": owner_info["latest_sale_price"],
            "owner": owner_name,
            "owner_type": owner_type,
            "owner_group_id": owner_group_id,
            "corporate_address": corporate_address,
            "contact_names": contact_names,
            "phones": phones,
            "contact_status": contact_status,
            "outreach_status": outreach_status,
        })

    return items


# ---------------------------------------------------------------------------
# Filter options
# ---------------------------------------------------------------------------

@router.get("/filter-options")
def filter_options():
    """Return available cities, brand names, and brand categories for filter dropdowns."""
    props = _load_properties()
    brand_matches = _load_brand_matches()

    cities: set[str] = set()
    for _pid, prop in props.items():
        city = prop.get("city", "").strip()
        if city:
            cities.add(city)

    brands: set[str] = set()
    for _pid, entries in brand_matches.items():
        for e in entries:
            b = e.get("brand", "").strip()
            if b:
                brands.add(b)

    return {
        "cities": sorted(cities),
        "brands": sorted(brands),
        "brand_categories": BRAND_CATEGORIES,
        "category_labels": CATEGORY_LABELS,
    }


# ---------------------------------------------------------------------------
# Preview (run filters without saving)
# ---------------------------------------------------------------------------

@router.post("/preview")
async def preview(request: Request):
    """Run filters and return enriched property+owner list (not saved)."""
    body = await request.json()
    filters = body.get("filters", {})

    props = _load_properties()
    parties = _load_parties()
    brand_matches = _load_brand_matches()
    rt_info = _build_rt_info()
    log_data = _load_log()
    name_to_gid = _build_name_to_gid(parties)

    # Filter cities
    filter_cities = set(c.upper().strip() for c in filters.get("cities", []) if c)
    filter_brands = set(b.strip() for b in filters.get("brands", []) if b)
    filter_categories = set(c.strip() for c in filters.get("brand_categories", []) if c)
    # Expand categories into brand names
    if filter_categories:
        for brand_name, cat in BRAND_CATEGORIES.items():
            if cat in filter_categories:
                filter_brands.add(brand_name)
    sale_date_from = filters.get("sale_date_from", "") or ""
    sale_date_to = filters.get("sale_date_to", "") or ""
    price_min = filters.get("price_min")
    price_max = filters.get("price_max")
    owner_type_filter = filters.get("owner_type") or ""
    exclude_contacted = filters.get("exclude_contacted", False)
    exclude_by_owner = filters.get("exclude_by_owner", False)

    # Build contacted indexes
    contacted_prop_ids: set[str] = set()
    contacted_owner_gids: set[str] = set()
    if exclude_contacted or exclude_by_owner:
        for _eid, entry in log_data.get("entries", {}).items():
            contacted_prop_ids.add(entry.get("prop_id", ""))
            if entry.get("owner_group_id"):
                contacted_owner_gids.add(entry["owner_group_id"])

    matching_ids: list[str] = []
    for pid, prop in props.items():
        # City filter
        if filter_cities:
            prop_city = prop.get("city", "").upper().strip()
            if prop_city not in filter_cities:
                continue

        # Brand filter
        if filter_brands:
            prop_brands = set(_brands_for_prop(brand_matches, pid))
            if not prop_brands & filter_brands:
                continue

        # Owner resolution for date/price/type filters
        owner_info = _resolve_owner(prop, rt_info)
        iso = owner_info["latest_sale_date_iso"]

        # Date filter
        if sale_date_from and (not iso or iso < sale_date_from):
            continue
        if sale_date_to and (not iso or iso > sale_date_to):
            continue

        # Price filter
        if price_min is not None or price_max is not None:
            raw_price = owner_info["latest_sale_price"]
            numeric = _parse_price(raw_price)
            if numeric is None:
                continue
            if price_min is not None and numeric < price_min:
                continue
            if price_max is not None and numeric > price_max:
                continue

        # Owner type filter
        if owner_type_filter:
            owner_name = owner_info["owner"]
            if owner_name:
                norm = owner_name.upper().strip()
                gid = name_to_gid.get(norm, "")
                if gid and gid in parties:
                    ot = "company" if parties[gid].get("is_company") else "person"
                else:
                    ot = ""
                if ot != owner_type_filter:
                    continue
            else:
                continue

        # Exclude contacted
        if exclude_contacted and pid in contacted_prop_ids:
            continue

        # Exclude by owner
        if exclude_by_owner:
            owner_name = owner_info["owner"]
            if owner_name:
                norm = owner_name.upper().strip()
                gid = name_to_gid.get(norm, "")
                if gid and gid in contacted_owner_gids:
                    continue

        matching_ids.append(pid)

    items = _resolve_outreach_items(
        matching_ids, props, parties, brand_matches, rt_info, log_data,
    )
    return JSONResponse({"items": items, "total": len(items)})


def _parse_price(raw: str) -> float | None:
    """Parse price string like '$2,090,000' to float."""
    if not raw:
        return None
    cleaned = raw.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Lists CRUD
# ---------------------------------------------------------------------------

@router.get("/lists")
def get_lists():
    """Return all saved outreach lists with summary stats."""
    store = _load_lists()
    log_data = _load_log()

    # Count contacted per list
    list_contacted: dict[str, int] = {}
    for _eid, entry in log_data.get("entries", {}).items():
        lid = entry.get("list_id", "")
        if lid:
            list_contacted[lid] = list_contacted.get(lid, 0) + 1

    result = []
    for lid, lst in store["lists"].items():
        result.append({
            **lst,
            "list_id": lid,
            "contacted_count": list_contacted.get(lid, 0),
        })
    result.sort(key=lambda x: x.get("updated", ""), reverse=True)
    return JSONResponse(result)


@router.post("/lists")
async def create_list(request: Request):
    """Save a new outreach list."""
    body = await request.json()
    store = _load_lists()
    list_id = _next_id(store, "OL")
    now = _now()

    lst = {
        "name": body.get("name", "").strip(),
        "description": body.get("description", "").strip(),
        "filters": body.get("filters", {}),
        "prop_ids": body.get("prop_ids", []),
        "item_count": len(body.get("prop_ids", [])),
        "created": now,
        "updated": now,
    }
    if not lst["name"]:
        raise HTTPException(400, "Name is required")

    store["lists"][list_id] = lst
    _save_lists(store)
    _log_edit({"action": "create_list", "list_id": list_id, "data": lst})
    return {**lst, "list_id": list_id}


@router.get("/lists/{list_id}")
def get_list(list_id: str):
    """Return list detail with resolved items."""
    store = _load_lists()
    lst = store["lists"].get(list_id)
    if not lst:
        raise HTTPException(404, f"List not found: {list_id}")

    items = _resolve_outreach_items(lst.get("prop_ids", []))
    return {
        **lst,
        "list_id": list_id,
        "items": items,
    }


@router.put("/lists/{list_id}")
async def update_list(list_id: str, request: Request):
    """Update list name/description."""
    body = await request.json()
    store = _load_lists()
    lst = store["lists"].get(list_id)
    if not lst:
        raise HTTPException(404, f"List not found: {list_id}")

    changes = {}
    for field in ("name", "description"):
        if field in body:
            val = body[field].strip() if isinstance(body[field], str) else body[field]
            if val != lst.get(field):
                changes[field] = val
                lst[field] = val

    if changes:
        lst["updated"] = _now()
        _save_lists(store)
        _log_edit({"action": "update_list", "list_id": list_id, "changes": changes})

    return {**lst, "list_id": list_id}


@router.delete("/lists/{list_id}")
def delete_list(list_id: str):
    """Delete a list."""
    store = _load_lists()
    if list_id not in store["lists"]:
        raise HTTPException(404, f"List not found: {list_id}")
    deleted = store["lists"].pop(list_id)
    _save_lists(store)
    _log_edit({"action": "delete_list", "list_id": list_id, "data": deleted})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Contact logging
# ---------------------------------------------------------------------------

@router.post("/log")
async def log_contact(request: Request):
    """Log a single contact event."""
    body = await request.json()
    log_data = _load_log()
    entry_id = _next_id(log_data, "OE")
    now = _now()

    outcome = body.get("outcome", "").strip() or None
    if outcome and outcome not in VALID_OUTCOMES:
        raise HTTPException(400, f"Invalid outcome: {outcome}")

    entry = {
        "list_id": body.get("list_id", "").strip(),
        "prop_id": body.get("prop_id", "").strip(),
        "owner_group_id": body.get("owner_group_id", "").strip(),
        "method": body.get("method", "mail").strip(),
        "outcome": outcome,
        "date": body.get("date", now[:10]).strip(),
        "notes": body.get("notes", "").strip(),
        "created": now,
    }
    if not entry["prop_id"]:
        raise HTTPException(400, "prop_id is required")

    log_data["entries"][entry_id] = entry
    _save_log(log_data)
    _log_edit({"action": "log_contact", "entry_id": entry_id, "data": entry})

    # Auto-update pipeline_status if currently not_started or attempted_contact
    prop_id = entry["prop_id"]
    props = _load_properties()
    prop = props.get(prop_id, {})
    current = prop.get("pipeline_status", "not_started")
    if current in ("not_started", "attempted_contact"):
        derived = "attempted_contact"
        if outcome == "spoke_with":
            derived = "interested"
        if current != derived and (current == "not_started" or derived == "interested"):
            _set_property_pipeline_status(prop_id, derived)

    return {**entry, "entry_id": entry_id}


@router.post("/log/bulk")
async def log_contacts_bulk(request: Request):
    """Log contact events for multiple items at once."""
    body = await request.json()
    items = body.get("items", [])
    method = body.get("method", "mail").strip()
    outcome = body.get("outcome", "").strip() or None
    if outcome and outcome not in VALID_OUTCOMES:
        raise HTTPException(400, f"Invalid outcome: {outcome}")
    date = body.get("date", _now()[:10]).strip()
    list_id = body.get("list_id", "").strip()
    notes = body.get("notes", "").strip()

    if not items:
        raise HTTPException(400, "items array is required")

    log_data = _load_log()
    created_ids = []
    now = _now()

    for item in items:
        entry_id = _next_id(log_data, "OE")
        entry = {
            "list_id": list_id,
            "prop_id": item.get("prop_id", "").strip(),
            "owner_group_id": item.get("owner_group_id", "").strip(),
            "method": method,
            "outcome": outcome,
            "date": date,
            "notes": notes,
            "created": now,
        }
        log_data["entries"][entry_id] = entry
        created_ids.append(entry_id)

    _save_log(log_data)
    _log_edit({
        "action": "log_contacts_bulk",
        "entry_ids": created_ids,
        "count": len(created_ids),
        "method": method,
        "date": date,
        "list_id": list_id,
    })
    return {"ok": True, "count": len(created_ids), "entry_ids": created_ids}


# ---------------------------------------------------------------------------
# Per-property outreach status + history
# ---------------------------------------------------------------------------

VALID_PIPELINE_STATUSES = {
    "not_started",
    "attempted_contact",
    "interested",
    "listed",
    "do_not_contact",
}

# Statuses that should not be auto-downgraded by log derivation
_MANUAL_STATUSES = {"interested", "listed", "do_not_contact"}


def _derive_outreach_status(prop_id: str, log_data: dict) -> str:
    """Derive pipeline status from activity log entries for a property.

    Returns unified pipeline statuses: not_started, attempted_contact, interested.
    Checks property record pipeline_status first for manual overrides.
    Falls back to log_data status_overrides for legacy compat.
    """
    # Check property record for manual pipeline_status
    props = _load_properties()
    prop = props.get(prop_id, {})
    prop_status = prop.get("pipeline_status", "")
    if prop_status in _MANUAL_STATUSES:
        return prop_status

    # Legacy: check log_data overrides (migrate on first access)
    overrides = log_data.get("status_overrides", {})
    if prop_id in overrides:
        legacy = overrides[prop_id]
        # Map old statuses to new ones
        status_map = {
            "awaiting_response": "attempted_contact",
            "follow_up_needed": "attempted_contact",
            "engaged": "interested",
            "converted": "interested",
        }
        return status_map.get(legacy, legacy)

    # Collect entries for this property, sorted newest-first
    entries = []
    for _eid, entry in log_data.get("entries", {}).items():
        if entry.get("prop_id") == prop_id:
            entries.append(entry)
    if not entries:
        return prop_status or "not_started"

    entries.sort(key=lambda e: (e.get("date", ""), e.get("created", "")), reverse=True)

    # Derive from latest outcome
    for entry in entries:
        outcome = entry.get("outcome")
        if not outcome:
            continue
        if outcome == "spoke_with":
            return "interested"
        if outcome in ("bounced", "no_answer", "sent", "left_vm"):
            return "attempted_contact"

    # Has entries but no outcomes — default to attempted_contact
    return "attempted_contact"


@router.get("/properties/{prop_id}/history")
def property_outreach_history(prop_id: str):
    """Return all outreach entries + derived status for a property."""
    log_data = _load_log()
    status = _derive_outreach_status(prop_id, log_data)

    entries = []
    for eid, entry in log_data.get("entries", {}).items():
        if entry.get("prop_id") == prop_id:
            entries.append({**entry, "entry_id": eid})

    entries.sort(key=lambda e: (e.get("date", ""), e.get("created", "")), reverse=True)

    return {
        "prop_id": prop_id,
        "outreach_status": status,
        "entries": entries,
    }


@router.put("/properties/{prop_id}/status")
async def set_outreach_status(prop_id: str, request: Request):
    """Set pipeline_status on a property record directly."""
    body = await request.json()
    new_status = body.get("status", "").strip()
    if new_status not in VALID_PIPELINE_STATUSES:
        raise HTTPException(400, f"Invalid pipeline status: {new_status}")

    _set_property_pipeline_status(prop_id, new_status)
    _log_edit({
        "action": "set_pipeline_status",
        "prop_id": prop_id,
        "status": new_status,
    })
    return {"ok": True, "prop_id": prop_id, "pipeline_status": new_status}


@router.post("/properties/{prop_id}/convert-to-deal")
async def convert_to_deal(prop_id: str, request: Request):
    """Create a CRM deal from outreach and mark status as converted."""
    body = await request.json()

    # Create deal via CRM helpers
    from cleo.web.crm import _load_deals, _save_deals, _next_id as _crm_next_id

    deals_store = _load_deals()
    deal_id = _crm_next_id(deals_store, "D")
    now = _now()

    props = _load_properties()
    prop = props.get(prop_id, {})
    default_title = body.get("title") or f"{prop.get('address', prop_id)}, {prop.get('city', '')}"

    deal = {
        "title": default_title.strip(),
        "prop_id": prop_id,
        "stage": "active_deal",
        "source": "outreach",
        "contact_ids": body.get("contact_ids", []),
        "notes": body.get("notes", "").strip() if body.get("notes") else "",
        "created": now,
        "updated": now,
    }
    deals_store["deals"][deal_id] = deal
    _save_deals(deals_store)

    # Log the deal creation
    edit_entry = {"action": "create_deal", "deal_id": deal_id, "data": deal, "timestamp": now}
    with open(CRM_EDITS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(edit_entry, ensure_ascii=False) + "\n")

    _log_edit({
        "action": "convert_to_deal",
        "prop_id": prop_id,
        "deal_id": deal_id,
    })

    return {"ok": True, "deal_id": deal_id, "prop_id": prop_id}


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

@router.get("/lists/{list_id}/export.csv")
def export_csv(list_id: str):
    """Export list items as CSV for mail merge."""
    store = _load_lists()
    lst = store["lists"].get(list_id)
    if not lst:
        raise HTTPException(404, f"List not found: {list_id}")

    items = _resolve_outreach_items(lst.get("prop_ids", []))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Property Address",
        "City",
        "Brands",
        "Latest Sale Date",
        "Latest Sale Price",
        "Owner Name",
        "Owner Type",
        "Corporate Address",
        "Contact Name",
        "Contact Phone",
        "Contact Method",
        "Contact Outcome",
        "Contact Date",
    ])

    for item in items:
        cs = item.get("contact_status")
        writer.writerow([
            item.get("address", ""),
            item.get("city", ""),
            ", ".join(item.get("brands", [])),
            item.get("latest_sale_date", ""),
            item.get("latest_sale_price", ""),
            item.get("owner", ""),
            item.get("owner_type", ""),
            item.get("corporate_address", ""),
            ", ".join(item.get("contact_names", [])),
            ", ".join(item.get("phones", [])),
            cs["method"] if cs else "",
            cs.get("outcome", "") or "" if cs else "",
            cs["date"] if cs else "",
        ])

    output.seek(0)
    safe_name = lst.get("name", "outreach").replace(" ", "_")[:40]
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.csv"'},
    )
