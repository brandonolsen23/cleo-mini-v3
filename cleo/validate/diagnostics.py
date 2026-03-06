"""Post-pipeline diagnostics: analyze unresolved records and compiled data quality.

Runs AFTER the pipeline produces output. Reads properties_unresolved.json and
compiled/active to produce a structured diagnostic report.

Two scopes:
  1. Unresolved records — WHY didn't they get a parcel?
  2. Compiled records — data quality issues in resolved records.

Reports are deterministic. Same data in → same report out. Every time.
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Unresolved diagnostics
# ---------------------------------------------------------------------------

def _classify_address(address: str) -> str:
    """Classify an unresolved address into a failure category.

    Categories:
        "has_number"       — starts with digit, should have geocoded
        "mall_or_centre"   — named shopping centre/mall/plaza
        "road_no_number"   — road/street name without a number
        "intersection"     — two roads joined by / or &
        "legal_description"— concession, lot, plan references
        "condo_plan"       — condo plan reference
        "empty"            — blank address
        "other"            — doesn't fit any pattern
    """
    if not address or not address.strip():
        return "empty"

    stripped = address.strip().upper()

    # Has a street number — geocode should have worked
    if re.match(r"^\d", stripped):
        return "has_number"

    # Strip ", CITY, PROVINCE" and ", POSTAL" from end for pattern matching.
    # primary_address includes city/province (e.g. "BOVAIRD DRIVE, BRAMPTON, ONTARIO")
    # We need to check the street portion only.
    street_part = stripped.split(",")[0].strip()

    # Legal description patterns (check before intersection — "PART CONCS 12 & 13" has &)
    if re.search(r"\bCONCS?\b|\bLOT\b|\bPLAN\s+\d", street_part):
        if re.search(r"\bCONDO\s+PLAN\b", street_part):
            return "condo_plan"
        return "legal_description"

    # Mall / shopping centre / plaza names
    mall_words = {"MALL", "CENTRE", "CENTER", "PLAZA", "SQUARE", "PLACE",
                  "DISTRICT", "CORNERS", "TOWERS", "POWER CENTRE"}
    for word in mall_words:
        if word in street_part:
            return "mall_or_centre"

    # Intersection — contains / or & between road names
    if " / " in street_part or re.search(r"\b&\b", street_part):
        return "intersection"

    # Road name without number — any word is a known street suffix
    road_suffixes = {
        "ST", "AVE", "RD", "DR", "BLVD", "CRES", "CT", "PL", "WAY",
        "CIR", "LANE", "LN", "PKWY", "HWY", "LINE", "CONC",
        "ROAD", "STREET", "AVENUE", "DRIVE", "BOULEVARD", "CRESCENT",
        "COURT", "PLACE", "CIRCLE", "PARKWAY", "HIGHWAY", "GROVE",
        "GATE", "GARDENS", "MEWS", "WALK", "CLOSE", "RISE", "RIDGE",
        "TRAIL", "TERRACE", "SQ",
    }
    words = street_part.split()
    for word in words:
        # Strip directional suffixes like S/S, N/S, E/S, W/S
        clean = re.sub(r"[/\\].*$", "", word)
        if clean in road_suffixes:
            return "road_no_number"

    return "other"


def diagnose_unresolved(unresolved_path: Path) -> Dict:
    """Analyze unresolved records and produce a structured diagnostic report.

    Returns:
    {
        "total": N,
        "by_source": {"realtrack": N, "brand": N, "osm": N, ...},
        "by_reason": {"no_parcel": N, "bad_arn": N},
        "by_source_reason": {"realtrack/no_parcel": N, ...},
        "by_address_category": {"has_number": N, "mall_or_centre": N, ...},
        "records": [
            {
                "id": "RT10416",
                "source": "realtrack",
                "reason": "no_parcel",
                "address_category": "intersection",
                "primary_address": "HARWOOD AVE / HWY 2, AJAX, ONTARIO",
                "city": "AJAX",
            },
            ...
        ]
    }
    """
    data = json.loads(unresolved_path.read_text(encoding="utf-8"))
    records = data.get("records", [])

    by_source: Counter = Counter()
    by_reason: Counter = Counter()
    by_source_reason: Counter = Counter()
    by_address_category: Counter = Counter()

    enriched = []
    for rec in records:
        source = rec.get("source", "unknown")
        reason = rec.get("reason", "unknown")
        address = rec.get("primary_address", "")
        category = _classify_address(address)

        by_source[source] += 1
        by_reason[reason] += 1
        by_source_reason[f"{source}/{reason}"] += 1
        by_address_category[category] += 1

        enriched.append({
            "id": rec["id"],
            "source": source,
            "reason": reason,
            "address_category": category,
            "primary_address": address,
            "city": rec.get("city", ""),
        })

    return {
        "total": len(records),
        "by_source": dict(by_source.most_common()),
        "by_reason": dict(by_reason.most_common()),
        "by_source_reason": dict(by_source_reason.most_common()),
        "by_address_category": dict(by_address_category.most_common()),
        "records": enriched,
    }


def format_unresolved_report(report: Dict) -> str:
    """Format the unresolved diagnostic report as a readable string."""
    lines = []
    total = report["total"]
    lines.append(f"Unresolved Records Report ({total:,} records)")
    lines.append("=" * 70)
    lines.append("")

    # By source
    lines.append("By source:")
    for source, count in report["by_source"].items():
        pct = count / total * 100 if total else 0
        lines.append(f"  {source:<12s}  {count:>5,}  ({pct:.1f}%)")
    lines.append("")

    # By reason
    lines.append("By reason:")
    for reason, count in report["by_reason"].items():
        pct = count / total * 100 if total else 0
        lines.append(f"  {reason:<12s}  {count:>5,}  ({pct:.1f}%)")
    lines.append("")

    # By address category
    lines.append("By address category:")
    for cat, count in report["by_address_category"].items():
        pct = count / total * 100 if total else 0
        lines.append(f"  {cat:<20s}  {count:>5,}  ({pct:.1f}%)")
    lines.append("")

    # Source + reason combos
    lines.append("By source + reason:")
    for combo, count in report["by_source_reason"].items():
        pct = count / total * 100 if total else 0
        lines.append(f"  {combo:<25s}  {count:>5,}  ({pct:.1f}%)")
    lines.append("")

    # List records grouped by address category
    by_cat: Dict[str, List] = {}
    for rec in report["records"]:
        cat = rec["address_category"]
        by_cat.setdefault(cat, []).append(rec)

    # Show categories in order: has_number first (most actionable), then others
    cat_order = ["has_number", "mall_or_centre", "road_no_number",
                 "intersection", "legal_description", "condo_plan",
                 "empty", "other"]
    for cat in cat_order:
        recs = by_cat.get(cat, [])
        if not recs:
            continue
        lines.append(f"--- {cat} ({len(recs)}) ---")
        for rec in sorted(recs, key=lambda r: r["id"]):
            lines.append(
                f"  {rec['id']:<12s}  [{rec['source'][:2].upper()}]  "
                f"{rec['primary_address']}"
            )
        lines.append("")

    return "\n".join(lines)
