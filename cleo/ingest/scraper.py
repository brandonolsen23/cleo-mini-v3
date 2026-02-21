"""Submit search to Realtrack and extract detail links from results page."""

import logging
import re
from typing import List, Optional

from bs4 import BeautifulSoup

from cleo.ingest.session import RealtrackSession

logger = logging.getLogger(__name__)

# Extracts total result count from: .pagination(15750, {
_TOTAL_PATTERN = re.compile(r"\.pagination\((\d+),")


# Search form parameters for Retail Buildings, 1996-2026, 50 per page
SEARCH_PARAMS = {
    "sf1": "",              # Region: all
    "sf2": "",              # Street: all
    "sf3": "retailBldg",    # Type: Retail Buildings
    "sf4": "",              # Keyword: none
    "startmo": "1/1",       # Period start: Jan 1
    "startyr": "1996",      # Period start year
    "endmo": "12/31",       # Period end: Dec 31
    "endyr": "2026",        # Period end year
    "minamt": "",           # Min price: none
    "maxamt": "",           # Max price: none
    "sf7": "",              # Parties: none
    "sf8": "",              # Broker/Agent: none
    "sort1": "regDate",     # Primary sort: Date
    "order1": "descending", # Newest first
    "sort2": "amount",      # Secondary sort: Amount
    "order2": "descending",
    "sf9": "50",            # Display: 50 per page
    "tabID": "",            # Required hidden field
}


def get_total_results(session: RealtrackSession) -> Optional[int]:
    """Submit a search and extract the total result count from the pagination JS.

    The results page contains: .pagination(15750, { ... })
    Returns the integer total, or None if it can't be extracted.
    """
    session.get("/?page=search")
    resp = session.post("/?page=results", data=SEARCH_PARAMS)

    match = _TOTAL_PATTERN.search(resp.text)
    if match:
        return int(match.group(1))

    logger.warning("Could not extract total result count from results page.")
    return None


def submit_search_and_get_links(session: RealtrackSession) -> List[int]:
    """Submit the search form and extract detail page skip indices.

    Returns a list of integer skip indices (e.g., [0, 1, 2, ..., 49])
    from the first page of results.
    """
    logger.info("Submitting search: Retail Buildings, 1996-2026, 50/page...")

    # Must GET the search page first to establish server-side session state.
    # Without this, the POST returns a 500 Internal Server Error.
    session.get("/?page=search")

    resp = session.post("/?page=results", data=SEARCH_PARAMS)
    html = resp.text

    soup = BeautifulSoup(html, "lxml")

    # Extract all detail links: <a class="propAddr" href="?page=details&skip=N">
    links = soup.find_all("a", class_="propAddr")
    if not links:
        logger.warning("No detail links found on results page.")
        return []

    skip_indices = []
    skip_pattern = re.compile(r"skip=(\d+)")

    for link in links:
        href = link.get("href", "")
        match = skip_pattern.search(href)
        if match:
            skip_indices.append(int(match.group(1)))

    logger.info("Found %d detail links on results page.", len(skip_indices))
    return skip_indices
