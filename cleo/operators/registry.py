"""Operator registry — CRUD, OP-ID assignment, atomic JSON writes."""

import json
import logging
from datetime import datetime
from pathlib import Path

from cleo.config import OPERATORS_REGISTRY_PATH, OPERATORS_EDITS_PATH

logger = logging.getLogger(__name__)


def load_registry() -> dict:
    """Load the operator registry."""
    if not OPERATORS_REGISTRY_PATH.exists():
        return {"operators": {}, "next_id": 1, "meta": {}}
    return json.loads(OPERATORS_REGISTRY_PATH.read_text(encoding="utf-8"))


def save_registry(data: dict) -> None:
    """Atomically write the operator registry."""
    OPERATORS_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OPERATORS_REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(OPERATORS_REGISTRY_PATH)


def _next_op_id(registry: dict) -> str:
    n = registry.get("next_id", 1)
    registry["next_id"] = n + 1
    return f"OP{n:05d}"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _log_edit(entry: dict) -> None:
    entry["timestamp"] = _now()
    OPERATORS_EDITS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OPERATORS_EDITS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def build_registry(match_results: dict, extracted_dir: Path) -> dict:
    """Build/update operator registry from extraction + matching results.

    Preserves existing OP-IDs and user decisions (confirmed/rejected matches).
    """
    registry = load_registry()
    operators = registry.get("operators", {})

    # Build slug -> op_id index
    slug_to_opid = {op["slug"]: opid for opid, op in operators.items()}

    results = match_results.get("results", {})
    updated = 0
    created = 0

    for slug, result in results.items():
        # Load extracted data for this operator
        ext_path = extracted_dir / f"{slug}.json"
        if not ext_path.exists():
            continue
        ext_data = json.loads(ext_path.read_text(encoding="utf-8"))

        if slug in slug_to_opid:
            op_id = slug_to_opid[slug]
            op = operators[op_id]
            # Update extracted data
            op["name"] = ext_data.get("name", op.get("name", ""))
            op["legal_names"] = ext_data.get("legal_names", [])
            op["description"] = ext_data.get("description", "")
            op["contacts"] = ext_data.get("contacts", [])
            op["extracted_properties"] = ext_data.get("properties", [])
            op["photos"] = ext_data.get("photos", [])

            # Merge new matches, preserving existing decisions
            _merge_property_matches(op, result.get("property_matches", []))
            _merge_party_matches(op, result.get("party_matches", []))
            op["updated"] = _now()
            updated += 1
        else:
            op_id = _next_op_id(registry)
            operators[op_id] = {
                "slug": slug,
                "name": ext_data.get("name", ""),
                "url": ext_data.get("url", ""),
                "legal_names": ext_data.get("legal_names", []),
                "description": ext_data.get("description", ""),
                "contacts": ext_data.get("contacts", []),
                "extracted_properties": ext_data.get("properties", []),
                "photos": ext_data.get("photos", []),
                "property_matches": result.get("property_matches", []),
                "party_matches": result.get("party_matches", []),
                "created": _now(),
                "updated": _now(),
            }
            slug_to_opid[slug] = op_id
            created += 1

    # Also populate URL from config
    from cleo.operators.engine import load_config
    config = load_config()
    config_by_slug = {c["slug"]: c for c in config}
    for opid, op in operators.items():
        if not op.get("url") and op["slug"] in config_by_slug:
            op["url"] = config_by_slug[op["slug"]]["url"]

    registry["operators"] = operators
    registry["meta"] = {
        "built": _now(),
        "total_operators": len(operators),
        "updated": updated,
        "created": created,
    }

    return registry


def _merge_property_matches(op: dict, new_matches: list[dict]) -> None:
    """Merge new property matches, preserving confirmed/rejected decisions."""
    existing = op.get("property_matches", [])
    # Index existing by extracted_address
    existing_by_addr = {
        m.get("extracted_address", "").upper(): m
        for m in existing
    }

    merged = list(existing)  # start with existing
    for nm in new_matches:
        addr_key = nm.get("extracted_address", "").upper()
        if addr_key in existing_by_addr:
            # Preserve user decision
            em = existing_by_addr[addr_key]
            if em.get("status") in ("confirmed", "rejected"):
                continue
            # Update match data but keep status
            em.update({k: v for k, v in nm.items() if k != "status"})
        else:
            merged.append(nm)

    op["property_matches"] = merged


def _merge_party_matches(op: dict, new_matches: list[dict]) -> None:
    """Merge new party matches, preserving confirmed/rejected decisions."""
    existing = op.get("party_matches", [])
    existing_by_gid = {
        m.get("group_id", ""): m for m in existing
    }

    merged = list(existing)
    for nm in new_matches:
        gid = nm.get("group_id", "")
        if gid in existing_by_gid:
            em = existing_by_gid[gid]
            if em.get("status") in ("confirmed", "rejected"):
                continue
            em.update({k: v for k, v in nm.items() if k != "status"})
        else:
            merged.append(nm)

    op["party_matches"] = merged


def confirm_property_match(op_id: str, match_idx: int) -> dict:
    """Confirm a property match and apply to registries."""
    registry = load_registry()
    operators = registry.get("operators", {})

    if op_id not in operators:
        raise ValueError(f"Operator {op_id} not found")

    op = operators[op_id]
    matches = op.get("property_matches", [])

    if match_idx < 0 or match_idx >= len(matches):
        raise ValueError(f"Match index {match_idx} out of range")

    match = matches[match_idx]
    if match.get("status") == "confirmed":
        return match

    match["status"] = "confirmed"
    match["confirmed_at"] = _now()
    op["updated"] = _now()

    # Apply to property registry
    prop_id = match.get("prop_id")
    if prop_id:
        _apply_property_confirmation(prop_id, op_id, op.get("slug", ""))

    save_registry(registry)
    _log_edit({
        "action": "confirm_property_match",
        "op_id": op_id,
        "match_idx": match_idx,
        "prop_id": prop_id,
    })

    return match


def reject_property_match(op_id: str, match_idx: int) -> dict:
    """Reject a property match."""
    registry = load_registry()
    operators = registry.get("operators", {})

    if op_id not in operators:
        raise ValueError(f"Operator {op_id} not found")

    op = operators[op_id]
    matches = op.get("property_matches", [])

    if match_idx < 0 or match_idx >= len(matches):
        raise ValueError(f"Match index {match_idx} out of range")

    match = matches[match_idx]
    match["status"] = "rejected"
    match["rejected_at"] = _now()
    op["updated"] = _now()

    save_registry(registry)
    _log_edit({
        "action": "reject_property_match",
        "op_id": op_id,
        "match_idx": match_idx,
    })

    return match


def confirm_party_match(op_id: str, match_idx: int) -> dict:
    """Confirm a party match and apply to party registry."""
    registry = load_registry()
    operators = registry.get("operators", {})

    if op_id not in operators:
        raise ValueError(f"Operator {op_id} not found")

    op = operators[op_id]
    matches = op.get("party_matches", [])

    if match_idx < 0 or match_idx >= len(matches):
        raise ValueError(f"Match index {match_idx} out of range")

    match = matches[match_idx]
    if match.get("status") == "confirmed":
        return match

    match["status"] = "confirmed"
    match["confirmed_at"] = _now()
    op["updated"] = _now()

    # Apply to party registry
    group_id = match.get("group_id")
    if group_id:
        _apply_party_confirmation(group_id, op_id, op)

    save_registry(registry)
    _log_edit({
        "action": "confirm_party_match",
        "op_id": op_id,
        "match_idx": match_idx,
        "group_id": group_id,
    })

    return match


def reject_party_match(op_id: str, match_idx: int) -> dict:
    """Reject a party match."""
    registry = load_registry()
    operators = registry.get("operators", {})

    if op_id not in operators:
        raise ValueError(f"Operator {op_id} not found")

    op = operators[op_id]
    matches = op.get("party_matches", [])

    if match_idx < 0 or match_idx >= len(matches):
        raise ValueError(f"Match index {match_idx} out of range")

    match = matches[match_idx]
    match["status"] = "rejected"
    match["rejected_at"] = _now()
    op["updated"] = _now()

    save_registry(registry)
    _log_edit({
        "action": "reject_party_match",
        "op_id": op_id,
        "match_idx": match_idx,
    })

    return match


def _apply_property_confirmation(prop_id: str, op_id: str, slug: str) -> None:
    """Add operator source to a property in the property registry."""
    from cleo.config import PROPERTIES_PATH
    from cleo.properties.registry import load_registry as load_prop_reg, save_registry as save_prop_reg

    reg = load_prop_reg(PROPERTIES_PATH)
    props = reg.get("properties", {})
    if prop_id not in props:
        return

    prop = props[prop_id]
    sources = prop.setdefault("sources", [])
    if "operator" not in sources:
        sources.append("operator")
    op_ids = prop.setdefault("operator_ids", [])
    if op_id not in op_ids:
        op_ids.append(op_id)

    save_prop_reg(reg, PROPERTIES_PATH)


def _apply_party_confirmation(group_id: str, op_id: str, operator: dict) -> None:
    """Add operator URL and contacts to a party group."""
    from cleo.config import PARTIES_PATH
    from cleo.parties.registry import load_registry as load_party_reg, save_registry as save_party_reg

    reg = load_party_reg(PARTIES_PATH)
    parties = reg.get("parties", {})
    if group_id not in parties:
        return

    group = parties[group_id]
    overrides = reg.setdefault("overrides", {})
    group_overrides = overrides.setdefault(group_id, {})

    # Set URL
    url = operator.get("url", "")
    if url:
        group_overrides["url"] = url

    # Add operator reference
    op_ids = group.setdefault("operator_ids", [])
    if op_id not in op_ids:
        op_ids.append(op_id)

    save_party_reg(reg, PARTIES_PATH)
