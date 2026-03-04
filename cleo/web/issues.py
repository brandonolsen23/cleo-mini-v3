"""Data issues API — flag, list, and resolve data quality issues from the UI."""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from cleo.config import DATA_ISSUES_PATH

router = APIRouter(prefix="/api/issues", tags=["issues"])


def _load() -> list[dict]:
    if DATA_ISSUES_PATH.exists():
        return json.loads(DATA_ISSUES_PATH.read_text())
    return []


def _save(issues: list[dict]) -> None:
    DATA_ISSUES_PATH.write_text(json.dumps(issues, indent=2))


def _next_id(issues: list[dict]) -> str:
    max_n = 0
    for iss in issues:
        try:
            max_n = max(max_n, int(iss["id"].split("_")[1]))
        except (IndexError, ValueError):
            pass
    return f"ISS_{max_n + 1:05d}"


@router.get("")
def api_list_issues(source_id: str = "", status: str = ""):
    """List all issues, optionally filtered by source_id or status."""
    issues = _load()
    if source_id:
        issues = [i for i in issues if i.get("source_id") == source_id]
    if status:
        issues = [i for i in issues if i.get("status") == status]
    return {"issues": issues, "total": len(issues)}


@router.post("")
async def api_create_issue(request: Request):
    """Create a new data issue.

    Body: {source_id, field, note, page?, context?}
    """
    body = await request.json()
    source_id = body.get("source_id", "").strip()
    field = body.get("field", "").strip()
    note = body.get("note", "").strip()

    if not source_id or not field:
        raise HTTPException(400, "source_id and field are required")

    issues = _load()
    issue = {
        "id": _next_id(issues),
        "source_id": source_id,
        "field": field,
        "note": note,
        "page": body.get("page", ""),
        "context": body.get("context", ""),
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    issues.append(issue)
    _save(issues)
    return issue


@router.patch("/{issue_id}")
async def api_update_issue(issue_id: str, request: Request):
    """Update an issue (e.g. resolve it).

    Body: {status?: "resolved"|"open", note?: "..."}
    """
    body = await request.json()
    issues = _load()
    for iss in issues:
        if iss["id"] == issue_id:
            if "status" in body:
                iss["status"] = body["status"]
            if "note" in body:
                iss["note"] = body["note"]
            iss["updated_at"] = datetime.now(timezone.utc).isoformat()
            _save(issues)
            return iss
    raise HTTPException(404, f"Issue {issue_id} not found")


@router.delete("/{issue_id}")
def api_delete_issue(issue_id: str):
    """Delete an issue."""
    issues = _load()
    filtered = [i for i in issues if i["id"] != issue_id]
    if len(filtered) == len(issues):
        raise HTTPException(404, f"Issue {issue_id} not found")
    _save(filtered)
    return {"ok": True}
