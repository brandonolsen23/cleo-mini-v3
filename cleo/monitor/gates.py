"""Programmable quality gates — evaluate metrics against thresholds.

Each gate is a simple rule that checks a metric value and returns
pass/fail with a message. Gates can be CRITICAL (block promotion),
WARNING (flag for review), or INFO (informational).
"""

from __future__ import annotations

from typing import Any


QUALITY_GATES = [
    # Parse stage
    {
        "id": "QG001",
        "stage": "parsed",
        "name": "Missing address",
        "check": lambda m: m.get("field_coverage", {}).get("address", {}).get("pct", 100) < 99,
        "level": "critical",
        "message": lambda m: f"Address coverage {m['field_coverage']['address']['pct']}% (expect >99%)",
    },
    {
        "id": "QG002",
        "stage": "parsed",
        "name": "Missing sale price",
        "check": lambda m: m.get("field_coverage", {}).get("sale_price", {}).get("pct", 100) < 90,
        "level": "warning",
        "message": lambda m: f"Sale price coverage {m['field_coverage']['sale_price']['pct']}% (expect >90%)",
    },
    {
        "id": "QG003",
        "stage": "parsed",
        "name": "Low zoning coverage",
        "check": lambda m: m.get("field_coverage", {}).get("zoning", {}).get("pct", 0) < 20,
        "level": "info",
        "message": lambda m: f"Zoning coverage {m['field_coverage']['zoning']['pct']}% — consider parser improvement",
    },
    # Normalize stage
    {
        "id": "QG010",
        "stage": "normalized",
        "name": "Unknown cities",
        "check": lambda m: m.get("city_statuses", {}).get("unknown", 0) > 0,
        "level": "warning",
        "message": lambda m: f"{m['city_statuses'].get('unknown', 0)} records with unknown city",
    },
    {
        "id": "QG011",
        "stage": "normalized",
        "name": "No street number rate",
        "check": lambda m: (
            m.get("categories", {}).get("no_street_number", 0) / max(m.get("total_records", 1), 1) * 100 > 0.5
        ),
        "level": "warning",
        "message": lambda m: (
            f"{m['categories'].get('no_street_number', 0)} records ({m['categories'].get('no_street_number', 0)/max(m['total_records'],1)*100:.1f}%) "
            f"have no street number"
        ),
    },
    # Geocode stage
    {
        "id": "QG020",
        "stage": "geocoded",
        "name": "Geocode coverage",
        "check": lambda m: m.get("coverage_pct", 100) < 95,
        "level": "warning",
        "message": lambda m: f"Geocode coverage {m.get('coverage_pct', 0)}% ({m.get('missing_coords', 0)} missing)",
    },
    {
        "id": "QG021",
        "stage": "geocoded",
        "name": "Low confidence rate",
        "check": lambda m: (
            m.get("confidence", {}).get("exact", 0) /
            max(m.get("with_coords", 1), 1) * 100 < 70
        ),
        "level": "info",
        "message": lambda m: (
            f"Exact confidence {m['confidence'].get('exact', 0)/max(m['with_coords'],1)*100:.1f}% — "
            f"consider address quality improvements"
        ),
    },
    # Parcel stage
    {
        "id": "QG030",
        "stage": "parcels",
        "name": "Parcel harvest incomplete",
        "check": lambda m: m.get("provincial_total", 0) == 0,
        "level": "critical",
        "message": lambda m: "No parcels harvested — run cleo parcels --harvest",
    },
    # Properties stage
    {
        "id": "QG040",
        "stage": "properties",
        "name": "Properties without coords",
        "check": lambda m: m.get("total", 0) > 0 and m.get("with_coords_pct", 100) < 90,
        "level": "warning",
        "message": lambda m: (
            f"{m['total'] - m['with_coords']} properties ({100 - m['with_coords_pct']:.1f}%) "
            f"have no coordinates"
        ),
    },
    {
        "id": "QG041",
        "stage": "properties",
        "name": "No parcel linkage",
        "check": lambda m: m.get("total", 0) > 0 and m.get("with_parcel", 0) == 0,
        "level": "info",
        "message": lambda m: "0 properties have parcel linkage — parcel compiler not wired yet",
    },
]


def evaluate_gates(all_metrics: dict[str, Any]) -> list[dict]:
    """Evaluate all quality gates against collected metrics.

    Returns list of triggered gates with id, level, stage, name, message.
    """
    triggered = []

    for gate in QUALITY_GATES:
        stage = gate["stage"]
        metrics = all_metrics.get(stage, {})

        if not metrics or metrics.get("total_records", metrics.get("total", metrics.get("total_addresses", 0))) == 0:
            continue

        try:
            if gate["check"](metrics):
                triggered.append({
                    "id": gate["id"],
                    "level": gate["level"],
                    "stage": stage,
                    "name": gate["name"],
                    "message": gate["message"](metrics),
                })
        except Exception:
            pass

    # Sort: critical first, then warning, then info
    level_order = {"critical": 0, "warning": 1, "info": 2}
    triggered.sort(key=lambda g: level_order.get(g["level"], 9))

    return triggered
