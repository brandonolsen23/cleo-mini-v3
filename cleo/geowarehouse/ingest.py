"""GeoWarehouse file ingestion.

Copies GW HTML files from a source directory (browser extension downloads)
into the project's data/gw_html/ directory, filtering to only property
detail page files (geowarehouse-* prefix).
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


def ingest_files(source_dir: Path, target_dir: Path, dry_run: bool = False) -> dict:
    """Copy GeoWarehouse HTML files from source_dir to target_dir.

    Only copies files matching the geowarehouse-*.html pattern (skips
    collaboration-* and other prefixes).

    Returns a stats dict with keys: total_found, gw_detail, skipped, copied, already_present.
    """
    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    all_files = sorted(source_dir.glob("*.html"))
    gw_files = [f for f in all_files if f.name.startswith("geowarehouse-")]
    skipped_files = [f for f in all_files if not f.name.startswith("geowarehouse-")]

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    already_present = 0

    for src in gw_files:
        dest = target_dir / src.name
        if dest.exists():
            already_present += 1
            continue

        if not dry_run:
            shutil.copy2(src, dest)
            copied += 1
        else:
            copied += 1  # Would be copied

    return {
        "total_found": len(all_files),
        "gw_detail": len(gw_files),
        "skipped": len(skipped_files),
        "copied": copied,
        "already_present": already_present,
    }
