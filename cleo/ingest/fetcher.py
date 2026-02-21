"""Fetch Realtrack detail pages and extract RT IDs."""

import logging
import re
from typing import Optional, Tuple

from bs4 import BeautifulSoup

from cleo.ingest.session import RealtrackSession

logger = logging.getLogger(__name__)

# RT ID pattern: "RT" followed by one or more digits (variable length)
RT_ID_PATTERN = re.compile(r"RT\d+")


def fetch_detail_page(
    session: RealtrackSession, skip_index: int
) -> Tuple[Optional[str], str]:
    """Fetch a detail page and extract the RT ID.

    The RT ID is found at the bottom of the page in a gray font tag:
    <font color="#848484">1 / 15750  ...  RT196880</font>

    Args:
        session: Authenticated Realtrack session.
        skip_index: The skip parameter for the detail page URL.

    Returns:
        Tuple of (rt_id, html_content). rt_id is None if extraction failed.
    """
    resp = session.get(f"/?page=details&skip={skip_index}")
    html = resp.text

    rt_id = _extract_rt_id(html)
    if rt_id is None:
        logger.warning("Could not extract RT ID from detail page skip=%d", skip_index)

    return rt_id, html


def _extract_rt_id(html: str) -> Optional[str]:
    """Extract the RT ID from a detail page's HTML.

    Looks for RT ID in <font color="#848484"> elements at the bottom
    of the page. The element contains text like:
    "1 / 15750       RT196880"
    """
    soup = BeautifulSoup(html, "lxml")

    # Find all gray font tags — the RT ID is in the last one
    gray_fonts = soup.find_all("font", color="#848484")

    for font in reversed(gray_fonts):
        text = font.get_text()
        match = RT_ID_PATTERN.search(text)
        if match:
            return match.group(0)

    return None
