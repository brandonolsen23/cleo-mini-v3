"""Core parse loop: HTML files → JSON files."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

from cleo.config import HTML_DIR
from cleo.ingest.html_index import HtmlIndex
from cleo.parse.parsers.build_transaction_context import build_transaction_context

logger = logging.getLogger(__name__)


def parse_all(
    output_dir: Path,
    html_dir: Path = HTML_DIR,
    rt_ids: Optional[List[str]] = None,
) -> Dict:
    """Parse HTML files into JSON, one per RT ID.

    Args:
        output_dir: Directory to write JSON files into.
        html_dir: Directory containing HTML files.
        rt_ids: Optional list of specific RT IDs to parse.
                If None, parses all HTML files (including subdirectories).

    Returns:
        Summary dict: {total, parsed, errors, error_ids, elapsed}
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if rt_ids is not None:
        html_index = HtmlIndex()
        html_files = [html_index.resolve(rt_id) for rt_id in rt_ids]
        html_files = [p for p in html_files if p.exists()]
    else:
        # rglob to find HTML in type subdirectories (e.g. html/retail/*.html)
        html_files = sorted(html_dir.rglob("*.html"))

    total = len(html_files)
    logger.info("Parsing %d HTML files → %s", total, output_dir)

    parsed = 0
    errors = 0
    error_ids: List[str] = []
    start = time.time()

    for i, path in enumerate(html_files):
        rt_id = path.stem
        try:
            html_content = path.read_text(encoding="utf-8")
            ctx = build_transaction_context(
                html_content=html_content,
                rt_id=rt_id,
                html_path=str(path),
            )
            out_path = output_dir / f"{rt_id}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(ctx.to_dict(), f, indent=2)
            parsed += 1
        except Exception:
            logger.exception("Error parsing %s", rt_id)
            errors += 1
            error_ids.append(rt_id)

        if (i + 1) % 2000 == 0:
            logger.info("Progress: %d / %d", i + 1, total)

    elapsed = time.time() - start
    logger.info(
        "Done: %d parsed, %d errors in %.1fs", parsed, errors, elapsed
    )

    return {
        "total": total,
        "parsed": parsed,
        "errors": errors,
        "error_ids": error_ids,
        "elapsed": round(elapsed, 1),
    }
