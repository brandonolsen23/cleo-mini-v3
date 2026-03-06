"""Contacts API — browse, detail, search, and manual linking."""

from fastapi import APIRouter, HTTPException, Request

from cleo.config import (
    CONTACT_REGISTRY_PATH,
    CONTACT_LINK_LOG_PATH,
    PROPERTIES_PATH,
    GROUP_REGISTRY_PATH,
)
from cleo.contacts.index import ContactIndex

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

# Singleton contact index — lazy-built, cached by mtime
_index = ContactIndex(CONTACT_REGISTRY_PATH, PROPERTIES_PATH, GROUP_REGISTRY_PATH)


@router.get("/browse")
def api_contacts_browse(
    name: str = "",
    phone: str = "",
    group: str = "",
    city: str = "",
    sort: str = "transaction_count",
    order: str = "desc",
    page: int = 1,
    per_page: int = 25,
):
    """Browse contacts with layered filtering, sorting, and pagination."""
    return _index.browse(
        name=name,
        phone=phone,
        group=group,
        city=city,
        sort=sort,
        order=order,
        page=page,
        per_page=per_page,
    )


@router.get("/filters")
def api_contacts_filters():
    """Available filter values for the contacts browse UI."""
    return _index.filters()


@router.get("/search")
def api_contacts_search(q: str = "", limit: int = 20):
    """Quick search across all contact fields."""
    if not q.strip():
        return {"results": []}
    return {"results": _index.search(q.strip(), limit=limit)}


@router.get("/{contact_id}")
def api_contact_detail(contact_id: str):
    """Full contact detail by CON_ ID."""
    _index.ensure_built()
    contact = _index.detail(contact_id)
    if not contact:
        raise HTTPException(404, f"Contact not found: {contact_id}")
    return contact


@router.post("/link")
async def api_contacts_link(request: Request):
    """Link contact names into one contact.

    Body: {names: ["name1", "name2", ...], display_name: "...", reason: "..."}
    """
    from cleo.contacts.linker import link_contacts

    body = await request.json()
    raw_names = body.get("names", [])
    display_name = body.get("display_name")
    reason = body.get("reason", "")

    if len(raw_names) < 2:
        raise HTTPException(400, "At least 2 names required to create a link")

    try:
        contact = link_contacts(
            CONTACT_REGISTRY_PATH, CONTACT_LINK_LOG_PATH,
            raw_names, display_name=display_name, reason=reason,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _index.invalidate()
    return {"ok": True, "contact": contact}


@router.post("/unlink")
async def api_contacts_unlink(request: Request):
    """Remove a name from a contact.

    Body: {name: "norm name", contact_id: "CON_00001", reason: "..."}
    """
    from cleo.contacts.linker import unlink_contact

    body = await request.json()
    name = body.get("name", "")
    contact_id = body.get("contact_id", "")
    reason = body.get("reason", "")

    if not name or not contact_id:
        raise HTTPException(400, "Both name and contact_id are required")

    try:
        result = unlink_contact(
            CONTACT_REGISTRY_PATH, CONTACT_LINK_LOG_PATH,
            name, contact_id, reason=reason,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _index.invalidate()
    return {"ok": True, "contact": result}


@router.put("/{contact_id}/name")
async def api_contact_set_name(contact_id: str, request: Request):
    """Set the display name for a contact.

    Body: {display_name: "..."}
    """
    from cleo.contacts.linker import set_display_name

    body = await request.json()
    display_name = body.get("display_name", "")
    if not display_name:
        raise HTTPException(400, "display_name is required")

    try:
        contact = set_display_name(
            CONTACT_REGISTRY_PATH, CONTACT_LINK_LOG_PATH,
            contact_id, display_name,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _index.invalidate()
    return {"ok": True, "contact": contact}
