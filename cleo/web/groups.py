"""Groups API — browse, detail, search, create, and manual linking."""

from fastapi import APIRouter, HTTPException, Request

from cleo.config import (
    GROUP_REGISTRY_PATH,
    GROUP_LINK_LOG_PATH,
    GROUP_PROPERTY_LINKS_PATH,
    PROPERTIES_PATH,
)
from cleo.groups.index import GroupIndex
from cleo.groups.registry import normalize_group_name

router = APIRouter(prefix="/api/groups", tags=["groups"])

# Singleton group index — lazy-built, cached by mtime
_index = GroupIndex(GROUP_REGISTRY_PATH, PROPERTIES_PATH, GROUP_PROPERTY_LINKS_PATH)


@router.get("/browse")
def api_groups_browse(
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
    """Browse groups with layered filtering, sorting, and pagination."""
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
def api_groups_filters():
    """Available filter values for the groups browse UI."""
    return _index.filters()


@router.get("/search")
def api_groups_search(q: str = "", limit: int = 20):
    """Quick search across all group fields."""
    if not q.strip():
        return {"results": []}
    return {"results": _index.search(q.strip(), limit=limit)}


@router.post("")
async def api_groups_create(request: Request):
    """Create a new Group from a name. No transaction required.

    Body: {name: "Southside Group", display_name: "Southside Group Inc."}
    """
    from cleo.groups.linker import create_group

    body = await request.json()
    name = body.get("name", "").strip()
    display_name = body.get("display_name")

    if not name:
        raise HTTPException(400, "name is required")

    try:
        group = create_group(
            GROUP_REGISTRY_PATH, GROUP_LINK_LOG_PATH,
            name, display_name=display_name,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _index.invalidate()
    return {"ok": True, "group": group}


@router.get("/{group_id}")
def api_group_detail(group_id: str):
    """Full group detail by GRP_ ID."""
    _index.ensure_built()
    group = _index.detail(group_id)
    if not group:
        raise HTTPException(404, f"Group not found: {group_id}")
    return group


@router.post("/{group_id}/properties")
async def api_group_link_property(group_id: str, request: Request):
    """Link a property to a Group.

    Body: {arn: "00000000000000000001", property_id: "PRO_00001"}
    """
    from cleo.groups.linker import link_property

    body = await request.json()
    arn = body.get("arn", "").strip()
    property_id = body.get("property_id", "").strip()

    if not arn:
        raise HTTPException(400, "arn is required")

    try:
        link = link_property(
            GROUP_PROPERTY_LINKS_PATH, GROUP_LINK_LOG_PATH,
            GROUP_REGISTRY_PATH,
            group_id, arn, property_id=property_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _index.invalidate()
    return {"ok": True, "link": link}


@router.delete("/{group_id}/properties/{arn}")
def api_group_unlink_property(group_id: str, arn: str):
    """Remove a property link from a Group."""
    from cleo.groups.linker import unlink_property

    removed = unlink_property(
        GROUP_PROPERTY_LINKS_PATH, GROUP_LINK_LOG_PATH,
        group_id, arn,
    )
    if not removed:
        raise HTTPException(404, "Link not found")

    _index.invalidate()
    return {"ok": True}


@router.post("/link")
async def api_groups_link(request: Request):
    """Link names into a group.

    Body: {names: ["name1", "name2", ...], display_name: "...", reason: "..."}
    """
    from cleo.groups.linker import link_names

    body = await request.json()
    raw_names = body.get("names", [])
    display_name = body.get("display_name")
    reason = body.get("reason", "")

    if len(raw_names) < 2:
        raise HTTPException(400, "At least 2 names required to create a link")

    try:
        group = link_names(
            GROUP_REGISTRY_PATH, GROUP_LINK_LOG_PATH,
            raw_names, display_name=display_name, reason=reason,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _index.invalidate()
    return {"ok": True, "group": group}


@router.post("/unlink")
async def api_groups_unlink(request: Request):
    """Remove a name from a group.

    Body: {name: "norm name", group_id: "GRP_00001", reason: "..."}
    """
    from cleo.groups.linker import unlink_name

    body = await request.json()
    name = body.get("name", "")
    group_id = body.get("group_id", "")
    reason = body.get("reason", "")

    if not name or not group_id:
        raise HTTPException(400, "Both name and group_id are required")

    try:
        result = unlink_name(
            GROUP_REGISTRY_PATH, GROUP_LINK_LOG_PATH,
            name, group_id, reason=reason,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _index.invalidate()
    return {"ok": True, "group": result}


@router.put("/{group_id}/name")
async def api_group_set_name(group_id: str, request: Request):
    """Set the display name for a group.

    Body: {display_name: "..."}
    """
    from cleo.groups.linker import set_display_name

    body = await request.json()
    display_name = body.get("display_name", "")
    if not display_name:
        raise HTTPException(400, "display_name is required")

    try:
        group = set_display_name(
            GROUP_REGISTRY_PATH, GROUP_LINK_LOG_PATH,
            group_id, display_name,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    _index.invalidate()
    return {"ok": True, "group": group}
