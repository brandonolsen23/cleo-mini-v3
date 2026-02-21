"""Format diff results for CLI display."""

from typing import Dict


def format_diff_report(diff: Dict) -> str:
    """Format a diff_sandbox_vs_active() result as a human-readable report."""
    lines = []
    total = diff["unchanged"] + diff["changed"] + diff["new"] + diff["removed"]
    lines.append(f"Compared {total:,} records\n")

    lines.append(f"  Unchanged:  {diff['unchanged']:>7,}")
    lines.append(f"  Changed:    {diff['changed']:>7,}")
    lines.append(f"  New:        {diff['new']:>7,}")
    lines.append(f"  Removed:    {diff['removed']:>7,}")

    if diff["field_changes"]:
        lines.append(f"\nField changes (top 10):")
        for field, count in list(diff["field_changes"].items())[:10]:
            lines.append(f"  {field:<50s}  {count:>6,}")

    if diff["samples"]:
        lines.append(f"\nSample diffs:")
        for s in diff["samples"]:
            lines.append(f"\n  {s['rt_id']}  →  {s['field']}")
            lines.append(f"    before: {_truncate(s['before'])}")
            lines.append(f"    after:  {_truncate(s['after'])}")

    regressions = diff.get("regressions", [])
    if regressions:
        lines.append(f"\n{'=' * 60}")
        lines.append(f"  REGRESSION WARNING: {len(regressions)} reviewed-Clean record(s) changed!")
        lines.append(f"{'=' * 60}")
        for r in regressions[:10]:
            fields = ", ".join(r["changed_fields"][:5])
            if len(r["changed_fields"]) > 5:
                fields += f" (+{len(r['changed_fields']) - 5} more)"
            lines.append(f"  {r['rt_id']}  →  {fields}")
        if len(regressions) > 10:
            lines.append(f"  ... and {len(regressions) - 10} more")
        lines.append(f"\nPromotion will be BLOCKED until regressions are resolved.")

    return "\n".join(lines)


def _truncate(value, max_len: int = 80) -> str:
    """Truncate a value for display."""
    s = repr(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s
