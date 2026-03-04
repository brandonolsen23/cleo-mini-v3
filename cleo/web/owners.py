"""Owner API — browse, detail, search, and manual linking."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from cleo.owners.index import OwnerIndex, normalize_owner_name
from cleo.owners.links import link_owners, unlink_owner, set_display_name, get_all_links

router = APIRouter(prefix="/api/owners", tags=["owners"])

# Singleton owner index — lazy-built, cached by mtime
_index = OwnerIndex()


@router.get("/browse")
def api_owners_browse(
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
):
    """Browse owners with layered filtering, sorting, and pagination.

    All filters are ANDed together for layered search:
      ?name=riocan&contact=jonathan  →  owners matching "riocan" in name AND "jonathan" in contacts
    """
    return _index.browse(
        name=name,
        contact=contact,
        phone=phone,
        address=address,
        city=city,
        min_properties=min_properties,
        sort=sort,
        order=order,
        page=page,
        per_page=per_page,
    )


@router.get("/filters")
def api_owners_filters():
    """Available filter values for the owners browse UI."""
    return _index.filters()


@router.get("/search")
def api_owners_search(q: str = "", limit: int = 20):
    """Quick search across all owner fields."""
    if not q.strip():
        return {"results": []}
    return {"results": _index.search(q.strip(), limit=limit)}


@router.get("/links")
def api_owners_links():
    """Return all manual link groups."""
    return {"links": get_all_links()}


@router.post("/link")
async def api_owners_link(request: Request):
    """Link owner names into a group.

    Body: {names: ["norm name 1", "norm name 2", ...], display_name: "...", reason: "..."}

    Names should be normalized owner names. If owner IDs are provided instead,
    they are resolved to normalized names first.
    """
    body = await request.json()
    raw_names = body.get("names", [])
    display_name = body.get("display_name")
    reason = body.get("reason", "")

    if len(raw_names) < 2:
        raise HTTPException(400, "At least 2 names required to create a link")

    # Normalize all names
    normalized = [normalize_owner_name(n) for n in raw_names]
    # Remove empty and deduplicate
    normalized = sorted(set(n for n in normalized if n))

    if len(normalized) < 1:
        raise HTTPException(400, "No valid names after normalization")

    # If all names already belong to the same group, nothing to do — but still allow
    # (e.g. adding a name to an existing group where the anchor is already a member)
    if len(normalized) < 2:
        # Check if the single name is already in a group — if so, just update display name
        from cleo.owners.links import _load_links
        link_data = _load_links()
        name_to_link = link_data.get("name_to_link", {})
        existing_lid = name_to_link.get(normalized[0])
        if existing_lid and display_name:
            from cleo.owners.links import set_display_name as _set_dn
            _set_dn(existing_lid, display_name)
            _index._built = False
            return {"ok": True, "link": {"id": existing_lid, "display_name": display_name}}
        raise HTTPException(400, "At least 2 distinct names required after normalization")

    group = link_owners(normalized, display_name=display_name, reason=reason)

    # Force index rebuild on next request
    _index._built = False

    return {"ok": True, "link": group}


@router.post("/unlink")
async def api_owners_unlink(request: Request):
    """Remove a name from a link group.

    Body: {name: "norm name", link_id: "LNK_00001", reason: "..."}
    """
    body = await request.json()
    name = body.get("name", "")
    link_id = body.get("link_id", "")
    reason = body.get("reason", "")

    if not name or not link_id:
        raise HTTPException(400, "name and link_id required")

    normalized = normalize_owner_name(name)

    try:
        result = unlink_owner(normalized, link_id, reason=reason)
    except ValueError as e:
        raise HTTPException(404, str(e))

    _index._built = False

    return {"ok": True, "link": result}


@router.put("/{owner_id}/name")
async def api_owners_set_display_name(owner_id: str, request: Request):
    """Set display name for any entity (linked or unlinked).

    Body: {display_name: "Skyline Retail REIT"}
    """
    body = await request.json()
    display_name = body.get("display_name", "")

    if not display_name:
        raise HTTPException(400, "display_name required")

    # For non-link entities, resolve the normalized name from the index
    normalized_name = ""
    if not owner_id.startswith("LNK_"):
        owner = _index.detail(owner_id)
        if not owner:
            raise HTTPException(404, f"Owner '{owner_id}' not found")
        # Use the first normalized name
        norm_names = owner.get("normalized_names", [])
        if norm_names:
            normalized_name = norm_names[0]

    try:
        result = set_display_name(owner_id, display_name, normalized_name=normalized_name)
    except ValueError as e:
        raise HTTPException(404, str(e))

    _index._built = False

    return {"ok": True, "result": result}


# IMPORTANT: This route must be declared AFTER all fixed-path routes above
# to prevent the path parameter from capturing "browse", "filters", etc.
@router.get("/{owner_id}")
def api_owner_detail(owner_id: str):
    """Full owner detail by ID (hash-based or LNK_NNNNN).

    Also accepts a normalized owner name — resolves to the owner ID first.
    """
    owner = _index.detail(owner_id)

    if not owner:
        # Try resolving as a normalized name
        resolved_id = _index.resolve(normalize_owner_name(owner_id))
        if resolved_id:
            owner = _index.detail(resolved_id)

    if not owner:
        raise HTTPException(404, f"Owner '{owner_id}' not found")

    return owner
