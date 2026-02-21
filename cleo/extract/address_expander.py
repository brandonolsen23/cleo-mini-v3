"""Address expansion for geocoding.

Splits compound addresses into individual geocodable strings and appends
city/province context.
"""

import re
from typing import List

# A "number" in an address can have an optional letter suffix: 620A, 373B, 30A, 900-A
_NUM = r"\d+(?:-?[A-Za-z½])?"

# Pattern: "92, 102 & 112 COMMERCE PARK DR" or "4, 14, 34 & 44 CEDAR POINTE DR"
_COMMA_AMP_RE = re.compile(
    rf"^({_NUM}(?:\s*,\s*{_NUM})*)\s*&\s*({_NUM})\s+(.+)$"
)

# Pattern: "21 & 111 COMMERCE PARK DR" (two numbers with &)
_AMP_RE = re.compile(
    rf"^({_NUM})\s*&\s*({_NUM})\s+(.+)$"
)

# Pattern: "138 - 142 COMMERCE PARK DR" or "1855 - 1911 DUNDAS ST E"
_RANGE_RE = re.compile(
    rf"^({_NUM})\s*[-\u2013]\s*({_NUM})\s+(.+)$"
)

# Pattern: comma-separated numbers WITHOUT & : "4, 8, 16 MAIN ST N" or "910, 922 KINGSTON RD"
_COMMA_RE = re.compile(
    rf"^({_NUM}(?:\s*,\s*{_NUM})+)\s+(.+)$"
)

# Legal description keywords — don't split these
_LEGAL_RE = re.compile(
    r"(?:^|\s)(?:LOT|LOTS|BLOCK|BLOCKS|PLAN|PT\s+LOT|PART\s+LOT|PART\s+CONC|PART\s+CONCS)\b",
    re.IGNORECASE,
)

# "CONC" as a legal keyword — but not "CONC ST", "CONC RD", etc.
_CONC_LEGAL_RE = re.compile(r"\bCONC\s+\d", re.IGNORECASE)

# Highway compound name: "HIGHWAY 6 & 21" — the & joins highway numbers, not addresses
_HIGHWAY_AMP_RE = re.compile(
    r"\bH(?:IGH)?W(?:A)?Y\s+\d+\s*&\s*\d+", re.IGNORECASE
)

# Province keywords for detecting if address already has province
_PROVINCES = {
    "ontario", "quebec", "alberta", "british columbia", "manitoba",
    "saskatchewan", "nova scotia", "new brunswick", "newfoundland",
    "prince edward island", "yukon", "northwest territories", "nunavut",
}


_PO_BOX_RE = re.compile(
    r"(?:^|[\s,])(?:PO\s*BOX|P\.?O\.?\s*BOX|BOX\s+\d|GENERAL\s+DELIVERY)",
    re.IGNORECASE,
)


def is_po_box(address: str) -> bool:
    """Return True if the address is a PO Box / rural route (not geocodable)."""
    if not address:
        return False
    return bool(_PO_BOX_RE.search(address))


_LEGAL_SKIP_RE = re.compile(
    r"\b(?:CONC|LOT|LOTS|BLOCK|BLOCKS|PLAN|PT\s+LOT|PART\s+LOT|PART\s+CONC|PART\s+CONCS|CONDO\s+PLAN)\b",
    re.IGNORECASE,
)


def is_legal_description(address: str) -> bool:
    """Return True if the address is a legal description (not geocodable)."""
    if not address:
        return False
    # Only flag non-digit-starting addresses — a street address like
    # "190 BALSAM ST" that happens to contain "LOT" in a suffix is fine
    if address[0].isdigit():
        return False
    return bool(_LEGAL_SKIP_RE.search(address))


def expand_compound_address(address: str, city: str, province: str) -> List[str]:
    """Expand a compound address into individual geocodable addresses.

    Handles:
    - Comma+& lists: "92, 102 & 112 COMMERCE PARK DR"
    - Ampersand pairs: "21 & 111 COMMERCE PARK DR"
    - Ranges (endpoints only): "138 - 142 COMMERCE PARK DR"
    - Comma lists (no &): "4, 8, 16 MAIN ST N"
    - Letter suffixes: "618 - 620A BLOOR ST W"
    - Parenthesized: "(74 - 76 YORK ST)"
    - Plain addresses: returned as-is with city/province appended

    Skips legal descriptions and highway names.

    Returns list of geocodable address strings.
    """
    address = address.strip()
    if not address:
        return []

    # Strip surrounding parentheses
    if address.startswith("(") and address.endswith(")"):
        address = address[1:-1].strip()

    suffix = _build_suffix(city, province)

    # Skip legal descriptions — not splittable addresses
    if _LEGAL_RE.search(address) or _CONC_LEGAL_RE.search(address):
        return [f"{address}{suffix}"]
    # Skip highway compound names like "HIGHWAY 6 & 21" — the & is part of the name
    if _HIGHWAY_AMP_RE.search(address):
        return [f"{address}{suffix}"]

    # Try comma+& pattern first (most specific)
    m = _COMMA_AMP_RE.match(address)
    if m:
        nums_str, last_num, street = m.group(1), m.group(2), m.group(3)
        nums = [n.strip() for n in nums_str.split(",")]
        nums.append(last_num)
        return [f"{n} {street}{suffix}" for n in nums]

    # Try range+& combo: "9 - 15 & 21 DUNDURN ST N" → split on & first, then expand each part
    range_amp_m = re.match(
        rf"^({_NUM}\s*[-\u2013]\s*{_NUM})\s*&\s*({_NUM})\s+(.+)$", address
    )
    if range_amp_m:
        range_part, amp_num, street = range_amp_m.group(1), range_amp_m.group(2), range_amp_m.group(3)
        # Expand the range part
        results = expand_compound_address(f"{range_part} {street}", city, province)
        # Add the & number
        results.append(f"{amp_num} {street}{suffix}")
        return results

    # Try simple & pattern
    m = _AMP_RE.match(address)
    if m:
        num1, num2, street = m.group(1), m.group(2), m.group(3)
        return [f"{num1} {street}{suffix}", f"{num2} {street}{suffix}"]

    # Try range+comma combo: "230 - 238, 244 BLOOR ST W" → split on comma first
    range_comma_m = re.match(
        rf"^({_NUM}\s*[-\u2013]\s*{_NUM})\s*,\s*({_NUM})\s+(.+)$", address
    )
    if range_comma_m:
        range_part, comma_num, street = range_comma_m.group(1), range_comma_m.group(2), range_comma_m.group(3)
        results = expand_compound_address(f"{range_part} {street}", city, province)
        results.append(f"{comma_num} {street}{suffix}")
        return results

    # Try comma+range combo: "316, 328 - 330 ST CLAIR ST" → number before range
    comma_range_m = re.match(
        rf"^({_NUM})\s*,\s*({_NUM}\s*[-\u2013]\s*{_NUM})\s+(.+)$", address
    )
    if comma_range_m:
        comma_num, range_part, street = comma_range_m.group(1), comma_range_m.group(2), comma_range_m.group(3)
        results = [f"{comma_num} {street}{suffix}"]
        results.extend(expand_compound_address(f"{range_part} {street}", city, province))
        return results

    # Try range pattern (endpoints only)
    m = _RANGE_RE.match(address)
    if m:
        start, end, street = m.group(1), m.group(2), m.group(3)
        if start == end:
            return [f"{start} {street}{suffix}"]
        return [f"{start} {street}{suffix}", f"{end} {street}{suffix}"]

    # Try comma-only list (no &): "4, 8, 16 MAIN ST N"
    m = _COMMA_RE.match(address)
    if m:
        nums_str, street = m.group(1), m.group(2)
        nums = [n.strip() for n in nums_str.split(",")]
        return [f"{n} {street}{suffix}" for n in nums]

    # Plain address
    return [f"{address}{suffix}"]


def normalize_party_address(address: str, city: str, province: str) -> str:
    """Normalize a party address: append city/province if missing.

    Party addresses are usually already clean single addresses like
    "18 York St, Ste 1500, Toronto, Ontario, M5J 2T8".
    Only appends city/province if not already present.
    """
    if not address:
        return ""

    if _has_city_province(address):
        return address

    suffix = _build_suffix(city, province)
    return f"{address}{suffix}"


def _build_suffix(city: str, province: str) -> str:
    """Build a ', City, Province' suffix from components."""
    parts = []
    if city:
        parts.append(city)
    if province:
        parts.append(province)
    if parts:
        return ", " + ", ".join(parts)
    return ""


def _has_city_province(address: str) -> bool:
    """Check if an address already contains a city/province component."""
    lowered = address.lower()
    for prov in _PROVINCES:
        if prov in lowered:
            return True
    return False
