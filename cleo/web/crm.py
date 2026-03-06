"""CRM API — Deals, Lists, and Connections."""

from fastapi import APIRouter, HTTPException, Request

from cleo.config import CRM_DEALS_PATH, CRM_LISTS_PATH, CRM_CONNECTIONS_PATH, CRM_EDITS_PATH
from cleo.crm.store import (
    DealStore,
    ListStore,
    ConnectionStore,
    DEAL_STAGES,
    DEAL_STAGE_LABELS,
    DEAL_STAGE_PHASES,
    CONNECTION_TYPES,
    CONNECTION_DIRECTIONS,
    CONNECTION_OUTCOMES,
)

router = APIRouter(prefix="/api/crm", tags=["crm"])

_deals = DealStore(CRM_DEALS_PATH, CRM_EDITS_PATH)
_lists = ListStore(CRM_LISTS_PATH, CRM_EDITS_PATH)
_connections = ConnectionStore(CRM_CONNECTIONS_PATH, CRM_EDITS_PATH)


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

@router.get("/deals")
def api_deals_list(stage: str = "", deal_owner: str = ""):
    """List all deals, optionally filtered by stage or owner."""
    deals = _deals.list_all()
    if stage:
        deals = [d for d in deals if d.get("stage") == stage]
    if deal_owner:
        deals = [d for d in deals if d.get("deal_owner") == deal_owner]
    return {"deals": deals, "total": len(deals)}


@router.get("/deals/pipeline")
def api_deals_pipeline():
    """Deals grouped by stage for pipeline/kanban view."""
    return {
        "stages": DEAL_STAGES,
        "stage_labels": DEAL_STAGE_LABELS,
        "stage_phases": DEAL_STAGE_PHASES,
        "pipeline": _deals.by_stage(),
    }


@router.get("/deals/stats")
def api_deals_stats():
    """Pipeline stats."""
    return _deals.stats()


@router.get("/deals/meta")
def api_deals_meta():
    """Deal stage definitions and enums for the frontend."""
    return {
        "stages": DEAL_STAGES,
        "stage_labels": DEAL_STAGE_LABELS,
        "stage_phases": DEAL_STAGE_PHASES,
    }


@router.get("/deals/{deal_id}")
def api_deal_detail(deal_id: str):
    """Get a single deal."""
    deal = _deals.get(deal_id)
    if not deal:
        raise HTTPException(404, f"Deal not found: {deal_id}")
    return deal


@router.post("/deals")
async def api_deal_create(request: Request):
    """Create a new deal.

    Body: {name, stage?, arn?, property_id?, group_id?, contact_ids?, amount?,
           close_date?, deal_owner?, description?, next_step?, priority?}
    """
    body = await request.json()
    if not body.get("name"):
        raise HTTPException(400, "Deal name is required")
    if body.get("stage") and body["stage"] not in DEAL_STAGES:
        raise HTTPException(400, f"Invalid stage: {body['stage']}")
    deal = _deals.create(body)
    return {"ok": True, "deal": deal}


@router.put("/deals/{deal_id}")
async def api_deal_update(deal_id: str, request: Request):
    """Update a deal.

    Body: any deal fields to update.
    """
    body = await request.json()
    if body.get("stage") and body["stage"] not in DEAL_STAGES:
        raise HTTPException(400, f"Invalid stage: {body['stage']}")
    try:
        deal = _deals.update(deal_id, body)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, "deal": deal}


@router.delete("/deals/{deal_id}")
def api_deal_delete(deal_id: str):
    """Delete a deal."""
    try:
        _deals.delete(deal_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

@router.get("/lists")
def api_lists_list():
    """List all prospecting lists."""
    lists = _lists.list_all()
    return {"lists": lists, "total": len(lists)}


@router.get("/lists/{list_id}")
def api_list_detail(list_id: str):
    """Get a single list."""
    lst = _lists.get(list_id)
    if not lst:
        raise HTTPException(404, f"List not found: {list_id}")
    return lst


@router.post("/lists")
async def api_list_create(request: Request):
    """Create a new list.

    Body: {name, description?}
    """
    body = await request.json()
    if not body.get("name"):
        raise HTTPException(400, "List name is required")
    lst = _lists.create(body)
    return {"ok": True, "list": lst}


@router.put("/lists/{list_id}")
async def api_list_update(list_id: str, request: Request):
    """Update list name/description.

    Body: {name?, description?}
    """
    body = await request.json()
    try:
        lst = _lists.update(list_id, body)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, "list": lst}


@router.post("/lists/{list_id}/items")
async def api_list_add_item(list_id: str, request: Request):
    """Add an item to a list.

    Body: {type: "property"|"group"|"contact", property_id?, arn?, group_id?, contact_id?}
    """
    body = await request.json()
    item_type = body.get("type")
    if item_type not in ("property", "group", "contact"):
        raise HTTPException(400, "Item type must be property, group, or contact")
    try:
        lst = _lists.add_item(list_id, body)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True, "list": lst}


@router.delete("/lists/{list_id}/items/{index}")
def api_list_remove_item(list_id: str, index: int):
    """Remove an item from a list by index."""
    try:
        lst = _lists.remove_item(list_id, index)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "list": lst}


@router.delete("/lists/{list_id}")
def api_list_delete(list_id: str):
    """Delete a list."""
    try:
        _lists.delete(list_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

@router.get("/connections")
def api_connections_list(
    contact_id: str = "",
    group_id: str = "",
    deal_id: str = "",
):
    """List connections, optionally filtered."""
    cxns = _connections.list_all(
        contact_id=contact_id,
        group_id=group_id,
        deal_id=deal_id,
    )
    return {"connections": cxns, "total": len(cxns)}


@router.get("/connections/meta")
def api_connections_meta():
    """Connection type/direction/outcome enums for the frontend."""
    return {
        "types": CONNECTION_TYPES,
        "directions": CONNECTION_DIRECTIONS,
        "outcomes": CONNECTION_OUTCOMES,
    }


@router.get("/connections/{cxn_id}")
def api_connection_detail(cxn_id: str):
    """Get a single connection."""
    cxn = _connections.get(cxn_id)
    if not cxn:
        raise HTTPException(404, f"Connection not found: {cxn_id}")
    return cxn


@router.post("/connections")
async def api_connection_create(request: Request):
    """Log a new connection.

    Body: {contact_id?, contact_name?, group_id?, group_name?, deal_id?,
           type, direction, outcome?, notes?, logged_by?}
    """
    body = await request.json()
    if body.get("type") and body["type"] not in CONNECTION_TYPES:
        raise HTTPException(400, f"Invalid connection type: {body['type']}")
    cxn = _connections.create(body)
    return {"ok": True, "connection": cxn}


@router.delete("/connections/{cxn_id}")
def api_connection_delete(cxn_id: str):
    """Delete a connection."""
    try:
        _connections.delete(cxn_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    return {"ok": True}
