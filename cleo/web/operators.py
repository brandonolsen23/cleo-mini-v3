"""Operator intelligence API — list, detail, confirm/reject matches, config CRUD, pipeline SSE."""

import json
import re
import subprocess
import sys

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from cleo.config import (
    OPERATORS_REGISTRY_PATH,
    OPERATORS_CONFIG_PATH,
    OPERATORS_CRAWL_DIR,
    PROPERTIES_PATH,
    PARTIES_PATH,
)
from cleo.operators.registry import (
    load_registry,
    confirm_property_match,
    reject_property_match,
    confirm_party_match,
    reject_party_match,
)

router = APIRouter(prefix="/api/operators", tags=["operators"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_properties() -> dict:
    if not PROPERTIES_PATH.exists():
        return {}
    raw = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    return raw.get("properties", {})


def _load_parties() -> dict:
    if not PARTIES_PATH.exists():
        return {}
    raw = json.loads(PARTIES_PATH.read_text(encoding="utf-8"))
    return raw.get("parties", {})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_operators():
    """Summary list of all operators for the table view.

    Merges two sources:
    1. Registry (operators.json) — operators that have been through the pipeline
    2. Config (config.json) — operators that were added but not yet crawled/matched

    Config-only entries appear with zero counts so the user can see them
    and trigger the pipeline from the UI.
    """
    reg = load_registry()
    registry_ops = reg.get("operators", {})

    # Build a slug->registry lookup for merging
    slug_to_reg: dict[str, tuple[str, dict]] = {}
    for op_id, op in registry_ops.items():
        s = op.get("slug", "")
        if s:
            slug_to_reg[s] = (op_id, op)

    items = []
    seen_slugs: set[str] = set()

    # 1) Emit config entries (preserves config ordering, merges registry data)
    config = _load_config()
    for cfg in config:
        slug = cfg.get("slug", "")
        if not slug:
            continue
        seen_slugs.add(slug)

        crawl_dir = OPERATORS_CRAWL_DIR / slug / "html"
        crawled_pages = len(list(crawl_dir.glob("*.html"))) if crawl_dir.is_dir() else 0

        if slug in slug_to_reg:
            op_id, op = slug_to_reg[slug]
            prop_matches = op.get("property_matches", [])
            party_matches = op.get("party_matches", [])
            items.append({
                "op_id": op_id,
                "slug": slug,
                "name": op.get("name", "") or cfg.get("name", ""),
                "url": op.get("url", "") or cfg.get("url", ""),
                "contacts_count": len(op.get("contacts", [])),
                "properties_count": len(op.get("extracted_properties", [])),
                "photos_count": len(op.get("photos", [])),
                "pending_property_matches": sum(1 for m in prop_matches if m.get("status") == "pending"),
                "confirmed_property_matches": sum(1 for m in prop_matches if m.get("status") == "confirmed"),
                "pending_party_matches": sum(1 for m in party_matches if m.get("status") == "pending"),
                "confirmed_party_matches": sum(1 for m in party_matches if m.get("status") == "confirmed"),
                "crawled_pages": crawled_pages,
                "updated": op.get("updated", ""),
            })
        else:
            # Config-only: not yet in registry
            items.append({
                "op_id": "",
                "slug": slug,
                "name": cfg.get("name", ""),
                "url": cfg.get("url", ""),
                "contacts_count": 0,
                "properties_count": 0,
                "photos_count": 0,
                "pending_property_matches": 0,
                "confirmed_property_matches": 0,
                "pending_party_matches": 0,
                "confirmed_party_matches": 0,
                "crawled_pages": crawled_pages,
                "updated": "",
            })

    # 2) Emit any registry entries whose slug isn't in config (edge case)
    for op_id, op in sorted(registry_ops.items()):
        slug = op.get("slug", "")
        if slug in seen_slugs:
            continue
        prop_matches = op.get("property_matches", [])
        party_matches = op.get("party_matches", [])
        crawl_dir = OPERATORS_CRAWL_DIR / slug / "html" if slug else None
        crawled_pages = len(list(crawl_dir.glob("*.html"))) if crawl_dir and crawl_dir.is_dir() else 0
        items.append({
            "op_id": op_id,
            "slug": slug,
            "name": op.get("name", ""),
            "url": op.get("url", ""),
            "contacts_count": len(op.get("contacts", [])),
            "properties_count": len(op.get("extracted_properties", [])),
            "photos_count": len(op.get("photos", [])),
            "pending_property_matches": sum(1 for m in prop_matches if m.get("status") == "pending"),
            "confirmed_property_matches": sum(1 for m in prop_matches if m.get("status") == "confirmed"),
            "pending_party_matches": sum(1 for m in party_matches if m.get("status") == "pending"),
            "confirmed_party_matches": sum(1 for m in party_matches if m.get("status") == "confirmed"),
            "crawled_pages": crawled_pages,
            "updated": op.get("updated", ""),
        })

    return items


@router.get("/stats")
def operator_stats():
    """Pipeline overview stats."""
    reg = load_registry()
    operators = reg.get("operators", {})

    total_contacts = 0
    total_extracted_props = 0
    total_photos = 0
    total_pending_props = 0
    total_confirmed_props = 0
    total_rejected_props = 0
    total_pending_parties = 0
    total_confirmed_parties = 0

    for op in operators.values():
        total_contacts += len(op.get("contacts", []))
        total_extracted_props += len(op.get("extracted_properties", []))
        total_photos += len(op.get("photos", []))
        for m in op.get("property_matches", []):
            status = m.get("status", "")
            if status == "pending":
                total_pending_props += 1
            elif status == "confirmed":
                total_confirmed_props += 1
            elif status == "rejected":
                total_rejected_props += 1
        for m in op.get("party_matches", []):
            status = m.get("status", "")
            if status == "pending":
                total_pending_parties += 1
            elif status == "confirmed":
                total_confirmed_parties += 1

    return {
        "total_operators": len(operators),
        "total_contacts": total_contacts,
        "total_extracted_properties": total_extracted_props,
        "total_photos": total_photos,
        "property_matches": {
            "pending": total_pending_props,
            "confirmed": total_confirmed_props,
            "rejected": total_rejected_props,
        },
        "party_matches": {
            "pending": total_pending_parties,
            "confirmed": total_confirmed_parties,
        },
    }


# ---------------------------------------------------------------------------
# Config CRUD
# ---------------------------------------------------------------------------

def _load_config() -> list[dict]:
    if not OPERATORS_CONFIG_PATH.exists():
        return []
    return json.loads(OPERATORS_CONFIG_PATH.read_text(encoding="utf-8"))


def _save_config(config: list[dict]) -> None:
    OPERATORS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    OPERATORS_CONFIG_PATH.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


@router.post("/config")
async def add_operator(request: Request):
    """Add a new operator to config.json."""
    body = await request.json()
    name = body.get("name", "").strip()
    url = body.get("url", "").strip()
    if not name or not url:
        raise HTTPException(400, "name and url are required")

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    config = _load_config()
    existing_slugs = {op["slug"] for op in config}
    if slug in existing_slugs:
        raise HTTPException(409, f"Operator '{slug}' already exists")

    entry = {"slug": slug, "name": name, "url": url, "enabled": True}
    config.append(entry)
    _save_config(config)
    return entry


@router.delete("/config/{slug}")
def remove_operator(slug: str):
    """Remove an operator from config.json."""
    config = _load_config()
    before = len(config)
    config = [op for op in config if op["slug"] != slug]
    if len(config) == before:
        raise HTTPException(404, f"No operator with slug '{slug}'")
    _save_config(config)
    return {"ok": True, "slug": slug}


# ---------------------------------------------------------------------------
# Pipeline run (SSE streaming) + kill
# ---------------------------------------------------------------------------

_OPERATOR_COMMANDS = {
    "crawl-all": [["op-crawl", "--all"]],
    "crawl-one": None,  # built dynamically with slug
    "extract": [
        ["op-extract", "--discard"],
        ["op-extract", "--sandbox"],
        ["op-extract", "--promote"],
    ],
    "match": [["op-match"]],
}

# Track the active subprocess so it can be killed from the UI
_active_proc: subprocess.Popen | None = None


@router.post("/kill")
def kill_operator_pipeline():
    """Kill the currently running operator pipeline subprocess."""
    global _active_proc
    if _active_proc is None or _active_proc.poll() is not None:
        return {"ok": False, "detail": "No running process"}
    _active_proc.kill()
    _active_proc = None
    return {"ok": True}


@router.post("/run")
async def run_operator_pipeline(request: Request):
    """Run an operator pipeline command, streaming output as SSE."""
    global _active_proc
    body = await request.json()
    command = body.get("command", "")
    slug = body.get("slug")

    if command not in _OPERATOR_COMMANDS:
        raise HTTPException(400, f"Unknown command: {command}")

    if command == "crawl-one":
        if not slug:
            raise HTTPException(400, "slug is required for crawl-one")
        steps = [["op-crawl", "--slug", slug]]
    else:
        steps = _OPERATOR_COMMANDS[command]

    python_bin = sys.executable

    def stream():
        global _active_proc
        ok = True
        for step in steps:
            parts = [python_bin, "-m", "cleo.cli"] + step
            step_label = " ".join(step)
            yield f"data: >>> {step_label}\n\n"
            proc = subprocess.Popen(
                parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            _active_proc = proc
            for line in proc.stdout:
                yield f"data: {line.rstrip()}\n\n"
            proc.wait()
            if proc.returncode != 0:
                yield f"data: [exit code {proc.returncode}]\n\n"
                ok = False
                break

        _active_proc = None
        status = "OK" if ok else "FAILED"
        yield f"data: [done: {status}]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

@router.get("/{op_id}")
def get_operator(op_id: str):
    """Full detail for a single operator (extracted data + matches)."""
    reg = load_registry()
    operators = reg.get("operators", {})

    if op_id not in operators:
        raise HTTPException(status_code=404, detail=f"Operator {op_id} not found")

    op = operators[op_id]

    # Enrich property matches with registry data
    properties = _load_properties()
    enriched_prop_matches = []
    for m in op.get("property_matches", []):
        enriched = dict(m)
        pid = m.get("prop_id")
        if pid and pid in properties:
            prop = properties[pid]
            enriched["registry_address"] = prop.get("address", "")
            enriched["registry_city"] = prop.get("city", "")
            enriched["registry_sources"] = prop.get("sources", [])
            enriched["registry_transaction_count"] = prop.get("transaction_count", 0)
        enriched_prop_matches.append(enriched)

    # Enrich party matches with registry data
    parties = _load_parties()
    enriched_party_matches = []
    for m in op.get("party_matches", []):
        enriched = dict(m)
        gid = m.get("group_id")
        if gid and gid in parties:
            group = parties[gid]
            enriched["party_type"] = group.get("type", "")
            enriched["party_transaction_count"] = group.get("transaction_count", 0)
            enriched["party_names"] = [
                n.get("display", n.get("raw", "")) if isinstance(n, dict) else n
                for n in group.get("names", [])[:5]
            ]
        enriched_party_matches.append(enriched)

    return {
        "op_id": op_id,
        "slug": op.get("slug", ""),
        "name": op.get("name", ""),
        "url": op.get("url", ""),
        "legal_names": op.get("legal_names", []),
        "description": op.get("description", ""),
        "contacts": op.get("contacts", []),
        "extracted_properties": op.get("extracted_properties", []),
        "photos": op.get("photos", []),
        "property_matches": enriched_prop_matches,
        "party_matches": enriched_party_matches,
        "created": op.get("created", ""),
        "updated": op.get("updated", ""),
    }


@router.post("/{op_id}/property-matches/{idx}/confirm")
def confirm_prop_match(op_id: str, idx: int):
    """Confirm a property match."""
    try:
        match = confirm_property_match(op_id, idx)
        return {"ok": True, "match": match}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{op_id}/property-matches/{idx}/reject")
def reject_prop_match(op_id: str, idx: int):
    """Reject a property match."""
    try:
        match = reject_property_match(op_id, idx)
        return {"ok": True, "match": match}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{op_id}/party-matches/{idx}/confirm")
def confirm_pty_match(op_id: str, idx: int):
    """Confirm a party match."""
    try:
        match = confirm_party_match(op_id, idx)
        return {"ok": True, "match": match}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{op_id}/party-matches/{idx}/reject")
def reject_pty_match(op_id: str, idx: int):
    """Reject a party match."""
    try:
        match = reject_party_match(op_id, idx)
        return {"ok": True, "match": match}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
