"""CRM module — contacts enrichment and deal tracking."""

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from cleo.config import (
    CRM_CONTACTS_PATH,
    CRM_DEALS_PATH,
    CRM_EDITS_PATH,
    PROPERTIES_PATH,
)

router = APIRouter(prefix="/api/crm", tags=["crm"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEAL_STAGES = [
    "active_deal",
    "in_negotiation",
    "under_contract",
    "closed_won",
    "lost_cancelled",
]
# Legacy stages still accepted for reads but not offered for new deals
_LEGACY_STAGES = {"lead", "contacted", "qualifying", "negotiating", "closed_lost"}
_ALL_STAGES = set(_DEAL_STAGES) | _LEGACY_STAGES
_CLOSED_STAGES = {"closed_won", "lost_cancelled", "closed_lost"}


def _load_contacts() -> dict:
    if CRM_CONTACTS_PATH.exists():
        return json.loads(CRM_CONTACTS_PATH.read_text(encoding="utf-8"))
    return {"contacts": {}, "next_id": 1}


def _save_contacts(data: dict) -> None:
    CRM_CONTACTS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _load_deals() -> dict:
    if CRM_DEALS_PATH.exists():
        return json.loads(CRM_DEALS_PATH.read_text(encoding="utf-8"))
    return {"deals": {}, "next_id": 1}


def _save_deals(data: dict) -> None:
    CRM_DEALS_PATH.write_text(
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
    with open(CRM_EDITS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_properties() -> dict:
    """Load property registry as {prop_id: record}."""
    if not PROPERTIES_PATH.exists():
        return {}
    raw = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    return raw.get("properties", raw) if isinstance(raw, dict) else {}


def _property_summary(props: dict, prop_id: str) -> dict | None:
    p = props.get(prop_id)
    if not p:
        return None
    return {
        "prop_id": prop_id,
        "address": p.get("address", ""),
        "city": p.get("city", ""),
    }


# ---------------------------------------------------------------------------
# CRM Contacts
# ---------------------------------------------------------------------------

@router.get("/contacts")
def list_contacts():
    store = _load_contacts()
    result = []
    deals_store = _load_deals()
    for cid, c in store["contacts"].items():
        deal_count = sum(
            1 for d in deals_store["deals"].values() if cid in d.get("contact_ids", [])
        )
        result.append({
            **c,
            "crm_id": cid,
            "deal_count": deal_count,
        })
    result.sort(key=lambda x: x.get("updated", ""), reverse=True)
    return JSONResponse(result)


@router.get("/contacts/by-computed/{computed_id:path}")
def contact_by_computed(computed_id: str):
    from urllib.parse import unquote
    computed_id = unquote(computed_id).strip()
    store = _load_contacts()
    for cid, c in store["contacts"].items():
        if c.get("computed_contact_id", "") == computed_id:
            return {**c, "crm_id": cid}
    raise HTTPException(404, "No CRM contact for this computed ID")


@router.get("/contacts/{crm_id}")
def get_contact(crm_id: str):
    store = _load_contacts()
    c = store["contacts"].get(crm_id)
    if not c:
        raise HTTPException(404, f"CRM contact not found: {crm_id}")

    # Attach linked deals
    deals_store = _load_deals()
    props = _load_properties()
    linked_deals = []
    for did, d in deals_store["deals"].items():
        if crm_id in d.get("contact_ids", []):
            linked_deals.append({
                **d,
                "deal_id": did,
                "property": _property_summary(props, d.get("prop_id", "")),
            })
    linked_deals.sort(key=lambda x: x.get("updated", ""), reverse=True)

    return {**c, "crm_id": crm_id, "deals": linked_deals}


@router.post("/contacts")
async def create_contact(request: Request):
    body = await request.json()
    store = _load_contacts()
    crm_id = _next_id(store, "C")
    now = _now()
    contact = {
        "name": body.get("name", "").strip(),
        "email": body.get("email", "").strip(),
        "mobile": body.get("mobile", "").strip(),
        "notes": body.get("notes", "").strip(),
        "tags": body.get("tags", []),
        "computed_contact_id": body.get("computed_contact_id", "").strip(),
        "party_group_ids": body.get("party_group_ids", []),
        "created": now,
        "updated": now,
    }
    if not contact["name"]:
        raise HTTPException(400, "Name is required")
    store["contacts"][crm_id] = contact
    _save_contacts(store)
    _log_edit({"action": "create_contact", "crm_id": crm_id, "data": contact})
    return {**contact, "crm_id": crm_id}


@router.put("/contacts/{crm_id}")
async def update_contact(crm_id: str, request: Request):
    body = await request.json()
    store = _load_contacts()
    c = store["contacts"].get(crm_id)
    if not c:
        raise HTTPException(404, f"CRM contact not found: {crm_id}")

    changes = {}
    for field in ("name", "email", "mobile", "notes", "computed_contact_id"):
        if field in body:
            val = body[field].strip() if isinstance(body[field], str) else body[field]
            if val != c.get(field):
                changes[field] = val
                c[field] = val
    for field in ("tags", "party_group_ids"):
        if field in body:
            if body[field] != c.get(field):
                changes[field] = body[field]
                c[field] = body[field]

    if changes:
        c["updated"] = _now()
        _save_contacts(store)
        _log_edit({"action": "update_contact", "crm_id": crm_id, "changes": changes})

    return {**c, "crm_id": crm_id}


@router.delete("/contacts/{crm_id}")
def delete_contact(crm_id: str):
    store = _load_contacts()
    if crm_id not in store["contacts"]:
        raise HTTPException(404, f"CRM contact not found: {crm_id}")
    deleted = store["contacts"].pop(crm_id)
    _save_contacts(store)
    _log_edit({"action": "delete_contact", "crm_id": crm_id, "data": deleted})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

@router.get("/deals")
def list_deals():
    store = _load_deals()
    contacts_store = _load_contacts()
    props = _load_properties()
    result = []
    for did, d in store["deals"].items():
        contact_names = []
        for cid in d.get("contact_ids", []):
            cc = contacts_store["contacts"].get(cid)
            if cc:
                contact_names.append({"crm_id": cid, "name": cc["name"]})
        result.append({
            **d,
            "deal_id": did,
            "property": _property_summary(props, d.get("prop_id", "")),
            "contacts": contact_names,
        })
    result.sort(key=lambda x: x.get("updated", ""), reverse=True)
    return JSONResponse(result)


@router.get("/deals/{deal_id}")
def get_deal(deal_id: str):
    store = _load_deals()
    d = store["deals"].get(deal_id)
    if not d:
        raise HTTPException(404, f"Deal not found: {deal_id}")

    contacts_store = _load_contacts()
    props = _load_properties()
    contact_details = []
    for cid in d.get("contact_ids", []):
        cc = contacts_store["contacts"].get(cid)
        if cc:
            contact_details.append({
                "crm_id": cid,
                "name": cc["name"],
                "email": cc.get("email", ""),
                "mobile": cc.get("mobile", ""),
            })

    return {
        **d,
        "deal_id": deal_id,
        "property": _property_summary(props, d.get("prop_id", "")),
        "contacts": contact_details,
    }


@router.post("/deals")
async def create_deal(request: Request):
    body = await request.json()
    store = _load_deals()
    deal_id = _next_id(store, "D")
    now = _now()

    stage = body.get("stage", "active_deal")
    if stage not in _DEAL_STAGES:
        raise HTTPException(400, f"Invalid stage: {stage}")

    deal = {
        "title": body.get("title", "").strip(),
        "prop_id": body.get("prop_id", "").strip(),
        "stage": stage,
        "contact_ids": body.get("contact_ids", []),
        "notes": body.get("notes", "").strip(),
        "created": now,
        "updated": now,
    }
    if not deal["title"]:
        raise HTTPException(400, "Title is required")
    store["deals"][deal_id] = deal
    _save_deals(store)
    _log_edit({"action": "create_deal", "deal_id": deal_id, "data": deal})
    return {**deal, "deal_id": deal_id}


@router.put("/deals/{deal_id}")
async def update_deal(deal_id: str, request: Request):
    body = await request.json()
    store = _load_deals()
    d = store["deals"].get(deal_id)
    if not d:
        raise HTTPException(404, f"Deal not found: {deal_id}")

    changes = {}
    for field in ("title", "prop_id", "notes"):
        if field in body:
            val = body[field].strip() if isinstance(body[field], str) else body[field]
            if val != d.get(field):
                changes[field] = val
                d[field] = val
    if "stage" in body:
        if body["stage"] not in _ALL_STAGES:
            raise HTTPException(400, f"Invalid stage: {body['stage']}")
        if body["stage"] != d.get("stage"):
            changes["stage"] = body["stage"]
            d["stage"] = body["stage"]
    if "contact_ids" in body:
        if body["contact_ids"] != d.get("contact_ids"):
            changes["contact_ids"] = body["contact_ids"]
            d["contact_ids"] = body["contact_ids"]

    if changes:
        d["updated"] = _now()
        _save_deals(store)
        _log_edit({"action": "update_deal", "deal_id": deal_id, "changes": changes})

    return {**d, "deal_id": deal_id}


@router.delete("/deals/{deal_id}")
def delete_deal(deal_id: str):
    store = _load_deals()
    if deal_id not in store["deals"]:
        raise HTTPException(404, f"Deal not found: {deal_id}")
    deleted = store["deals"].pop(deal_id)
    _save_deals(store)
    _log_edit({"action": "delete_deal", "deal_id": deal_id, "data": deleted})
    return {"ok": True}


@router.get("/properties/{prop_id}/deals")
def deals_for_property(prop_id: str):
    store = _load_deals()
    contacts_store = _load_contacts()
    result = []
    for did, d in store["deals"].items():
        if d.get("prop_id") != prop_id:
            continue
        contact_names = []
        for cid in d.get("contact_ids", []):
            cc = contacts_store["contacts"].get(cid)
            if cc:
                contact_names.append({"crm_id": cid, "name": cc["name"]})
        result.append({
            **d,
            "deal_id": did,
            "contacts": contact_names,
        })
    result.sort(key=lambda x: x.get("updated", ""), reverse=True)
    return JSONResponse(result)
