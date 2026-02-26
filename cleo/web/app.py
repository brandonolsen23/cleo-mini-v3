"""Cleo review web app — compare HTML source, active, and sandbox."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from cleo.config import HTML_DIR, PARSED_DIR, DATA_DIR, EXTRACT_REVIEWS_PATH, GEOCODE_CACHE_PATH, PROPERTIES_PATH, PROPERTY_EDITS_PATH, FEEDBACK_PATH, PARTIES_PATH, PARTY_EDITS_PATH, KEYWORDS_PATH, BRAND_MATCHES_PATH, BRANDS_DATA_DIR, MARKETS_PATH, GW_PARSED_DIR, OPERATORS_REGISTRY_PATH, CRM_DEALS_PATH, PARCELS_PATH, PARCELS_MATCHES_PATH
from cleo.ingest.html_index import HtmlIndex
from cleo.parse.versioning import active_dir, active_version, sandbox_path, sandbox_exists, list_versions, VOLATILE_FIELDS
from cleo.extract import versioning as extract_ver
from cleo.web.crm import router as crm_router
from cleo.web.operators import router as operators_router
from cleo.web.outreach import router as outreach_router

app = FastAPI(title="Cleo Review")
app.include_router(crm_router)
app.include_router(operators_router)
app.include_router(outreach_router)

STATIC_DIR = Path(__file__).parent / "static"
REVIEWS_PATH = DATA_DIR / "reviews.json"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    from fastapi.responses import HTMLResponse as HR
    content = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HR(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline():
    from fastapi.responses import HTMLResponse as HR
    content = (STATIC_DIR / "pipeline.html").read_text(encoding="utf-8")
    return HR(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/party-review", response_class=HTMLResponse)
def party_review():
    from fastapi.responses import HTMLResponse as HR
    content = (STATIC_DIR / "party_review.html").read_text(encoding="utf-8")
    return HR(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/api/party-review-page", response_class=HTMLResponse)
def party_review_page():
    """Alias under /api/ so the React app can link here without Vite intercepting."""
    from fastapi.responses import HTMLResponse as HR
    content = (STATIC_DIR / "party_review.html").read_text(encoding="utf-8")
    return HR(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

@app.get("/api/status")
def api_status():
    ext_store = extract_ver.store
    return {
        "active_version": active_version(),
        "versions": list_versions(),
        "has_sandbox": sandbox_exists(),
        "extract_active_version": ext_store.active_version(),
        "extract_has_sandbox": ext_store.sandbox_path().is_dir(),
    }


@app.get("/api/rt-ids")
def api_rt_ids():
    """List all RT IDs with their flags."""
    html_flags = _load_json(DATA_DIR / "html_flags.json")
    parse_flags = _load_json(DATA_DIR / "parse_flags.json")

    act = active_dir()
    if act is None:
        raise HTTPException(404, "No active version")

    rt_ids = sorted(
        f.stem for f in act.glob("*.json") if f.stem != "_meta"
    )

    reviews = _load_json(REVIEWS_PATH)

    records = []
    for rt_id in rt_ids:
        h = html_flags.get(rt_id, [])
        p = parse_flags.get(rt_id, [])
        reviewed = rt_id in reviews
        records.append({
            "rt_id": rt_id,
            "html_flags": h,
            "parse_flags": p,
            "flagged": bool(h or p),
            "reviewed": reviewed,
            "determination": reviews.get(rt_id, {}).get("determination", ""),
        })

    return records


# ---------------------------------------------------------------------------
# Markets (static population lookup, cached by mtime)
# ---------------------------------------------------------------------------

_markets_cache: dict[str, int] | None = None
_markets_cache_mtime: float = 0


def _get_markets() -> dict[str, int]:
    """Load markets.json and return upper(city) -> population lookup."""
    global _markets_cache, _markets_cache_mtime
    if not MARKETS_PATH.exists():
        return {}
    mtime = MARKETS_PATH.stat().st_mtime
    if _markets_cache is not None and _markets_cache_mtime == mtime:
        return _markets_cache
    data = _load_json(MARKETS_PATH)
    _markets_cache = {
        k.upper(): v["population"]
        for k, v in data.get("markets", {}).items()
    }
    _markets_cache_mtime = mtime
    return _markets_cache


def _lookup_population(city: str) -> int | None:
    """Return population for a city name, or None if not found."""
    if not city:
        return None
    markets = _get_markets()
    return markets.get(city.upper().strip())


# ---------------------------------------------------------------------------
# Brands (loaded once, cached by mtime)
# ---------------------------------------------------------------------------

_brand_matches_cache: dict | None = None
_brand_matches_mtime: float = 0


def _get_brand_matches() -> dict:
    """Load brand_matches.json: {prop_id: [{brand, ...}]}."""
    global _brand_matches_cache, _brand_matches_mtime
    if not BRAND_MATCHES_PATH.exists():
        return {}
    mtime = BRAND_MATCHES_PATH.stat().st_mtime
    if _brand_matches_cache is not None and _brand_matches_mtime == mtime:
        return _brand_matches_cache
    _brand_matches_cache = _load_json(BRAND_MATCHES_PATH)
    _brand_matches_mtime = mtime
    return _brand_matches_cache


def _brands_for_prop(prop_id: str) -> list[str]:
    """Return sorted unique brand names for a property."""
    matches = _get_brand_matches()
    entries = matches.get(prop_id, [])
    return sorted(set(e["brand"] for e in entries))


def _operators_for_prop(prop_id: str) -> list[dict]:
    """Return linked operators for a property (confirmed matches)."""
    if not OPERATORS_REGISTRY_PATH.exists():
        return []
    try:
        from cleo.operators.registry import load_registry as load_op_reg
        reg = load_op_reg()
        result = []
        for op_id, op in reg.get("operators", {}).items():
            for m in op.get("property_matches", []):
                if m.get("prop_id") == prop_id and m.get("status") == "confirmed":
                    result.append({
                        "op_id": op_id,
                        "name": op.get("name", ""),
                        "slug": op.get("slug", ""),
                        "url": op.get("url", ""),
                    })
                    break
        return result
    except Exception:
        return []


def _operators_for_party(group_id: str) -> list[dict]:
    """Return linked operators for a party group (confirmed matches)."""
    if not OPERATORS_REGISTRY_PATH.exists():
        return []
    try:
        from cleo.operators.registry import load_registry as load_op_reg
        reg = load_op_reg()
        result = []
        for op_id, op in reg.get("operators", {}).items():
            for m in op.get("party_matches", []):
                if m.get("group_id") == group_id and m.get("status") == "confirmed":
                    result.append({
                        "op_id": op_id,
                        "name": op.get("name", ""),
                        "slug": op.get("slug", ""),
                        "url": op.get("url", ""),
                    })
                    break
        return result
    except Exception:
        return []


def _build_rt_to_brands(properties: dict) -> dict[str, list[str]]:
    """Build rt_id -> brands lookup from property registry + brand matches."""
    matches = _get_brand_matches()
    rt_brands: dict[str, list[str]] = {}
    for pid, entries in matches.items():
        brands = sorted(set(e["brand"] for e in entries))
        prop = properties.get(pid, {})
        for rt_id in prop.get("rt_ids", []):
            rt_brands[rt_id] = brands
    return rt_brands


# ---------------------------------------------------------------------------
# Brands endpoint (front-facing app)
# ---------------------------------------------------------------------------

_brands_cache: list | None = None
_brands_cache_mtime: float = 0


@app.get("/api/brands")
def api_brands():
    """Return all brand store locations with property linkage."""
    global _brands_cache, _brands_cache_mtime

    # Check cache freshness (keyed on brand_matches.json mtime)
    matches_mtime = BRAND_MATCHES_PATH.stat().st_mtime if BRAND_MATCHES_PATH.exists() else 0
    if _brands_cache is not None and _brands_cache_mtime == matches_mtime:
        return JSONResponse(_brands_cache)

    # Load all brand store JSON files
    stores: list[dict] = []
    if BRANDS_DATA_DIR.exists():
        for path in sorted(BRANDS_DATA_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            stores.extend(data)

    # Load brand matches and property registry
    matches = _get_brand_matches()
    # Build reverse lookup: (address_upper, city_upper, brand_upper) -> prop_id
    store_to_prop: dict[tuple[str, str, str], str] = {}
    for pid, entries in matches.items():
        for e in entries:
            key = (
                e.get("address", "").upper().strip(),
                e.get("city", "").upper().strip(),
                e.get("brand", "").upper().strip(),
            )
            store_to_prop[key] = pid

    # Load property registry for transaction counts
    props: dict = {}
    if PROPERTIES_PATH.exists():
        from cleo.properties.registry import load_registry
        reg = load_registry(PROPERTIES_PATH)
        props = reg.get("properties", {})

    records = []
    for store in stores:
        addr = store.get("address", "")
        city = store.get("city", "")
        brand = store.get("brand", "")
        lookup_key = (addr.upper().strip(), city.upper().strip(), brand.upper().strip())
        pid = store_to_prop.get(lookup_key)
        prop = props.get(pid, {}) if pid else {}
        rt_ids = prop.get("rt_ids", [])
        records.append({
            "brand": brand,
            "store_name": store.get("store_name", ""),
            "address": addr,
            "city": city,
            "province": store.get("province", ""),
            "postal_code": store.get("postal_code", ""),
            "lat": store.get("lat"),
            "lng": store.get("lng"),
            "prop_id": pid,
            "has_transactions": bool(rt_ids),
            "transaction_count": len(rt_ids),
        })

    _brands_cache = records
    _brands_cache_mtime = matches_mtime
    return JSONResponse(records)


# ---------------------------------------------------------------------------
# Full-record search text helper
# ---------------------------------------------------------------------------


def _build_record_search_text(data: dict) -> str:
    """Concatenate all searchable fields from a parsed RT record into one string.

    This powers the "pool of info" search: any text in the record — party names,
    alternate names, contacts, phones, addresses, PINs, description, broker, etc.
    — becomes searchable from the frontend global filter.
    """
    parts: list[str] = []

    # Transaction-level fields
    tx = data.get("transaction", {})
    addr = tx.get("address", {})
    parts.append(data.get("rt_id", ""))
    parts.append(addr.get("address", ""))
    parts.append(addr.get("city", ""))
    parts.append(addr.get("municipality", ""))
    parts.append(addr.get("postal_code", ""))
    parts.append(addr.get("address_suite", ""))
    for alt in addr.get("alternate_addresses", []):
        parts.append(alt)
    parts.append(tx.get("sale_price", ""))
    parts.append(tx.get("arn", ""))
    for pin in tx.get("pins", []):
        parts.append(pin)

    # Description (building type, tenants, SF, lease info)
    parts.append(data.get("description", ""))

    # Broker
    broker = data.get("broker", {})
    parts.append(broker.get("brokerage", ""))
    parts.append(broker.get("phone", ""))

    # Site
    site = data.get("site", {})
    parts.append(site.get("legal_description", ""))
    parts.append(site.get("zoning", ""))
    for pin in site.get("pins", []):
        parts.append(pin)

    # Consideration (chargees = lender names)
    consideration = data.get("consideration", {})
    for ch in consideration.get("chargees", []):
        parts.append(ch)

    # Both parties
    for role_key in ("transferor", "transferee"):
        party = data.get(role_key, {})
        if not party:
            continue
        parts.append(party.get("name", ""))
        parts.append(party.get("contact", ""))
        parts.append(party.get("attention", ""))
        parts.append(party.get("phone", ""))
        parts.append(party.get("address", ""))
        for v in party.get("alternate_names", []):
            parts.append(v)
        for v in party.get("aliases", []):
            parts.append(v)
        for v in party.get("company_lines", []):
            parts.append(v)
        for v in party.get("contact_lines", []):
            parts.append(v)
        for v in party.get("phones", []):
            parts.append(v)
        for v in party.get("address_lines", []):
            parts.append(v)
        for v in party.get("officer_titles", []):
            parts.append(v)

    # Join with space, lowercase for case-insensitive matching
    return " ".join(p for p in parts if p).lower()


def _calculate_ppsf(sale_price: str, building_sf: str) -> str | None:
    """Return formatted price-per-square-foot like '$542', or None."""
    if not sale_price or not building_sf:
        return None
    try:
        price = float(sale_price.replace("$", "").replace(",", ""))
        sf = float(building_sf.replace(",", ""))
        if sf <= 0 or price <= 0:
            return None
        ppsf = price / sf
        return f"${ppsf:,.0f}"
    except (ValueError, ZeroDivisionError):
        return None


# ---------------------------------------------------------------------------
# Party name -> group_id reverse index (cached)
# ---------------------------------------------------------------------------

_name_to_gid_cache: dict[str, str] | None = None
_name_to_gid_mtime: float = 0.0


def _get_name_to_gid() -> dict[str, str]:
    """Return a cached name -> group_id reverse index from the party registry."""
    global _name_to_gid_cache, _name_to_gid_mtime

    if not PARTIES_PATH.exists():
        return {}

    mtime = PARTIES_PATH.stat().st_mtime
    if _name_to_gid_cache is not None and _name_to_gid_mtime == mtime:
        return _name_to_gid_cache

    from cleo.parties.registry import load_registry as load_party_registry
    reg = load_party_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    idx: dict[str, str] = {}
    for gid, p in parties_data.items():
        for name in p.get("normalized_names", []):
            idx[name] = gid
        for name in p.get("names", []):
            idx[name.upper().strip()] = gid
    _name_to_gid_cache = idx
    _name_to_gid_mtime = mtime
    return idx


def _lookup_group_id(party_name: str) -> str | None:
    """Look up the party group_id for a given name string."""
    if not party_name:
        return None
    idx = _get_name_to_gid()
    # Try uppercase match (matches the raw names index)
    gid = idx.get(party_name.upper().strip())
    if gid:
        return gid
    # Try normalized match
    from cleo.parties.normalize import normalize_name
    return idx.get(normalize_name(party_name))


def _make_contact_id(contact_name: str) -> str | None:
    """Return normalized contact_id for a contact person name, or None."""
    if not contact_name or not contact_name.strip():
        return None
    from cleo.parties.normalize import normalize_contact
    return normalize_contact(contact_name)


# ---------------------------------------------------------------------------
# Transactions (front-facing app)
# ---------------------------------------------------------------------------

_transactions_cache: list | None = None
_transactions_cache_version: str | None = None


@app.get("/api/transactions")
def api_transactions():
    """Return summary array for all parsed records (cached per active version)."""
    global _transactions_cache, _transactions_cache_version

    ver = active_version()
    if ver is None:
        raise HTTPException(404, "No active version")

    if _transactions_cache is not None and _transactions_cache_version == ver:
        return JSONResponse(_transactions_cache)

    act = active_dir()

    # Build rt_id -> brands lookup
    rt_brands: dict[str, list[str]] = {}
    if PROPERTIES_PATH.exists():
        from cleo.properties.registry import load_registry
        reg = load_registry(PROPERTIES_PATH)
        rt_brands = _build_rt_to_brands(reg.get("properties", {}))

    records = []
    for f in sorted(act.glob("*.json")):
        if f.stem == "_meta":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        rt_id = data.get("rt_id", f.stem)
        tx = data.get("transaction", {})
        addr = tx.get("address", {})
        city = addr.get("city", "")
        records.append({
            "rt_id": rt_id,
            "address": addr.get("address", ""),
            "city": city,
            "municipality": addr.get("municipality", ""),
            "population": _lookup_population(city),
            "sale_price": tx.get("sale_price", ""),
            "sale_date": tx.get("sale_date", ""),
            "sale_date_iso": tx.get("sale_date_iso", ""),
            "seller": data.get("transferor", {}).get("name", ""),
            "buyer": data.get("transferee", {}).get("name", ""),
            "seller_group_id": _lookup_group_id(data.get("transferor", {}).get("name", "")),
            "buyer_group_id": _lookup_group_id(data.get("transferee", {}).get("name", "")),
            "building_sf": data.get("export_extras", {}).get("building_sf", ""),
            "site_area": data.get("site", {}).get("site_area", ""),
            "ppsf": _calculate_ppsf(tx.get("sale_price", ""), data.get("export_extras", {}).get("building_sf", "")),
            "has_photos": bool(data.get("photos")),
            "brands": rt_brands.get(rt_id, []),
            "_search_text": _build_record_search_text(data),
        })

    _transactions_cache = records
    _transactions_cache_version = ver
    return JSONResponse(records)


# ---------------------------------------------------------------------------
# Contacts (front-facing app)
# ---------------------------------------------------------------------------

_contacts_cache: list | None = None
_contacts_cache_version: str | None = None


def _build_contacts_index() -> list[dict]:
    """Scan all parsed JSONs and group by normalized contact name.

    Indexes both the ``contact`` and ``attention`` fields.  When ``attention``
    differs from ``contact`` and looks like a person name (not a company), it
    is indexed as a separate contact entry.
    """
    from cleo.parties.normalize import normalize_contact
    from cleo.parties.registry import _is_company_name

    act = active_dir()
    if act is None:
        return []

    # contact_id -> { raw_names: Counter, phones: set, roles: Counter,
    #                  dates: list, entities: set, alt_entities: set,
    #                  appearances: list }
    from collections import Counter
    contacts: dict[str, dict] = {}

    def _add_contact(
        cid: str, raw_name: str, role_label: str, entity_name: str,
        phone: str, party_address: str, rt_id: str, sale_date_iso: str,
        sale_price: str, prop_address: str, prop_city: str, phones: list[str],
        alt_names: list[str] | None = None,
    ):
        if cid not in contacts:
            contacts[cid] = {
                "raw_names": Counter(),
                "phones": set(),
                "addresses": set(),
                "roles": Counter(),
                "dates": [],
                "entities": set(),
                "alt_entities": set(),
                "appearances": [],
            }
        c = contacts[cid]
        c["raw_names"][raw_name] += 1
        c["roles"][role_label] += 1
        if entity_name:
            c["entities"].add(entity_name)
        if phone:
            c["phones"].add(phone)
        for p in phones:
            if p and p.strip():
                c["phones"].add(p.strip())
        for an in (alt_names or []):
            if an and an.strip():
                c["alt_entities"].add(an.strip())
        if party_address:
            c["addresses"].add(party_address)
        if sale_date_iso:
            c["dates"].append(sale_date_iso)
        c["appearances"].append({
            "rt_id": rt_id,
            "role": role_label,
            "entity_name": entity_name,
            "sale_date_iso": sale_date_iso,
            "sale_price": sale_price,
            "prop_address": prop_address,
            "prop_city": prop_city,
            "phone": phone,
            "address": party_address,
        })

    for f in act.glob("*.json"):
        if f.stem == "_meta":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        rt_id = data.get("rt_id", f.stem)
        tx = data.get("transaction", {})
        addr = tx.get("address", {})
        sale_date_iso = tx.get("sale_date_iso", "")
        sale_price = tx.get("sale_price", "")
        prop_address = addr.get("address", "")
        prop_city = addr.get("city", "")

        for role_key, role_label in [("transferor", "seller"), ("transferee", "buyer")]:
            party = data.get(role_key, {})
            if not party:
                continue

            entity_name = party.get("name", "")
            phone = (party.get("phone") or "").strip()
            phones = party.get("phones", [])
            party_address = (party.get("address") or "").strip()
            alt_names = party.get("alternate_names", [])

            # Primary source: contact_lines (all person names on this party)
            contact_lines = party.get("contact_lines", [])

            # Dedupe by normalized name
            seen_cids: set[str] = set()
            names_to_index: list[str] = []

            for line in contact_lines:
                line = line.strip()
                if not line:
                    continue
                ncid = normalize_contact(line)
                if ncid and ncid not in seen_cids:
                    seen_cids.add(ncid)
                    names_to_index.append(line)

            # Fallback: if contact_lines was empty, use contact/attention
            if not names_to_index:
                contact_raw = (party.get("contact") or "").strip()
                attention_raw = (party.get("attention") or "").strip()
                if contact_raw:
                    ncid = normalize_contact(contact_raw)
                    if ncid and ncid not in seen_cids:
                        seen_cids.add(ncid)
                        names_to_index.append(contact_raw)
                if attention_raw and not _is_company_name(attention_raw):
                    ncid = normalize_contact(attention_raw)
                    if ncid and ncid not in seen_cids:
                        seen_cids.add(ncid)
                        names_to_index.append(attention_raw)

            for raw_name in names_to_index:
                cid = normalize_contact(raw_name)
                if not cid:
                    continue
                _add_contact(
                    cid, raw_name, role_label, entity_name,
                    phone, party_address, rt_id, sale_date_iso,
                    sale_price, prop_address, prop_city, phones,
                    alt_names=alt_names,
                )

    # Build summary list
    result = []
    for cid, c in contacts.items():
        dates = sorted(d for d in c["dates"] if d)
        entities = sorted(c["entities"])
        # Alt entities that aren't already in the primary entity list
        alt_entities = sorted(c["alt_entities"] - c["entities"])
        # Build search text: all entities, alt entities, addresses, phones, raw names
        search_parts = [cid]
        search_parts.extend(c["raw_names"].keys())
        search_parts.extend(entities)
        search_parts.extend(alt_entities)
        search_parts.extend(c["phones"])
        search_parts.extend(c["addresses"])
        contact_search_text = " ".join(s for s in search_parts if s).lower()

        result.append({
            "contact_id": cid,
            "name": c["raw_names"].most_common(1)[0][0],
            "transaction_count": len(c["appearances"]),
            "entity_count": len(entities),
            "phones": sorted(c["phones"]),
            "roles": {"buyer": c["roles"].get("buyer", 0), "seller": c["roles"].get("seller", 0)},
            "first_active_iso": dates[0] if dates else "",
            "last_active_iso": dates[-1] if dates else "",
            "sample_entities": entities[:3],
            "alt_entities": alt_entities,
            "_search_text": contact_search_text,
        })

    result.sort(key=lambda x: x["transaction_count"], reverse=True)
    return result


@app.get("/api/contacts")
def api_contacts():
    """Return summary array for all contacts (cached per active version)."""
    global _contacts_cache, _contacts_cache_version

    ver = active_version()
    if ver is None:
        raise HTTPException(404, "No active version")

    if _contacts_cache is not None and _contacts_cache_version == ver:
        return JSONResponse(_contacts_cache)

    _contacts_cache = _build_contacts_index()
    _contacts_cache_version = ver
    return JSONResponse(_contacts_cache)


@app.get("/api/contacts/{contact_id:path}")
def api_contact_detail(contact_id: str):
    """Return full detail for a single contact."""
    from cleo.parties.normalize import normalize_contact
    from urllib.parse import unquote

    contact_id = unquote(contact_id).strip()
    cid = normalize_contact(contact_id)

    act = active_dir()
    if act is None:
        raise HTTPException(404, "No active version")

    # Build the full index and find the contact
    # Use cached summary to verify existence, then scan for full data
    global _contacts_cache, _contacts_cache_version
    ver = active_version()
    if _contacts_cache is None or _contacts_cache_version != ver:
        _contacts_cache = _build_contacts_index()
        _contacts_cache_version = ver

    # Check contact exists
    summary = None
    for s in _contacts_cache:
        if s["contact_id"] == cid:
            summary = s
            break
    if summary is None:
        raise HTTPException(404, f"Contact not found: {contact_id}")

    # Build full appearances by re-scanning (we need full data)
    from collections import Counter
    from cleo.parties.registry import _is_company_name
    raw_names: Counter = Counter()
    phones: set = set()
    addresses: set = set()
    roles: Counter = Counter()
    dates: list = []
    entities: set = set()
    appearances: list = []

    for f in act.glob("*.json"):
        if f.stem == "_meta":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        rt_id = data.get("rt_id", f.stem)
        tx = data.get("transaction", {})
        addr = tx.get("address", {})
        sale_date_iso = tx.get("sale_date_iso", "")
        sale_price = tx.get("sale_price", "")
        prop_address = addr.get("address", "")
        prop_city = addr.get("city", "")

        for role_key, role_label in [("transferor", "seller"), ("transferee", "buyer")]:
            party = data.get(role_key, {})
            if not party:
                continue

            # Check contact_lines first, then fallback to contact/attention
            contact_lines = party.get("contact_lines", [])
            matched_name = None
            for line in contact_lines:
                line = line.strip()
                if line and normalize_contact(line) == cid:
                    matched_name = line
                    break

            if not matched_name and not contact_lines:
                contact_raw = (party.get("contact") or "").strip()
                attention_raw = (party.get("attention") or "").strip()
                if contact_raw and normalize_contact(contact_raw) == cid:
                    matched_name = contact_raw
                elif attention_raw and normalize_contact(attention_raw) == cid and not _is_company_name(attention_raw):
                    matched_name = attention_raw

            if not matched_name:
                continue

            raw_names[matched_name] += 1
            roles[role_label] += 1

            entity_name = party.get("name", "")
            if entity_name:
                entities.add(entity_name)

            phone = (party.get("phone") or "").strip()
            if phone:
                phones.add(phone)
            for p in party.get("phones", []):
                if p and p.strip():
                    phones.add(p.strip())

            party_address = (party.get("address") or "").strip()
            if party_address:
                addresses.add(party_address)

            if sale_date_iso:
                dates.append(sale_date_iso)

            appearances.append({
                "rt_id": rt_id,
                "role": role_label,
                "entity_name": entity_name,
                "sale_date_iso": sale_date_iso,
                "sale_price": sale_price,
                "prop_address": prop_address,
                "prop_city": prop_city,
                "phone": phone,
                "address": party_address,
            })

    appearances.sort(key=lambda x: x.get("sale_date_iso", ""), reverse=True)
    sorted_dates = sorted(d for d in dates if d)
    sorted_entities = sorted(entities)

    # Cross-reference party registry
    party_groups: list[dict] = []
    if PARTIES_PATH.exists():
        from cleo.parties.registry import load_registry as load_party_registry
        reg = load_party_registry(PARTIES_PATH)
        parties_data = reg.get("parties", {})

        # Find groups containing any of the contact's entities
        entity_norms = {e.upper().strip() for e in entities}
        for gid, p in parties_data.items():
            group_norms = {n.upper().strip() for n in p.get("names", [])}
            if entity_norms & group_norms:
                party_groups.append({
                    "group_id": gid,
                    "display_name": p.get("display_name_override") or p.get("display_name", ""),
                    "transaction_count": p.get("transaction_count", 0),
                })

    return {
        "contact_id": cid,
        "name": raw_names.most_common(1)[0][0] if raw_names else contact_id,
        "phones": sorted(phones),
        "addresses": sorted(addresses),
        "transaction_count": len(appearances),
        "entity_count": len(sorted_entities),
        "first_active_iso": sorted_dates[0] if sorted_dates else "",
        "last_active_iso": sorted_dates[-1] if sorted_dates else "",
        "appearances": appearances,
        "entities": sorted_entities,
        "party_groups": party_groups,
    }


# ---------------------------------------------------------------------------
# GeoWarehouse helpers
# ---------------------------------------------------------------------------

def _get_gw_active_dir():
    """Return the active GW parsed directory, or None."""
    from cleo.versioning import VersionedStore
    store = VersionedStore(base_dir=GW_PARSED_DIR)
    return store.active_dir()


# ---------------------------------------------------------------------------
# Properties (front-facing app)
# ---------------------------------------------------------------------------

_properties_cache: list | None = None
_properties_cache_mtime: float = 0

_DEAL_STAGE_PRIORITY = {
    "active_deal": 0,
    "in_negotiation": 1,
    "under_contract": 2,
    # legacy stages treated as active
    "qualifying": 0,
    "negotiating": 1,
    "lead": 0,
    "contacted": 0,
}
_DEAL_CLOSED_STAGES = {"closed_won", "lost_cancelled", "closed_lost"}


def _build_prop_deal_stage_lookup() -> dict[str, str]:
    """Scan deals and return {prop_id: best_deal_stage}.

    Priority: active (non-closed) deals first (by pipeline order),
    then closed deals.
    """
    if not CRM_DEALS_PATH.exists():
        return {}
    deals = json.loads(CRM_DEALS_PATH.read_text(encoding="utf-8")).get("deals", {})
    result: dict[str, str] = {}
    for _did, d in deals.items():
        pid = d.get("prop_id", "")
        stage = d.get("stage", "")
        if not pid or not stage:
            continue
        existing = result.get(pid)
        if existing is None:
            result[pid] = stage
            continue
        # Active beats closed
        existing_closed = existing in _DEAL_CLOSED_STAGES
        new_closed = stage in _DEAL_CLOSED_STAGES
        if existing_closed and not new_closed:
            result[pid] = stage
        elif not existing_closed and not new_closed:
            # Both active — prefer higher priority (lower number)
            if _DEAL_STAGE_PRIORITY.get(stage, 99) < _DEAL_STAGE_PRIORITY.get(existing, 99):
                result[pid] = stage
    return result


def _derive_pin_status(pipeline_status: str, deal_stage: str | None) -> str:
    """Derive the single pin_status for map coloring.

    Priority: do_not_contact > active deal stage > closed deal > pipeline_status
    """
    if pipeline_status == "do_not_contact":
        return "do_not_contact"
    if deal_stage:
        return deal_stage
    return pipeline_status or "not_started"


@app.get("/api/properties")
def api_properties():
    """Return property registry as a summary array for the front-facing app."""
    global _properties_cache, _properties_cache_mtime

    if not PROPERTIES_PATH.exists():
        raise HTTPException(404, "Property registry not built. Run: cleo properties")

    mtime = PROPERTIES_PATH.stat().st_mtime
    if _properties_cache is not None and _properties_cache_mtime == mtime:
        return JSONResponse(_properties_cache)

    from cleo.properties.registry import load_registry
    from cleo.parcels.store import ParcelStore
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    # Load parcel property mapping for parcel_id lookup
    parcel_store = ParcelStore()
    prop_to_parcel: dict[str, str] = parcel_store.property_to_parcel

    # Scan parsed files for photos, dates, and prices per RT ID
    act = active_dir()
    rt_with_photos: set[str] = set()
    rt_primary_photo: dict[str, str] = {}  # rt_id -> first photo URL
    rt_info: dict[str, dict] = {}
    if act:
        for f in act.glob("*.json"):
            if f.stem == "_meta":
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
            rt_id = data.get("rt_id", f.stem)
            if data.get("photos"):
                rt_with_photos.add(rt_id)
                rt_primary_photo[rt_id] = data["photos"][0]
            tx = data.get("transaction", {})
            rt_info[rt_id] = {
                "sale_date": tx.get("sale_date", ""),
                "sale_date_iso": tx.get("sale_date_iso", ""),
                "sale_price": tx.get("sale_price", ""),
                "buyer": data.get("transferee", {}).get("name", ""),
                "buyer_contact": data.get("transferee", {}).get("contact", ""),
                "buyer_phone": data.get("transferee", {}).get("phone", ""),
                "search_text": _build_record_search_text(data),
            }

    # Build deal stage lookup for pin coloring
    prop_deal_stages = _build_prop_deal_stage_lookup()

    records = []
    for pid, prop in props.items():
        rt_ids = prop.get("rt_ids", [])
        # Compute date/price summaries from linked transactions
        years = []
        latest_price = ""
        latest_iso = ""
        latest_date = ""
        owner = ""
        owner_contact = ""
        owner_phone = ""
        primary_photo = ""
        for rt_id in rt_ids:
            info = rt_info.get(rt_id)
            if not info:
                continue
            iso = info["sale_date_iso"]
            if iso and len(iso) >= 4:
                years.append(iso[:4])
                if iso > latest_iso:
                    latest_iso = iso
                    latest_date = info["sale_date"]
                    latest_price = info["sale_price"]
                    owner = info["buyer"]
                    owner_contact = info["buyer_contact"]
                    owner_phone = info["buyer_phone"]
        # Primary photo: prefer latest transaction with photos, fall back to any
        for rt_id in sorted(rt_ids, key=lambda r: rt_info.get(r, {}).get("sale_date_iso", ""), reverse=True):
            if rt_id in rt_primary_photo:
                primary_photo = rt_primary_photo[rt_id]
                break
        prop_city = prop.get("city", "")
        # Aggregate search text from all linked transactions
        search_parts = [pid, prop.get("address", ""), prop_city,
                        prop.get("municipality", ""), prop.get("postal_code", "")]
        for rt_id in rt_ids:
            info = rt_info.get(rt_id)
            if info:
                search_parts.append(info.get("search_text", ""))
            search_parts.append(rt_id)
        prop_search_text = " ".join(p for p in search_parts if p).lower()

        pipeline_status = prop.get("pipeline_status", "not_started")
        deal_stage = prop_deal_stages.get(pid)
        pin_status = _derive_pin_status(pipeline_status, deal_stage)

        records.append({
            "prop_id": pid,
            "address": prop.get("address", ""),
            "city": prop_city,
            "municipality": prop.get("municipality", ""),
            "population": _lookup_population(prop_city),
            "province": prop.get("province", ""),
            "postal_code": prop.get("postal_code", ""),
            "lat": prop.get("lat"),
            "lng": prop.get("lng"),
            "transaction_count": prop.get("transaction_count", len(rt_ids)),
            "rt_ids": rt_ids,
            "sources": prop.get("sources", []),
            "has_photos": any(rt in rt_with_photos for rt in rt_ids),
            "primary_photo": primary_photo or None,
            "latest_sale_year": max(years) if years else "",
            "earliest_sale_year": min(years) if years else "",
            "latest_sale_date": latest_date,
            "latest_sale_date_iso": latest_iso,
            "latest_sale_price": latest_price,
            "owner": owner,
            "has_contact": bool(owner_contact),
            "has_phone": bool(owner_phone),
            "brands": _brands_for_prop(pid),
            "building_sf": prop.get("building_sf", ""),
            "site_area": prop.get("site_area", ""),
            "has_gw_data": bool(prop.get("gw_ids")),
            "pipeline_status": pipeline_status,
            "pin_status": pin_status,
            "parcel_id": prop_to_parcel.get(pid),
            "parcel_group_size": len(prop.get("parcel_group", [])) + 1,
            "_search_text": prop_search_text,
        })

    _properties_cache = records
    _properties_cache_mtime = mtime
    return JSONResponse(records)


@app.get("/api/properties/{prop_id}")
def api_property_detail(prop_id: str):
    """Return full detail for a single property, including linked transaction summaries."""
    if not PROPERTIES_PATH.exists():
        raise HTTPException(404, "Property registry not built. Run: cleo properties")

    from cleo.properties.registry import load_registry
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    if prop_id not in props:
        raise HTTPException(404, f"Property not found: {prop_id}")

    prop = props[prop_id]

    # Load transaction summaries for linked RT IDs
    act = active_dir()
    transactions = []
    if act:
        for rt_id in prop.get("rt_ids", []):
            f = act / f"{rt_id}.json"
            if not f.exists():
                continue
            data = json.loads(f.read_text(encoding="utf-8"))
            tx = data.get("transaction", {})
            bsf = data.get("export_extras", {}).get("building_sf", "")
            transactions.append({
                "rt_id": rt_id,
                "sale_price": tx.get("sale_price", ""),
                "sale_date": tx.get("sale_date", ""),
                "sale_date_iso": tx.get("sale_date_iso", ""),
                "seller": data.get("transferor", {}).get("name", ""),
                "buyer": data.get("transferee", {}).get("name", ""),
                "seller_group_id": _lookup_group_id(data.get("transferor", {}).get("name", "")),
                "buyer_group_id": _lookup_group_id(data.get("transferee", {}).get("name", "")),
                "buyer_contact": data.get("transferee", {}).get("contact", ""),
                "buyer_contact_id": _make_contact_id(data.get("transferee", {}).get("contact", "")),
                "buyer_phone": data.get("transferee", {}).get("phone", ""),
                "building_sf": bsf,
                "ppsf": _calculate_ppsf(tx.get("sale_price", ""), bsf),
                "photos": data.get("photos", []),
            })

    transactions.sort(key=lambda t: t.get("sale_date_iso", ""), reverse=True)

    # Load GW records for this property
    gw_records = []
    gw_ids = prop.get("gw_ids", [])
    if gw_ids:
        gw_dir = _get_gw_active_dir()
        if gw_dir:
            for gw_id in gw_ids:
                gw_path = gw_dir / f"{gw_id}.json"
                if gw_path.exists():
                    gw_records.append(json.loads(gw_path.read_text(encoding="utf-8")))

    # Load linked operators
    linked_operators = _operators_for_prop(prop_id)

    return {
        **prop,
        "prop_id": prop_id,
        "transactions": transactions,
        "brands": _brands_for_prop(prop_id),
        "gw_records": gw_records,
        "linked_operators": linked_operators,
    }


def _log_property_edit(entry: dict) -> None:
    """Append an edit entry to the property edits JSONL audit log."""
    entry["timestamp"] = datetime.now().isoformat(timespec="seconds")
    with open(PROPERTY_EDITS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@app.patch("/api/properties/{prop_id}")
async def api_update_property(prop_id: str, request: Request):
    """Update address/location fields on a property.

    Body: any subset of {address, city, municipality, province, postal_code, lat, lng}
    """
    global _properties_cache, _properties_cache_mtime

    if not PROPERTIES_PATH.exists():
        raise HTTPException(404, "Property registry not built. Run: cleo properties")

    from cleo.properties.registry import load_registry, save_registry

    body = await request.json()
    allowed = {"address", "city", "municipality", "province", "postal_code", "lat", "lng"}
    changes = {k: v for k, v in body.items() if k in allowed}

    if not changes:
        raise HTTPException(400, "No valid fields provided")

    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    if prop_id not in props:
        raise HTTPException(404, f"Property not found: {prop_id}")

    prop = props[prop_id]

    # Apply changes
    for k, v in changes.items():
        prop[k] = v
    prop["updated"] = datetime.now().strftime("%Y-%m-%d")

    # If lat+lng+address provided, also update geocode cache so coords survive rebuilds
    if "lat" in changes and "lng" in changes and prop.get("address"):
        from cleo.geocode.cache import GeocodeCache

        cache = GeocodeCache(GEOCODE_CACHE_PATH)
        addr_key = f"{prop['address']}, {prop.get('city', '')}, {prop.get('province', 'Ontario')}"
        cache.put(addr_key, {
            "lat": changes["lat"],
            "lng": changes["lng"],
            "formatted_address": addr_key,
            "accuracy": "manual",
            "failed": False,
        })
        cache.save()

    save_registry(reg, PROPERTIES_PATH)
    _properties_cache = None
    _properties_cache_mtime = 0

    _log_property_edit({
        "action": "update_property",
        "prop_id": prop_id,
        "changes": changes,
    })

    return {"status": "saved", "prop_id": prop_id}


_VALID_PIPELINE_STATUSES = {
    "not_started", "attempted_contact", "interested", "listed", "do_not_contact",
}


@app.put("/api/properties/{prop_id}/pipeline-status")
async def api_set_pipeline_status(prop_id: str, request: Request):
    """Set pipeline_status on a property record."""
    global _properties_cache, _properties_cache_mtime

    body = await request.json()
    new_status = body.get("status", "").strip()
    if new_status not in _VALID_PIPELINE_STATUSES:
        raise HTTPException(400, f"Invalid pipeline status: {new_status}")

    if not PROPERTIES_PATH.exists():
        raise HTTPException(404, "Property registry not built. Run: cleo properties")

    from cleo.properties.registry import load_registry, save_registry

    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    if prop_id not in props:
        raise HTTPException(404, f"Property not found: {prop_id}")

    props[prop_id]["pipeline_status"] = new_status
    props[prop_id]["updated"] = datetime.now().strftime("%Y-%m-%d")
    save_registry(reg, PROPERTIES_PATH)
    _properties_cache = None
    _properties_cache_mtime = 0

    _log_property_edit({
        "action": "set_pipeline_status",
        "prop_id": prop_id,
        "status": new_status,
    })

    return {"ok": True, "prop_id": prop_id, "pipeline_status": new_status}


# ---------------------------------------------------------------------------
# Google Places & Street View (front-facing app)
# ---------------------------------------------------------------------------

from cleo.config import GOOGLE_PLACES_PATH, STREETVIEW_DIR, STREETVIEW_META_PATH, GOOGLE_BUDGET_PATH  # noqa: E402


@app.get("/api/properties/{prop_id}/streetview")
def api_property_streetview(prop_id: str):
    """Serve Street View image, fetching on-demand if not cached.

    1. Check local cache → serve immediately if exists
    2. If no cache: look up property coords, check metadata (free),
       fetch image through BudgetGuardian, cache it, serve it
    3. Returns 404 if no coverage or budget exhausted
    """
    image_path = STREETVIEW_DIR / f"{prop_id}.jpg"

    # Serve from cache if available
    if image_path.exists():
        return FileResponse(image_path, media_type="image/jpeg")

    # On-demand fetch
    from cleo.config import GOOGLE_API_KEY, PROPERTIES_PATH
    if not GOOGLE_API_KEY:
        raise HTTPException(404, "Street View not configured")

    # Look up property coordinates
    from cleo.properties.registry import load_registry
    reg = load_registry(PROPERTIES_PATH)
    prop = reg.get("properties", {}).get(prop_id)
    if not prop or prop.get("lat") is None or prop.get("lng") is None:
        raise HTTPException(404, "Property has no coordinates")

    lat = prop["lat"]
    lng = prop["lng"]

    from cleo.google.budget import BudgetGuardian
    from cleo.google.streetview import StreetViewClient
    from cleo.google.store import StreetViewMetaStore

    budget = BudgetGuardian()
    sv_meta = StreetViewMetaStore()

    try:
        client = StreetViewClient(GOOGLE_API_KEY, budget)

        # Check metadata (free) if not already checked
        if not sv_meta.has_metadata(prop_id):
            meta = client.check_metadata(lat, lng)
            sv_meta.set_metadata(prop_id, meta)
            sv_meta.save()
            if not meta["has_coverage"]:
                client.close()
                raise HTTPException(404, "No Street View coverage")
        elif not sv_meta.has_coverage(prop_id):
            client.close()
            raise HTTPException(404, "No Street View coverage")

        # Check budget before fetching image
        if not budget.can_use("streetview_image"):
            client.close()
            raise HTTPException(429, "Street View daily/monthly budget exhausted")

        # Fetch and cache the image
        path = client.fetch_image(lat, lng, prop_id)
        client.close()

        if path and path.exists():
            sv_meta.set_image_fetched(prop_id)
            sv_meta.save()
            return FileResponse(path, media_type="image/jpeg")

        raise HTTPException(404, "Street View image unavailable")

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Street View fetch failed for %s: %s", prop_id, e)
        raise HTTPException(500, "Street View fetch failed")


@app.get("/api/properties/{prop_id}/places")
def api_property_places(prop_id: str):
    """Return cached Google Places data for a property. Never calls Google API."""
    if not GOOGLE_PLACES_PATH.exists():
        raise HTTPException(404, "Google Places data not yet collected")

    import json as _json
    data = _json.loads(GOOGLE_PLACES_PATH.read_text(encoding="utf-8"))
    entry = data.get("properties", {}).get(prop_id)
    if not entry:
        raise HTTPException(404, "No Places data for this property")

    # Also include street view metadata if available
    sv_meta = None
    if STREETVIEW_META_PATH.exists():
        sv_data = _json.loads(STREETVIEW_META_PATH.read_text(encoding="utf-8"))
        sv_meta = sv_data.get("properties", {}).get(prop_id)

    return {
        **entry,
        "prop_id": prop_id,
        "streetview": sv_meta,
        "has_streetview_image": (STREETVIEW_DIR / f"{prop_id}.jpg").exists(),
    }


@app.get("/api/google/status")
def api_google_status():
    """Return Google API budget usage and enrichment progress (admin)."""
    result = {}

    # Budget
    if GOOGLE_BUDGET_PATH.exists():
        import json as _json
        budget_data = _json.loads(GOOGLE_BUDGET_PATH.read_text(encoding="utf-8"))
        result["budget"] = budget_data
    else:
        result["budget"] = None

    # Places enrichment stats
    if GOOGLE_PLACES_PATH.exists():
        import json as _json
        places_data = _json.loads(GOOGLE_PLACES_PATH.read_text(encoding="utf-8"))
        props = places_data.get("properties", {})
        result["places"] = {
            "total": len(props),
            "with_place_id": sum(1 for p in props.values() if "place_id" in p),
            "with_essentials": sum(1 for p in props.values() if "essentials" in p),
            "with_pro": sum(1 for p in props.values() if "pro" in p),
            "with_enterprise": sum(1 for p in props.values() if "enterprise" in p),
        }
    else:
        result["places"] = None

    # Street view stats
    if STREETVIEW_META_PATH.exists():
        import json as _json
        sv_data = _json.loads(STREETVIEW_META_PATH.read_text(encoding="utf-8"))
        sv_props = sv_data.get("properties", {})
        result["streetview"] = {
            "total_checked": len(sv_props),
            "with_coverage": sum(1 for p in sv_props.values() if p.get("has_coverage")),
            "images_fetched": sum(1 for p in sv_props.values() if p.get("image_fetched")),
        }
    else:
        result["streetview"] = None

    return result


# ---------------------------------------------------------------------------
# OSM Tenants (front-facing app)
# ---------------------------------------------------------------------------

from cleo.osm.store import OSM_TENANTS_PATH  # noqa: E402
from cleo.osm.brand_search import OSM_BRANDS_PATH  # noqa: E402


@app.get("/api/properties/{prop_id}/tenants")
def api_property_tenants(prop_id: str):
    """Return OSM tenant + brand data for a property. Merges proximity and brand search."""
    import json as _json
    confirmed: list[dict] = []

    # Proximity-based tenant data (only confirmed via address match)
    if OSM_TENANTS_PATH.exists():
        data = _json.loads(OSM_TENANTS_PATH.read_text(encoding="utf-8"))
        entry = data.get("properties", {}).get(prop_id)
        if entry:
            for t in entry.get("tenants", []):
                if t.get("match_type") == "confirmed":
                    confirmed.append(t)

    # Brand search data (only confirmed via address match)
    if OSM_BRANDS_PATH.exists():
        brand_data = _json.loads(OSM_BRANDS_PATH.read_text(encoding="utf-8"))
        brand_entry = brand_data.get("properties", {}).get(prop_id)
        if brand_entry:
            seen = {t["osm_id"] for t in confirmed}
            for t in brand_entry.get("confirmed", []):
                if t["osm_id"] not in seen:
                    confirmed.append(t)
                    seen.add(t["osm_id"])

    if not confirmed:
        raise HTTPException(404, "No tenant data for this property")

    return {
        "prop_id": prop_id,
        "confirmed": confirmed,
        "confirmed_count": len(confirmed),
    }


# ---------------------------------------------------------------------------
# Parties (front-facing app)
# ---------------------------------------------------------------------------

_parties_cache: list | None = None
_parties_cache_mtime: float = 0


@app.get("/api/parties/known-attributes")
def api_known_attributes():
    """Return attribute-to-group-name lookup for all confirmed party groups.

    Only groups with at least one confirmed name are included.
    Used by the evidence drawer to tag known contacts, phones, and addresses.
    """
    if not PARTIES_PATH.exists():
        return {"phones": {}, "contacts": {}, "addresses": {}}

    from cleo.parties.registry import load_registry
    from cleo.parties.suggestions import build_known_attributes

    reg = load_registry(PARTIES_PATH)
    mtime = PARTIES_PATH.stat().st_mtime
    return build_known_attributes(reg.get("parties", {}), reg.get("overrides", {}), mtime)


@app.get("/api/parties")
def api_parties():
    """Return party groups as a summary array for the front-facing app."""
    global _parties_cache, _parties_cache_mtime

    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    mtime = PARTIES_PATH.stat().st_mtime
    if _parties_cache is not None and _parties_cache_mtime == mtime:
        return JSONResponse(_parties_cache)

    from cleo.parties.registry import load_registry
    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})
    overrides = reg.get("overrides", {})
    dn_overrides = overrides.get("display_name", {})

    records = []
    for gid, p in parties_data.items():
        names = p.get("names", [])
        contacts = p.get("contacts", [])
        phones = p.get("phones", [])

        # Compute current ownership: for each property, check if the
        # most recent transaction was a buy (meaning they still own it)
        prop_latest: dict[str, tuple[str, str]] = {}  # (addr,city) -> (date, role)
        for app in p.get("appearances", []):
            addr = (app.get("prop_address") or "").upper().strip()
            city = (app.get("prop_city") or "").upper().strip()
            if not addr:
                continue
            key = (addr, city)
            d = app.get("sale_date_iso", "")
            prev = prop_latest.get(key)
            if prev is None or d > prev[0]:
                prop_latest[key] = (d, app.get("role", ""))
        owns_count = sum(1 for _, role in prop_latest.values() if role == "buyer")

        # Build search text from all party data
        search_parts = [gid]
        search_parts.extend(names)
        search_parts.extend(contacts)
        search_parts.extend(phones)
        search_parts.extend(p.get("addresses", []))
        search_parts.extend(p.get("aliases", []))
        search_parts.extend(p.get("alternate_names", []))
        dn = p.get("display_name_override") or p.get("display_name", "")
        if dn:
            search_parts.append(dn)
        party_search_text = " ".join(s for s in search_parts if s).lower()

        records.append({
            "group_id": gid,
            "display_name": dn,
            "is_company": p.get("is_company", True),
            "names_count": len(names),
            "names": names[:3],
            "addresses_count": len(p.get("addresses", [])),
            "transaction_count": p.get("transaction_count", 0),
            "buy_count": p.get("buy_count", 0),
            "sell_count": p.get("sell_count", 0),
            "owns_count": owns_count,
            "contacts": contacts[:2],
            "phones": phones[:1],
            "first_active_iso": p.get("first_active_iso", ""),
            "last_active_iso": p.get("last_active_iso", ""),
            "has_override": gid in dn_overrides,
            "_search_text": party_search_text,
        })

    _parties_cache = records
    _parties_cache_mtime = mtime
    return JSONResponse(records)


@app.get("/api/parties/{group_id}")
def api_party_detail(group_id: str):
    """Return full detail for a single party group."""
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry
    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    p = parties_data[group_id]

    # Enrich appearances with property address/city and photos
    act = active_dir()
    enriched_appearances = []
    for app in p.get("appearances", []):
        entry = dict(app)
        # Add photo info from parsed data
        if act:
            f = act / f"{app['rt_id']}.json"
            if f.exists():
                data = json.loads(f.read_text(encoding="utf-8"))
                entry["photos"] = data.get("photos", [])
            else:
                entry["photos"] = []
        else:
            entry["photos"] = []
        enriched_appearances.append(entry)

    # Cross-reference linked properties
    linked_properties = []
    if PROPERTIES_PATH.exists():
        from cleo.properties.registry import load_registry as load_prop_registry
        prop_reg = load_prop_registry(PROPERTIES_PATH)
        props = prop_reg.get("properties", {})
        party_rt_ids = set(p.get("rt_ids", []))
        for pid, prop in props.items():
            prop_rt_ids = set(prop.get("rt_ids", []))
            if party_rt_ids & prop_rt_ids:
                linked_properties.append({
                    "prop_id": pid,
                    "address": prop.get("address", ""),
                    "city": prop.get("city", ""),
                    "transaction_count": prop.get("transaction_count", 0),
                })

    overrides = reg.get("overrides", {})
    url_overrides = overrides.get("url", {})
    confirmed = overrides.get("confirmed", {}).get(group_id, [])

    return {
        "group_id": group_id,
        "display_name": p.get("display_name_override") or p.get("display_name", ""),
        "display_name_auto": p.get("display_name", ""),
        "display_name_override": p.get("display_name_override", ""),
        "url": url_overrides.get(group_id, ""),
        "is_company": p.get("is_company", True),
        "names": p.get("names", []),
        "normalized_names": p.get("normalized_names", []),
        "addresses": p.get("addresses", []),
        "contacts": p.get("contacts", []),
        "phones": p.get("phones", []),
        "aliases": p.get("aliases", []),
        "alternate_names": p.get("alternate_names", []),
        "appearances": enriched_appearances,
        "transaction_count": p.get("transaction_count", 0),
        "buy_count": p.get("buy_count", 0),
        "sell_count": p.get("sell_count", 0),
        "first_active_iso": p.get("first_active_iso", ""),
        "last_active_iso": p.get("last_active_iso", ""),
        "rt_ids": p.get("rt_ids", []),
        "created": p.get("created", ""),
        "updated": p.get("updated", ""),
        "linked_properties": linked_properties,
        "confirmed_names": confirmed,
        "linked_operators": _operators_for_party(group_id),
    }


@app.post("/api/parties/{group_id}")
async def api_save_party_overrides(group_id: str, request: Request):
    """Save overrides for a party group.

    Body: {
        "display_name": "Choice Properties",
        "url": "https://www.choicereit.ca"
    }
    """
    global _parties_cache
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry, save_registry

    body = await request.json()
    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    overrides = reg.setdefault("overrides", {})
    dn_overrides = overrides.setdefault("display_name", {})
    url_overrides = overrides.setdefault("url", {})

    # Display name override
    display_name = (body.get("display_name") or "").strip()
    if display_name:
        dn_overrides[group_id] = display_name
        parties_data[group_id]["display_name_override"] = display_name
    else:
        dn_overrides.pop(group_id, None)
        parties_data[group_id]["display_name_override"] = ""

    # URL override
    url = (body.get("url") or "").strip()
    if url:
        url_overrides[group_id] = url
    else:
        url_overrides.pop(group_id, None)

    parties_data[group_id]["updated"] = datetime.now().strftime("%Y-%m-%d")

    save_registry(reg, PARTIES_PATH)
    _parties_cache = None  # bust cache

    return {"status": "saved", "group_id": group_id}


@app.post("/api/parties/{group_id}/disconnect")
async def api_party_disconnect(group_id: str, request: Request):
    """Disconnect a name from a party group, moving it to a new or existing group.

    Body: {
        "name": "1873280 Ontario Inc",
        "target_group": "",   // empty = create new group
        "reason": "Different parent company"
    }
    """
    global _parties_cache
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry, save_registry
    from cleo.parties.normalize import normalize_name

    body = await request.json()
    name = (body.get("name") or "").strip()
    target_group = (body.get("target_group") or "").strip()
    reason = (body.get("reason") or "").strip()

    if not name:
        raise HTTPException(400, "name is required")

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    source = parties_data[group_id]
    norm_name = normalize_name(name)

    # Find matching appearances
    matching = [a for a in source["appearances"] if normalize_name(a["name"]) == norm_name]
    if not matching:
        raise HTTPException(400, f"Name not found in group: {name}")

    remaining = [a for a in source["appearances"] if normalize_name(a["name"]) != norm_name]

    if not remaining:
        raise HTTPException(400, "Cannot disconnect the only name in a group")

    # Determine target group
    if target_group and target_group in parties_data:
        tgt_gid = target_group
    else:
        # Create new group ID
        max_num = 0
        for gid in parties_data:
            if gid.startswith("G") and gid[1:].isdigit():
                max_num = max(max_num, int(gid[1:]))
        tgt_gid = f"G{max_num + 1:05d}"

    today = datetime.now().strftime("%Y-%m-%d")

    # Update source group — remove the name's appearances
    source["appearances"] = remaining
    source["names"] = sorted(set(a["name"] for a in remaining))
    source["normalized_names"] = sorted(set(normalize_name(a["name"]) for a in remaining))
    source["rt_ids"] = sorted(set(a["rt_id"] for a in remaining))
    source["transaction_count"] = len(source["rt_ids"])
    source["buy_count"] = sum(1 for a in remaining if a["role"] == "buyer")
    source["sell_count"] = sum(1 for a in remaining if a["role"] == "seller")
    dates = [a["sale_date_iso"] for a in remaining if a.get("sale_date_iso")]
    source["first_active_iso"] = min(dates) if dates else ""
    source["last_active_iso"] = max(dates) if dates else ""
    # Recompute addresses/contacts/phones from remaining appearances
    source["addresses"] = sorted(set(a.get("address", "") or "" for a in remaining if (a.get("address") or "").strip()))
    source["contacts"] = sorted(set(a.get("contact", "") or "" for a in remaining if (a.get("contact") or "").strip()))
    seen_phones: set[str] = set()
    new_phones: list[str] = []
    for a in remaining:
        for p in a.get("phones", []):
            if p and p not in seen_phones:
                new_phones.append(p)
                seen_phones.add(p)
    source["phones"] = new_phones
    source["updated"] = today

    # Build or extend target group
    if tgt_gid in parties_data:
        tgt = parties_data[tgt_gid]
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
        tgt["updated"] = today
    else:
        # Create new group
        from cleo.parties.registry import _is_company_name
        from cleo.parties.normalize import make_alias

        names = sorted(set(a["name"] for a in matching))
        is_company = any(_is_company_name(n) for n in names)
        aliases = sorted(set(
            alias for a in matching for alias in a.get("aliases", [])
        ))
        for n in names:
            alias = make_alias(n)
            if alias and alias.upper() not in {a.upper() for a in aliases}:
                aliases.append(alias)
        aliases = sorted(set(aliases))

        parties_data[tgt_gid] = {
            "display_name": max(set(a["name"] for a in matching), key=lambda n: sum(1 for a in matching if a["name"] == n)),
            "display_name_override": "",
            "is_company": is_company,
            "names": names,
            "normalized_names": sorted(set(normalize_name(a["name"]) for a in matching)),
            "addresses": sorted(set(a.get("address", "") for a in matching if (a.get("address") or "").strip())),
            "contacts": sorted(set(a.get("contact", "") for a in matching if (a.get("contact") or "").strip())),
            "phones": list(dict.fromkeys(p for a in matching for p in a.get("phones", []) if p)),
            "aliases": aliases,
            "appearances": sorted(matching, key=lambda x: x.get("sale_date_iso", ""), reverse=True),
            "transaction_count": len(set(a["rt_id"] for a in matching)),
            "buy_count": sum(1 for a in matching if a["role"] == "buyer"),
            "sell_count": sum(1 for a in matching if a["role"] == "seller"),
            "first_active_iso": min((a["sale_date_iso"] for a in matching if a.get("sale_date_iso")), default=""),
            "last_active_iso": max((a["sale_date_iso"] for a in matching if a.get("sale_date_iso")), default=""),
            "rt_ids": sorted(set(a["rt_id"] for a in matching)),
            "created": today,
            "updated": today,
        }

    # Store split override for rebuild persistence
    overrides = reg.setdefault("overrides", {})
    splits = overrides.setdefault("splits", [])
    splits.append({
        "source": group_id,
        "normalized_name": norm_name,
        "target": tgt_gid,
        "reason": reason,
        "date": today,
    })

    # Sort parties by ID
    reg["parties"] = dict(sorted(parties_data.items()))
    save_registry(reg, PARTIES_PATH)
    _parties_cache = None

    # Audit log
    _log_party_edit({
        "action": "disconnect",
        "source_group": group_id,
        "name": name,
        "normalized_name": norm_name,
        "target_group": tgt_gid,
        "reason": reason,
    })

    return {"status": "disconnected", "source_group": group_id, "target_group": tgt_gid, "name": name}


@app.post("/api/parties/{group_id}/split-cluster")
async def api_party_split_cluster(group_id: str, request: Request):
    """Split multiple names from a party group into a new group together.

    Body: {
        "names": ["Name A", "Name B"],
        "reason": "These belong together but not in this group"
    }
    """
    global _parties_cache
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry, save_registry, _is_company_name
    from cleo.parties.normalize import normalize_name, make_alias

    body = await request.json()
    names = body.get("names") or []
    reason = (body.get("reason") or "").strip()

    if not names or len(names) < 2:
        raise HTTPException(400, "At least 2 names are required")

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    source = parties_data[group_id]
    norm_names = {normalize_name(n) for n in names}

    # Collect matching appearances for ALL names
    matching = [a for a in source["appearances"] if normalize_name(a["name"]) in norm_names]
    if not matching:
        raise HTTPException(400, "None of the specified names found in group")

    remaining = [a for a in source["appearances"] if normalize_name(a["name"]) not in norm_names]
    if not remaining:
        raise HTTPException(400, "Cannot split all names out of a group — at least one must remain")

    # Create new group ID
    max_num = 0
    for gid in parties_data:
        if gid.startswith("G") and gid[1:].isdigit():
            max_num = max(max_num, int(gid[1:]))
    tgt_gid = f"G{max_num + 1:05d}"

    today = datetime.now().strftime("%Y-%m-%d")

    # Update source group — remove matched appearances
    source["appearances"] = remaining
    source["names"] = sorted(set(a["name"] for a in remaining))
    source["normalized_names"] = sorted(set(normalize_name(a["name"]) for a in remaining))
    source["rt_ids"] = sorted(set(a["rt_id"] for a in remaining))
    source["transaction_count"] = len(source["rt_ids"])
    source["buy_count"] = sum(1 for a in remaining if a["role"] == "buyer")
    source["sell_count"] = sum(1 for a in remaining if a["role"] == "seller")
    dates = [a["sale_date_iso"] for a in remaining if a.get("sale_date_iso")]
    source["first_active_iso"] = min(dates) if dates else ""
    source["last_active_iso"] = max(dates) if dates else ""
    source["addresses"] = sorted(set(a.get("address", "") or "" for a in remaining if (a.get("address") or "").strip()))
    source["contacts"] = sorted(set(a.get("contact", "") or "" for a in remaining if (a.get("contact") or "").strip()))
    seen_phones: set[str] = set()
    new_phones: list[str] = []
    for a in remaining:
        for p in a.get("phones", []):
            if p and p not in seen_phones:
                new_phones.append(p)
                seen_phones.add(p)
    source["phones"] = new_phones
    source["updated"] = today

    # Create new group with all matched appearances
    tgt_names = sorted(set(a["name"] for a in matching))
    is_company = any(_is_company_name(n) for n in tgt_names)
    aliases = sorted(set(
        alias for a in matching for alias in a.get("aliases", [])
    ))
    for n in tgt_names:
        alias = make_alias(n)
        if alias and alias.upper() not in {a.upper() for a in aliases}:
            aliases.append(alias)
    aliases = sorted(set(aliases))

    parties_data[tgt_gid] = {
        "display_name": max(set(a["name"] for a in matching), key=lambda n: sum(1 for a in matching if a["name"] == n)),
        "display_name_override": "",
        "is_company": is_company,
        "names": tgt_names,
        "normalized_names": sorted(set(normalize_name(a["name"]) for a in matching)),
        "addresses": sorted(set(a.get("address", "") for a in matching if (a.get("address") or "").strip())),
        "contacts": sorted(set(a.get("contact", "") for a in matching if (a.get("contact") or "").strip())),
        "phones": list(dict.fromkeys(p for a in matching for p in a.get("phones", []) if p)),
        "aliases": aliases,
        "appearances": sorted(matching, key=lambda x: x.get("sale_date_iso", ""), reverse=True),
        "transaction_count": len(set(a["rt_id"] for a in matching)),
        "buy_count": sum(1 for a in matching if a["role"] == "buyer"),
        "sell_count": sum(1 for a in matching if a["role"] == "seller"),
        "first_active_iso": min((a["sale_date_iso"] for a in matching if a.get("sale_date_iso")), default=""),
        "last_active_iso": max((a["sale_date_iso"] for a in matching if a.get("sale_date_iso")), default=""),
        "rt_ids": sorted(set(a["rt_id"] for a in matching)),
        "created": today,
        "updated": today,
    }

    # Store split overrides for each name (rebuild persistence)
    overrides = reg.setdefault("overrides", {})
    splits = overrides.setdefault("splits", [])
    for nn in norm_names:
        splits.append({
            "source": group_id,
            "normalized_name": nn,
            "target": tgt_gid,
            "reason": reason or "Split cluster via party review",
            "date": today,
        })

    # Sort parties by ID
    reg["parties"] = dict(sorted(parties_data.items()))
    save_registry(reg, PARTIES_PATH)
    _parties_cache = None

    # Audit log
    _log_party_edit({
        "action": "split_cluster",
        "source_group": group_id,
        "names": list(names),
        "normalized_names": list(norm_names),
        "target_group": tgt_gid,
        "reason": reason,
    })

    return {
        "status": "split_cluster",
        "source_group": group_id,
        "target_group": tgt_gid,
        "names": list(names),
    }


@app.post("/api/parties/{group_id}/confirm")
async def api_party_confirm(group_id: str, request: Request):
    """Confirm a name belongs in a party group.

    Body: {"name": "H&R REIT"}
    """
    global _parties_cache
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry, save_registry
    from cleo.parties.normalize import normalize_name

    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name is required")

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    norm_name = normalize_name(name)

    # Verify the name exists in this group
    group_norms = [normalize_name(n) for n in parties_data[group_id].get("names", [])]
    if norm_name not in group_norms:
        raise HTTPException(400, f"Name not found in group: {name}")

    # Store confirmation
    overrides = reg.setdefault("overrides", {})
    confirmed = overrides.setdefault("confirmed", {})
    group_confirmed = confirmed.setdefault(group_id, [])
    if norm_name not in group_confirmed:
        group_confirmed.append(norm_name)

    save_registry(reg, PARTIES_PATH)
    _parties_cache = None

    # Audit log
    _log_party_edit({
        "action": "confirm",
        "group": group_id,
        "name": name,
        "normalized_name": norm_name,
    })

    return {"status": "confirmed", "group_id": group_id, "name": name}


# ---------------------------------------------------------------------------
# Party Suggestions (affiliate matching)
# ---------------------------------------------------------------------------

@app.get("/api/parties/{group_id}/suggestions")
def api_party_suggestions(group_id: str):
    """Return suggested affiliate groups based on shared attributes."""
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry
    from cleo.parties.suggestions import get_suggestions

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    overrides = reg.get("overrides", {})
    dismissed = overrides.get("dismissed_suggestions", {}).get(group_id, [])
    mtime = PARTIES_PATH.stat().st_mtime

    return get_suggestions(group_id, parties_data, dismissed, mtime)


@app.get("/api/parties/{group_id}/grouping-reason")
def api_grouping_reason(group_id: str, name: str = ""):
    """Explain why a name is in this group — shared phones, contacts, aliases.

    Query param: ?name=755 Gardiners Road Inc
    """
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")
    if not name.strip():
        raise HTTPException(400, "name query parameter is required")

    from cleo.parties.registry import load_registry
    from cleo.parties.suggestions import get_grouping_reason

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    act = active_dir()
    if act is None:
        raise HTTPException(404, "No active parse version")

    return get_grouping_reason(group_id, name.strip(), parties_data, act)


@app.get("/api/party-review/chain/{group_id}")
def api_party_review_chain(group_id: str, name: str = ""):
    """Return chain link data with full RT records for the chain viewer.

    Builds a 2-3 step chain showing exactly how a name is linked to the group,
    with full parsed transaction data for each chain step.
    """
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")
    if not name.strip():
        raise HTTPException(400, "name query parameter is required")

    from cleo.parties.registry import load_registry
    from cleo.parties.suggestions import get_grouping_reason

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    act = active_dir()
    if act is None:
        raise HTTPException(404, "No active parse version")

    reasons = get_grouping_reason(group_id, name.strip(), parties_data, act)

    # Build chain from reasons
    chain = []
    direct_reasons = []

    if reasons and reasons[0].get("type") == "chain" and reasons[0].get("chain"):
        # Transitive chain — use structured chain data
        chain = reasons[0]["chain"][:3]  # Cap at 3 steps
    elif reasons:
        # Direct link — build 2-step chain from the best reason
        direct_reasons = reasons
        # Pick the first reason that has linked names (skip alias-only matches)
        r = None
        for candidate in reasons:
            if candidate.get("linked_rt_data"):
                r = candidate
                break
        if r is None:
            r = reasons[0]

        chain.append({
            "name": name.strip(),
            "rt_id": r.get("target_rt_id"),
            "role": r.get("target_role"),
            "link_type": r.get("type"),
            "link_value": r.get("value"),
        })
        # Add first linked name as step 2
        linked = r.get("linked_rt_data", [])
        if linked:
            ld = linked[0]
            chain.append({
                "name": ld["name"],
                "rt_id": ld.get("rt_id"),
                "role": ld.get("role"),
                "link_type": None,
                "link_value": None,
            })
    else:
        # No reasons found — fallback: show review name and anchor with normalization banner
        p = parties_data[group_id]
        group_names = p.get("names", [])
        # Pick anchor (name with most appearances)
        apps = p.get("appearances", [])
        name_counts: dict[str, int] = {}
        for a in apps:
            name_counts[a["name"]] = name_counts.get(a["name"], 0) + 1
        anchor = max(group_names, key=lambda n: name_counts.get(n, 0)) if group_names else None

        # Find any RT for the review name
        review_rt = None
        review_role = None
        for a in apps:
            if a["name"] == name.strip():
                review_rt = a["rt_id"]
                review_role = a["role"]
                break
        chain.append({
            "name": name.strip(),
            "rt_id": review_rt,
            "role": review_role,
            "link_type": "normalization",
            "link_value": "Same normalized name",
        })
        if anchor and anchor != name.strip():
            anchor_rt = None
            anchor_role = None
            for a in apps:
                if a["name"] == anchor:
                    anchor_rt = a["rt_id"]
                    anchor_role = a["role"]
                    break
            chain.append({
                "name": anchor,
                "rt_id": anchor_rt,
                "role": anchor_role,
                "link_type": None,
                "link_value": None,
            })

    # Load full RT data for each chain step
    for step in chain:
        rt_id = step.get("rt_id")
        if rt_id:
            rt_file = act / f"{rt_id}.json"
            if rt_file.exists():
                data = json.loads(rt_file.read_text(encoding="utf-8"))
                step["rt_data"] = {
                    "transaction": data.get("transaction", {}),
                    "transferor": data.get("transferor", {}),
                    "transferee": data.get("transferee", {}),
                    "site": data.get("site", {}),
                    "consideration": data.get("consideration", {}),
                    "description": data.get("description", ""),
                    "photos": data.get("photos", []),
                    "export_extras": data.get("export_extras", {}),
                }
            else:
                step["rt_data"] = None
        else:
            step["rt_data"] = None

    return {"chain": chain, "direct_reasons": direct_reasons}


@app.post("/api/parties/{group_id}/merge")
async def api_party_merge(group_id: str, request: Request):
    """Merge a source group into this target group.

    Body: {"source_group": "G02654", "reason": "Same parent company"}
    """
    global _parties_cache
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry, save_registry

    body = await request.json()
    source_group = (body.get("source_group") or "").strip()
    reason = (body.get("reason") or "").strip()

    if not source_group:
        raise HTTPException(400, "source_group is required")

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Target group not found: {group_id}")
    if source_group not in parties_data:
        raise HTTPException(404, f"Source group not found: {source_group}")
    if group_id == source_group:
        raise HTTPException(400, "Cannot merge a group into itself")

    today = datetime.now().strftime("%Y-%m-%d")

    # Perform merge (same pattern as registry.py)
    src = parties_data.pop(source_group)
    tgt = parties_data[group_id]

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
    tgt["updated"] = today

    # Store merge override for rebuild persistence
    overrides = reg.setdefault("overrides", {})
    merges = overrides.setdefault("merge", [])
    merges.append([group_id, source_group])

    reg["parties"] = dict(sorted(parties_data.items()))
    save_registry(reg, PARTIES_PATH)
    _parties_cache = None

    # Audit log
    _log_party_edit({
        "action": "merge",
        "target_group": group_id,
        "source_group": source_group,
        "reason": reason,
    })

    return {"status": "merged", "target_group": group_id, "source_group": source_group}


@app.post("/api/parties/{group_id}/dismiss-suggestion")
async def api_party_dismiss_suggestion(group_id: str, request: Request):
    """Dismiss a suggested affiliate group.

    Body: {"suggested_group": "G02654", "reason": "Not related"}
    """
    global _parties_cache
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry, save_registry

    body = await request.json()
    suggested_group = (body.get("suggested_group") or "").strip()
    reason = (body.get("reason") or "").strip()

    if not suggested_group:
        raise HTTPException(400, "suggested_group is required")

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    overrides = reg.setdefault("overrides", {})
    dismissed = overrides.setdefault("dismissed_suggestions", {})
    group_dismissed = dismissed.setdefault(group_id, [])
    if suggested_group not in group_dismissed:
        group_dismissed.append(suggested_group)

    save_registry(reg, PARTIES_PATH)

    # Audit log
    _log_party_edit({
        "action": "dismiss_suggestion",
        "group": group_id,
        "suggested_group": suggested_group,
        "reason": reason,
    })

    return {"status": "dismissed", "group_id": group_id, "suggested_group": suggested_group}


# ---------------------------------------------------------------------------
# Party Review (investigative review page)
# ---------------------------------------------------------------------------

@app.get("/api/party-review/search")
def api_party_review_search(q: str = ""):
    """Fuzzy search across all party group fields, ranked by relevance."""
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    q = q.strip()
    if not q:
        return []

    from cleo.parties.registry import load_registry
    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})
    overrides = reg.get("overrides", {})
    confirmed = overrides.get("confirmed", {})
    q_lower = q.lower()

    results = []
    for gid, p in parties_data.items():
        score = 0.0
        matched_fields: list[str] = []
        matched_values: list[str] = []

        # Search names
        for name in p.get("names", []):
            name_lower = name.lower()
            if name_lower == q_lower:
                score += 100
                if "name" not in matched_fields:
                    matched_fields.append("name")
                matched_values.append(name)
            elif name_lower.startswith(q_lower):
                score += 50
                if "name" not in matched_fields:
                    matched_fields.append("name")
                matched_values.append(name)
            elif q_lower in name_lower:
                score += 10
                if "name" not in matched_fields:
                    matched_fields.append("name")
                matched_values.append(name)

        # Search aliases
        for alias in p.get("aliases", []):
            alias_lower = alias.lower()
            if alias_lower == q_lower:
                score += 80
                if "alias" not in matched_fields:
                    matched_fields.append("alias")
                matched_values.append(alias)
            elif q_lower in alias_lower:
                score += 10
                if "alias" not in matched_fields:
                    matched_fields.append("alias")
                matched_values.append(alias)

        # Search alternate_names
        for alt in p.get("alternate_names", []):
            alt_lower = alt.lower()
            if alt_lower == q_lower:
                score += 80
                if "alt_name" not in matched_fields:
                    matched_fields.append("alt_name")
                matched_values.append(alt)
            elif q_lower in alt_lower:
                score += 10
                if "alt_name" not in matched_fields:
                    matched_fields.append("alt_name")
                matched_values.append(alt)

        # Search contacts
        for contact in p.get("contacts", []):
            contact_lower = contact.lower()
            if contact_lower == q_lower:
                score += 60
                if "contact" not in matched_fields:
                    matched_fields.append("contact")
                matched_values.append(contact)
            elif q_lower in contact_lower:
                score += 10
                if "contact" not in matched_fields:
                    matched_fields.append("contact")
                matched_values.append(contact)

        # Search phones
        q_digits = "".join(c for c in q if c.isdigit())
        if q_digits and len(q_digits) >= 3:
            for phone in p.get("phones", []):
                phone_digits = "".join(c for c in phone if c.isdigit())
                if q_digits in phone_digits:
                    score += 60
                    if "phone" not in matched_fields:
                        matched_fields.append("phone")
                    matched_values.append(phone)

        # Search addresses
        for addr in p.get("addresses", []):
            if q_lower in addr.lower():
                score += 60
                if "address" not in matched_fields:
                    matched_fields.append("address")
                matched_values.append(addr)

        # Search display_name
        dn = p.get("display_name_override") or p.get("display_name", "")
        if dn and q_lower in dn.lower() and "name" not in matched_fields:
            score += 10
            matched_fields.append("display_name")
            matched_values.append(dn)

        if score > 0:
            # Tiebreaker: more transactions = more relevant
            score += p.get("transaction_count", 0) * 0.1
            results.append({
                "group_id": gid,
                "display_name": p.get("display_name_override") or p.get("display_name", ""),
                "is_company": p.get("is_company", True),
                "names_count": len(p.get("names", [])),
                "transaction_count": p.get("transaction_count", 0),
                "matched_fields": matched_fields,
                "matched_values": sorted(set(matched_values)),
                "relevance_score": round(score, 1),
            })

    results.sort(key=lambda r: r["relevance_score"], reverse=True)
    return results[:50]


@app.get("/api/party-review/needs-review")
def api_party_review_needs_review():
    """Groups sorted by suspicion score for the review queue."""
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry
    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})
    overrides = reg.get("overrides", {})
    confirmed = overrides.get("confirmed", {})

    results = []
    for gid, p in parties_data.items():
        score = 0
        names_count = len(p.get("names", []))
        txn_count = p.get("transaction_count", 0)

        # Suspicion: many names
        if names_count >= 20:
            score += 50
        elif names_count >= 10:
            score += 30

        # Suspicion: no confirmed names
        if not confirmed.get(gid):
            score += 15

        # Suspicion: high name diversity (names/txns close to 1.0)
        if txn_count > 0:
            diversity = names_count / txn_count
            if diversity > 0.8:
                score += 10

        # Suspicion: has alternate_names
        alt_count = len(p.get("alternate_names", []))
        if alt_count >= 5:
            score += 15
        elif alt_count > 0:
            score += 5

        # Filter: score >= 20 OR (score >= 15 AND names_count >= 3)
        if score >= 20 or (score >= 15 and names_count >= 3):
            results.append({
                "group_id": gid,
                "display_name": p.get("display_name_override") or p.get("display_name", ""),
                "is_company": p.get("is_company", True),
                "names_count": names_count,
                "transaction_count": txn_count,
                "suspicion_score": score,
                "has_confirmed": bool(confirmed.get(gid)),
            })

    results.sort(key=lambda r: r["suspicion_score"], reverse=True)
    return results[:200]


@app.get("/api/party-review/appearances/{group_id}")
def api_party_review_appearances(group_id: str):
    """Load full parsed RT records for each appearance in a party group."""
    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry
    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    if group_id not in parties_data:
        raise HTTPException(404, f"Party group not found: {group_id}")

    p = parties_data[group_id]
    act = active_dir()
    if act is None:
        raise HTTPException(404, "No active parse version")

    appearances = []
    skipped = 0

    # Frequency counters for highlighting
    phone_freq: dict[str, int] = {}
    contact_freq: dict[str, int] = {}
    address_freq: dict[str, int] = {}

    for app_entry in p.get("appearances", []):
        rt_id = app_entry["rt_id"]
        role = app_entry["role"]
        rt_file = act / f"{rt_id}.json"

        if not rt_file.exists():
            skipped += 1
            continue

        data = json.loads(rt_file.read_text(encoding="utf-8"))
        party_key = "transferor" if role == "seller" else "transferee"
        party = data.get(party_key, {})
        txn = data.get("transaction", {})

        addr = txn.get("address", {})
        site = data.get("site", {})
        consideration = data.get("consideration", {})
        broker = data.get("broker", {})
        extras = data.get("export_extras", {})

        entry = {
            "rt_id": rt_id,
            "role": role,
            # Party fields
            "entity_name": party.get("name", app_entry.get("name", "")),
            "contact": party.get("contact", ""),
            "attention": party.get("attention", ""),
            "phone": party.get("phone", ""),
            "phones": party.get("phones", []),
            "address": party.get("address", ""),
            "aliases": party.get("aliases", []),
            "alternate_names": party.get("alternate_names", []),
            "company_lines": party.get("company_lines", []),
            "contact_lines": party.get("contact_lines", []),
            "address_lines": party.get("address_lines", []),
            "officer_titles": party.get("officer_titles", []),
            # Transaction fields
            "sale_date_iso": app_entry.get("sale_date_iso", ""),
            "sale_date": txn.get("sale_date", ""),
            "sale_price": app_entry.get("sale_price", ""),
            "prop_address": app_entry.get("prop_address", addr.get("address", "")),
            "prop_address_suite": addr.get("address_suite", ""),
            "prop_city": app_entry.get("prop_city", addr.get("city", "")),
            "prop_municipality": addr.get("municipality", ""),
            "prop_province": addr.get("province", ""),
            "prop_postal_code": addr.get("postal_code", "") or extras.get("postal_code", ""),
            "arn": txn.get("arn", ""),
            "pins": txn.get("pins", []),
            # Site
            "legal_description": site.get("legal_description", ""),
            "site_area": site.get("site_area", ""),
            "site_area_units": site.get("site_area_units", ""),
            "zoning": site.get("zoning", ""),
            # Consideration
            "cash": consideration.get("cash", ""),
            "assumed_debt": consideration.get("assumed_debt", ""),
            "consideration_verbatim": consideration.get("verbatim", ""),
            # Broker
            "brokerage": broker.get("brokerage", ""),
            "broker_phone": broker.get("phone", ""),
            # Extras
            "building_sf": extras.get("building_sf", ""),
            "description": data.get("description", ""),
            "photos": data.get("photos", []),
        }
        appearances.append(entry)

        # Track frequencies
        for ph in entry["phones"]:
            if ph:
                phone_freq[ph] = phone_freq.get(ph, 0) + 1
        if entry["contact"]:
            contact_freq[entry["contact"]] = contact_freq.get(entry["contact"], 0) + 1
        if entry["address"]:
            address_freq[entry["address"]] = address_freq.get(entry["address"], 0) + 1

    # Only include fields appearing 2+ times
    field_frequencies = {
        "phones": {k: v for k, v in phone_freq.items() if v >= 2},
        "contacts": {k: v for k, v in contact_freq.items() if v >= 2},
        "addresses": {k: v for k, v in address_freq.items() if v >= 2},
    }

    return {
        "group_id": group_id,
        "appearances": appearances,
        "total": len(appearances),
        "skipped": skipped,
        "field_frequencies": field_frequencies,
    }


# ---------------------------------------------------------------------------
# Keywords (brand keyword matching)
# ---------------------------------------------------------------------------

def _load_keywords() -> dict:
    """Load brand keywords data from disk."""
    if not KEYWORDS_PATH.exists():
        return {"keywords": {}, "reviews": {}}
    data = json.loads(KEYWORDS_PATH.read_text(encoding="utf-8"))
    data.setdefault("keywords", {})
    data.setdefault("reviews", {})
    return data


def _save_keywords(data: dict) -> None:
    """Atomically save brand keywords data."""
    tmp = KEYWORDS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(KEYWORDS_PATH)


def _search_parties_for_keyword(keyword: str, parties_data: dict) -> list[dict]:
    """Case-insensitive substring search across party group fields."""
    kw_lower = keyword.lower()
    results = []

    for gid, p in parties_data.items():
        matched_fields: list[str] = []
        matched_snippets: list[str] = []

        # Search names
        for name in p.get("names", []):
            if kw_lower in name.lower():
                if "names" not in matched_fields:
                    matched_fields.append("names")
                matched_snippets.append(name)

        # Search aliases
        for alias in p.get("aliases", []):
            if kw_lower in alias.lower():
                if "aliases" not in matched_fields:
                    matched_fields.append("aliases")
                matched_snippets.append(alias)

        # Search alternate_names
        for alt in p.get("alternate_names", []):
            if kw_lower in alt.lower():
                if "alternate_names" not in matched_fields:
                    matched_fields.append("alternate_names")
                matched_snippets.append(alt)

        # Search contacts
        for contact in p.get("contacts", []):
            if kw_lower in contact.lower():
                if "contacts" not in matched_fields:
                    matched_fields.append("contacts")
                matched_snippets.append(contact)

        if matched_fields:
            results.append({
                "group_id": gid,
                "display_name": p.get("display_name_override") or p.get("display_name", ""),
                "transaction_count": p.get("transaction_count", 0),
                "matched_fields": matched_fields,
                "matched_snippets": sorted(set(matched_snippets)),
                "is_company": p.get("is_company", True),
            })

    # Sort by transaction count descending
    results.sort(key=lambda r: r["transaction_count"], reverse=True)
    return results


@app.get("/api/keywords")
def api_keywords():
    """List all keywords with match counts and review progress."""
    kw_data = _load_keywords()
    keywords = kw_data["keywords"]
    reviews = kw_data["reviews"]

    # Load parties for match counting
    if PARTIES_PATH.exists():
        from cleo.parties.registry import load_registry
        reg = load_registry(PARTIES_PATH)
        parties_data = reg.get("parties", {})
    else:
        parties_data = {}

    result = []
    for kw, meta in keywords.items():
        # Count matches
        matches = _search_parties_for_keyword(kw, parties_data)
        # Count reviews for this keyword
        reviewed = sum(
            1 for rk, rv in reviews.items()
            if rk.startswith(f"{kw}::")
        )
        result.append({
            "keyword": kw,
            "display_name": meta.get("display_name", ""),
            "parent_group_id": meta.get("parent_group_id", ""),
            "created": meta.get("created", ""),
            "match_count": len(matches),
            "reviewed_count": reviewed,
        })

    return result


@app.post("/api/keywords")
async def api_add_keyword(request: Request):
    """Add a new keyword.

    Body: {"keyword": "H&R", "display_name": "H&R REIT", "parent_group_id": "G00882"}
    """
    body = await request.json()
    keyword = (body.get("keyword") or "").strip()
    display_name = (body.get("display_name") or "").strip()
    parent_group_id = (body.get("parent_group_id") or "").strip()

    if not keyword:
        raise HTTPException(400, "keyword is required")
    if not display_name:
        raise HTTPException(400, "display_name is required")

    kw_data = _load_keywords()
    if keyword in kw_data["keywords"]:
        raise HTTPException(409, f"Keyword already exists: {keyword}")

    kw_data["keywords"][keyword] = {
        "display_name": display_name,
        "parent_group_id": parent_group_id,
        "created": datetime.now().strftime("%Y-%m-%d"),
    }
    _save_keywords(kw_data)

    return {"status": "created", "keyword": keyword}


@app.delete("/api/keywords/{keyword:path}")
def api_delete_keyword(keyword: str):
    """Remove a keyword and its reviews."""
    kw_data = _load_keywords()
    if keyword not in kw_data["keywords"]:
        raise HTTPException(404, f"Keyword not found: {keyword}")

    del kw_data["keywords"][keyword]
    # Remove associated reviews
    prefix = f"{keyword}::"
    kw_data["reviews"] = {
        k: v for k, v in kw_data["reviews"].items()
        if not k.startswith(prefix)
    }
    _save_keywords(kw_data)

    return {"status": "deleted", "keyword": keyword}


@app.get("/api/keywords/{keyword:path}/matches")
def api_keyword_matches(keyword: str):
    """Search all party data for a keyword, return matching groups."""
    kw_data = _load_keywords()
    if keyword not in kw_data["keywords"]:
        raise HTTPException(404, f"Keyword not found: {keyword}")

    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry
    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})

    matches = _search_parties_for_keyword(keyword, parties_data)

    # Enrich with review status
    reviews = kw_data["reviews"]
    for m in matches:
        review_key = f"{keyword}::{m['group_id']}"
        review = reviews.get(review_key)
        if review:
            m["review"] = review.get("decision", "")
            m["review_notes"] = review.get("notes", "")
        else:
            m["review"] = ""
            m["review_notes"] = ""

    return matches


@app.post("/api/keywords/{keyword:path}/review/{group_id}")
async def api_keyword_review(keyword: str, group_id: str, request: Request):
    """Review a keyword match for a group.

    Body: {"decision": "confirmed"|"denied", "notes": ""}
    """
    body = await request.json()
    decision = (body.get("decision") or "").strip()
    notes = (body.get("notes") or "").strip()

    if decision not in ("confirmed", "denied"):
        raise HTTPException(400, "decision must be 'confirmed' or 'denied'")

    kw_data = _load_keywords()
    if keyword not in kw_data["keywords"]:
        raise HTTPException(404, f"Keyword not found: {keyword}")

    if not PARTIES_PATH.exists():
        raise HTTPException(404, "Party registry not built. Run: cleo parties")

    from cleo.parties.registry import load_registry
    reg = load_registry(PARTIES_PATH)
    if group_id not in reg.get("parties", {}):
        raise HTTPException(404, f"Party group not found: {group_id}")

    # Get matched fields/snippets for audit
    parties_data = reg.get("parties", {})
    matches = _search_parties_for_keyword(keyword, {group_id: parties_data[group_id]})
    matched_fields = matches[0]["matched_fields"] if matches else []
    matched_snippets = matches[0]["matched_snippets"] if matches else []

    review_key = f"{keyword}::{group_id}"
    kw_data["reviews"][review_key] = {
        "keyword": keyword,
        "group_id": group_id,
        "decision": decision,
        "notes": notes,
        "matched_fields": matched_fields,
        "matched_snippets": matched_snippets,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    _save_keywords(kw_data)

    # Audit log
    _log_party_edit({
        "action": "keyword_review",
        "keyword": keyword,
        "group_id": group_id,
        "decision": decision,
        "notes": notes,
        "matched_fields": matched_fields,
        "matched_snippets": matched_snippets,
    })

    return {"status": "saved", "keyword": keyword, "group_id": group_id, "decision": decision}


def _log_party_edit(entry: dict) -> None:
    """Append an edit entry to the party edits JSONL audit log."""
    entry["timestamp"] = datetime.now().isoformat(timespec="seconds")
    with open(PARTY_EDITS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@app.get("/api/html/{rt_id}")
def api_html(rt_id: str):
    """Serve raw HTML file for iframe display."""
    path = HtmlIndex().resolve(rt_id)
    if not path.exists():
        raise HTTPException(404, f"HTML not found: {rt_id}")
    return FileResponse(path, media_type="text/html")


@app.get("/api/active/{rt_id}")
def api_active(rt_id: str):
    """Get parsed JSON from active version."""
    act = active_dir()
    if act is None:
        raise HTTPException(404, "No active version")
    path = act / f"{rt_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Not in active: {rt_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    # Enrich with brands via property registry lookup
    brands: list[str] = []
    if PROPERTIES_PATH.exists():
        matches = _get_brand_matches()
        from cleo.properties.registry import load_registry
        reg = load_registry(PROPERTIES_PATH)
        for pid, prop in reg.get("properties", {}).items():
            if rt_id in prop.get("rt_ids", []):
                brands = _brands_for_prop(pid)
                break
    data["brands"] = brands
    data["ppsf"] = _calculate_ppsf(
        data.get("transaction", {}).get("sale_price", ""),
        data.get("export_extras", {}).get("building_sf", ""),
    )
    # Enrich parties with group_id and contact_id for linking
    for party_key in ("transferor", "transferee"):
        if party_key in data:
            data[party_key]["group_id"] = _lookup_group_id(
                data[party_key].get("name", "")
            )
            data[party_key]["contact_id"] = _make_contact_id(
                data[party_key].get("contact", "")
            )
    return JSONResponse(data)


@app.get("/api/sandbox/{rt_id}")
def api_sandbox(rt_id: str):
    """Get parsed JSON from sandbox."""
    sb = sandbox_path()
    if not sb.is_dir():
        raise HTTPException(404, "No sandbox")
    path = sb / f"{rt_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Not in sandbox: {rt_id}")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@app.get("/api/flags")
def api_flags():
    """Get all flag definitions and counts."""
    from cleo.validate.html_checks import FLAG_DEFS
    from cleo.validate.parse_checks import PARSE_FLAG_DEFS

    html_flags = _load_json(DATA_DIR / "html_flags.json")
    parse_flags = _load_json(DATA_DIR / "parse_flags.json")

    # Count per flag
    html_counts = {}
    for flags in html_flags.values():
        for f in flags:
            html_counts[f] = html_counts.get(f, 0) + 1

    parse_counts = {}
    for flags in parse_flags.values():
        for f in flags:
            parse_counts[f] = parse_counts.get(f, 0) + 1

    return {
        "html_flag_defs": FLAG_DEFS,
        "parse_flag_defs": PARSE_FLAG_DEFS,
        "html_counts": html_counts,
        "parse_counts": parse_counts,
    }


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

@app.get("/api/review/{rt_id}")
def api_get_review(rt_id: str):
    """Get existing review for an RT ID."""
    reviews = _load_json(REVIEWS_PATH)
    return reviews.get(rt_id, {})


@app.post("/api/review/{rt_id}")
async def api_save_review(rt_id: str, request: Request):
    """Save a review for an RT ID.

    Body: {
        "determination": "bad_source" | "parser_issue" | "clean" | "",
        "notes": "free text",
        "overrides": {"city": "Richards Landing", ...}
    }
    """
    body = await request.json()
    reviews = _load_json(REVIEWS_PATH)

    determination = body.get("determination", "")
    notes = body.get("notes", "")
    overrides = body.get("overrides", {})

    # Clean empty overrides
    overrides = {k: v for k, v in overrides.items() if v.strip()}

    sandbox_accepted = body.get("sandbox_accepted", None)

    if not determination and not notes and not overrides:
        # Empty review — remove if exists
        if rt_id in reviews:
            del reviews[rt_id]
    else:
        review_entry = {
            "determination": determination,
            "notes": notes,
            "overrides": overrides,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        if sandbox_accepted is True:
            review_entry["sandbox_accepted"] = True
        reviews[rt_id] = review_entry

    _save_json(REVIEWS_PATH, reviews)
    return {"status": "saved", "rt_id": rt_id}


@app.get("/api/reviews/stats")
def api_reviews_stats():
    """Get review summary stats."""
    reviews = _load_json(REVIEWS_PATH)
    total = len(reviews)
    by_det = {}
    with_overrides = 0
    for r in reviews.values():
        det = r.get("determination", "") or "unset"
        by_det[det] = by_det.get(det, 0) + 1
        if r.get("overrides"):
            with_overrides += 1
    return {
        "total_reviewed": total,
        "by_determination": by_det,
        "with_overrides": with_overrides,
    }


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

@app.get("/api/extracted/{rt_id}")
def api_extracted(rt_id: str):
    """Get extracted JSON from active extraction version."""
    ext_dir = extract_ver.store.active_dir()
    if ext_dir is None:
        raise HTTPException(404, "No active extraction version")
    path = ext_dir / f"{rt_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Not in extracted: {rt_id}")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@app.get("/api/extract-sandbox/{rt_id}")
def api_extract_sandbox(rt_id: str):
    """Get extracted JSON from extraction sandbox."""
    sb = extract_ver.store.sandbox_path()
    if not sb.is_dir():
        raise HTTPException(404, "No extraction sandbox")
    path = sb / f"{rt_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Not in extraction sandbox: {rt_id}")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


_extract_changes_cache: list | None = None

@app.get("/api/extract-changes")
def api_extract_changes():
    """Return RT IDs where extraction sandbox differs from active."""
    global _extract_changes_cache
    if _extract_changes_cache is not None:
        return _extract_changes_cache

    ext_store = extract_ver.store
    ext_active = ext_store.active_dir()
    ext_sb = ext_store.sandbox_path()
    if ext_active is None or not ext_sb.is_dir():
        return []

    changed = []
    for sb_file in sorted(ext_sb.glob("*.json")):
        act_file = ext_active / sb_file.name
        if not act_file.exists():
            changed.append(sb_file.stem)
            continue
        sb_data = json.loads(sb_file.read_text(encoding="utf-8"))
        act_data = json.loads(act_file.read_text(encoding="utf-8"))
        # Compare ignoring volatile source_version field
        sb_cmp = {k: v for k, v in sb_data.items() if k != "source_version"}
        act_cmp = {k: v for k, v in act_data.items() if k != "source_version"}
        if sb_cmp != act_cmp:
            changed.append(sb_file.stem)

    _extract_changes_cache = changed
    return changed


@app.get("/api/extract-changes/clear-cache")
def api_clear_extract_changes_cache():
    """Clear the extract changes cache (call after new sandbox/promote)."""
    global _extract_changes_cache
    _extract_changes_cache = None
    return {"status": "cleared"}


@app.get("/api/extract-status")
def api_extract_status():
    """Get extraction versioning status."""
    ext_store = extract_ver.store
    return {
        "active_version": ext_store.active_version(),
        "versions": ext_store.list_versions(),
        "has_sandbox": ext_store.sandbox_path().is_dir(),
    }


import re as _re

_addr_issues_cache: dict | None = None

@app.get("/api/extract-address-issues")
def api_extract_address_issues():
    """Classify extracted addresses into geocoding issue categories.

    Returns dict of category -> list of RT IDs.
    """
    global _addr_issues_cache
    if _addr_issues_cache is not None:
        return _addr_issues_cache

    ext_store = extract_ver.store
    ext_active = ext_store.active_dir()
    if ext_active is None:
        return {}

    cats: dict[str, set[str]] = {
        "no_street_number": set(),
        "garbage_address": set(),
        "legal_description": set(),
        "suite_leading": set(),
        "intersection": set(),
        "half_address": set(),
        "building_name": set(),
        "minor_issues": set(),
    }

    _SUITE_RE = _re.compile(r"^(?:suite|ste|unit|apt)\b", _re.I)
    _BUILDING_RE = _re.compile(
        r"^(?:commerce court|toronto[- ]dominion|td bank|royal bank|"
        r"first canadian|bay adelaide|brookfield)", _re.I,
    )
    _LEGAL_RE = _re.compile(r"\b(?:LOT|LOTS|BLOCK|PLAN|PART|CONC)\b", _re.I)
    _INTERSECT_RE = _re.compile(r"\b(?:NEC|SEC|NWC|SWC|N/E|S/E|N/W|S/W)\b")

    for f in sorted(ext_active.glob("*.json")):
        if f.stem == "_meta":
            continue
        rt_id = f.stem
        data = json.loads(f.read_text(encoding="utf-8"))

        # Property expanded addresses
        for addr_obj in data.get("property", {}).get("addresses", []):
            if addr_obj.get("skip_geocode"):
                continue
            for exp in addr_obj.get("expanded", []):
                if not exp:
                    continue
                first = exp.split(",")[0]
                low = exp.lower()

                if "1/2" in exp or "\u00bd" in exp:
                    cats["half_address"].add(rt_id)
                if "/" in first or _INTERSECT_RE.search(first):
                    cats["intersection"].add(rt_id)
                if not exp[0].isdigit():
                    if _LEGAL_RE.search(exp):
                        cats["legal_description"].add(rt_id)
                    else:
                        cats["no_street_number"].add(rt_id)

        # Seller / buyer
        for party_key in ("seller", "buyer"):
            p = data.get(party_key, {})
            if not isinstance(p, dict) or p.get("skip_geocode"):
                continue
            norm = (p.get("normalized") or "").strip()
            if not norm:
                continue
            low = norm.lower()

            if "PIN:" in norm or "cash:" in norm or "principal:" in norm:
                cats["garbage_address"].add(rt_id)
            elif _SUITE_RE.match(low):
                cats["suite_leading"].add(rt_id)
            elif _BUILDING_RE.match(low):
                cats["building_name"].add(rt_id)
            elif _re.match(r"^(?:transit|attn|attention|c/o|c/0)\b", low):
                cats["minor_issues"].add(rt_id)
            elif _re.match(r"^(?:\d+\w*\s+)?(?:floor|level|flr)\b", low):
                cats["minor_issues"].add(rt_id)
            elif "," not in norm or not _re.search(r"\d", norm.split(",")[0]):
                cats["minor_issues"].add(rt_id)

    result = {k: sorted(v) for k, v in cats.items()}
    _addr_issues_cache = result
    return result


# ---------------------------------------------------------------------------
# Extraction Reviews
# ---------------------------------------------------------------------------

@app.get("/api/extract-review/{rt_id}")
def api_get_extract_review(rt_id: str):
    """Get existing extraction review for an RT ID."""
    reviews = _load_json(EXTRACT_REVIEWS_PATH)
    return reviews.get(rt_id, {})


@app.post("/api/extract-review/{rt_id}")
async def api_save_extract_review(rt_id: str, request: Request):
    """Save an extraction review for an RT ID.

    Body: {
        "determination": "clean" | "extraction_issue" | "parser_issue" | "",
        "notes": "free text",
        "sandbox_accepted": true  (optional)
    }
    """
    body = await request.json()
    reviews = _load_json(EXTRACT_REVIEWS_PATH)

    determination = body.get("determination", "")
    notes = body.get("notes", "")
    overrides = body.get("overrides", {})
    sandbox_accepted = body.get("sandbox_accepted", None)

    # Clean empty overrides
    overrides = {k: v for k, v in overrides.items() if v and v.strip()}

    if not determination and not notes and not overrides:
        if rt_id in reviews:
            del reviews[rt_id]
    else:
        review_entry = {
            "determination": determination,
            "notes": notes,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }
        if overrides:
            review_entry["overrides"] = overrides
        if sandbox_accepted is True:
            review_entry["sandbox_accepted"] = True
        reviews[rt_id] = review_entry

    _save_json(EXTRACT_REVIEWS_PATH, reviews)
    return {"status": "saved", "rt_id": rt_id}


# ---------------------------------------------------------------------------
# Regressions
# ---------------------------------------------------------------------------

@app.get("/api/regressions")
def api_regressions():
    """Return RT IDs of reviewed records that changed in sandbox.

    These are records that have been reviewed (any determination) but
    differ between active and sandbox, excluding those already approved
    via sandbox_accepted.
    """
    act = active_dir()
    sb = sandbox_path()
    if act is None or not sb.is_dir():
        return []

    reviews = _load_json(REVIEWS_PATH)
    reviewed_ids = {
        rt_id for rt_id, r in reviews.items()
        if r.get("determination") and not r.get("sandbox_accepted")
    }
    if not reviewed_ids:
        return []

    regression_ids = []
    for rt_id in sorted(reviewed_ids):
        act_file = act / f"{rt_id}.json"
        sb_file = sb / f"{rt_id}.json"
        if not act_file.exists() or not sb_file.exists():
            continue
        act_data = json.loads(act_file.read_text(encoding="utf-8"))
        sb_data = json.loads(sb_file.read_text(encoding="utf-8"))
        # Strip volatile fields
        act_clean = {k: v for k, v in act_data.items() if k not in VOLATILE_FIELDS}
        sb_clean = {k: v for k, v in sb_data.items() if k not in VOLATILE_FIELDS}
        if act_clean != sb_clean:
            regression_ids.append(rt_id)

    return regression_ids


@app.get("/api/extract-regressions")
def api_extract_regressions():
    """Return RT IDs of extraction-reviewed records that changed in extraction sandbox.

    These are records that have an extraction review with a determination
    but differ between extraction active and extraction sandbox, excluding
    those already approved via sandbox_accepted.
    """
    ext_store = extract_ver.store
    ext_active = ext_store.active_dir()
    ext_sb = ext_store.sandbox_path()
    if ext_active is None or not ext_sb.is_dir():
        return []

    reviews = _load_json(EXTRACT_REVIEWS_PATH)
    reviewed_ids = {
        rt_id for rt_id, r in reviews.items()
        if r.get("determination") and not r.get("sandbox_accepted")
    }
    if not reviewed_ids:
        return []

    regression_ids = []
    for rt_id in sorted(reviewed_ids):
        act_file = ext_active / f"{rt_id}.json"
        sb_file = ext_sb / f"{rt_id}.json"
        if not act_file.exists() or not sb_file.exists():
            continue
        act_data = json.loads(act_file.read_text(encoding="utf-8"))
        sb_data = json.loads(sb_file.read_text(encoding="utf-8"))
        act_clean = {k: v for k, v in act_data.items() if k != "source_version"}
        sb_clean = {k: v for k, v in sb_data.items() if k != "source_version"}
        if act_clean != sb_clean:
            regression_ids.append(rt_id)

    return regression_ids


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

_geocode_cache: dict | None = None

def _get_geocode_cache() -> dict:
    global _geocode_cache
    if _geocode_cache is None:
        _geocode_cache = _load_json(GEOCODE_CACHE_PATH)
    return _geocode_cache


@app.get("/api/geocoded/{rt_id}")
def api_geocoded(rt_id: str):
    """Get geocode results for an RT ID's addresses.

    Looks up each address from the extracted data in the geocode cache.
    Returns the extracted data enriched with geocode results.
    """
    ext_dir = extract_ver.store.active_dir()
    if ext_dir is None:
        raise HTTPException(404, "No active extraction version")
    path = ext_dir / f"{rt_id}.json"
    if not path.exists():
        raise HTTPException(404, f"Not in extracted: {rt_id}")

    data = json.loads(path.read_text(encoding="utf-8"))
    cache = _get_geocode_cache()

    # Check for overrides
    ext_reviews = _load_json(EXTRACT_REVIEWS_PATH)
    overrides = ext_reviews.get(rt_id, {}).get("overrides", {})

    result = {"rt_id": rt_id, "property": [], "seller": None, "buyer": None}

    # Property addresses
    for i, addr_obj in enumerate(data.get("property", {}).get("addresses", [])):
        override_key = f"property_{i}"
        entry = {
            "original": addr_obj.get("original", ""),
            "expanded": addr_obj.get("expanded", []),
            "skip_geocode": addr_obj.get("skip_geocode", False),
            "override": overrides.get(override_key, ""),
            "geocode_results": [],
        }

        if entry["override"]:
            # Override replaces expanded — geocode the override
            geo = cache.get(entry["override"].strip().upper(), {})
            entry["geocode_results"].append({
                "address": entry["override"],
                "geo": _format_geo(geo),
            })
        else:
            for exp_addr in entry["expanded"]:
                geo = cache.get(exp_addr.strip().upper(), {})
                entry["geocode_results"].append({
                    "address": exp_addr,
                    "geo": _format_geo(geo),
                })

        result["property"].append(entry)

    # Seller
    seller = data.get("seller", {})
    seller_addr = overrides.get("seller", "").strip() or seller.get("normalized", "")
    seller_geo = cache.get(seller_addr.strip().upper(), {}) if seller_addr else {}
    result["seller"] = {
        "original": seller.get("original", ""),
        "normalized": seller.get("normalized", ""),
        "skip_geocode": seller.get("skip_geocode", False),
        "override": overrides.get("seller", ""),
        "geo": _format_geo(seller_geo),
    }

    # Buyer
    buyer = data.get("buyer", {})
    buyer_addr = overrides.get("buyer", "").strip() or buyer.get("normalized", "")
    buyer_geo = cache.get(buyer_addr.strip().upper(), {}) if buyer_addr else {}
    result["buyer"] = {
        "original": buyer.get("original", ""),
        "normalized": buyer.get("normalized", ""),
        "skip_geocode": buyer.get("skip_geocode", False),
        "override": overrides.get("buyer", ""),
        "geo": _format_geo(buyer_geo),
    }

    return result


def _format_geo(geo: dict) -> dict:
    """Format a geocode cache entry for API response."""
    if not geo:
        return {"status": "not_cached"}
    if geo.get("failed"):
        return {"status": "failed", "reason": geo.get("fail_reason", "")}
    return {
        "status": "success",
        "lat": geo.get("lat"),
        "lng": geo.get("lng"),
        "formatted_address": geo.get("formatted_address", ""),
        "accuracy": geo.get("accuracy", ""),
        "confidence": geo.get("match_code", {}).get("confidence", ""),
    }


@app.get("/api/geocode-status")
def api_geocode_status():
    """Get geocode cache statistics."""
    cache = _get_geocode_cache()
    total = len(cache)
    failures = sum(1 for v in cache.values() if v.get("failed"))
    return {
        "total": total,
        "successes": total - failures,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Feedback (front-facing app)
# ---------------------------------------------------------------------------

@app.get("/api/feedback/{entity_id}")
def api_get_feedback(entity_id: str):
    """Get feedback for a transaction or property."""
    feedback = _load_json(FEEDBACK_PATH)
    return feedback.get(entity_id, {})


@app.post("/api/feedback/{entity_id}")
async def api_save_feedback(entity_id: str, request: Request):
    """Save feedback for a transaction or property.

    Body: {"has_issue": true/false, "notes": "free text"}
    """
    body = await request.json()
    feedback = _load_json(FEEDBACK_PATH)

    has_issue = body.get("has_issue", False)
    notes = body.get("notes", "").strip()

    if not has_issue and not notes:
        if entity_id in feedback:
            del feedback[entity_id]
    else:
        feedback[entity_id] = {
            "has_issue": has_issue,
            "notes": notes,
            "date": datetime.now().strftime("%Y-%m-%d"),
        }

    _save_json(FEEDBACK_PATH, feedback)
    return {"status": "saved", "entity_id": entity_id}


# ---------------------------------------------------------------------------
# Dashboard (front-facing app)
# ---------------------------------------------------------------------------

_dashboard_cache: dict | None = None
_dashboard_cache_key: tuple | None = None


def _parse_price_float(price_str: str) -> float | None:
    """Parse a price string like '$1,234,567' into a float, or None."""
    if not price_str:
        return None
    try:
        return float(price_str.replace("$", "").replace(",", ""))
    except ValueError:
        return None


@app.get("/api/dashboard")
def api_dashboard():
    """Return aggregated dashboard data."""
    global _dashboard_cache, _dashboard_cache_key
    from collections import Counter

    ver = active_version()
    if ver is None:
        raise HTTPException(404, "No active version")

    bm_mtime = BRAND_MATCHES_PATH.stat().st_mtime if BRAND_MATCHES_PATH.exists() else 0
    cache_key = (ver, bm_mtime)
    if _dashboard_cache is not None and _dashboard_cache_key == cache_key:
        return JSONResponse(_dashboard_cache)

    act = active_dir()

    # --- Load registries for counts ---
    prop_count = 0
    geocoded_count = 0
    branded_props = set()
    gw_props = 0
    rt_to_brands: dict[str, list[str]] = {}  # rt_id -> [brand names]
    if PROPERTIES_PATH.exists():
        from cleo.properties.registry import load_registry
        reg = load_registry(PROPERTIES_PATH)
        props = reg.get("properties", {})
        prop_count = len(props)
        brand_matches = _get_brand_matches()
        branded_props = set(brand_matches.keys())
        # Build rt_id -> brand names lookup
        for pid, p in props.items():
            if p.get("lat") is not None and p.get("lng") is not None:
                geocoded_count += 1
            if p.get("gw_ids"):
                gw_props += 1
            if pid in branded_props:
                brands = sorted(set(e["brand"] for e in brand_matches[pid]))
                for rt_id in p.get("rt_ids", []):
                    rt_to_brands[rt_id] = brands

    party_count = 0
    if PARTIES_PATH.exists():
        parties_data = _load_json(PARTIES_PATH)
        party_count = len(parties_data.get("groups", {}))

    # --- Scan transactions ---
    year_counter: Counter = Counter()
    year_volume: Counter = Counter()
    month_volume: Counter = Counter()
    month_count: Counter = Counter()
    city_counter: Counter = Counter()
    city_pop: dict[str, int | None] = {}
    price_buckets: Counter = Counter()
    recent: list[dict] = []
    tx_count = 0
    largest_by_month: dict[str, dict] = {}  # YYYY-MM -> best tx
    brand_tx_12mo: Counter = Counter()  # brand -> count in last 12 months
    brand_tx_6mo: Counter = Counter()  # brand -> count in last 6 months
    brand_tx_1mo: Counter = Counter()  # brand -> count in last month
    brand_tx_all: Counter = Counter()  # brand -> count all time
    brands_current_month: set[str] = set()  # unique brands traded this month
    brands_last_month: set[str] = set()  # unique brands traded last month
    recent_brand_txns: list[dict] = []  # brand transactions sorted by date

    from datetime import datetime, timedelta
    cutoff_12mo = (datetime.now() - timedelta(days=365)).strftime("%Y-%m")
    cutoff_6mo = (datetime.now() - timedelta(days=180)).strftime("%Y-%m")
    current_month = datetime.now().strftime("%Y-%m")
    now = datetime.now()
    if now.month == 1:
        last_month = f"{now.year - 1}-12"
    else:
        last_month = f"{now.year}-{now.month - 1:02d}"

    for f in sorted(act.glob("*.json")):
        if f.stem == "_meta":
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        tx_count += 1

        tx = data.get("transaction", {})
        addr = tx.get("address", {})
        city = addr.get("city", "")
        iso = tx.get("sale_date_iso", "")
        price_str = tx.get("sale_price", "")

        # Year
        price = _parse_price_float(price_str)
        if iso and len(iso) >= 4:
            year_counter[iso[:4]] += 1
            if price is not None:
                year_volume[iso[:4]] += price
            if len(iso) >= 7:
                month_count[iso[:7]] += 1
                if price is not None:
                    month_volume[iso[:7]] += price

        # City
        if city:
            city_counter[city] += 1
            if city not in city_pop:
                city_pop[city] = _lookup_population(city)

        # Price bucket
        if price is not None:
            if price < 500_000:
                price_buckets["<$500K"] += 1
            elif price < 1_000_000:
                price_buckets["$500K-$1M"] += 1
            elif price < 2_500_000:
                price_buckets["$1M-$2.5M"] += 1
            elif price < 5_000_000:
                price_buckets["$2.5M-$5M"] += 1
            elif price < 10_000_000:
                price_buckets["$5M-$10M"] += 1
            else:
                price_buckets["$10M+"] += 1

        # Collect for recent sort
        rt_id = data.get("rt_id", f.stem)
        recent.append({
            "rt_id": rt_id,
            "address": addr.get("address", ""),
            "city": city,
            "sale_price": price_str,
            "sale_date": tx.get("sale_date", ""),
            "sale_date_iso": iso,
            "buyer": data.get("transferee", {}).get("name", ""),
        })

        # Largest transaction per month (last 6 months)
        if iso and len(iso) >= 7 and price is not None:
            ym = iso[:7]
            if ym not in largest_by_month or price > largest_by_month[ym]["price"]:
                largest_by_month[ym] = {
                    "month": ym,
                    "rt_id": rt_id,
                    "address": addr.get("address", ""),
                    "city": city,
                    "sale_price": price_str,
                    "price": price,
                }

        # Brand-linked transaction tracking
        tx_brands = rt_to_brands.get(rt_id, [])
        if tx_brands and iso:
            for brand in tx_brands:
                brand_tx_all[brand] += 1
                if iso >= cutoff_12mo:
                    brand_tx_12mo[brand] += 1
                if iso >= cutoff_6mo:
                    brand_tx_6mo[brand] += 1
                if iso[:7] == current_month:
                    brand_tx_1mo[brand] += 1
                    brands_current_month.add(brand)
                if iso[:7] == last_month:
                    brands_last_month.add(brand)
            recent_brand_txns.append({
                "rt_id": rt_id,
                "brands": tx_brands,
                "sale_date_iso": iso,
            })

    # Sort recent by date descending, take top 15
    recent.sort(key=lambda r: r.get("sale_date_iso", ""), reverse=True)
    recent_top = [
        {k: v for k, v in r.items() if k != "sale_date_iso"}
        for r in recent[:15]
    ]

    # Build sorted year data
    years_sorted = sorted(year_counter.items())
    transactions_by_year = [{"year": y, "count": c} for y, c in years_sorted]
    volume_by_year = [
        {"year": y, "volume": round(year_volume.get(y, 0))}
        for y, _c in years_sorted
    ]

    # Last 12 months of volume
    months_sorted = sorted(m for m in month_volume if m >= cutoff_12mo)
    volume_by_month = [
        {"month": m, "volume": round(month_volume[m])}
        for m in months_sorted
    ]
    transactions_by_month = [
        {"month": m, "count": month_count[m]}
        for m in months_sorted
    ]

    # Top 15 cities
    top_cities = [
        {"city": city, "count": count, "population": city_pop.get(city)}
        for city, count in city_counter.most_common(15)
    ]

    # Price ranges in order
    price_order = ["<$500K", "$500K-$1M", "$1M-$2.5M", "$2.5M-$5M", "$5M-$10M", "$10M+"]
    price_ranges = [
        {"range": r, "count": price_buckets.get(r, 0)}
        for r in price_order
    ]

    # Largest transaction per month (last 6 months, sorted chronologically)
    largest_monthly = sorted(
        [
            {k: v for k, v in rec.items() if k != "price"}
            for ym, rec in largest_by_month.items()
            if ym >= cutoff_6mo
        ],
        key=lambda r: r["month"],
        reverse=True,
    )[:6]

    # 5 most recently sold brands (unique brand names, newest first)
    recent_brand_txns.sort(key=lambda r: r["sale_date_iso"], reverse=True)
    seen_brands: set[str] = set()
    recently_sold_brands: list[str] = []
    for bt in recent_brand_txns:
        for brand in bt["brands"]:
            if brand not in seen_brands:
                seen_brands.add(brand)
                recently_sold_brands.append(brand)
                if len(recently_sold_brands) >= 5:
                    break
        if len(recently_sold_brands) >= 5:
            break

    # Most traded brand in last 12 months
    top_brand = None
    if brand_tx_12mo:
        brand_name, brand_count = brand_tx_12mo.most_common(1)[0]
        top_brand = {"brand": brand_name, "count": brand_count}

    # Top brands by period (top 8 each)
    def _top_brands(counter: Counter, n: int = 8) -> list[dict]:
        return [{"brand": b, "count": c} for b, c in counter.most_common(n)]

    top_brands_by_period = {
        "month": _top_brands(brand_tx_1mo),
        "6months": _top_brands(brand_tx_6mo),
        "year": _top_brands(brand_tx_12mo),
        "all": _top_brands(brand_tx_all),
    }

    result = {
        "stats": {
            "total_transactions": tx_count,
            "total_properties": prop_count,
            "total_parties": party_count,
            "properties_with_brands": len(branded_props),
            "brands_traded_current_month": len(brands_current_month),
            "brands_traded_last_month": len(brands_last_month),
            "geocoded_properties": geocoded_count,
            "properties_with_gw": gw_props,
        },
        "transactions_by_year": transactions_by_year,
        "volume_by_year": volume_by_year,
        "volume_by_month": volume_by_month,
        "transactions_by_month": transactions_by_month,
        "top_cities": top_cities,
        "price_ranges": price_ranges,
        "recent_transactions": recent_top,
        "largest_monthly": largest_monthly,
        "recently_sold_brands": recently_sold_brands,
        "top_brand_12mo": top_brand,
        "top_brands_by_period": top_brands_by_period,
    }

    _dashboard_cache = result
    _dashboard_cache_key = cache_key
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Dashboard — Pipeline & Prospects
# ---------------------------------------------------------------------------


@app.get("/api/dashboard/pipeline")
def api_dashboard_pipeline():
    """Aggregate CRM deal data by stage for the pipeline summary."""
    deals_data: dict = {}
    if CRM_DEALS_PATH.exists():
        deals_data = json.loads(CRM_DEALS_PATH.read_text(encoding="utf-8"))

    deals = deals_data.get("deals", {})

    # Load properties for price lookup
    props: dict = {}
    if PROPERTIES_PATH.exists():
        from cleo.properties.registry import load_registry
        reg = load_registry(PROPERTIES_PATH)
        props = reg.get("properties", {})

    stage_agg: dict[str, dict] = {}
    active_stages = {"active_deal", "in_negotiation", "under_contract"}
    closed_stages = {"closed_won", "lost_cancelled"}
    all_stages = active_stages | closed_stages

    for stage in all_stages:
        stage_agg[stage] = {"count": 0, "value": 0}

    for deal in deals.values():
        stage = deal.get("stage", "active_deal")
        if stage not in all_stages:
            continue
        stage_agg[stage]["count"] += 1
        # Try to get deal value from associated property's latest sale price
        prop_id = deal.get("prop_id", "")
        if prop_id and prop_id in props:
            p = props[prop_id]
            price = _parse_price_float(p.get("latest_sale_price", ""))
            if price:
                stage_agg[stage]["value"] += price

    total_active = sum(stage_agg[s]["count"] for s in active_stages)
    total_active_value = sum(stage_agg[s]["value"] for s in active_stages)

    return JSONResponse({
        "stages": stage_agg,
        "total_active": total_active,
        "total_active_value": round(total_active_value),
    })


@app.get("/api/dashboard/prospects")
def api_dashboard_prospects():
    """Return top prospecting targets: stale properties and repeat traders."""
    # Load properties
    props: dict = {}
    if PROPERTIES_PATH.exists():
        from cleo.properties.registry import load_registry
        reg = load_registry(PROPERTIES_PATH)
        props = reg.get("properties", {})

    # Load deals to determine pipeline status
    deals_data: dict = {}
    if CRM_DEALS_PATH.exists():
        deals_data = json.loads(CRM_DEALS_PATH.read_text(encoding="utf-8"))
    deals = deals_data.get("deals", {})

    # Build set of prop_ids that already have deals
    props_with_deals: set[str] = set()
    for deal in deals.values():
        pid = deal.get("prop_id", "")
        if pid:
            props_with_deals.add(pid)

    # Load brand matches for enrichment
    brand_matches = _get_brand_matches()

    from datetime import datetime
    now = datetime.now()

    # Stale properties: oldest last_sale_date, not yet in pipeline
    stale: list[dict] = []
    for pid, p in props.items():
        if pid in props_with_deals:
            continue
        iso = p.get("latest_sale_date_iso", "")
        if not iso or len(iso) < 10:
            continue
        try:
            sale_dt = datetime.strptime(iso[:10], "%Y-%m-%d")
            days = (now - sale_dt).days
        except ValueError:
            continue
        brands = sorted(set(e["brand"] for e in brand_matches.get(pid, [])))
        stale.append({
            "prop_id": pid,
            "address": p.get("address", ""),
            "city": p.get("city", ""),
            "last_sale_date": iso[:10],
            "last_price": p.get("latest_sale_price", ""),
            "days_since_sale": days,
            "brands": brands,
            "pipeline_status": "not_started",
        })

    stale.sort(key=lambda x: x["days_since_sale"], reverse=True)
    stale_top = stale[:10]

    # Repeat traders: party groups with highest buy+sell count
    parties_data: dict = {}
    if PARTIES_PATH.exists():
        parties_data = _load_json(PARTIES_PATH)

    groups = parties_data.get("groups", {})
    traders: list[dict] = []
    for gid, g in groups.items():
        buy = g.get("buy_count", 0)
        sell = g.get("sell_count", 0)
        total = buy + sell
        if total < 2:
            continue
        traders.append({
            "group_id": gid,
            "name": g.get("canonical_name", ""),
            "buy_count": buy,
            "sell_count": sell,
            "total_volume": round(g.get("total_volume", 0)),
            "last_active": g.get("last_active", ""),
        })

    traders.sort(key=lambda x: x["buy_count"] + x["sell_count"], reverse=True)
    traders_top = traders[:10]

    return JSONResponse({
        "stale_properties": stale_top,
        "repeat_traders": traders_top,
    })


# ---------------------------------------------------------------------------
# Universal search
# ---------------------------------------------------------------------------


@app.get("/api/search")
def api_search(q: str = "", limit: int = 5):
    """Search across transactions, properties, parties, and contacts."""
    q = q.strip().lower()
    if len(q) < 2:
        return JSONResponse({"transactions": [], "properties": [], "parties": [], "contacts": []})

    def _match(items: list[dict], key: str, id_field: str, label_fn, sublabel_fn):
        hits = []
        for item in items:
            if q in item.get(key, ""):
                hits.append({
                    "id": item[id_field],
                    "label": label_fn(item),
                    "sublabel": sublabel_fn(item),
                })
                if len(hits) >= limit:
                    break
        return hits

    # Transactions
    tx_data = _transactions_cache
    if tx_data is None:
        try:
            api_transactions()
            tx_data = _transactions_cache or []
        except Exception:
            tx_data = []
    tx_hits = _match(
        tx_data, "_search_text", "rt_id",
        lambda r: f"{r.get('address', '')} — {r.get('city', '')}",
        lambda r: f"{r.get('rt_id', '')} | {r.get('sale_date', '')} | {r.get('sale_price', '')}",
    )

    # Properties
    prop_data = _properties_cache
    if prop_data is None:
        try:
            api_properties()
            prop_data = _properties_cache or []
        except Exception:
            prop_data = []
    prop_hits = _match(
        prop_data, "_search_text", "prop_id",
        lambda r: f"{r.get('address', '')} — {r.get('city', '')}",
        lambda r: f"{r.get('prop_id', '')} | {r.get('transaction_count', 0)} transactions",
    )

    # Parties
    party_data = _parties_cache
    if party_data is None:
        try:
            api_parties()
            party_data = _parties_cache or []
        except Exception:
            party_data = []
    party_hits = _match(
        party_data, "_search_text", "group_id",
        lambda r: r.get("display_name", ""),
        lambda r: f"{r.get('group_id', '')} | {r.get('transaction_count', 0)} transactions",
    )

    # Contacts
    contact_data = _contacts_cache
    if contact_data is None:
        try:
            api_contacts()
            contact_data = _contacts_cache or []
        except Exception:
            contact_data = []
    contact_hits = _match(
        contact_data, "_search_text", "contact_id",
        lambda r: r.get("name", ""),
        lambda r: f"{r.get('transaction_count', 0)} transactions | {', '.join(r.get('phones', [])[:1])}",
    )

    return JSONResponse({
        "transactions": tx_hits,
        "properties": prop_hits,
        "parties": party_hits,
        "contacts": contact_hits,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Admin — run CLI commands from the frontend
# ---------------------------------------------------------------------------

_ALLOWED_COMMANDS: dict[str, list[str]] = {
    "rebuild-properties": ["properties"],
    "rebuild-parties": ["parties"],
    "rebuild-all": ["properties", "&&", "parties"],
    "apply-geocodes": ["properties", "--apply-geocodes"],
    "refresh-geocodes": ["properties", "--apply-geocodes", "--refresh"],
    "frontend-build": ["_frontend_build"],
    "clear-caches": ["_clear_caches"],
    "restart-backend": ["_restart_backend"],
}

_admin_log: list[dict] = []


@app.post("/api/admin/run")
async def api_admin_run(request: Request):
    """Run a predefined admin command, streaming output as SSE."""
    body = await request.json()
    cmd_key = body.get("command", "")
    if cmd_key not in _ALLOWED_COMMANDS:
        raise HTTPException(400, f"Unknown command: {cmd_key}")

    python_bin = sys.executable

    # Special: touch a file to trigger uvicorn --reload (instant, no streaming)
    if cmd_key == "restart-backend":
        init_file = Path(__file__).parent.parent / "__init__.py"
        init_file.touch()
        entry = {"command": cmd_key, "ts": datetime.now().isoformat(), "ok": True, "output": "Touched cleo/__init__.py — uvicorn reload triggered. Only works when started via ./dev.sh."}
        _admin_log.append(entry)
        return entry

    # Special: clear in-process caches (instant, no streaming needed)
    if cmd_key == "clear-caches":
        global _properties_cache, _properties_cache_mtime
        _properties_cache = None
        _properties_cache_mtime = 0
        entry = {"command": cmd_key, "ts": datetime.now().isoformat(), "ok": True, "output": "All caches cleared."}
        _admin_log.append(entry)
        return entry

    def _build_parts(cmd_key: str) -> tuple[list[list[str]], str | None]:
        """Return (cli_parts, cwd) for the command."""
        if cmd_key == "frontend-build":
            frontend_dir = str(Path(__file__).parent.parent.parent / "frontend")
            return [["/usr/bin/env", "npm", "run", "build"]], frontend_dir
        steps = _ALLOWED_COMMANDS[cmd_key]
        parts: list[list[str]] = []
        current: list[str] = []
        for tok in steps:
            if tok == "&&":
                if current:
                    parts.append([python_bin, "-m", "cleo.cli"] + current)
                current = []
            else:
                current.append(tok)
        if current:
            parts.append([python_bin, "-m", "cleo.cli"] + current)
        return parts, None

    def stream():
        parts, cwd = _build_parts(cmd_key)
        all_output = ""
        ok = True
        for part in parts:
            step_label = " ".join(part[-2:]) if len(part) > 2 else " ".join(part)
            yield f"data: >>> {step_label}\n\n"
            proc = subprocess.Popen(
                part,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=cwd,
            )
            for line in proc.stdout:
                all_output += line
                yield f"data: {line.rstrip()}\n\n"
            proc.wait()
            if proc.returncode != 0:
                yield f"data: [exit code {proc.returncode}]\n\n"
                ok = False
                break

        # Auto-clear properties cache after rebuild or geocode apply
        if ok and cmd_key in ("rebuild-properties", "rebuild-all", "apply-geocodes", "refresh-geocodes"):
            _clear_props_cache()
            yield "data: [caches cleared]\n\n"

        status = "OK" if ok else "FAILED"
        yield f"data: [done: {status}]\n\n"
        _admin_log.append({
            "command": cmd_key,
            "ts": datetime.now().isoformat(),
            "ok": ok,
            "output": all_output[-4000:],
        })

    return StreamingResponse(stream(), media_type="text/event-stream")


def _clear_props_cache():
    global _properties_cache, _properties_cache_mtime
    _properties_cache = None
    _properties_cache_mtime = 0


@app.get("/api/admin/log")
def api_admin_log():
    """Return recent admin command log (last 20)."""
    return _admin_log[-20:]


# ---------------------------------------------------------------------------
# Building Footprints (front-facing app)
# ---------------------------------------------------------------------------

from cleo.config import FOOTPRINTS_PATH, FOOTPRINTS_MATCHES_PATH  # noqa: E402

# ---------------------------------------------------------------------------
# Parcel boundary endpoints
# ---------------------------------------------------------------------------

_parcel_index = None
_parcel_index_mtime: float = 0


def _get_parcel_index():
    """Lazy-load the parcel spatial index, reloading when file changes."""
    global _parcel_index, _parcel_index_mtime
    if PARCELS_PATH.exists():
        mtime = PARCELS_PATH.stat().st_mtime
        if _parcel_index is None or mtime != _parcel_index_mtime:
            from cleo.parcels.spatial import ParcelIndex
            _parcel_index = ParcelIndex()
            _parcel_index.load()
            _parcel_index_mtime = mtime
    return _parcel_index


@app.get("/api/parcels/geojson")
def api_parcels_geojson(
    south: float, west: float, north: float, east: float
):
    """Return parcel polygons within the map viewport.

    Only returns data -- activated at zoom >= 15 by the frontend.
    """
    index = _get_parcel_index()
    if index is None or index.count == 0:
        return {"type": "FeatureCollection", "features": []}

    features = index.features_in_bbox(south, west, north, east)
    if len(features) > 2000:
        features = features[:2000]
    return {"type": "FeatureCollection", "features": features}


@app.get("/api/properties/{prop_id}/parcel")
def api_property_parcel(prop_id: str):
    """Return the parcel polygon for a specific property, with group and brands."""
    from cleo.parcels.store import ParcelStore

    store = ParcelStore()
    parcel = store.get_parcel_for_property(prop_id)
    if parcel is None:
        raise HTTPException(404, "No parcel for this property")

    pcl_props = parcel.get("properties", {})

    # Read consolidation fields from properties.json
    prop_data = {}
    if PROPERTIES_PATH.exists():
        reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
        prop_data = reg.get("properties", {}).get(prop_id, {})

    return {
        "parcel_id": pcl_props.get("pcl_id"),
        "municipality": pcl_props.get("municipality", ""),
        "pin": pcl_props.get("pin"),
        "arn": pcl_props.get("arn"),
        "address": pcl_props.get("address"),
        "city": pcl_props.get("city"),
        "zone_code": pcl_props.get("zone_code"),
        "zone_desc": pcl_props.get("zone_desc"),
        "area_sqm": pcl_props.get("area_sqm"),
        "assessment": pcl_props.get("assessment"),
        "property_use": pcl_props.get("property_use"),
        "legal_desc": pcl_props.get("legal_desc"),
        "geometry": parcel.get("geometry"),
        "parcel_group": prop_data.get("parcel_group", []),
        "parcel_brands": prop_data.get("parcel_brands", []),
        "parcel_building_count": prop_data.get("parcel_building_count"),
    }


@app.get("/api/parcels/stats")
def api_parcels_stats():
    """Return parcel coverage and harvest statistics."""
    from cleo.parcels.harvester import harvest_status
    from cleo.parcels.matcher import match_status

    return {
        "harvest": harvest_status(),
        "matches": match_status(),
    }


@app.get("/api/parcels/consolidation")
def api_parcels_consolidation():
    """Return parcel consolidation summary."""
    from cleo.config import PARCELS_CONSOLIDATION_PATH

    if not PARCELS_CONSOLIDATION_PATH.exists():
        raise HTTPException(404, "No consolidation data. Run 'cleo parcel-enrich' first.")

    return json.loads(PARCELS_CONSOLIDATION_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Building footprint endpoints
# ---------------------------------------------------------------------------

_footprint_index = None
_footprint_index_mtime: float = 0


def _get_footprint_index():
    """Lazy-load the footprint spatial index, reloading when file changes."""
    global _footprint_index, _footprint_index_mtime
    if FOOTPRINTS_PATH.exists():
        mtime = FOOTPRINTS_PATH.stat().st_mtime
        if _footprint_index is None or mtime != _footprint_index_mtime:
            from cleo.footprints.spatial import FootprintIndex
            _footprint_index = FootprintIndex()
            _footprint_index.load()
            _footprint_index_mtime = mtime
    return _footprint_index


@app.get("/api/footprints/geojson")
def api_footprints_geojson(
    south: float, west: float, north: float, east: float
):
    """Return building footprint polygons within the map viewport.

    Only returns data — activated at zoom >= 15 by the frontend.
    """
    index = _get_footprint_index()
    if index is None or index.count == 0:
        return {"type": "FeatureCollection", "features": []}

    features = index.features_in_bbox(south, west, north, east)
    # Cap at 2000 features to avoid huge payloads
    if len(features) > 2000:
        features = features[:2000]
    return {"type": "FeatureCollection", "features": features}


@app.get("/api/properties/{prop_id}/footprint")
def api_property_footprint(prop_id: str):
    """Return the building footprint polygon for a specific property."""
    if not FOOTPRINTS_MATCHES_PATH.exists():
        raise HTTPException(404, "No footprint matches")

    matches = json.loads(FOOTPRINTS_MATCHES_PATH.read_text(encoding="utf-8"))
    prop_fp = matches.get("property_footprints", {}).get(prop_id)
    if not prop_fp:
        raise HTTPException(404, "No footprint for this property")

    fp_id = prop_fp.get("footprint_id")
    index = _get_footprint_index()
    if index is None:
        raise HTTPException(404, "Footprint index not loaded")

    geom = index.get_polygon_geojson(fp_id)
    if geom is None:
        raise HTTPException(404, "Footprint geometry not found")

    area = index.get_area_sqm(fp_id)
    feat_props = index.get_feature(fp_id) or {}

    return {
        "footprint_id": fp_id,
        "method": prop_fp.get("method", ""),
        "geometry": geom,
        "area_sqm": area,
        "building_type": feat_props.get("building_type", ""),
        "building_name": feat_props.get("building_name", ""),
    }


@app.get("/api/footprints/stats")
def api_footprints_stats():
    """Return footprint coverage and matching statistics."""
    from cleo.footprints.ingest import footprint_status
    from cleo.footprints.matcher import match_status

    return {
        "footprints": footprint_status(),
        "matches": match_status(),
    }


# ---------------------------------------------------------------------------
# React app (front-facing) — must be after all other routes
# ---------------------------------------------------------------------------

_APP_DIR = STATIC_DIR / "app"

if (_APP_DIR / "assets").is_dir():
    app.mount("/app/assets", StaticFiles(directory=_APP_DIR / "assets"), name="app-assets")


@app.get("/app/{path:path}")
def serve_react_app(path: str = ""):
    """Serve the React SPA — all client routes return index.html."""
    index = _APP_DIR / "index.html"
    if not index.exists():
        raise HTTPException(404, "React app not built. Run: cd frontend && npm run build")
    return FileResponse(index, media_type="text/html")
