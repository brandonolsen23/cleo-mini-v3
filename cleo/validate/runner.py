"""Run HTML validation checks across all HTML files."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from cleo.config import HTML_DIR, DATA_DIR
from cleo.validate.html_checks import FLAG_DEFS, check_html

logger = logging.getLogger(__name__)

HTML_FLAGS_PATH = DATA_DIR / "html_flags.json"
DETERMINATIONS_PATH = DATA_DIR / "determinations.json"


def run_all_checks() -> Tuple[Dict[str, List[str]], Dict[str, int]]:
    """Run HTML checks on every file in data/html/.

    Returns:
        (flags_by_rt, summary) where:
        - flags_by_rt: {"RT196880": ["H003"], "RT43746": [], ...}
        - summary: {"H001": 0, "H002": 0, "H003": 83, ...}
    """
    html_files = sorted(HTML_DIR.glob("*.html"))
    total = len(html_files)
    logger.info("Scanning %d HTML files...", total)

    flags_by_rt: Dict[str, List[str]] = {}
    summary: Dict[str, int] = {flag_id: 0 for flag_id in FLAG_DEFS}

    for i, path in enumerate(html_files):
        rt_id = path.stem  # "RT196880" from "RT196880.html"
        html_content = path.read_text(encoding="utf-8")
        flags = check_html(html_content)

        flags_by_rt[rt_id] = flags
        for flag_id in flags:
            summary[flag_id] = summary.get(flag_id, 0) + 1

        if (i + 1) % 2000 == 0:
            logger.info("Progress: %d / %d", i + 1, total)

    return flags_by_rt, summary


def save_flags(flags_by_rt: Dict[str, List[str]]) -> None:
    """Save HTML flags to data/html_flags.json."""
    # Only save records that have flags (keeps file small)
    flagged = {rt_id: flags for rt_id, flags in flags_by_rt.items() if flags}
    with open(HTML_FLAGS_PATH, "w", encoding="utf-8") as f:
        json.dump(flagged, f, indent=2, sort_keys=True)
    logger.info("Saved flags to %s (%d flagged records)", HTML_FLAGS_PATH, len(flagged))


def load_flags() -> Dict[str, List[str]]:
    """Load HTML flags from disk."""
    if not HTML_FLAGS_PATH.exists():
        return {}
    with open(HTML_FLAGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_determinations() -> Dict[str, dict]:
    """Load manual determinations from disk."""
    if not DETERMINATIONS_PATH.exists():
        return {}
    with open(DETERMINATIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_determinations(determinations: Dict[str, dict]) -> None:
    """Save manual determinations to disk."""
    with open(DETERMINATIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(determinations, f, indent=2, sort_keys=True)
