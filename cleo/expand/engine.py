"""Expansion engine: reads normalized JSON and produces expanded address packages."""

import json
import logging
import time
from pathlib import Path
from typing import Dict, List

from .expander import expand_record

logger = logging.getLogger(__name__)


def expand_all(
    source_dir: Path,
    output_dir: Path,
    source_version: str = "",
) -> Dict:
    """Expand all normalized JSON files into geocodable address packages.

    Reads each {ID}.json in source_dir (normalized output), expands
    addresses, and writes to output_dir/{ID}.json.

    Returns summary: {total, expanded, errors, elapsed, by_source}
    """
    start = time.time()
    total = 0
    expanded = 0
    errors = 0
    error_ids: List[str] = []
    by_source: Dict[str, int] = {}

    source_files = sorted(source_dir.glob("*.json"))

    for src_path in source_files:
        if src_path.stem == "_meta":
            continue
        total += 1

        try:
            data = json.loads(src_path.read_text(encoding="utf-8"))

            # Override source_version with the normalize version we're reading
            if source_version:
                data["source_version"] = source_version

            result = expand_record(data)

            out_path = output_dir / src_path.name
            out_path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            expanded += 1

            src = data.get("source", "unknown")
            by_source[src] = by_source.get(src, 0) + 1

        except Exception as e:
            errors += 1
            error_ids.append(src_path.stem)
            logger.error("Error expanding %s: %s", src_path.stem, e)

        if total % 5000 == 0:
            logger.info("Progress: %d records", total)

    elapsed = time.time() - start
    logger.info(
        "Done: %d expanded, %d errors in %.1fs",
        expanded, errors, elapsed,
    )

    return {
        "total": total,
        "expanded": expanded,
        "errors": errors,
        "error_ids": error_ids,
        "elapsed": elapsed,
        "by_source": by_source,
    }
