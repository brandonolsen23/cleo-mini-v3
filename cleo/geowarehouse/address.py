"""MPAC address parser for GeoWarehouse records.

Splits site_structure.property_address (e.g. "121 CONCESSION ST E TILLSONBURG ON N4G4W4")
into street, city, province, postal_code components using the separately-available
municipality field as an anchor.
"""

import re

_POSTAL_RE = re.compile(r"([A-Z]\d[A-Z])\s?(\d[A-Z]\d)\s*$")


def parse_mpac_address(
    property_address: str,
    municipality: str,
    summary_address: str = "",
) -> dict:
    """Parse an MPAC property_address into components.

    Args:
        property_address: e.g. "121 CONCESSION ST E TILLSONBURG ON N4G4W4"
        municipality: e.g. "TILLSONBURG" — used as anchor to split street from city
        summary_address: fallback, e.g. "121 CONCESSION ST E, TILLSONBURG, N4G4W4"

    Returns:
        {"street": ..., "city": ..., "province": "ON", "postal_code": ...}
    """
    result = {"street": "", "city": "", "province": "ON", "postal_code": ""}

    addr = (property_address or "").strip()

    # Fallback to summary_address if property_address is empty
    if not addr and summary_address:
        return _parse_summary_address(summary_address)

    if not addr:
        return result

    # 1. Extract postal code from end
    m = _POSTAL_RE.search(addr)
    if m:
        result["postal_code"] = f"{m.group(1)} {m.group(2)}"
        addr = addr[: m.start()].strip()

    # 2. Strip trailing " ON"
    if addr.upper().endswith(" ON"):
        addr = addr[:-3].strip()

    # 3. Find municipality in remaining string, split into street + city
    muni = (municipality or "").strip().upper()
    if muni:
        # rfind to handle cases where municipality name appears in street
        idx = addr.upper().rfind(muni)
        if idx > 0:
            result["street"] = addr[:idx].strip()
            result["city"] = municipality.strip().title()
            return result

    # If municipality not found in string, treat entire remainder as street
    result["street"] = addr
    result["city"] = municipality.strip().title() if municipality else ""
    return result


def _parse_summary_address(summary_address: str) -> dict:
    """Parse a comma-separated summary address like '121 CONCESSION ST E, TILLSONBURG, N4G4W4'."""
    result = {"street": "", "city": "", "province": "ON", "postal_code": ""}
    parts = [p.strip() for p in summary_address.split(",")]

    if len(parts) >= 1:
        result["street"] = parts[0]
    if len(parts) >= 2:
        result["city"] = parts[1].title()
    if len(parts) >= 3:
        # Could be postal code or province+postal
        last = parts[-1].strip()
        m = _POSTAL_RE.search(last)
        if m:
            result["postal_code"] = f"{m.group(1)} {m.group(2)}"
        elif re.match(r"^[A-Z]\d[A-Z]\d[A-Z]\d$", last):
            # No space postal code
            result["postal_code"] = f"{last[:3]} {last[3:]}"

    return result
