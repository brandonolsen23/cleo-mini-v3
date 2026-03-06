"""Field rules runner: executes field validation rules against parsed records.

Usage:
    from cleo.validate.field_runner import run_field_rules
    report = run_field_rules(parsed_dir)
    print_report(report)
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from .field_rules import RULES, FieldRule, _get_field

logger = logging.getLogger(__name__)


def check_record(data: Dict, rules: Optional[List[FieldRule]] = None) -> Dict[str, Dict]:
    """Run all field rules against a single parsed record.

    Returns dict keyed by rule_id:
        {"R001": {"status": "pass"|"fail"|"skip", "value": "..."}, ...}
    """
    if rules is None:
        rules = RULES

    results = {}
    for rule in rules:
        value = _get_field(data, rule.field)

        # Handle list fields (e.g. site.pins) — check first element
        if isinstance(value, list):
            value = value[0] if value else ""

        # Convert non-string to string for checks
        if not isinstance(value, str):
            value = str(value) if value else ""

        is_empty = not value.strip() if isinstance(value, str) else not value

        if is_empty and rule.when_present:
            results[rule.rule_id] = {"status": "skip", "value": ""}
            continue

        try:
            passed = rule.check(value, data)
        except Exception:
            passed = False

        results[rule.rule_id] = {
            "status": "pass" if passed else "fail",
            "value": value[:100] if isinstance(value, str) else str(value)[:100],
        }

    return results


def run_field_rules(
    parsed_dir: Path,
    rules: Optional[List[FieldRule]] = None,
    limit: Optional[int] = None,
) -> Dict:
    """Run field rules against all parsed records in a directory.

    Returns summary report:
    {
        "total_records": N,
        "rules": {
            "R001": {
                "name": "...",
                "field": "...",
                "description": "...",
                "pass": N,
                "fail": N,
                "skip": N,
                "fail_samples": [{"rt_id": "...", "value": "..."}, ...],
            },
            ...
        }
    }
    """
    if rules is None:
        rules = RULES

    # Initialize counters
    rule_stats = {}
    for rule in rules:
        rule_stats[rule.rule_id] = {
            "name": rule.name,
            "field": rule.field,
            "description": rule.description,
            "severity": rule.severity,
            "pass": 0,
            "fail": 0,
            "skip": 0,
            "fail_samples": [],
        }

    total = 0
    files = sorted(parsed_dir.glob("*.json"))

    for f in files:
        if f.stem == "_meta":
            continue
        if limit is not None and total >= limit:
            break

        total += 1

        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        results = check_record(data, rules)

        for rule_id, result in results.items():
            stats = rule_stats[rule_id]
            status = result["status"]
            stats[status] += 1

            if status == "fail" and len(stats["fail_samples"]) < 5:
                stats["fail_samples"].append({
                    "rt_id": data.get("rt_id", f.stem),
                    "value": result["value"],
                })

        if total % 10000 == 0:
            logger.info("Progress: %d records", total)

    return {
        "total_records": total,
        "rules": rule_stats,
    }


def format_report(report: Dict) -> str:
    """Format a rules report as a readable string."""
    lines = []
    total = report["total_records"]
    lines.append(f"Field Rules Report ({total:,} records)")
    lines.append("=" * 80)
    lines.append("")

    # Sort: errors before warnings, then by fail count desc, then rule_id
    sorted_rules = sorted(
        report["rules"].items(),
        key=lambda x: (0 if x[1].get("severity") == "error" else 1, -x[1]["fail"], x[0]),
    )

    for rule_id, stats in sorted_rules:
        passed = stats["pass"]
        failed = stats["fail"]
        skipped = stats["skip"]
        checked = passed + failed
        severity = stats.get("severity", "warning")

        if checked == 0:
            pct = "n/a"
        else:
            pct = f"{passed / checked * 100:.1f}%"

        status_icon = "PASS" if failed == 0 else "FAIL"
        sev_tag = "ERR" if severity == "error" else "wrn"

        lines.append(
            f"  {rule_id}  {status_icon:4s}  [{sev_tag}]  {stats['name']:<35s}  "
            f"{passed:>6,} pass  {failed:>6,} fail  {skipped:>6,} skip  ({pct})"
        )

        if stats["fail_samples"]:
            for sample in stats["fail_samples"][:3]:
                val = sample["value"]
                if len(val) > 60:
                    val = val[:57] + "..."
                lines.append(f"                      {sample['rt_id']}: {val!r}")

    lines.append("")

    # Summary split by severity
    error_rules = {k: v for k, v in report["rules"].items() if v.get("severity") == "error"}
    warn_rules = {k: v for k, v in report["rules"].items() if v.get("severity") != "error"}

    err_fails = sum(s["fail"] for s in error_rules.values())
    err_failing = sum(1 for s in error_rules.values() if s["fail"] > 0)
    wrn_fails = sum(s["fail"] for s in warn_rules.values())
    wrn_failing = sum(1 for s in warn_rules.values() if s["fail"] > 0)

    lines.append(f"Errors:   {err_failing} rules failing, {err_fails:,} records with address-critical issues")
    lines.append(f"Warnings: {wrn_failing} rules failing, {wrn_fails:,} records with metadata issues")

    return "\n".join(lines)
