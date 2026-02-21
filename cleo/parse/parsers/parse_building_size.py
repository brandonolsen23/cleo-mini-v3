"""Extract building square footage from transaction descriptions."""

import re

_SF_PATTERN = re.compile(
    r"(\d{1,3}(?:,\d{3})*)\s*(?:sf|sq\.?\s*ft\.?|square\s+feet?)",
    re.IGNORECASE,
)


def parse_building_size(description: str) -> str:
    """Return the first building SF match as a numeric string (commas stripped).

    Returns ``""`` if no match is found.
    """
    m = _SF_PATTERN.search(description)
    if m:
        return m.group(1).replace(",", "")
    return ""
