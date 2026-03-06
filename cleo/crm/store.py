"""CRM Store: persistent JSON-backed stores for Deals, Lists, and Connections.

Each store uses append-only IDs (DEAL_NNNNN, LST_NNNNN, CXN_NNNNN).
All mutations are logged to crm/edits.jsonl for audit trail.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deal stages (from definitions.md)
# ---------------------------------------------------------------------------

DEAL_STAGES = [
    "long_shot",
    "priority_deal",
    "mandate",
    "viable_deal",
    "in_negotiation",
    "under_contract",
    "firm",
    "closed",
    "lost",
]

DEAL_STAGE_LABELS = {
    "long_shot": "Long Shot",
    "priority_deal": "Priority Deal",
    "mandate": "Mandate",
    "viable_deal": "Viable Deal",
    "in_negotiation": "In Negotiation",
    "under_contract": "Under Contract",
    "firm": "Firm",
    "closed": "Closed",
    "lost": "Lost",
}

DEAL_STAGE_PHASES = {
    "long_shot": "Prospecting",
    "priority_deal": "Nurturing",
    "mandate": "Nurturing",
    "viable_deal": "Negotiating",
    "in_negotiation": "Negotiating",
    "under_contract": "Under Contract",
    "firm": "Firm",
    "closed": "Closed",
    "lost": "Lost",
}

CONNECTION_TYPES = ["phone_call", "email", "meeting", "text", "note", "other"]
CONNECTION_DIRECTIONS = ["outbound", "inbound"]
CONNECTION_OUTCOMES = [
    "spoke_with",
    "left_message",
    "no_answer",
    "email_sent",
    "email_received",
    "meeting_held",
    "other",
]


# ---------------------------------------------------------------------------
# Generic JSON store helpers
# ---------------------------------------------------------------------------

def _load_store(path: Path) -> Dict:
    """Load a JSON store from disk. Returns empty structure if not found."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"meta": {"next_id": 1}, "records": {}}


def _save_store(data: Dict, path: Path) -> None:
    """Write a JSON store to disk. Creates parent directory if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _append_log(log_path: Path, entry: Dict) -> None:
    """Append an audit log entry."""
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------

class DealStore:
    """Persistent store for CRM Deals."""

    def __init__(self, deals_path: Path, log_path: Path):
        self._path = deals_path
        self._log_path = log_path

    def _load(self) -> Dict:
        return _load_store(self._path)

    def _save(self, data: Dict) -> None:
        _save_store(data, self._path)

    def list_all(self) -> List[Dict]:
        """Return all deals, sorted by updated_at desc."""
        data = self._load()
        deals = list(data["records"].values())
        deals.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
        return deals

    def get(self, deal_id: str) -> Optional[Dict]:
        data = self._load()
        return data["records"].get(deal_id)

    def create(self, fields: Dict) -> Dict:
        """Create a new deal. Returns the created record."""
        data = self._load()
        next_id = data["meta"]["next_id"]
        deal_id = f"DEAL_{next_id:05d}"
        data["meta"]["next_id"] = next_id + 1

        now = _now()
        deal = {
            "deal_id": deal_id,
            "name": fields.get("name", ""),
            "stage": fields.get("stage", "long_shot"),
            "arn": fields.get("arn", ""),
            "property_id": fields.get("property_id", ""),
            "group_id": fields.get("group_id", ""),
            "contact_ids": fields.get("contact_ids", []),
            "amount": fields.get("amount"),
            "close_date": fields.get("close_date"),
            "deal_owner": fields.get("deal_owner", "brandon"),
            "description": fields.get("description", ""),
            "next_step": fields.get("next_step", ""),
            "priority": fields.get("priority", "medium"),
            "lost_reason": fields.get("lost_reason", ""),
            "created_at": now,
            "updated_at": now,
        }
        data["records"][deal_id] = deal
        self._save(data)

        _append_log(self._log_path, {
            "action": "deal_create",
            "deal_id": deal_id,
            "fields": {k: v for k, v in deal.items() if k not in ("created_at", "updated_at")},
        })
        return deal

    def update(self, deal_id: str, fields: Dict) -> Dict:
        """Update an existing deal. Returns the updated record."""
        data = self._load()
        if deal_id not in data["records"]:
            raise ValueError(f"Deal not found: {deal_id}")

        deal = data["records"][deal_id]
        changes = {}
        allowed = {
            "name", "stage", "arn", "property_id", "group_id",
            "contact_ids", "amount", "close_date", "deal_owner",
            "description", "next_step", "priority", "lost_reason",
        }
        for k, v in fields.items():
            if k in allowed and deal.get(k) != v:
                changes[k] = {"old": deal.get(k), "new": v}
                deal[k] = v

        if changes:
            deal["updated_at"] = _now()
            self._save(data)
            _append_log(self._log_path, {
                "action": "deal_update",
                "deal_id": deal_id,
                "changes": changes,
            })
        return deal

    def delete(self, deal_id: str) -> None:
        """Delete a deal."""
        data = self._load()
        if deal_id not in data["records"]:
            raise ValueError(f"Deal not found: {deal_id}")
        del data["records"][deal_id]
        self._save(data)
        _append_log(self._log_path, {
            "action": "deal_delete",
            "deal_id": deal_id,
        })

    def by_stage(self) -> Dict[str, List[Dict]]:
        """Group deals by stage for pipeline view."""
        deals = self.list_all()
        result: Dict[str, List[Dict]] = {s: [] for s in DEAL_STAGES}
        for d in deals:
            stage = d.get("stage", "long_shot")
            if stage in result:
                result[stage].append(d)
        return result

    def stats(self) -> Dict:
        """Pipeline stats."""
        deals = self.list_all()
        by_stage = {}
        total_value = 0
        for d in deals:
            s = d.get("stage", "long_shot")
            by_stage[s] = by_stage.get(s, 0) + 1
            if d.get("amount") and s not in ("lost", "closed"):
                total_value += d["amount"]
        active = sum(1 for d in deals if d.get("stage") not in ("closed", "lost"))
        return {
            "total": len(deals),
            "active": active,
            "by_stage": by_stage,
            "pipeline_value": total_value,
        }


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

class ListStore:
    """Persistent store for prospecting Lists."""

    def __init__(self, lists_path: Path, log_path: Path):
        self._path = lists_path
        self._log_path = log_path

    def _load(self) -> Dict:
        return _load_store(self._path)

    def _save(self, data: Dict) -> None:
        _save_store(data, self._path)

    def list_all(self) -> List[Dict]:
        data = self._load()
        lists = list(data["records"].values())
        lists.sort(key=lambda l: l.get("updated_at", ""), reverse=True)
        return lists

    def get(self, list_id: str) -> Optional[Dict]:
        data = self._load()
        return data["records"].get(list_id)

    def create(self, fields: Dict) -> Dict:
        data = self._load()
        next_id = data["meta"]["next_id"]
        list_id = f"LST_{next_id:05d}"
        data["meta"]["next_id"] = next_id + 1

        now = _now()
        rec = {
            "list_id": list_id,
            "name": fields.get("name", ""),
            "description": fields.get("description", ""),
            "items": fields.get("items", []),
            "created_at": now,
            "updated_at": now,
        }
        data["records"][list_id] = rec
        self._save(data)
        _append_log(self._log_path, {
            "action": "list_create",
            "list_id": list_id,
            "name": rec["name"],
        })
        return rec

    def update(self, list_id: str, fields: Dict) -> Dict:
        data = self._load()
        if list_id not in data["records"]:
            raise ValueError(f"List not found: {list_id}")

        rec = data["records"][list_id]
        changes = {}
        for k in ("name", "description"):
            if k in fields and rec.get(k) != fields[k]:
                changes[k] = {"old": rec.get(k), "new": fields[k]}
                rec[k] = fields[k]
        if changes:
            rec["updated_at"] = _now()
            self._save(data)
            _append_log(self._log_path, {
                "action": "list_update",
                "list_id": list_id,
                "changes": changes,
            })
        return rec

    def add_item(self, list_id: str, item: Dict) -> Dict:
        """Add an item to a list. Item: {type, property_id/group_id/contact_id, arn?}"""
        data = self._load()
        if list_id not in data["records"]:
            raise ValueError(f"List not found: {list_id}")

        rec = data["records"][list_id]
        rec["items"].append(item)
        rec["updated_at"] = _now()
        self._save(data)
        _append_log(self._log_path, {
            "action": "list_add_item",
            "list_id": list_id,
            "item": item,
        })
        return rec

    def remove_item(self, list_id: str, index: int) -> Dict:
        """Remove an item by index from a list."""
        data = self._load()
        if list_id not in data["records"]:
            raise ValueError(f"List not found: {list_id}")

        rec = data["records"][list_id]
        if index < 0 or index >= len(rec["items"]):
            raise ValueError(f"Item index out of range: {index}")

        removed = rec["items"].pop(index)
        rec["updated_at"] = _now()
        self._save(data)
        _append_log(self._log_path, {
            "action": "list_remove_item",
            "list_id": list_id,
            "index": index,
            "item": removed,
        })
        return rec

    def delete(self, list_id: str) -> None:
        data = self._load()
        if list_id not in data["records"]:
            raise ValueError(f"List not found: {list_id}")
        del data["records"][list_id]
        self._save(data)
        _append_log(self._log_path, {
            "action": "list_delete",
            "list_id": list_id,
        })


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

class ConnectionStore:
    """Persistent store for logged interactions (Connections)."""

    def __init__(self, connections_path: Path, log_path: Path):
        self._path = connections_path
        self._log_path = log_path

    def _load(self) -> Dict:
        return _load_store(self._path)

    def _save(self, data: Dict) -> None:
        _save_store(data, self._path)

    def list_all(self, contact_id: str = "", group_id: str = "", deal_id: str = "") -> List[Dict]:
        """List connections, optionally filtered."""
        data = self._load()
        cxns = list(data["records"].values())
        if contact_id:
            cxns = [c for c in cxns if c.get("contact_id") == contact_id]
        if group_id:
            cxns = [c for c in cxns if c.get("group_id") == group_id]
        if deal_id:
            cxns = [c for c in cxns if c.get("deal_id") == deal_id]
        cxns.sort(key=lambda c: c.get("logged_at", ""), reverse=True)
        return cxns

    def get(self, cxn_id: str) -> Optional[Dict]:
        data = self._load()
        return data["records"].get(cxn_id)

    def create(self, fields: Dict) -> Dict:
        data = self._load()
        next_id = data["meta"]["next_id"]
        cxn_id = f"CXN_{next_id:05d}"
        data["meta"]["next_id"] = next_id + 1

        rec = {
            "connection_id": cxn_id,
            "contact_id": fields.get("contact_id", ""),
            "contact_name": fields.get("contact_name", ""),
            "group_id": fields.get("group_id", ""),
            "group_name": fields.get("group_name", ""),
            "deal_id": fields.get("deal_id", ""),
            "type": fields.get("type", "phone_call"),
            "direction": fields.get("direction", "outbound"),
            "outcome": fields.get("outcome", ""),
            "notes": fields.get("notes", ""),
            "logged_by": fields.get("logged_by", "brandon"),
            "logged_at": fields.get("logged_at") or _now(),
        }
        data["records"][cxn_id] = rec
        self._save(data)
        _append_log(self._log_path, {
            "action": "connection_create",
            "connection_id": cxn_id,
            "fields": rec,
        })
        return rec

    def delete(self, cxn_id: str) -> None:
        data = self._load()
        if cxn_id not in data["records"]:
            raise ValueError(f"Connection not found: {cxn_id}")
        del data["records"][cxn_id]
        self._save(data)
        _append_log(self._log_path, {
            "action": "connection_delete",
            "connection_id": cxn_id,
        })
