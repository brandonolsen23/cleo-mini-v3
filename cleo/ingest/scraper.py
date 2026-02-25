"""Submit search to Realtrack and extract detail links from results page."""

import logging
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

from cleo.ingest.session import RealtrackSession

logger = logging.getLogger(__name__)

# Extracts total result count from: .pagination(15750, {
_TOTAL_PATTERN = re.compile(r"\.pagination\((\d+),")

# Property type slug -> sf3 form value
# Populated by running `cleo discover-types` against the live search form.
PROPERTY_TYPES: Dict[str, str] = {
    "retail": "retailBldg",
    "industrial": "indBldg",
    "multifamily": "multiRes",
    "office": "officeBldg",
    "hotel-motel": "hotelMotel",
    "restaurant-bar": "restaurantBar",
    "other-bldg": "otherImprv",
    "comm-ind-land": "comIndLand",
    "res-land": "resLand",
    "farm": "farmLand",
    "other-land": "otherLand",
}


def make_search_params(prop_type: str = "retail") -> dict:
    """Build search form parameters for a given property type.

    Args:
        prop_type: Key from PROPERTY_TYPES (e.g. "retail", "industrial").

    Returns:
        Dict of form fields suitable for POSTing to Realtrack search.
    """
    sf3_value = PROPERTY_TYPES.get(prop_type)
    if sf3_value is None:
        raise ValueError(
            f"Unknown property type {prop_type!r}. "
            f"Valid types: {', '.join(sorted(PROPERTY_TYPES))}"
        )
    return {
        "sf1": "",              # Region: all
        "sf2": "",              # Street: all
        "sf3": sf3_value,       # Type
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


# Backward-compat alias
SEARCH_PARAMS = make_search_params("retail")


def discover_property_types(session: RealtrackSession) -> List[Dict[str, str]]:
    """Fetch the search form and extract all sf3 <select> options.

    Returns list of dicts: [{"value": "retailBldg", "label": "Retail Buildings"}, ...]
    """
    resp = session.get("/?page=search")
    soup = BeautifulSoup(resp.text, "lxml")

    select = soup.find("select", attrs={"name": "sf3"})
    if not select:
        logger.warning("Could not find sf3 <select> on search page.")
        return []

    options = []
    for opt in select.find_all("option"):
        value = opt.get("value", "").strip()
        label = opt.get_text(strip=True)
        if value:  # skip empty "All" option
            options.append({"value": value, "label": label})

    return options


def get_total_results(
    session: RealtrackSession, prop_type: str = "retail"
) -> Optional[int]:
    """Submit a search and extract the total result count from the pagination JS.

    The results page contains: .pagination(15750, { ... })
    Returns the integer total, or None if it can't be extracted.
    """
    params = make_search_params(prop_type)
    session.get("/?page=search")
    resp = session.post("/?page=results", data=params)

    match = _TOTAL_PATTERN.search(resp.text)
    if match:
        return int(match.group(1))

    logger.warning("Could not extract total result count from results page.")
    return None


def submit_search_and_get_links(
    session: RealtrackSession, prop_type: str = "retail"
) -> List[int]:
    """Submit the search form and extract detail page skip indices.

    Returns a list of integer skip indices (e.g., [0, 1, 2, ..., 49])
    from the first page of results.
    """
    params = make_search_params(prop_type)
    label = PROPERTY_TYPES.get(prop_type, prop_type)
    logger.info("Submitting search: %s, 1996-2026, 50/page...", label)

    # Must GET the search page first to establish server-side session state.
    # Without this, the POST returns a 500 Internal Server Error.
    session.get("/?page=search")

    resp = session.post("/?page=results", data=params)
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
