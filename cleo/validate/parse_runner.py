"""Run parse-level validation checks across all parsed JSON files."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from cleo.config import DATA_DIR
from cleo.validate.parse_checks import PARSE_FLAG_DEFS, check_parsed

logger = logging.getLogger(__name__)

PARSE_FLAGS_PATH = DATA_DIR / "parse_flags.json"


def run_parse_checks(
    json_dir: Path,
) -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    """Run parse checks on every JSON file in a directory.

    Args:
        json_dir: Directory containing parsed RT JSON files.

    Returns:
        (flags_by_rt, summary) where:
        - flags_by_rt: {"RT196880": ["P007", "P009"], ...}
        - summary: {"P001": 0, "P002": 0, "P007": 15759, ...}
    """
    json_files = sorted(json_dir.glob("*.json"))
    json_files = [f for f in json_files if f.stem != "_meta"]
    total = len(json_files)
    logger.info("Checking %d parsed JSON files in %s", total, json_dir)

    flags_by_rt: Dict[str, List[str]] = {}
    summary: Dict[str, int] = {flag_id: 0 for flag_id in PARSE_FLAG_DEFS}

    for i, path in enumerate(json_files):
        rt_id = path.stem
        data = json.loads(path.read_text(encoding="utf-8"))
        flags = check_parsed(data)

        flags_by_rt[rt_id] = flags
        for flag_id in flags:
            summary[flag_id] = summary.get(flag_id, 0) + 1

        if (i + 1) % 2000 == 0:
            logger.info("Progress: %d / %d", i + 1, total)

    return flags_by_rt, summary


def save_parse_flags(flags_by_rt: Dict[str, List[str]]) -> None:
    """Save parse flags to data/parse_flags.json."""
    flagged = {rt_id: flags for rt_id, flags in flags_by_rt.items() if flags}
    with open(PARSE_FLAGS_PATH, "w", encoding="utf-8") as f:
        json.dump(flagged, f, indent=2, sort_keys=True)
    logger.info(
        "Saved parse flags to %s (%d flagged records)",
        PARSE_FLAGS_PATH,
        len(flagged),
    )


def load_parse_flags() -> Dict[str, List[str]]:
    """Load parse flags from disk."""
    if not PARSE_FLAGS_PATH.exists():
        return {}
    with open(PARSE_FLAGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cross_reference_html_flags(
    parse_flags: Dict[str, List[str]],
    html_flags: Dict[str, List[str]],
) -> Dict[str, Dict]:
    """Cross-reference parse flags with HTML flags.

    For each flagged record, notes whether the HTML source is also
    flagged. This is informational only — actual determinations
    (bad_source, parser_issue, etc.) are always manual.

    Returns:
        {rt_id: {"parse_flags": [...], "html_flags": [...], "html_also_flagged": bool}}
    """
    result = {}
    for rt_id, p_flags in parse_flags.items():
        if not p_flags:
            continue
        h_flags = html_flags.get(rt_id, [])
        result[rt_id] = {
            "parse_flags": p_flags,
            "html_flags": h_flags,
            "html_also_flagged": bool(h_flags),
        }
    return result
