"""One-off full scan: find and download missing RT IDs."""

import argparse
import logging
import re
import sys
import time
from datetime import datetime

from bs4 import BeautifulSoup

from cleo.config import HTML_DIR, get_credentials
from cleo.ingest.fetcher import fetch_detail_page
from cleo.ingest.html_index import HtmlIndex
from cleo.ingest.scraper import PROPERTY_TYPES, make_search_params, _TOTAL_PATTERN
from cleo.ingest.session import RealtrackSession
from cleo.ingest.tracker import IngestTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("full_scan")

DELAY = 0.4
START_PAGE = 0
skip_pattern = re.compile(r"skip=(\d+)")


def extract_skip_indices(html: str) -> list[int]:
    soup = BeautifulSoup(html, "lxml")
    links = soup.find_all("a", class_="propAddr")
    indices = []
    for link in links:
        href = link.get("href", "")
        match = skip_pattern.search(href)
        if match:
            indices.append(int(match.group(1)))
    return indices


def main():
    parser = argparse.ArgumentParser(description="Full scan for missing RT IDs.")
    parser.add_argument(
        "--type", dest="prop_type", default="retail",
        choices=sorted(PROPERTY_TYPES.keys()),
        help="Property type to scan (default: retail).",
    )
    parser.add_argument(
        "--start-page", type=int, default=0,
        help="Page number to start from (0-indexed).",
    )
    args = parser.parse_args()

    prop_type = args.prop_type
    start_page = args.start_page
    search_params = make_search_params(prop_type)

    username, password = get_credentials()
    session = RealtrackSession(username, password)

    try:
        tracker = IngestTracker()
        html_index = HtmlIndex()
        target_gap = None

        # Ensure type subdirectory exists
        type_dir = HTML_DIR / prop_type
        type_dir.mkdir(parents=True, exist_ok=True)

        # Submit search to get total and establish session
        session.get("/?page=search")
        resp = session.post("/?page=results", data=search_params)

        total_match = _TOTAL_PATTERN.search(resp.text)
        if total_match:
            total = int(total_match.group(1))
            local_count = tracker.count_by_type(prop_type)
            target_gap = total - local_count
            total_pages = (total + 49) // 50
            logger.info(
                "[%s] Realtrack total: %d | Local: %d | Gap: %d | Pages to scan: %d",
                prop_type, total, local_count, target_gap, total_pages - start_page,
            )
        else:
            total_pages = 316
            logger.warning("Could not extract total, using %d pages", total_pages)

        found_new = 0
        checked = 0
        errors = 0
        consecutive_empty = 0
        # For types with small gaps, stop after many consecutive empty pages
        MAX_CONSECUTIVE_EMPTY = 20

        for page_num in range(start_page, total_pages):
            try:
                resp = session.get(f"/?page=results&tabID={page_num}")
            except Exception as e:
                logger.error("Failed to load results page %d: %s", page_num + 1, e)
                errors += 1
                continue

            page_indices = extract_skip_indices(resp.text)
            if not page_indices:
                logger.info("Page %d: no results, stopping.", page_num + 1)
                break

            page_new = 0
            for skip in page_indices:
                try:
                    rt_id, html = fetch_detail_page(session, skip)
                except Exception as e:
                    logger.error("Failed skip=%d: %s", skip, e)
                    errors += 1
                    time.sleep(1)
                    continue

                checked += 1

                if rt_id and rt_id not in tracker.seen:
                    path = type_dir / f"{rt_id}.html"
                    path.write_text(html, encoding="utf-8")
                    tracker.seen[rt_id] = {
                        "ts": datetime.now().isoformat(timespec="seconds"),
                        "type": prop_type,
                    }
                    html_index.register(rt_id, prop_type)
                    found_new += 1
                    page_new += 1
                    logger.info(
                        "NEW: %s (skip=%d) — %d/%s found",
                        rt_id, skip, found_new, target_gap or "?",
                    )

                time.sleep(DELAY)

            # Save tracker and index after each page with new finds
            if page_new > 0:
                tracker._save()
                html_index.save()
                consecutive_empty = 0
            else:
                consecutive_empty += 1

            # Progress every page
            skip_range = f"skip {min(page_indices)}-{max(page_indices)}"
            logger.info(
                "Page %d/%d (%s) | checked: %d | +%d new | %d total new | %d errors",
                page_num + 1, total_pages, skip_range, checked, page_new, found_new, errors,
            )
            sys.stdout.flush()

            # Stop early if gap is closed
            if target_gap and found_new >= target_gap:
                logger.info("All %d missing RT IDs found! Stopping early.", target_gap)
                break

            # Stop if too many consecutive pages with no new records
            if consecutive_empty >= MAX_CONSECUTIVE_EMPTY:
                logger.info(
                    "No new records in %d consecutive pages — likely all known. Stopping.",
                    MAX_CONSECUTIVE_EMPTY,
                )
                break

        tracker._save()
        html_index.save()
        logger.info(
            "=== COMPLETE === Checked: %d | New: %d | Errors: %d | Total known: %d",
            checked, found_new, errors, tracker.count,
        )
        print(f"\nDone! Found {found_new} new {prop_type} RT IDs. Total known: {tracker.count}.")

    finally:
        session.close()


if __name__ == "__main__":
    main()
