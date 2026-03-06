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

from cleo.config import HTML_DIR, PARSED_DIR, DATA_DIR, EXTRACT_REVIEWS_PATH, GEOCODE_CACHE_PATH, PROPERTIES_PATH, PROPERTY_EDITS_PATH, FEEDBACK_PATH, BRAND_MATCHES_PATH, BRANDS_DATA_DIR, MARKETS_PATH, GW_PARSED_DIR, OPERATORS_REGISTRY_PATH, PARCELS_PATH, PARCELS_MATCHES_PATH, NORMALIZED_DIR, NORM_REVIEWS_PATH, EXPANDED_DIR, EXPAND_REVIEWS_PATH, PARCEL_REGISTRY_PATH, PARCELLED_DIR, PARCELLED_REVIEWS_PATH, COMPILED_DIR, COMPILED_REVIEWS_PATH, OSM_POIS_DIR, PARCEL_CACHE_PATH
from cleo.ingest.html_index import HtmlIndex
from cleo.parse.versioning import active_dir, active_version, sandbox_path, sandbox_exists, list_versions, VOLATILE_FIELDS, _store as _parse_store
from cleo.extract import versioning as extract_ver
from cleo.web.operators import router as operators_router
from cleo.web.issues import router as issues_router
from cleo.web.groups import router as groups_router
from cleo.web.contacts import router as contacts_router
from cleo.web.crm import router as crm_router

app = FastAPI(title="Cleo Review")
app.include_router(operators_router)
app.include_router(issues_router)
app.include_router(groups_router)
app.include_router(contacts_router)
app.include_router(crm_router)


@app.on_event("startup")
def _warm_caches():
    """Pre-compute sandbox-changed set in a background thread."""
    import threading
    def _warm():
        try:
            api_norm_sandbox_changed()
        except Exception:
            pass
    threading.Thread(target=_warm, daemon=True).start()

STATIC_DIR = Path(__file__).parent / "static"
REVIEWS_PATH = DATA_DIR / "reviews.json"


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/review", status_code=302)


@app.get("/legacy-review", response_class=HTMLResponse)
def legacy_review():
    from fastapi.responses import HTMLResponse as HR
    content = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HR(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/pipeline", response_class=HTMLResponse)
def pipeline():
    from fastapi.responses import HTMLResponse as HR
    content = (STATIC_DIR / "pipeline.html").read_text(encoding="utf-8")
    return HR(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


# Stage review pages (new standardized review UI per pipeline stage)
@app.get("/review", response_class=HTMLResponse)
def review_landing():
    content = (STATIC_DIR / "review_landing.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/review/shared.css")
def review_shared_css():
    return FileResponse(STATIC_DIR / "review_shared.css", media_type="text/css",
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/review/shared.js")
def review_shared_js():
    return FileResponse(STATIC_DIR / "review_shared.js", media_type="application/javascript",
                        headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/review/parse", response_class=HTMLResponse)
def review_parse():
    content = (STATIC_DIR / "review_parse.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/review/normalize", response_class=HTMLResponse)
def review_normalize():
    content = (STATIC_DIR / "review_normalize.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/review/extract", response_class=HTMLResponse)
def review_extract():
    content = (STATIC_DIR / "review_extract.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/review/expand", response_class=HTMLResponse)
def review_expand():
    content = (STATIC_DIR / "review_expand.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/review/parcelled", response_class=HTMLResponse)
def review_parcelled():
    content = (STATIC_DIR / "review_parcelled.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


@app.get("/review/compiled", response_class=HTMLResponse)
def review_compiled():
    content = (STATIC_DIR / "review_compiled.html").read_text(encoding="utf-8")
    return HTMLResponse(content=content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})


# ---------------------------------------------------------------------------
# API — Normalization endpoints
# ---------------------------------------------------------------------------

@app.get("/api/norm-status")
def api_norm_status():
    """Return normalization pipeline versioning status."""
    norm_dir = NORMALIZED_DIR
    active_link = norm_dir / "active"
    has_active = active_link.exists()
    active_ver = active_link.resolve().name if has_active else None
    has_sandbox = (norm_dir / "sandbox").is_dir()
    versions = sorted([d.name for d in norm_dir.iterdir()
                       if d.is_dir() and d.name.startswith("v")]) if norm_dir.exists() else []
    return {
        "active_version": active_ver,
        "versions": versions,
        "has_sandbox": has_sandbox,
    }


@app.get("/api/norm-rt-ids")
def api_norm_rt_ids():
    """List all normalized record IDs (RT, brand, GW) with review status."""
    norm_active = NORMALIZED_DIR / "active"
    if not norm_active.exists():
        raise HTTPException(404, "No active normalized version")

    all_ids = sorted(
        f.stem for f in norm_active.glob("*.json") if f.stem != "_meta"
    )

    norm_reviews = _load_json(NORM_REVIEWS_PATH)

    records = []
    for record_id in all_ids:
        reviewed = record_id in norm_reviews
        # Determine source from ID prefix
        if record_id.startswith("BR_"):
            source = "brand"
        elif record_id.startswith("GW"):
            source = "geowarehouse"
        else:
            source = "realtrack"
        records.append({
            "rt_id": record_id,
            "source": source,
            "reviewed": reviewed,
            "determination": norm_reviews.get(record_id, {}).get("determination", ""),
        })

    return records


@app.get("/api/norm-no-street-number")
def api_norm_no_street_number():
    """Return IDs of normalized records with empty property street_number.

    Checks sandbox first (if exists), otherwise active.
    """
    norm_sandbox = NORMALIZED_DIR / "sandbox"
    norm_active = NORMALIZED_DIR / "active"
    check_dir = norm_sandbox if norm_sandbox.exists() else norm_active
    if not check_dir.exists():
        return []

    result = []
    for f in check_dir.glob("*.json"):
        if f.stem == "_meta":
            continue
        try:
            data = json.loads(f.read_text())
            prop = data.get("property", {})
            if not prop.get("street_number", "").strip():
                result.append(f.stem)
        except Exception:
            continue
    return sorted(result)


@app.get("/api/normalized/{rt_id}")
def api_normalized(rt_id: str):
    """Return normalized JSON from active version."""
    norm_active = NORMALIZED_DIR / "active" / f"{rt_id}.json"
    if not norm_active.exists():
        raise HTTPException(404, "Not in active normalized version")
    return json.loads(norm_active.read_text(encoding="utf-8"))


@app.get("/api/normalize-sandbox/{rt_id}")
def api_normalize_sandbox(rt_id: str):
    """Return normalized JSON from sandbox."""
    norm_sandbox = NORMALIZED_DIR / "sandbox" / f"{rt_id}.json"
    if not norm_sandbox.exists():
        raise HTTPException(404, "Not in normalize sandbox")
    return json.loads(norm_sandbox.read_text(encoding="utf-8"))


@app.get("/api/norm-review/{rt_id}")
def api_norm_review_get(rt_id: str):
    """Get normalization review for an RT ID."""
    reviews = _load_json(NORM_REVIEWS_PATH)
    return reviews.get(rt_id, {})


@app.post("/api/norm-review/{rt_id}")
async def api_norm_review_post(rt_id: str, request: Request):
    """Save normalization review for an RT ID."""
    body = await request.json()
    reviews = _load_json(NORM_REVIEWS_PATH)
    reviews[rt_id] = {
        "determination": body.get("determination", ""),
        "notes": body.get("notes", ""),
        "overrides": body.get("overrides", {}),
        "sandbox_accepted": body.get("sandbox_accepted", False),
        "date": datetime.now().isoformat()[:10],
    }
    _save_json(NORM_REVIEWS_PATH, reviews)
    return {"ok": True}


@app.get("/api/norm-regressions")
def api_norm_regressions():
    """Return RT IDs of reviewed normalized records that changed in sandbox."""
    reviews = _load_json(NORM_REVIEWS_PATH)
    norm_active = NORMALIZED_DIR / "active"
    norm_sandbox = NORMALIZED_DIR / "sandbox"

    if not norm_active.exists() or not norm_sandbox.exists():
        return []

    regressions = []
    for rt_id, rev in reviews.items():
        if rev.get("sandbox_accepted"):
            continue
        if rev.get("determination") != "clean":
            continue
        active_file = norm_active / f"{rt_id}.json"
        sandbox_file = norm_sandbox / f"{rt_id}.json"
        if not active_file.exists() or not sandbox_file.exists():
            continue
        active_data = json.loads(active_file.read_text(encoding="utf-8"))
        sandbox_data = json.loads(sandbox_file.read_text(encoding="utf-8"))
        # Strip volatile fields
        for d in (active_data, sandbox_data):
            d.pop("source_version", None)
        if active_data != sandbox_data:
            regressions.append(rt_id)

    return regressions


_norm_sandbox_changed_cache: dict = {"key": None, "data": []}

@app.get("/api/norm-sandbox-changed")
def api_norm_sandbox_changed():
    """Return RT IDs where sandbox normalization differs from active (cached)."""
    from cleo.normalize.versioning import NORM_VOLATILE_FIELDS, store as norm_store

    norm_active = NORMALIZED_DIR / "active"
    norm_sandbox = NORMALIZED_DIR / "sandbox"

    if not norm_active.exists() or not norm_sandbox.exists():
        return []

    # Cache key: sandbox dir mtime (changes when files are written)
    try:
        cache_key = norm_sandbox.stat().st_mtime
    except OSError:
        cache_key = None

    if cache_key and _norm_sandbox_changed_cache["key"] == cache_key:
        return _norm_sandbox_changed_cache["data"]

    def _strip_volatile(d: dict) -> dict:
        out = {}
        for k, v in d.items():
            if k in NORM_VOLATILE_FIELDS:
                continue
            if isinstance(v, dict):
                v = _strip_volatile(v)
            out[k] = v
        return out

    changed = []
    for sf in norm_sandbox.glob("*.json"):
        if sf.stem == "_meta":
            continue
        af = norm_active / sf.name
        if not af.exists():
            changed.append(sf.stem)
            continue
        # Fast path: byte-identical files are unchanged
        if sf.read_bytes() == af.read_bytes():
            continue
        # Slow path: strip volatile fields and compare
        ad = _strip_volatile(json.loads(af.read_text(encoding="utf-8")))
        sd = _strip_volatile(json.loads(sf.read_text(encoding="utf-8")))
        if ad != sd:
            changed.append(sf.stem)

    _norm_sandbox_changed_cache["key"] = cache_key
    _norm_sandbox_changed_cache["data"] = changed
    return changed


# ---------------------------------------------------------------------------
# Expand stage endpoints
# ---------------------------------------------------------------------------

@app.get("/api/expand-status")
def api_expand_status():
    """Return expand stage version info."""
    from cleo.expand import versioning as expand_ver
    store = expand_ver.store
    return {
        "active_version": store.active_version() or "",
        "versions": store.list_versions(),
        "has_sandbox": store.sandbox_path().is_dir(),
    }


@app.get("/api/expand-rt-ids")
def api_expand_rt_ids():
    """List all expanded record IDs with review status."""
    expand_active = EXPANDED_DIR / "active"
    if not expand_active.exists():
        raise HTTPException(404, "No active expanded version")

    all_ids = sorted(
        f.stem for f in expand_active.glob("*.json") if f.stem != "_meta"
    )

    reviews = _load_json(EXPAND_REVIEWS_PATH)

    records = []
    for record_id in all_ids:
        reviewed = record_id in reviews
        if record_id.startswith("BR_"):
            source = "brand"
        elif record_id.startswith("GW"):
            source = "geowarehouse"
        else:
            source = "realtrack"
        records.append({
            "rt_id": record_id,
            "source": source,
            "reviewed": reviewed,
            "determination": reviews.get(record_id, {}).get("determination", ""),
        })

    return records


@app.get("/api/expanded/{rt_id}")
def api_expanded(rt_id: str):
    """Return expanded JSON from active version."""
    expand_active = EXPANDED_DIR / "active" / f"{rt_id}.json"
    if not expand_active.exists():
        raise HTTPException(404, "Not in active expanded version")
    return json.loads(expand_active.read_text(encoding="utf-8"))


@app.get("/api/expand-sandbox/{rt_id}")
def api_expand_sandbox(rt_id: str):
    """Return expanded JSON from sandbox."""
    expand_sandbox = EXPANDED_DIR / "sandbox" / f"{rt_id}.json"
    if not expand_sandbox.exists():
        raise HTTPException(404, "Not in expand sandbox")
    return json.loads(expand_sandbox.read_text(encoding="utf-8"))


@app.get("/api/expand-review/{rt_id}")
def api_expand_review_get(rt_id: str):
    """Get expansion review for a record."""
    reviews = _load_json(EXPAND_REVIEWS_PATH)
    return reviews.get(rt_id, {})


@app.post("/api/expand-review/{rt_id}")
async def api_expand_review_post(rt_id: str, request: Request):
    """Save expansion review for a record."""
    body = await request.json()
    reviews = _load_json(EXPAND_REVIEWS_PATH)
    reviews[rt_id] = {
        "determination": body.get("determination", ""),
        "notes": body.get("notes", ""),
        "overrides": body.get("overrides", {}),
        "sandbox_accepted": body.get("sandbox_accepted", False),
        "date": datetime.now().isoformat()[:10],
    }
    _save_json(EXPAND_REVIEWS_PATH, reviews)
    return {"ok": True}


@app.get("/api/expand-regressions")
def api_expand_regressions():
    """Return IDs of reviewed expanded records that changed in sandbox."""
    from cleo.expand.versioning import EXPAND_VOLATILE_FIELDS

    reviews = _load_json(EXPAND_REVIEWS_PATH)
    expand_active = EXPANDED_DIR / "active"
    expand_sandbox = EXPANDED_DIR / "sandbox"

    if not expand_active.exists() or not expand_sandbox.exists():
        return []

    regressions = []
    for rt_id, rev in reviews.items():
        if rev.get("sandbox_accepted"):
            continue
        if rev.get("determination") != "clean":
            continue
        af = expand_active / f"{rt_id}.json"
        sf = expand_sandbox / f"{rt_id}.json"
        if not af.exists() or not sf.exists():
            continue
        ad = json.loads(af.read_text(encoding="utf-8"))
        sd = json.loads(sf.read_text(encoding="utf-8"))
        for d in (ad, sd):
            for k in EXPAND_VOLATILE_FIELDS:
                d.pop(k, None)
        if ad != sd:
            regressions.append(rt_id)

    return regressions


@app.get("/api/expand-no-street-number")
def api_expand_no_street_number():
    """Return IDs of expanded records where property has no street number.

    Checks sandbox first (if exists), otherwise active.
    """
    expand_sandbox = EXPANDED_DIR / "sandbox"
    expand_active = EXPANDED_DIR / "active"
    check_dir = expand_sandbox if expand_sandbox.exists() else expand_active
    if not check_dir.exists():
        return []

    result = []
    for f in check_dir.glob("*.json"):
        if f.stem == "_meta":
            continue
        try:
            data = json.loads(f.read_text())
            prop = data.get("property", {})
            addresses = prop.get("addresses", [])
            if addresses and not addresses[0].get("street_number", "").strip():
                result.append(f.stem)
            elif not addresses:
                result.append(f.stem)
        except Exception:
            continue
    return sorted(result)


_expand_sandbox_changed_cache: dict = {"key": None, "data": []}

@app.get("/api/expand-sandbox-changed")
def api_expand_sandbox_changed():
    """Return IDs where sandbox expansion differs from active (cached)."""
    from cleo.expand.versioning import EXPAND_VOLATILE_FIELDS

    expand_active = EXPANDED_DIR / "active"
    expand_sandbox = EXPANDED_DIR / "sandbox"

    if not expand_active.exists() or not expand_sandbox.exists():
        return []

    try:
        cache_key = expand_sandbox.stat().st_mtime
    except OSError:
        cache_key = None

    if cache_key and _expand_sandbox_changed_cache["key"] == cache_key:
        return _expand_sandbox_changed_cache["data"]

    changed = []
    for sf in expand_sandbox.glob("*.json"):
        if sf.stem == "_meta":
            continue
        af = expand_active / sf.name
        if not af.exists():
            changed.append(sf.stem)
            continue
        if sf.read_bytes() == af.read_bytes():
            continue
        ad = json.loads(af.read_text(encoding="utf-8"))
        sd = json.loads(sf.read_text(encoding="utf-8"))
        for d in (ad, sd):
            for k in EXPAND_VOLATILE_FIELDS:
                d.pop(k, None)
        if ad != sd:
            changed.append(sf.stem)

    _expand_sandbox_changed_cache["key"] = cache_key
    _expand_sandbox_changed_cache["data"] = changed
    return changed


# ---------------------------------------------------------------------------
# API — Parcelled endpoints
# ---------------------------------------------------------------------------

@app.get("/api/parcelled-status")
def api_parcelled_status():
    """Return parcelled stage version info."""
    from cleo.parcelled import versioning as parcelled_ver
    store = parcelled_ver.store
    return {
        "active_version": store.active_version() or "",
        "versions": store.list_versions(),
        "has_sandbox": store.sandbox_path().is_dir(),
    }


@app.get("/api/parcelled-rt-ids")
def api_parcelled_rt_ids():
    """List all parcelled record IDs with review status."""
    parcelled_active = PARCELLED_DIR / "active"
    if not parcelled_active.exists():
        raise HTTPException(404, "No active parcelled version")

    all_ids = sorted(
        f.stem for f in parcelled_active.glob("*.json") if f.stem != "_meta"
    )

    reviews = _load_json(PARCELLED_REVIEWS_PATH)

    records = []
    for record_id in all_ids:
        reviewed = record_id in reviews
        if record_id.startswith("BR_"):
            source = "brand"
        elif record_id.startswith("GW"):
            source = "geowarehouse"
        else:
            source = "realtrack"
        records.append({
            "rt_id": record_id,
            "source": source,
            "reviewed": reviewed,
            "determination": reviews.get(record_id, {}).get("determination", ""),
        })

    return records


@app.get("/api/parcelled-methods")
def api_parcelled_methods():
    """Return {record_id: method} map for all parcelled records (for filter enrichment)."""
    parcelled_active = PARCELLED_DIR / "active"
    if not parcelled_active.exists():
        return {}

    methods = {}
    for f in parcelled_active.glob("*.json"):
        if f.stem == "_meta":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            res = data.get("resolution", {})
            methods[f.stem] = res.get("method", "none")
        except Exception:
            continue
    return methods


@app.get("/api/parcelled/{rt_id}")
def api_parcelled(rt_id: str):
    """Return parcelled JSON from active version."""
    parcelled_path = PARCELLED_DIR / "active" / f"{rt_id}.json"
    if not parcelled_path.exists():
        raise HTTPException(404, "Not in active parcelled version")
    return json.loads(parcelled_path.read_text(encoding="utf-8"))


@app.get("/api/parcelled-sandbox/{rt_id}")
def api_parcelled_sandbox(rt_id: str):
    """Return parcelled JSON from sandbox."""
    parcelled_path = PARCELLED_DIR / "sandbox" / f"{rt_id}.json"
    if not parcelled_path.exists():
        raise HTTPException(404, "Not in parcelled sandbox")
    return json.loads(parcelled_path.read_text(encoding="utf-8"))


@app.get("/api/parcelled-review/{rt_id}")
def api_parcelled_review_get(rt_id: str):
    """Get parcelled review for a record."""
    reviews = _load_json(PARCELLED_REVIEWS_PATH)
    return reviews.get(rt_id, {})


@app.post("/api/parcelled-review/{rt_id}")
async def api_parcelled_review_post(rt_id: str, request: Request):
    """Save parcelled review for a record."""
    body = await request.json()
    reviews = _load_json(PARCELLED_REVIEWS_PATH)
    reviews[rt_id] = {
        "determination": body.get("determination", ""),
        "notes": body.get("notes", ""),
        "overrides": body.get("overrides", {}),
        "sandbox_accepted": body.get("sandbox_accepted", False),
        "date": datetime.now().isoformat()[:10],
    }
    _save_json(PARCELLED_REVIEWS_PATH, reviews)
    return {"ok": True}


@app.get("/api/parcelled-regressions")
def api_parcelled_regressions():
    """Return IDs of reviewed parcelled records that changed in sandbox."""
    from cleo.parcelled.versioning import PARCELLED_VOLATILE_FIELDS

    reviews = _load_json(PARCELLED_REVIEWS_PATH)
    parcelled_active = PARCELLED_DIR / "active"
    parcelled_sandbox = PARCELLED_DIR / "sandbox"

    if not parcelled_active.exists() or not parcelled_sandbox.exists():
        return []

    regressions = []
    for rt_id, rev in reviews.items():
        if rev.get("sandbox_accepted"):
            continue
        if rev.get("determination") != "clean":
            continue
        af = parcelled_active / f"{rt_id}.json"
        sf = parcelled_sandbox / f"{rt_id}.json"
        if not af.exists() or not sf.exists():
            continue
        ad = json.loads(af.read_text(encoding="utf-8"))
        sd = json.loads(sf.read_text(encoding="utf-8"))
        for d in (ad, sd):
            for k in PARCELLED_VOLATILE_FIELDS:
                d.pop(k, None)
        if ad != sd:
            regressions.append(rt_id)

    return regressions


# ---------------------------------------------------------------------------
# API — Compiled review endpoints
# ---------------------------------------------------------------------------

@app.get("/api/compiled-status")
def api_compiled_status():
    """Return compiled stage version info."""
    from cleo.compiled import versioning as compiled_ver
    store = compiled_ver.store
    compiled_active = COMPILED_DIR / "active"
    record_count = sum(1 for f in compiled_active.glob("*.json") if f.stem != "_meta") if compiled_active.exists() else 0
    return {
        "active_version": store.active_version() or "",
        "versions": store.list_versions(),
        "has_sandbox": store.sandbox_path().is_dir(),
        "record_count": record_count,
    }


@app.get("/api/compiled-rt-ids")
def api_compiled_rt_ids():
    """List all compiled record IDs with review status."""
    compiled_active = COMPILED_DIR / "active"
    if not compiled_active.exists():
        raise HTTPException(404, "No active compiled version")

    all_ids = sorted(
        f.stem for f in compiled_active.glob("*.json") if f.stem != "_meta"
    )

    reviews = _load_json(COMPILED_REVIEWS_PATH)

    records = []
    for record_id in all_ids:
        reviewed = record_id in reviews
        det = reviews.get(record_id, {}).get("determination", "")
        records.append({
            "rt_id": record_id,
            "reviewed": reviewed,
            "determination": det,
        })

    return records


@app.get("/api/compiled-meta")
def api_compiled_meta():
    """Return {record_id: {source, has_parcel, parcel_method}} for filtering."""
    compiled_active = COMPILED_DIR / "active"
    if not compiled_active.exists():
        return {}

    meta = {}
    for f in compiled_active.glob("*.json"):
        if f.stem == "_meta":
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            parcel = data.get("parcel")
            meta[f.stem] = {
                "source": data.get("source", "unknown"),
                "has_parcel": parcel is not None,
                "parcel_method": parcel.get("method", "") if parcel else "",
            }
        except Exception:
            meta[f.stem] = {"source": "unknown", "has_parcel": False, "parcel_method": ""}

    return meta


@app.get("/api/compiled/{rt_id}")
def api_compiled_record(rt_id: str):
    """Return compiled JSON from active version."""
    compiled_path = COMPILED_DIR / "active" / f"{rt_id}.json"
    if not compiled_path.exists():
        raise HTTPException(404, "Not in active compiled version")
    return json.loads(compiled_path.read_text(encoding="utf-8"))


@app.get("/api/compiled-sandbox/{rt_id}")
def api_compiled_sandbox(rt_id: str):
    """Return compiled JSON from sandbox."""
    compiled_path = COMPILED_DIR / "sandbox" / f"{rt_id}.json"
    if not compiled_path.exists():
        raise HTTPException(404, "Not in compiled sandbox")
    return json.loads(compiled_path.read_text(encoding="utf-8"))


@app.get("/api/compiled-review/{rt_id}")
def api_compiled_review_get(rt_id: str):
    """Get compiled review for a record."""
    reviews = _load_json(COMPILED_REVIEWS_PATH)
    return reviews.get(rt_id, {})


@app.post("/api/compiled-review/{rt_id}")
async def api_compiled_review_post(rt_id: str, request: Request):
    """Save compiled review for a record."""
    body = await request.json()
    reviews = _load_json(COMPILED_REVIEWS_PATH)
    reviews[rt_id] = {
        "determination": body.get("determination", ""),
        "notes": body.get("notes", ""),
        "overrides": body.get("overrides", {}),
        "sandbox_accepted": body.get("sandbox_accepted", False),
        "date": datetime.now().isoformat()[:10],
    }
    _save_json(COMPILED_REVIEWS_PATH, reviews)
    return {"ok": True}


@app.get("/api/compiled-regressions")
def api_compiled_regressions():
    """Return IDs of reviewed compiled records that changed in sandbox."""
    from cleo.compiled.versioning import COMPILED_VOLATILE_FIELDS

    reviews = _load_json(COMPILED_REVIEWS_PATH)
    compiled_active = COMPILED_DIR / "active"
    compiled_sandbox = COMPILED_DIR / "sandbox"

    if not compiled_active.exists() or not compiled_sandbox.exists():
        return []

    regressions = []
    for rt_id, rev in reviews.items():
        if rev.get("sandbox_accepted"):
            continue
        if rev.get("determination") != "clean":
            continue
        af = compiled_active / f"{rt_id}.json"
        sf = compiled_sandbox / f"{rt_id}.json"
        if not af.exists() or not sf.exists():
            continue
        ad = json.loads(af.read_text(encoding="utf-8"))
        sd = json.loads(sf.read_text(encoding="utf-8"))
        for d in (ad, sd):
            for k in COMPILED_VOLATILE_FIELDS:
                d.pop(k, None)
        if ad != sd:
            regressions.append(rt_id)

    return regressions


@app.get("/api/osm-poi/{record_id}")
def api_osm_poi(record_id: str):
    """Get raw OSM POI record from active snapshot."""
    osm_active = OSM_POIS_DIR / "active"
    if not osm_active.exists():
        raise HTTPException(404, "No OSM POIs active version")
    path = osm_active / f"{record_id}.json"
    if not path.exists():
        raise HTTPException(404, f"OSM POI not found: {record_id}")
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


# ---------------------------------------------------------------------------
# Properties search API
# ---------------------------------------------------------------------------

class _PropCache:
    data = None
    mtime = 0

class _IdxCache:
    data = None
    mtime = 0


def _load_properties():
    """Load properties.json with simple caching."""
    from cleo.config import PROPERTIES_PATH
    if not PROPERTIES_PATH.exists():
        return None
    mtime = PROPERTIES_PATH.stat().st_mtime
    if _PropCache.mtime != mtime:
        _PropCache.data = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
        _PropCache.mtime = mtime
    return _PropCache.data


def _load_search_index():
    """Load search_index.json with simple caching."""
    from cleo.config import SEARCH_INDEX_PATH
    if not SEARCH_INDEX_PATH.exists():
        return None
    mtime = SEARCH_INDEX_PATH.stat().st_mtime
    if _IdxCache.mtime != mtime:
        _IdxCache.data = json.loads(SEARCH_INDEX_PATH.read_text(encoding="utf-8"))
        _IdxCache.mtime = mtime
    return _IdxCache.data


@app.get("/api/properties/search")
def api_properties_search(q: str = "", limit: int = 50):
    """Search properties by any field. Returns matching property summaries."""
    from cleo.properties.search import search

    if not q.strip():
        return []

    index_data = _load_search_index()
    if not index_data:
        raise HTTPException(404, "No search index. Run 'cleo properties' first.")

    props_data = _load_properties()
    if not props_data:
        raise HTTPException(404, "No properties. Run 'cleo properties' first.")

    results = search(index_data, q.strip(), limit=limit)
    properties = props_data.get("properties", {})

    # Return lightweight summaries for the results list
    output = []
    for pid, score in results:
        prop = properties.get(pid)
        if not prop:
            continue
        output.append({
            "property_id": pid,
            "arn": prop.get("arn"),
            "primary_address": prop.get("primary_address"),
            "city": prop.get("city"),
            "current_owner": (prop.get("current_owner") or {}).get("name", ""),
            "latest_sale_date": (prop.get("latest_transaction") or {}).get("sale_date", ""),
            "latest_sale_price": (prop.get("latest_transaction") or {}).get("sale_price"),
            "sources": prop.get("sources"),
            "transaction_count": prop.get("transaction_count"),
            "tenant_count": len(prop.get("tenants", [])),
            "centroid_lat": prop.get("centroid_lat"),
            "centroid_lng": prop.get("centroid_lng"),
            "score": score,
        })

    return output


@app.get("/api/properties/stats")
def api_properties_stats():
    """Get property master list stats."""
    props_data = _load_properties()
    if not props_data:
        return {"built": False}
    return props_data.get("meta", {})


# ---------------------------------------------------------------------------
# Properties browse API (front-facing app)
# ---------------------------------------------------------------------------

class _BrandInfoCache:
    data: dict | None = None

def _load_brand_info() -> dict:
    """Build BR_XXXXX -> {brand, store_name, category} lookup (cached in memory)."""
    if _BrandInfoCache.data is not None:
        return _BrandInfoCache.data

    from cleo.config import NORMALIZED_DIR, MASTER_BRANDS_CSV
    import csv

    # Brand name -> category from master CSV
    categories: dict[str, str] = {}
    if MASTER_BRANDS_CSV.exists():
        with open(MASTER_BRANDS_CSV, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = (row.get("Brand Name") or "").strip()
                cat = (row.get("Category") or "").strip()
                if name and cat:
                    categories[name.lower()] = cat

    # Aliases for scraped brand names that differ from CSV names
    _BRAND_ALIASES: dict[str, str] = {
        "chipotle": "chipotle mexican grill",
        "domino's": "dominos pizza",
        "indigo": "indigo / chapters",
        "kelseys": "kelseys original roadhouse",
        "land rover": "land-rover",
        "longo's": "longos",
        "mary brown's": "mary brown's chicken",
        "mcdonald's": "mcdonalds",
        "montana's": "montana's bbq & bar",
        "no frills": "nofrills",
        "petsmart": "pet smart",
        "popeyes": "popeyes louisiana kitchen",
        "your independent grocer": "independant",
    }

    def _lookup_category(brand_name: str) -> str:
        key = brand_name.lower()
        cat = categories.get(key, "")
        if not cat:
            alias = _BRAND_ALIASES.get(key, "")
            cat = categories.get(alias, "")
        return cat

    # BR_XXXXX -> {brand, store_name, category} from normalized records
    info: dict[str, dict] = {}
    norm_active = NORMALIZED_DIR / "active"
    if norm_active.exists():
        for path in norm_active.glob("BR_*.json"):
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
                brand = rec.get("brand", "")
                info[path.stem] = {
                    "brand": brand,
                    "store_name": rec.get("store_name", ""),
                    "category": _lookup_category(brand),
                }
            except Exception:
                continue

    _BrandInfoCache.data = info
    return info


class _FiltersCache:
    data: dict | None = None
    mtime: float = 0

def _load_filters() -> dict:
    """Build available filter values (cached by properties.json mtime)."""
    from cleo.config import PROPERTIES_PATH
    if not PROPERTIES_PATH.exists():
        return {"cities": [], "categories": []}
    mtime = PROPERTIES_PATH.stat().st_mtime
    if _FiltersCache.mtime == mtime and _FiltersCache.data is not None:
        return _FiltersCache.data

    props_data = _load_properties()
    if not props_data:
        return {"cities": [], "categories": []}

    brand_info = _load_brand_info()
    properties = props_data.get("properties", {})
    cities: set[str] = set()
    categories: set[str] = set()

    brands: set[str] = set()

    for prop in properties.values():
        city = prop.get("city", "").strip()
        # Skip cities that look like full addresses (start with digits)
        if city and not city[0].isdigit():
            cities.add(city)
        for tenant in prop.get("tenants", []):
            if tenant.get("source") == "brand":
                info = brand_info.get(tenant["source_id"]) or {}
                cat = info.get("category", "")
                brand_name = info.get("brand", "")
                if cat:
                    categories.add(cat)
                if brand_name:
                    brands.add(brand_name)
            elif tenant.get("source") == "osm":
                cat = tenant.get("category", "")
                name = tenant.get("name", "")
                if cat:
                    categories.add(cat)
                if name:
                    brands.add(name)

    _FiltersCache.data = {"cities": sorted(cities), "categories": sorted(categories), "brands": sorted(brands)}
    _FiltersCache.mtime = mtime
    return _FiltersCache.data


@app.get("/api/properties/filters")
def api_properties_filters():
    """Return available filter values for the properties browse UI."""
    return _load_filters()


@app.get("/api/properties/browse")
def api_properties_browse(
    q: str = "",
    city: str = "",
    category: str = "",
    min_price: int = 0,
    max_price: int = 0,
    sort: str = "latest_sale_date",
    order: str = "desc",
    page: int = 1,
    per_page: int = 25,
):
    """Browse properties with filtering, sorting, and pagination."""
    from cleo.properties.search import search as idx_search

    props_data = _load_properties()
    if not props_data:
        raise HTTPException(404, "No properties. Run 'cleo properties' first.")

    properties = props_data.get("properties", {})
    brand_info = _load_brand_info()

    # --- determine candidate PIDs ---
    scores: dict[str, float] = {}
    if q.strip():
        index_data = _load_search_index()
        if index_data:
            results = idx_search(index_data, q.strip(), limit=20000)
            scores = {pid: sc for pid, sc in results}
            candidates = set(scores.keys())
        else:
            candidates = set(properties.keys())
    else:
        candidates = set(properties.keys())

    # --- helper: tenant categories for a property ---
    def _tenant_categories(prop: dict) -> set[str]:
        cats: set[str] = set()
        for t in prop.get("tenants", []):
            if t.get("source") == "brand":
                c = (brand_info.get(t["source_id"]) or {}).get("category", "")
                if c:
                    cats.add(c.lower())
            elif t.get("source") == "osm":
                c = t.get("category", "")
                if c:
                    cats.add(c.lower())
        return cats

    # --- helper: tenant display names (deduplicated) ---
    def _tenant_names(prop: dict) -> list[str]:
        seen: set[str] = set()
        names: list[str] = []
        for t in prop.get("tenants", []):
            if t.get("source") == "brand":
                info = brand_info.get(t["source_id"])
                n = info["brand"] if info else t["source_id"]
            elif t.get("source") == "osm":
                n = t.get("name", t["source_id"])
            else:
                continue
            if n.lower() not in seen:
                seen.add(n.lower())
                names.append(n)
        return names

    # --- apply filters ---
    filtered: list[dict] = []
    city_lower = city.lower() if city else ""
    cat_lower = category.lower() if category else ""

    for pid in candidates:
        prop = properties.get(pid)
        if not prop:
            continue

        if city_lower and prop.get("city", "").lower() != city_lower:
            continue

        if cat_lower and cat_lower not in _tenant_categories(prop):
            continue

        latest = prop.get("latest_transaction") or {}
        price = latest.get("sale_price") or 0
        if min_price and price < min_price:
            continue
        if max_price and price > max_price:
            continue

        filtered.append(prop)

    # --- sort ---
    def _sort_key(p: dict):
        if sort == "latest_sale_price":
            return (p.get("latest_transaction") or {}).get("sale_price") or 0
        if sort == "city":
            return p.get("city", "").lower()
        if sort == "transaction_count":
            return p.get("transaction_count", 0)
        if sort == "relevance" and scores:
            return scores.get(p.get("property_id", ""), 0)
        # default: latest_sale_date
        return (p.get("latest_transaction") or {}).get("sale_date") or ""

    use_sort = sort
    if q.strip() and sort == "latest_sale_date":
        use_sort = "relevance"

    reverse = order == "desc"
    if use_sort == "relevance":
        reverse = True
    filtered.sort(key=lambda p: _sort_key(p) if use_sort != "relevance" else scores.get(p.get("property_id", ""), 0), reverse=reverse)

    # --- paginate ---
    total = len(filtered)
    start = (page - 1) * per_page
    page_items = filtered[start:start + per_page]

    # --- build response ---
    results = []
    for prop in page_items:
        latest = prop.get("latest_transaction") or {}
        owner = prop.get("current_owner") or {}
        results.append({
            "property_id": prop.get("property_id"),
            "arn": prop.get("arn"),
            "primary_address": prop.get("primary_address"),
            "city": prop.get("city"),
            "current_owner": owner.get("name", ""),
            "latest_sale_date": latest.get("sale_date", ""),
            "latest_sale_price": latest.get("sale_price"),
            "sources": prop.get("sources", []),
            "transaction_count": prop.get("transaction_count", 0),
            "tenants": _tenant_names(prop),
            "tenant_count": len(prop.get("tenants", [])),
        })

    return {
        "results": results,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# Properties geo API (map)
# ---------------------------------------------------------------------------

class _GeoCache:
    data: dict | None = None
    mtime: float = 0


def _resolve_tenants(prop: dict, brand_info: dict) -> tuple[list[str], list[str], list[str]]:
    """Resolve tenant names and categories for a property record."""
    tenant_names: list[str] = []
    tenant_cat_list: list[str] = []
    tenant_cats: set[str] = set()
    seen: set[str] = set()
    for t in prop.get("tenants", []):
        if t.get("source") == "brand":
            info = brand_info.get(t["source_id"]) or {}
            n = info.get("brand", t["source_id"])
            cat = info.get("category", "")
        elif t.get("source") == "osm":
            n = t.get("name", t["source_id"])
            cat = t.get("category", "")
        else:
            continue
        key = n.lower()
        if key not in seen:
            seen.add(key)
            tenant_names.append(n)
            tenant_cat_list.append(cat)
        if cat:
            tenant_cats.add(cat)
    return tenant_names, tenant_cat_list, list(tenant_cats)


def _build_geo_features() -> dict:
    """Build GeoJSON FeatureCollection of all properties with coordinates."""
    props_data = _load_properties()
    if not props_data:
        return {"type": "FeatureCollection", "features": [], "total": 0}

    brand_info = _load_brand_info()
    properties = props_data.get("properties", {})
    features = []

    for pid, prop in properties.items():
        lat = prop.get("centroid_lat")
        lng = prop.get("centroid_lng")
        if lat is None or lng is None:
            continue

        tenant_names, tenant_cat_list, categories = _resolve_tenants(prop, brand_info)
        latest = prop.get("latest_transaction") or {}
        owner = prop.get("current_owner") or {}

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": {
                "id": pid,
                "address": prop.get("primary_address", ""),
                "city": prop.get("city", ""),
                "owner": owner.get("name", ""),
                "latest_price": latest.get("sale_price"),
                "latest_date": latest.get("sale_date", ""),
                "tenants": tenant_names,
                "tenant_categories": tenant_cat_list,
                "categories": categories,
                "sources": prop.get("sources", []),
                "transaction_count": prop.get("transaction_count", 0),
                "parcel_method": prop.get("parcel_method", ""),
            },
        })

    return {"type": "FeatureCollection", "features": features, "total": len(features)}


@app.get("/api/properties/geo")
def api_properties_geo():
    """Return all properties as a GeoJSON FeatureCollection for the map."""
    if not PROPERTIES_PATH.exists():
        return {"type": "FeatureCollection", "features": [], "total": 0}
    mtime = PROPERTIES_PATH.stat().st_mtime
    if _GeoCache.mtime != mtime or _GeoCache.data is None:
        _GeoCache.data = _build_geo_features()
        _GeoCache.mtime = mtime
    return JSONResponse(_GeoCache.data)


# ---------------------------------------------------------------------------
# Parcel cache bbox API (map)
# ---------------------------------------------------------------------------

class _ParcelCacheStore:
    data: dict | None = None
    mtime: float = 0
    arn_to_pid: dict[str, str] | None = None


def _load_parcel_cache() -> dict | None:
    """Load parcel_cache.json with mtime-based caching."""
    if not PARCEL_CACHE_PATH.exists():
        return None
    mtime = PARCEL_CACHE_PATH.stat().st_mtime
    if _ParcelCacheStore.mtime != mtime:
        raw = json.loads(PARCEL_CACHE_PATH.read_text(encoding="utf-8"))
        _ParcelCacheStore.data = raw.get("parcels", {})
        _ParcelCacheStore.mtime = mtime
        # Rebuild ARN -> property_id index
        props_data = _load_properties()
        idx: dict[str, str] = {}
        if props_data:
            for pid, prop in props_data.get("properties", {}).items():
                arn = prop.get("arn")
                if arn:
                    idx[arn] = pid
        _ParcelCacheStore.arn_to_pid = idx
    return _ParcelCacheStore.data


def _resolve_group_for_parcel(
    arn: str,
    owner_name: str,
    group_name_index: dict,
    group_records: dict,
    manual_links_by_arn: dict,
) -> tuple:
    """Resolve group_id and group_name for a parcel.

    Priority: manual link > transaction-derived owner.
    Returns (group_id, group_name).
    """
    # Manual link takes priority
    manual = manual_links_by_arn.get(arn)
    if manual:
        gid = manual["group_id"]
        grp = group_records.get(gid, {})
        name = grp.get("display_name") or (grp.get("known_names") or [""])[0]
        return gid, name

    # Fall back to owner name → group lookup
    if owner_name:
        from cleo.groups.registry import normalize_group_name
        norm = normalize_group_name(owner_name)
        gid = group_name_index.get(norm, "")
        if gid:
            grp = group_records.get(gid, {})
            name = grp.get("display_name") or owner_name
            return gid, name

    return "", ""


class _GroupLookupCache:
    """Mtime-based cache for group registry + property links used in parcel bbox."""
    name_index: dict = {}
    groups: dict = {}
    links_by_arn: dict = {}
    _reg_mtime: float = 0
    _links_mtime: float = 0

    @classmethod
    def load(cls):
        from cleo.config import GROUP_REGISTRY_PATH, GROUP_PROPERTY_LINKS_PATH
        import json

        reg_path = GROUP_REGISTRY_PATH
        links_path = GROUP_PROPERTY_LINKS_PATH

        reg_changed = reg_path.exists() and reg_path.stat().st_mtime != cls._reg_mtime
        links_changed = links_path.exists() and links_path.stat().st_mtime != cls._links_mtime

        if reg_changed or not cls.name_index:
            data = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.exists() else {}
            cls.name_index = data.get("name_index", {})
            cls.groups = data.get("groups", {})
            cls._reg_mtime = reg_path.stat().st_mtime if reg_path.exists() else 0

        if links_changed or not cls.links_by_arn:
            if links_path.exists():
                links = json.loads(links_path.read_text(encoding="utf-8"))
                cls.links_by_arn = {l["arn"]: l for l in links}
                cls._links_mtime = links_path.stat().st_mtime
            else:
                cls.links_by_arn = {}


@app.get("/api/parcels/cache/bbox")
def api_parcels_cache_bbox(
    south: float, west: float, north: float, east: float
):
    """Return provincial parcel polygons within the map viewport, enriched with property data."""
    parcels = _load_parcel_cache()
    if not parcels:
        return {"type": "FeatureCollection", "features": []}

    arn_to_pid = _ParcelCacheStore.arn_to_pid or {}
    props_data = _load_properties()
    properties = props_data.get("properties", {}) if props_data else {}
    brand_info = _load_brand_info()

    # Load group lookup data for resolving owner → group
    _GroupLookupCache.load()

    features = []

    for arn, parcel in parcels.items():
        centroid = parcel.get("centroid")
        if not centroid or len(centroid) < 2:
            continue
        lat, lng = centroid[0], centroid[1]
        if not (south <= lat <= north and west <= lng <= east):
            continue

        geom = parcel.get("geometry")
        if not geom:
            continue

        pid = arn_to_pid.get(arn, "")
        prop = properties.get(pid, {})
        tenant_names, tenant_cat_list, categories = _resolve_tenants(prop, brand_info)
        latest = prop.get("latest_transaction") or {}
        owner = prop.get("current_owner") or {}
        owner_name = owner.get("name", "")

        # Resolve group
        group_id, group_name = _resolve_group_for_parcel(
            arn, owner_name,
            _GroupLookupCache.name_index,
            _GroupLookupCache.groups,
            _GroupLookupCache.links_by_arn,
        )

        # First photo from latest transaction (if any)
        photo = ""
        for txn in prop.get("transactions", []):
            photos = txn.get("photos", [])
            if photos:
                photo = photos[0]
                break

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "arn": arn,
                "pin": parcel.get("pin"),
                "property_id": pid,
                "address": prop.get("primary_address", ""),
                "city": prop.get("city", ""),
                "owner": owner_name,
                "group_id": group_id,
                "group_name": group_name,
                "latest_price": latest.get("sale_price"),
                "latest_date": latest.get("sale_date", ""),
                "tenants": tenant_names,
                "tenant_categories": tenant_cat_list,
                "categories": categories,
                "sources": prop.get("sources", []),
                "transaction_count": prop.get("transaction_count", 0),
                "parcel_method": prop.get("parcel_method", ""),
                "photo": photo,
            },
        })

        if len(features) >= 2000:
            break

    return {"type": "FeatureCollection", "features": features}


@app.get("/api/parcels/cache/arn/{arn}")
def api_parcels_cache_arn(arn: str):
    """Return a single parcel polygon by ARN."""
    parcels = _load_parcel_cache()
    if not parcels or arn not in parcels:
        raise HTTPException(status_code=404, detail="Parcel not found")
    parcel = parcels[arn]
    geom = parcel.get("geometry")
    if not geom:
        raise HTTPException(status_code=404, detail="No geometry for parcel")
    return {
        "type": "Feature",
        "geometry": geom,
        "properties": {
            "arn": arn,
            "pin": parcel.get("pin"),
        },
    }


# Property detail — MUST be after all fixed-path /api/properties/* routes
# so that FastAPI doesn't match "browse", "filters", "stats", "search" as a property_id.
@app.get("/api/properties/{property_id}")
def api_property_detail(property_id: str):
    """Get full property record by P-ID, enriched with brand names."""
    props_data = _load_properties()
    if not props_data:
        raise HTTPException(404, "No properties. Run 'cleo properties' first.")

    prop = props_data.get("properties", {}).get(property_id)
    if not prop:
        raise HTTPException(404, f"Property not found: {property_id}")

    # Enrich brand tenants with name + category
    brand_info = _load_brand_info()
    enriched = dict(prop)
    enriched_tenants = []
    for t in enriched.get("tenants", []):
        t = dict(t)
        if t.get("source") == "brand":
            info = brand_info.get(t["source_id"]) or {}
            t["brand"] = info.get("brand", "")
            t["store_name"] = info.get("store_name", "")
            t["category"] = info.get("category", "")
        enriched_tenants.append(t)
    enriched["tenants"] = enriched_tenants

    return JSONResponse(enriched)


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
    """List all RT IDs with their flags and property type."""
    html_flags = _load_json(DATA_DIR / "html_flags.json")
    parse_flags = _load_json(DATA_DIR / "parse_flags.json")
    seen = _load_json(DATA_DIR / "seen_rt_ids.json")

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
            "property_type": (seen.get(rt_id) or {}).get("type", ""),
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




def _make_contact_id(contact_name: str) -> str | None:
    """Return normalized contact_id for a contact person name, or None."""
    if not contact_name or not contact_name.strip():
        return None
    from cleo.utils.text import normalize_contact
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
    from cleo.utils.text import normalize_contact, is_company_name

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
                if attention_raw and not is_company_name(attention_raw):
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
    from cleo.utils.text import normalize_contact
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
    from cleo.utils.text import is_company_name
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
                elif attention_raw and normalize_contact(attention_raw) == cid and not is_company_name(attention_raw):
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

    party_groups: list[dict] = []

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

def _build_prop_deal_stage_lookup() -> dict[str, str]:
    """Stub — legacy CRM deals removed. Will be rebuilt with anchor layer."""
    return {}


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


# TODO: Dead endpoint — no frontend UI calls this. Remove after confirming no external consumers.
@app.get("/api/properties/{prop_id}/places", deprecated=True)
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


# TODO: Dead endpoint — tenant UI removed from PropertyDetailPage. Remove after confirming no external consumers.
@app.get("/api/properties/{prop_id}/tenants", deprecated=True)
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
    # Enrich parties with contact_id for linking
    for party_key in ("transferor", "transferee"):
        if party_key in data:
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
        # Strip volatile fields (recurse into nested dicts)
        act_clean = _parse_store._strip_volatile(act_data)
        sb_clean = _parse_store._strip_volatile(sb_data)
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
    """Stub — legacy CRM deals removed. Will be rebuilt with anchor layer."""
    return JSONResponse({
        "stages": {},
        "total_active": 0,
        "total_active_value": 0,
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

    # Deals — stub until CRM rebuilt with anchor layer
    props_with_deals: set[str] = set()

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

    return JSONResponse({
        "stale_properties": stale_top,
        "repeat_traders": [],
    })


# ---------------------------------------------------------------------------
# Universal search
# ---------------------------------------------------------------------------


@app.get("/api/search")
def api_search(q: str = "", limit: int = 5):
    """Search across transactions, properties, and contacts."""
    q = q.strip().lower()
    if len(q) < 2:
        return JSONResponse({"transactions": [], "properties": [], "contacts": []})

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
    "rebuild-all": ["properties"],
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
# POC: Parcel + POI demo endpoint
# ---------------------------------------------------------------------------

_POC_DIR = DATA_DIR / "poc_parcel"


@app.get("/api/poc/parcel-pois")
def api_poc_parcel_pois():
    """Return the POC parcel + POI GeoJSON for map rendering."""
    geojson_path = _POC_DIR / "parcel_pois.geojson"
    if not geojson_path.exists():
        raise HTTPException(404, "POC data not found. Run: python scripts/poc_parcel_poi.py")
    return json.loads(geojson_path.read_text(encoding="utf-8"))


@app.get("/api/poc/summary")
def api_poc_summary():
    """Return the POC combined summary."""
    summary_path = _POC_DIR / "summary.json"
    if not summary_path.exists():
        raise HTTPException(404, "POC data not found. Run: python scripts/poc_parcel_poi.py")
    return json.loads(summary_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Branded parcels endpoints (harvested city data)
# ---------------------------------------------------------------------------

_BRANDED_PARCELS_DIR = DATA_DIR / "branded_parcels"


@app.get("/api/branded-parcels/cities")
def api_branded_parcel_cities():
    """List harvested cities and their stats."""
    if not _BRANDED_PARCELS_DIR.exists():
        return []
    cities = []
    for path in sorted(_BRANDED_PARCELS_DIR.glob("*.json")):
        if path.suffix != ".json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cities.append({
                "city": data.get("city", path.stem),
                "harvested_at": data.get("harvested_at", ""),
                "stats": data.get("stats", {}),
            })
        except Exception:
            continue
    return cities


@app.get("/api/branded-parcels/{city}/geojson")
def api_branded_parcels_geojson(
    city: str,
    brand: str | None = None,
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
):
    """Return branded parcel GeoJSON for a city, optionally filtered by brand and/or bbox."""
    geo_path = _BRANDED_PARCELS_DIR / f"{city}.geojson"
    if not geo_path.exists():
        raise HTTPException(404, f"No harvest data for '{city}'")

    data = json.loads(geo_path.read_text(encoding="utf-8"))
    features = data.get("features", [])

    # Filter by brand if specified
    if brand:
        brand_lower = brand.lower()
        filtered = []
        # Keep parcel features that have the brand + only the matching brand's POI dots
        parcel_gis_ids = set()
        for f in features:
            props = f.get("properties", {})
            if props.get("type") == "parcel":
                brand_list = props.get("brand_list", [])
                if any(brand_lower in b.lower() for b in brand_list):
                    filtered.append(f)
                    parcel_gis_ids.add(props.get("gis_id"))
        # Second pass: only show POI dots for the matching brand
        for f in features:
            props = f.get("properties", {})
            if props.get("type") == "poi":
                poi_name = (props.get("name") or "").lower()
                on_matching_parcel = props.get("parcel_gis_id") in parcel_gis_ids
                name_matches = brand_lower in poi_name
                if on_matching_parcel and name_matches:
                    filtered.append(f)
        features = filtered

    # Filter by bounding box if specified
    if south is not None and west is not None and north is not None and east is not None:
        bbox_filtered = []
        for f in features:
            geom = f.get("geometry", {})
            if geom.get("type") == "Point":
                coords = geom.get("coordinates", [])
                if len(coords) >= 2 and west <= coords[0] <= east and south <= coords[1] <= north:
                    bbox_filtered.append(f)
            elif geom.get("type") == "Polygon":
                # Check if any vertex is in bbox
                rings = geom.get("coordinates", [])
                in_bbox = False
                for ring in rings:
                    for pt in ring:
                        if west <= pt[0] <= east and south <= pt[1] <= north:
                            in_bbox = True
                            break
                    if in_bbox:
                        break
                if in_bbox:
                    bbox_filtered.append(f)
        features = bbox_filtered

    return {"type": "FeatureCollection", "features": features}


@app.get("/api/branded-parcels/{city}/brands")
def api_branded_parcel_brands(city: str):
    """Return all unique brands found in a city's harvested data."""
    data_path = _BRANDED_PARCELS_DIR / f"{city}.json"
    if not data_path.exists():
        raise HTTPException(404, f"No harvest data for '{city}'")

    data = json.loads(data_path.read_text(encoding="utf-8"))
    brand_counts: dict[str, int] = {}
    for parcel in data.get("parcels", {}).values():
        for b in parcel.get("brands", []):
            name = b.get("name", "")
            if name:
                brand_counts[name] = brand_counts.get(name, 0) + 1

    return sorted(
        [{"brand": name, "parcel_count": count} for name, count in brand_counts.items()],
        key=lambda x: -x["parcel_count"],
    )


@app.get("/api/branded-parcels/all/geojson")
def api_branded_parcels_all_geojson(
    brand: str | None = None,
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
):
    """Return branded parcel GeoJSON from ALL harvested cities.

    Merges all city GeoJSON files. Required: brand filter (otherwise too much data).
    Optional bbox filter for viewport-based loading.
    """
    if not brand:
        raise HTTPException(400, "brand parameter required for all-cities query")

    if not _BRANDED_PARCELS_DIR.exists():
        return {"type": "FeatureCollection", "features": []}

    all_features = []
    brand_lower = brand.lower()

    for geo_path in sorted(_BRANDED_PARCELS_DIR.glob("*.geojson")):
        try:
            data = json.loads(geo_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        features = data.get("features", [])
        city_name = geo_path.stem

        # Brand filter (always applied for all-cities)
        parcel_gis_ids = set()
        for f in features:
            props = f.get("properties", {})
            if props.get("type") == "parcel":
                brand_list = props.get("brand_list", [])
                if any(brand_lower in b.lower() for b in brand_list):
                    props["city"] = city_name
                    all_features.append(f)
                    parcel_gis_ids.add(props.get("gis_id"))

        for f in features:
            props = f.get("properties", {})
            if props.get("type") == "poi":
                poi_name = (props.get("name") or "").lower()
                if props.get("parcel_gis_id") in parcel_gis_ids and brand_lower in poi_name:
                    props["city"] = city_name
                    all_features.append(f)

    # Bbox filter
    if south is not None and west is not None and north is not None and east is not None:
        bbox_filtered = []
        for f in all_features:
            geom = f.get("geometry", {})
            if geom.get("type") == "Point":
                coords = geom.get("coordinates", [])
                if len(coords) >= 2 and west <= coords[0] <= east and south <= coords[1] <= north:
                    bbox_filtered.append(f)
            elif geom.get("type") == "Polygon":
                rings = geom.get("coordinates", [])
                in_bbox = any(
                    west <= pt[0] <= east and south <= pt[1] <= north
                    for ring in rings for pt in ring
                )
                if in_bbox:
                    bbox_filtered.append(f)
        all_features = bbox_filtered

    return {"type": "FeatureCollection", "features": all_features}


@app.get("/api/branded-parcels/all/brands")
def api_branded_parcels_all_brands():
    """Return all unique brands across ALL harvested cities with counts."""
    if not _BRANDED_PARCELS_DIR.exists():
        return []

    brand_counts: dict[str, dict] = {}  # brand -> {parcels, cities}

    for data_path in sorted(_BRANDED_PARCELS_DIR.glob("*.json")):
        if data_path.stem == "summary":
            continue
        try:
            data = json.loads(data_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        city = data.get("city", data_path.stem)
        for parcel in data.get("parcels", {}).values():
            for b in parcel.get("brands", []):
                name = b.get("name", "")
                if name:
                    if name not in brand_counts:
                        brand_counts[name] = {"parcels": 0, "cities": set()}
                    brand_counts[name]["parcels"] += 1
                    brand_counts[name]["cities"].add(city)

    return sorted(
        [
            {"brand": name, "parcel_count": info["parcels"], "city_count": len(info["cities"])}
            for name, info in brand_counts.items()
        ],
        key=lambda x: -x["parcel_count"],
    )


# ---------------------------------------------------------------------------
# Parcel Registry API (new parcel-centric endpoints)
# ---------------------------------------------------------------------------

_parcel_registry_cache: dict | None = None
_parcel_registry_mtime: float = 0


def _get_parcel_registry() -> dict:
    """Load and cache parcel_registry.json, reloading when file changes."""
    global _parcel_registry_cache, _parcel_registry_mtime
    if not PARCEL_REGISTRY_PATH.exists():
        return {"parcels": {}, "indexes": {}, "meta": {}}
    mtime = PARCEL_REGISTRY_PATH.stat().st_mtime
    if _parcel_registry_cache is not None and _parcel_registry_mtime == mtime:
        return _parcel_registry_cache
    _parcel_registry_cache = json.loads(PARCEL_REGISTRY_PATH.read_text(encoding="utf-8"))
    _parcel_registry_mtime = mtime
    return _parcel_registry_cache


@app.get("/api/parcels/registry")
def api_parcel_registry_list(
    city: str | None = None,
    brand: str | None = None,
    has_transactions: bool | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    min_date: str | None = None,
    max_date: str | None = None,
    offset: int = 0,
    limit: int = 500,
):
    """List/search parcels from the registry with filters.

    Returns summary records (no geometry) for table display.
    Pagination via offset/limit.
    """
    reg = _get_parcel_registry()
    parcels = reg.get("parcels", {})

    results = []
    for arn, rec in parcels.items():
        if city and (rec.get("city") or "").upper() != city.upper():
            continue

        if brand:
            brand_names = [b.get("name", "").lower() for b in rec.get("brands", [])]
            if not any(brand.lower() in bn for bn in brand_names):
                continue

        if has_transactions is not None:
            if has_transactions and not rec.get("transactions"):
                continue
            if not has_transactions and rec.get("transactions"):
                continue

        if min_price or max_price:
            prices = [t.get("price") for t in rec.get("transactions", []) if t.get("price")]
            if not prices:
                if min_price:
                    continue
            else:
                latest_price = prices[0]
                if min_price and latest_price < min_price:
                    continue
                if max_price and latest_price > max_price:
                    continue

        if min_date or max_date:
            dates = [t.get("date", "") for t in rec.get("transactions", []) if t.get("date")]
            if not dates:
                continue
            latest_date = dates[0]
            if min_date and latest_date < min_date:
                continue
            if max_date and latest_date > max_date:
                continue

        txns = rec.get("transactions", [])
        latest_txn = txns[0] if txns else {}
        brand_names_sorted = sorted(set(b.get("name", "") for b in rec.get("brands", []) if b.get("name")))

        results.append({
            "arn": arn,
            "pid": rec.get("pid"),
            "pin": rec.get("pin"),
            "city": rec.get("city"),
            "address": rec["addresses"][0] if rec.get("addresses") else "",
            "addresses": rec.get("addresses", []),
            "population": rec.get("population"),
            "zoning": rec.get("zoning"),
            "area_sqm": rec.get("area_sqm"),
            "brand_count": len(brand_names_sorted),
            "brands": brand_names_sorted[:5],
            "transaction_count": len(txns),
            "latest_price": latest_txn.get("price"),
            "latest_date": latest_txn.get("date"),
            "latest_buyer": latest_txn.get("buyer"),
            "has_assessment": bool(rec.get("assessment")),
            "sources": rec.get("sources", []),
            "centroid": rec.get("centroid"),
        })

    total = len(results)
    results = results[offset:offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "results": results,
    }


@app.get("/api/parcels/registry/stats")
def api_parcel_registry_stats():
    """Return registry statistics for the dashboard."""
    reg = _get_parcel_registry()
    meta = reg.get("meta", {})
    parcels = reg.get("parcels", {})

    city_counts: dict[str, int] = {}
    for rec in parcels.values():
        c = rec.get("city") or "Unknown"
        city_counts[c] = city_counts.get(c, 0) + 1

    return {
        "meta": meta,
        "city_counts": dict(sorted(city_counts.items(), key=lambda x: -x[1])[:50]),
        "total_parcels": meta.get("total", 0),
    }


@app.get("/api/parcels/registry/filters")
def api_parcel_registry_filters():
    """Return available filter values for the UI."""
    reg = _get_parcel_registry()
    parcels = reg.get("parcels", {})

    cities: dict[str, int] = {}
    brands: dict[str, int] = {}
    for rec in parcels.values():
        c = rec.get("city")
        if c:
            cities[c] = cities.get(c, 0) + 1
        for b in rec.get("brands", []):
            name = b.get("name", "")
            if name:
                brands[name] = brands.get(name, 0) + 1

    return {
        "cities": sorted(
            [{"name": c, "count": n} for c, n in cities.items()],
            key=lambda x: -x["count"],
        ),
        "brands": sorted(
            [{"name": b, "count": n} for b, n in brands.items()],
            key=lambda x: -x["count"],
        )[:200],
    }


@app.get("/api/parcels/registry/geojson")
def api_parcel_registry_geojson(
    south: float | None = None,
    west: float | None = None,
    north: float | None = None,
    east: float | None = None,
    city: str | None = None,
    brand: str | None = None,
    has_transactions: bool | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
):
    """Return GeoJSON FeatureCollection for map display.

    Bbox required for viewport-based loading. Features include
    polygon geometry + summary properties for popup/styling.
    Cap at 3000 features per request.
    """
    reg = _get_parcel_registry()
    parcels = reg.get("parcels", {})

    features = []
    for arn, rec in parcels.items():
        centroid = rec.get("centroid")
        if not centroid:
            continue

        if south is not None and west is not None and north is not None and east is not None:
            lat, lng = centroid
            if not (south <= lat <= north and west <= lng <= east):
                continue

        if city and (rec.get("city") or "").upper() != city.upper():
            continue
        if brand:
            brand_names = [b.get("name", "").lower() for b in rec.get("brands", [])]
            if not any(brand.lower() in bn for bn in brand_names):
                continue
        if has_transactions is not None:
            if has_transactions and not rec.get("transactions"):
                continue
            if not has_transactions and rec.get("transactions"):
                continue
        if min_price or max_price:
            prices = [t.get("price") for t in rec.get("transactions", []) if t.get("price")]
            latest_price = prices[0] if prices else None
            if min_price and (latest_price is None or latest_price < min_price):
                continue
            if max_price and latest_price and latest_price > max_price:
                continue

        txns = rec.get("transactions", [])
        latest = txns[0] if txns else {}
        brand_list = sorted(set(b.get("name", "") for b in rec.get("brands", []) if b.get("name")))

        geometry = rec.get("geometry")
        if not geometry:
            geometry = {
                "type": "Point",
                "coordinates": [centroid[1], centroid[0]],
            }

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "arn": arn,
                "pid": rec.get("pid"),
                "city": rec.get("city"),
                "address": rec["addresses"][0] if rec.get("addresses") else "",
                "brand_count": len(brand_list),
                "brands": brand_list[:3],
                "transaction_count": len(txns),
                "latest_price": latest.get("price"),
                "latest_date": latest.get("date"),
                "has_transactions": bool(txns),
                "population": rec.get("population"),
                "zoning": rec.get("zoning"),
                "sources": rec.get("sources", []),
            },
        })

        if len(features) >= 3000:
            break

    return {"type": "FeatureCollection", "features": features}


@app.get("/api/parcels/registry/{arn}")
def api_parcel_registry_detail(arn: str):
    """Return full detail for a single parcel, including geometry."""
    reg = _get_parcel_registry()
    parcels = reg.get("parcels", {})

    if arn not in parcels:
        if len(arn) == 15:
            arn_20 = arn + "00000"
            if arn_20 in parcels:
                arn = arn_20
            else:
                raise HTTPException(404, f"Parcel not found: {arn}")
        else:
            raise HTTPException(404, f"Parcel not found: {arn}")

    return {**parcels[arn], "arn": arn}


@app.get("/api/parcels/registry/by-pid/{pid}")
def api_parcel_by_pid(pid: str):
    """Look up a parcel by its P-ID. Returns redirect ARN."""
    reg = _get_parcel_registry()
    pid_to_arn = reg.get("indexes", {}).get("pid_to_arn", {})
    arn = pid_to_arn.get(pid)
    if not arn:
        raise HTTPException(404, f"No parcel for P-ID: {pid}")
    return {"arn": arn, "pid": pid}


# ---------------------------------------------------------------------------
# Monitor API — pipeline health metrics
# ---------------------------------------------------------------------------

@app.get("/api/monitor")
def api_monitor():
    """Return full pipeline health metrics and quality gate results."""
    from cleo.monitor.collectors import collect_all
    from cleo.monitor.gates import evaluate_gates

    metrics = collect_all()
    gates = evaluate_gates(metrics)

    return {
        **metrics,
        "gates": gates,
    }


@app.get("/api/monitor/gates")
def api_monitor_gates():
    """Return only triggered quality gates."""
    from cleo.monitor.collectors import collect_all
    from cleo.monitor.gates import evaluate_gates

    metrics = collect_all()
    return evaluate_gates(metrics)


@app.post("/api/monitor/snapshot")
def api_monitor_snapshot():
    """Save a timestamped metrics snapshot and return it."""
    import json as _json
    from cleo.monitor.collectors import collect_all
    from cleo.monitor.gates import evaluate_gates
    from cleo.config import METRICS_DIR

    metrics = collect_all()
    gates = evaluate_gates(metrics)
    result = {**metrics, "gates": gates}

    ts = metrics["collected_at"].replace(":", "-")
    snap_path = METRICS_DIR / f"snapshot_{ts}.json"
    snap_path.write_text(_json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    return {"saved": str(snap_path), **result}


@app.get("/api/monitor/snapshots")
def api_monitor_snapshots():
    """List available metric snapshots."""
    from cleo.config import METRICS_DIR
    snapshots = []
    if METRICS_DIR.exists():
        for f in sorted(METRICS_DIR.glob("snapshot_*.json"), reverse=True):
            snapshots.append({
                "filename": f.name,
                "timestamp": f.name.replace("snapshot_", "").replace(".json", "").replace("-", ":", 2),
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    return snapshots


# ---------------------------------------------------------------------------
# Pipeline Trace — follow a single record through every stage
# ---------------------------------------------------------------------------

@app.get("/api/trace/{record_id}")
def api_trace(record_id: str):
    """Trace a single record (RT ID, GW ID, or Brand ID) through every pipeline stage."""
    from cleo.config import (
        HTML_INDEX_PATH, TRACKER_PATH, PARSED_DIR, NORMALIZED_DIR,
        EXPANDED_DIR, COORDINATES_PATH, PROPERTIES_PATH,
        PROPERTY_PARCEL_INDEX_PATH, PARCELS_PATH, COMPILED_DIR,
    )

    result: dict = {"id": record_id, "source": None, "stages": {}}

    # Detect source type
    rid = record_id.upper()
    if rid.startswith("RT"):
        result["source"] = "realtrack"
    elif rid.startswith("GW"):
        result["source"] = "geowarehouse"
    elif rid.startswith("BR"):
        result["source"] = "brand"
    else:
        raise HTTPException(400, f"Unrecognized ID format: {record_id}")

    # --- Stage: Ingest (RT only) ---
    if result["source"] == "realtrack":
        ingest: dict = {}
        try:
            idx = json.loads(HTML_INDEX_PATH.read_text(encoding="utf-8"))
            subpath = idx.get(record_id)
            if subpath:
                ingest["html_subpath"] = subpath
        except FileNotFoundError:
            pass
        try:
            tracker = json.loads(TRACKER_PATH.read_text(encoding="utf-8"))
            t = tracker.get(record_id)
            if t:
                ingest["first_seen"] = t.get("ts")
                ingest["property_type"] = t.get("type")
        except FileNotFoundError:
            pass
        if ingest:
            result["stages"]["ingest"] = ingest

    # --- Stage: Parsed (RT only) ---
    if result["source"] == "realtrack":
        parsed_active = PARSED_DIR / "active"
        pf = parsed_active / f"{record_id}.json"
        if pf.exists():
            result["stages"]["parsed"] = json.loads(pf.read_text(encoding="utf-8"))

    # --- Stage: Normalized ---
    norm_active = NORMALIZED_DIR / "active"
    nf = norm_active / f"{record_id}.json"
    if nf.exists():
        result["stages"]["normalized"] = json.loads(nf.read_text(encoding="utf-8"))

    # --- Stage: Expanded ---
    exp_active = EXPANDED_DIR / "active"
    ef = exp_active / f"{record_id}.json"
    if ef.exists():
        result["stages"]["expanded"] = json.loads(ef.read_text(encoding="utf-8"))

    # --- Stage: Geocoded (look up each canonical address) ---
    expanded = result["stages"].get("expanded", {})
    if expanded:
        try:
            coords_data = json.loads(COORDINATES_PATH.read_text(encoding="utf-8"))
            addresses_store = coords_data.get("addresses", {})
        except FileNotFoundError:
            addresses_store = {}

        geocoded: dict = {}
        for role in ("property", "seller", "buyer", "property_alt", "owner_address"):
            role_data = expanded.get(role, {})
            addrs = role_data.get("addresses", [])
            for addr in addrs:
                canon = addr.get("canonical", "")
                if canon and canon in addresses_store:
                    geocoded[canon] = addresses_store[canon]
        if geocoded:
            result["stages"]["geocoded"] = geocoded

    # --- Stage: Property ---
    try:
        props_data = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
        props = props_data.get("properties", {})
    except FileNotFoundError:
        props = {}

    matched_prop = None
    for pid, pdata in props.items():
        rt_ids = pdata.get("rt_ids", [])
        # For GW/brand, check source-specific fields
        sources = pdata.get("sources", [])
        if record_id in rt_ids:
            matched_prop = {"property_id": pid, **pdata}
            break
        if result["source"] == "geowarehouse" and "gw" in sources:
            gw_data = pdata.get("gw_data", {})
            if gw_data.get("gw_id") == record_id:
                matched_prop = {"property_id": pid, **pdata}
                break

    if matched_prop:
        result["stages"]["property"] = matched_prop

        # --- Stage: Parcels (via property ID) ---
        pid = matched_prop["property_id"]
        try:
            ppi = json.loads(PROPERTY_PARCEL_INDEX_PATH.read_text(encoding="utf-8"))
            parcel_match = ppi.get("matches", {}).get(pid)
            if parcel_match:
                result["stages"]["parcel"] = {"property_id": pid, **parcel_match}
        except FileNotFoundError:
            pass

    # --- Stage: Compiled ---
    compiled_active = COMPILED_DIR / "active"
    cf = compiled_active / f"{record_id}.json"
    if cf.exists():
        result["stages"]["compiled"] = json.loads(cf.read_text(encoding="utf-8"))

    # Check if record exists at all
    if not result["stages"]:
        raise HTTPException(404, f"No data found for {record_id}")

    return result


@app.get("/api/trace/search/{query}")
def api_trace_search(query: str):
    """Search for record IDs matching a query (partial RT ID, address, etc.)."""
    from cleo.config import PARSED_DIR, NORMALIZED_DIR

    query_upper = query.upper().strip()
    results: list[dict] = []
    limit = 20

    # Search by RT ID prefix
    parsed_active = PARSED_DIR / "active"
    if parsed_active.is_dir():
        for f in sorted(parsed_active.glob("RT*.json")):
            if f.stem.upper().startswith(query_upper) or query_upper in f.stem.upper():
                if len(results) < limit:
                    try:
                        rec = json.loads(f.read_text(encoding="utf-8"))
                        addr = rec.get("transaction", {}).get("address", {})
                        results.append({
                            "id": f.stem,
                            "source": "realtrack",
                            "label": f"{f.stem} — {addr.get('address', '')} {addr.get('city', '')}".strip(),
                        })
                    except Exception:
                        results.append({"id": f.stem, "source": "realtrack", "label": f.stem})

    # Search by GW ID
    norm_active = NORMALIZED_DIR / "active"
    if norm_active.is_dir():
        for f in sorted(norm_active.glob("GW*.json")):
            if f.stem.upper().startswith(query_upper) or query_upper in f.stem.upper():
                if len(results) < limit:
                    try:
                        rec = json.loads(f.read_text(encoding="utf-8"))
                        prop = rec.get("property", {})
                        city = prop.get("normalized_city", prop.get("raw_city", ""))
                        results.append({
                            "id": f.stem,
                            "source": "geowarehouse",
                            "label": f"{f.stem} — {prop.get('raw_address', '')} {city}".strip(),
                        })
                    except Exception:
                        results.append({"id": f.stem, "source": "geowarehouse", "label": f.stem})

        # Search by brand ID
        for f in sorted(norm_active.glob("BR_*.json")):
            if f.stem.upper().startswith(query_upper) or query_upper in f.stem.upper():
                if len(results) < limit:
                    try:
                        rec = json.loads(f.read_text(encoding="utf-8"))
                        prop = rec.get("property", {})
                        results.append({
                            "id": f.stem,
                            "source": "brand",
                            "label": f"{f.stem} — {prop.get('raw_address', '')} {prop.get('normalized_city', '')}".strip(),
                        })
                    except Exception:
                        results.append({"id": f.stem, "source": "brand", "label": f.stem})

    # Address search (if query doesn't look like an ID prefix)
    if not query_upper.startswith(("RT", "GW", "BR")) and len(query) >= 3:
        if parsed_active.is_dir():
            count = 0
            for f in parsed_active.glob("RT*.json"):
                if count >= limit - len(results):
                    break
                try:
                    rec = json.loads(f.read_text(encoding="utf-8"))
                    addr = rec.get("transaction", {}).get("address", {})
                    full_addr = f"{addr.get('address', '')} {addr.get('city', '')}".upper()
                    if query_upper in full_addr:
                        results.append({
                            "id": f.stem,
                            "source": "realtrack",
                            "label": f"{f.stem} — {addr.get('address', '')} {addr.get('city', '')}".strip(),
                        })
                        count += 1
                except Exception:
                    pass

    return results[:limit]


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
