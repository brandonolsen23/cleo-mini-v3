"""Batch extraction engine for operator websites.

Uses VersionedStore for sandbox/promote/diff lifecycle.
"""

import json
import logging
import time
from pathlib import Path

from cleo.config import OPERATORS_CONFIG_PATH, OPERATORS_CRAWL_DIR, OPERATORS_EXTRACTED_DIR
from cleo.versioning import VersionedStore

logger = logging.getLogger(__name__)

store = VersionedStore(base_dir=OPERATORS_EXTRACTED_DIR)


def load_config() -> list[dict]:
    """Load operator config list."""
    if not OPERATORS_CONFIG_PATH.exists():
        return []
    return json.loads(OPERATORS_CONFIG_PATH.read_text(encoding="utf-8"))


def run_extraction(
    output_dir: Path,
    model: str = "claude-haiku-4-5-20251001",
    slug_filter: str | None = None,
) -> dict:
    """Run AI extraction on all (or one) operator's crawled pages.

    Returns summary dict.
    """
    import anthropic
    from cleo.config import ANTHROPIC_API_KEY
    from cleo.operators.extractor import classify_page, extract_page, merge_extractions

    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set. Add it to your .env file.")

    # The SDK has built-in retry with backoff for 429s — no custom retry needed.
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    operators = load_config()
    if slug_filter:
        operators = [op for op in operators if op["slug"] == slug_filter]

    total_pages = 0
    relevant_pages = 0
    extracted_ops = 0
    errors = 0

    for op in operators:
        if not op.get("enabled", True):
            continue

        slug = op["slug"]
        name = op["name"]
        url = op["url"]
        crawl_dir = OPERATORS_CRAWL_DIR / slug / "html"

        if not crawl_dir.is_dir():
            logger.warning("No crawl data for %s", slug)
            continue

        html_files = sorted(crawl_dir.glob("*.html"))
        if not html_files:
            logger.warning("No HTML files for %s", slug)
            continue

        num_files = len(html_files)
        logger.info("Processing %s (%d pages)", slug, num_files)
        page_extractions = []

        for page_num, html_path in enumerate(html_files, 1):
            total_pages += 1
            html = html_path.read_text(encoding="utf-8")

            # Step 1: Classify
            try:
                category = classify_page(html, client, model=model)
            except Exception as e:
                logger.warning("Classification error for %s/%s: %s", slug, html_path.name, e)
                errors += 1
                continue

            # Throttle between API calls to stay under rate limits
            time.sleep(5)

            if category == "IRRELEVANT":
                logger.info("  [%d/%d] %s → skip (irrelevant)", page_num, num_files, html_path.name)
                continue

            relevant_pages += 1

            # Step 2: Extract
            try:
                extraction = extract_page(html, url, client, model=model)
                if extraction:
                    page_extractions.append(extraction)
                    logger.info("  [%d/%d] %s → %s (extracted)", page_num, num_files, html_path.name, category)
                else:
                    logger.info("  [%d/%d] %s → %s (no data)", page_num, num_files, html_path.name, category)
            except Exception as e:
                logger.warning("  [%d/%d] %s → extraction error: %s", page_num, num_files, html_path.name, e)
                errors += 1

            time.sleep(5)

        # Step 3: Merge
        if page_extractions:
            merged = merge_extractions(page_extractions, slug, name, url)
            out_path = output_dir / f"{slug}.json"
            out_path.write_text(
                json.dumps(merged, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            extracted_ops += 1
            logger.info(
                "  %s: %d contacts, %d properties, %d photos",
                slug,
                len(merged["contacts"]),
                len(merged["properties"]),
                len(merged["photos"]),
            )

    return {
        "total_operators": len(operators),
        "extracted_operators": extracted_ops,
        "total_pages": total_pages,
        "relevant_pages": relevant_pages,
        "errors": errors,
    }
