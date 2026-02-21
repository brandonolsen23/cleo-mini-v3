"""GeoWarehouse batch parse engine.

Parses all GW HTML files into structured JSON, deduplicates by PIN
(keeping the most recent snapshot), and assigns stable GW IDs.
"""

import json
import logging
import time
from pathlib import Path

from cleo.geowarehouse.parser import parse_gw_html

logger = logging.getLogger(__name__)


def _extract_timestamp(filename: str) -> str:
    """Extract the ISO-ish timestamp from a GW filename for sorting.

    Filenames look like: geowarehouse-2025-11-20T17-25-57-019Z.html
    Returns the timestamp portion for string comparison.
    """
    stem = Path(filename).stem
    # Strip the "geowarehouse-" prefix
    ts = stem.removeprefix("geowarehouse-")
    return ts


def run_parse(html_dir: Path, output_dir: Path) -> dict:
    """Parse all GW HTML files and write deduplicated JSON to output_dir.

    Deduplication: when multiple files share the same PIN, only the file
    with the latest timestamp (from filename) is kept.

    Output files are named GW00001.json, GW00002.json, etc., assigned
    in PIN-sorted order.

    Returns a stats dict with keys: parsed, skipped, errors, duplicates, elapsed.
    """
    start = time.time()
    html_files = sorted(html_dir.glob("*.html"))

    parsed_records = []  # list of (pin, filename, record_dict)
    skipped = 0
    errors = 0
    error_files = []

    for html_path in html_files:
        try:
            html = html_path.read_text(encoding="utf-8")
            record = parse_gw_html(html, html_path.name)
        except Exception:
            logger.exception("Error parsing %s", html_path.name)
            errors += 1
            error_files.append(html_path.name)
            continue

        if record is None:
            skipped += 1
            continue

        pin = record.get("pin", "")
        if not pin:
            logger.warning("No PIN found in %s, skipping", html_path.name)
            skipped += 1
            continue

        parsed_records.append((pin, html_path.name, record))

    # Deduplicate by PIN — keep the file with the latest timestamp
    pin_best: dict[str, tuple[str, dict]] = {}
    for pin, filename, record in parsed_records:
        ts = _extract_timestamp(filename)
        existing = pin_best.get(pin)
        if existing is None or ts > existing[0]:
            pin_best[pin] = (ts, record)

    duplicates = len(parsed_records) - len(pin_best)

    # Assign GW IDs in PIN-sorted order
    sorted_pins = sorted(pin_best.keys())
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, pin in enumerate(sorted_pins, start=1):
        gw_id = f"GW{i:05d}"
        _, record = pin_best[pin]
        record["gw_id"] = gw_id

        out_path = output_dir / f"{gw_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)

    elapsed = round(time.time() - start, 1)

    return {
        "total_html": len(html_files),
        "parsed": len(pin_best),
        "skipped": skipped,
        "duplicates": duplicates,
        "errors": errors,
        "error_files": error_files,
        "elapsed": elapsed,
    }
