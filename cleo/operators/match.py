"""Operator-to-registry matching engine.

Property matching reuses brands/match.py infrastructure.
Party matching uses cleo/parties/normalize.py name normalization.
"""

import json
import logging
from pathlib import Path

from cleo.config import PROPERTIES_PATH, PARTIES_PATH

logger = logging.getLogger(__name__)


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


def match_properties(extracted_properties: list[dict], properties: dict) -> list[dict]:
    """Match extracted property addresses against the property registry.

    Returns list of match dicts with confidence scores.
    """
    from brands.match import (
        build_property_index,
        extract_street_number,
        normalize_city,
        street_similarity,
    )

    prop_index = build_property_index(properties)
    matches = []

    for ep in extracted_properties:
        addr = ep.get("address", "")
        city = ep.get("city", "")
        if not addr:
            continue

        num = extract_street_number(addr)
        if not num:
            matches.append({
                "extracted_address": addr,
                "extracted_city": city,
                "prop_id": None,
                "confidence": 0.0,
                "status": "no_match",
                "reason": "no_street_number",
            })
            continue

        norm_city = normalize_city(city) if city else ""
        key = (num, norm_city)
        candidates = prop_index.get(key, [])

        if not candidates:
            matches.append({
                "extracted_address": addr,
                "extracted_city": city,
                "prop_id": None,
                "confidence": 0.0,
                "status": "no_match",
                "reason": "no_candidates",
            })
            continue

        # Score candidates
        scored = []
        for pid, prop_addr in candidates:
            score = street_similarity(addr, prop_addr)
            scored.append((pid, prop_addr, score))
        scored.sort(key=lambda x: -x[2])
        best_pid, best_addr, best_score = scored[0]

        if best_score >= 0.6:
            confidence = round(best_score, 3)
            matches.append({
                "extracted_address": addr,
                "extracted_city": city,
                "prop_id": best_pid,
                "prop_address": best_addr,
                "prop_city": properties[best_pid].get("city", ""),
                "confidence": confidence,
                "status": "pending",
            })
        else:
            matches.append({
                "extracted_address": addr,
                "extracted_city": city,
                "prop_id": None,
                "confidence": round(best_score, 3),
                "status": "no_match",
                "reason": f"low_similarity (best={best_score:.2f})",
            })

    return matches


def match_parties(
    operator_name: str,
    legal_names: list[str],
    contacts: list[dict],
    parties: dict,
) -> list[dict]:
    """Match operator company names and contacts against the party registry.

    Returns list of match dicts.
    """
    from cleo.parties.normalize import normalize_name

    matches = []
    seen_gids: set[str] = set()

    # All names to check
    names_to_check = [operator_name] + (legal_names or [])
    names_to_check = [n for n in names_to_check if n]

    for name in names_to_check:
        norm = normalize_name(name)
        if not norm:
            continue

        for gid, group in parties.items():
            if gid in seen_gids:
                continue

            # Check normalized names
            group_names = group.get("normalized_names", [])
            if norm in group_names:
                seen_gids.add(gid)
                display = group.get("display_name_override") or group.get("display_name", "")
                matches.append({
                    "group_id": gid,
                    "party_display_name": display,
                    "match_type": "name_match",
                    "matched_name": name,
                    "confidence": 1.0,
                    "status": "pending",
                })
                continue

            # Check aliases
            aliases = group.get("aliases", [])
            for alias in aliases:
                if normalize_name(alias) == norm:
                    seen_gids.add(gid)
                    display = group.get("display_name_override") or group.get("display_name", "")
                    matches.append({
                        "group_id": gid,
                        "party_display_name": display,
                        "match_type": "alias_match",
                        "matched_name": name,
                        "confidence": 0.9,
                        "status": "pending",
                    })
                    break

            # Check display name (partial match)
            display = group.get("display_name_override") or group.get("display_name", "")
            if display and normalize_name(display) == norm:
                if gid not in seen_gids:
                    seen_gids.add(gid)
                    matches.append({
                        "group_id": gid,
                        "party_display_name": display,
                        "match_type": "display_name_match",
                        "matched_name": name,
                        "confidence": 0.95,
                        "status": "pending",
                    })

    # Contact name matching
    contact_names = [c.get("name", "").strip() for c in contacts if c.get("name")]
    for cname in contact_names:
        norm_contact = normalize_name(cname)
        if not norm_contact:
            continue

        for gid, group in parties.items():
            if gid in seen_gids:
                continue
            # Check group contacts
            for gc in group.get("contacts", []):
                gc_name = gc if isinstance(gc, str) else gc.get("name", "")
                if normalize_name(gc_name) == norm_contact:
                    seen_gids.add(gid)
                    display = group.get("display_name_override") or group.get("display_name", "")
                    matches.append({
                        "group_id": gid,
                        "party_display_name": display,
                        "match_type": "contact_match",
                        "matched_contact": cname,
                        "confidence": 0.7,
                        "status": "pending",
                    })
                    break

    return matches


def run_matching(
    extracted_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Run property and party matching for all extracted operators.

    Returns summary dict.
    """
    properties = _load_properties()
    parties = _load_parties()

    if not properties:
        logger.warning("No property registry found")
    if not parties:
        logger.warning("No party registry found")

    json_files = sorted(extracted_dir.glob("*.json"))
    json_files = [f for f in json_files if f.stem != "_meta"]

    results = {}
    total_prop_matches = 0
    total_prop_pending = 0
    total_party_matches = 0

    for json_path in json_files:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        slug = data.get("slug", json_path.stem)

        # Property matching
        prop_matches = match_properties(
            data.get("properties", []),
            properties,
        )
        pending_props = [m for m in prop_matches if m["status"] == "pending"]
        total_prop_matches += len(pending_props)
        total_prop_pending += len(pending_props)

        # Party matching
        party_matches = match_parties(
            data.get("name", ""),
            data.get("legal_names", []),
            data.get("contacts", []),
            parties,
        )
        total_party_matches += len(party_matches)

        results[slug] = {
            "name": data.get("name", ""),
            "property_matches": prop_matches,
            "party_matches": party_matches,
            "extracted_properties": len(data.get("properties", [])),
            "extracted_contacts": len(data.get("contacts", [])),
        }

    return {
        "total_operators": len(json_files),
        "total_property_matches": total_prop_matches,
        "total_party_matches": total_party_matches,
        "results": results,
    }
