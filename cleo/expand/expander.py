"""Address expander — splits compound street numbers into individual addresses.

Input: normalized address block (street_number, street_name, street_suffix,
       street_direction, unit, normalized_city, normalized_province, category, etc.)

Output: list of address entries, each with decomposed fields + canonical string.
No aliases are generated — matching normalizes both sides at comparison time.
"""

import re
from typing import Dict, List, Optional

# Match individual number tokens within a compound street number.
# Handles: "123", "123A", "123 1/2"
_NUM_TOKEN_RE = re.compile(r"\d+[A-Z]?(?:\s+\d/\d)?")


def _split_numbers(num_str: str) -> List[str]:
    """Split a compound street number into individual number tokens.

    Handles &, commas, dashes (ranges). Returns individual number strings.

    Examples:
        "123"           → ["123"]
        "123A"          → ["123A"]
        "123 1/2"       → ["123 1/2"]
        "123 & 125"     → ["123", "125"]
        "92, 102 & 112" → ["92", "102", "112"]
        "138 - 142"     → ["138", "142"]
        "4, 8, 16"      → ["4", "8", "16"]
    """
    if not num_str or not num_str.strip():
        return []
    tokens = _NUM_TOKEN_RE.findall(num_str)
    return tokens if tokens else [num_str.strip()]


def _build_canonical(
    number: str, name: str, suffix: str, direction: str,
    unit: str, unit_type: str, city: str, province: str,
    postal_code: str = "",
) -> str:
    """Build canonical address string from decomposed fields."""
    parts = []
    if number:
        parts.append(number)
    if name:
        parts.append(name)
    if suffix:
        parts.append(suffix)
    if direction:
        parts.append(direction)
    if unit:
        if unit_type:
            parts.append(unit_type)
        parts.append(unit)

    street = " ".join(parts)
    loc_parts = []
    if city:
        loc_parts.append(city)
    if province:
        loc_parts.append(province)
    if postal_code:
        loc_parts.append(postal_code)
    if loc_parts:
        loc_str = ", ".join(loc_parts)
        if street:
            return street + ", " + loc_str
        return loc_str
    return street


def _should_skip(block: Dict) -> bool:
    """Determine if an address block should be skipped for geocoding."""
    cat = block.get("category", "")
    scope = block.get("address_scope", "")
    if cat in ("empty", "po_box", "legal_description", "no_street_number"):
        return True
    if scope == "international":
        return True
    # Brand records without a street number won't geocode reliably
    if not block.get("street_number", "").strip():
        return True
    return False


def expand_block(block: Dict) -> Optional[Dict]:
    """Expand a single normalized address block into individual address entries.

    Splits compound street numbers into individual addresses. Each entry has
    decomposed fields for structured matching and a canonical string for
    geocoding/display.

    Returns dict with 'addresses' list, or None if block is empty/missing.
    """
    if not block:
        return None

    cat = block.get("category", "")
    if cat == "empty":
        return None

    skip = _should_skip(block)
    name = block.get("street_name", "")
    suffix = block.get("street_suffix", "")
    direction = block.get("street_direction", "")
    unit = block.get("unit", "")
    unit_type = block.get("unit_type", "")
    city = block.get("normalized_city", "")
    province = block.get("normalized_province", "")
    postal_code = block.get("normalized_postal_code", "")
    num_str = block.get("street_number", "")
    raw = block.get("raw_address", "")

    # No street info — PO box, rural route, or similar: pass through raw
    if not name and not num_str:
        if not raw:
            return None
        loc_parts = []
        if city:
            loc_parts.append(city)
        if province:
            loc_parts.append(province)
        if postal_code:
            loc_parts.append(postal_code)
        canonical = raw
        if loc_parts:
            canonical += ", " + ", ".join(loc_parts)
        return {
            "addresses": [{
                "street_number": "",
                "street_name": "",
                "street_suffix": "",
                "street_direction": "",
                "unit": unit,
                "unit_type": unit_type,
                "city": city,
                "province": province,
                "postal_code": postal_code,
                "canonical": canonical,
                "skip_geocode": skip,
            }],
        }

    # Split compound street numbers into individual tokens
    numbers = _split_numbers(num_str)
    if not numbers:
        numbers = [""]

    addresses = []
    for num in numbers:
        canonical = _build_canonical(
            num, name, suffix, direction, unit, unit_type, city, province,
            postal_code,
        )
        addresses.append({
            "street_number": num,
            "street_name": name,
            "street_suffix": suffix,
            "street_direction": direction,
            "unit": unit,
            "unit_type": unit_type,
            "city": city,
            "province": province,
            "postal_code": postal_code,
            "canonical": canonical,
            "skip_geocode": skip,
        })

    return {"addresses": addresses}


def expand_record(data: Dict) -> Dict:
    """Expand a single normalized record.

    Splits compound street numbers into individual alternate addresses.
    Each address entry has decomposed fields for structured matching
    and a canonical string for geocoding/display.
    """
    result: Dict = {
        "id": data.get("rt_id") or data.get("brand_id") or data.get("gw_id", ""),
        "source": data.get("source", ""),
        "source_version": data.get("source_version", ""),
    }

    # Property address
    prop = data.get("property")
    if prop:
        result["property"] = expand_block(prop)

    # Alternate property addresses — always include key if input had it
    prop_alt = data.get("property_alt", [])
    if prop_alt:
        alts = []
        for alt in prop_alt:
            expanded = expand_block(alt)
            if expanded:
                alts.append(expanded)
        result["property_alt"] = alts

    # Seller
    seller = data.get("seller")
    if seller:
        result["seller"] = expand_block(seller)

    # Buyer
    buyer = data.get("buyer")
    if buyer:
        result["buyer"] = expand_block(buyer)

    # Owner address (GeoWarehouse)
    owner = data.get("owner_address")
    if owner:
        result["owner_address"] = expand_block(owner)

    # Pass through brand coordinates if available
    prop_block = data.get("property", {})
    if prop_block and prop_block.get("raw_coords"):
        result["raw_coords"] = prop_block["raw_coords"]

    return result
