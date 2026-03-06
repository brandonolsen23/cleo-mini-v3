"""Field-level validation rules for parsed transaction data.

Rules are the fast feedback loop for parser development:
  Parse sandbox → Rules flag issues → Fix parser → Reparse → Rules report → Repeat

Each rule tests ONE field expectation. Once you catch an issue and codify it
as a rule, it stays caught forever. Rules accumulate over time into a
comprehensive automated quality gate.

Adding a new rule:
    1. Write a check function: takes (value, record) → True if PASS
    2. Add a FieldRule entry to RULES list
    3. Re-run: cleo parse --rules
"""

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class FieldRule:
    """A single field validation rule.

    severity:
        "error"   — address-critical: failure means the record can't resolve
                     to a property (e.g. empty city, mangled address).
                     These records are dead weight in the pipeline.
        "warning" — metadata-only: the address is fine, the record still
                     compiles and links to a property, but a field is
                     missing or malformed (e.g. zero site area, missing
                     seller name). Flagged for manual review.
    """
    rule_id: str           # e.g. "R001"
    name: str              # e.g. "address_starts_with_number"
    field: str             # dot-path e.g. "transaction.address.address"
    check: Callable        # (value, record) → True if PASS
    when_present: bool = False  # only check when field is non-empty
    description: str = ""  # human-readable description
    severity: str = "warning"  # "error" or "warning"


def _get_field(data: Dict, path: str) -> Any:
    """Traverse a dot-path to extract a field value from nested dict."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, "")
        else:
            return ""
    return current


# ---------------------------------------------------------------------------
# Known enums
# ---------------------------------------------------------------------------

KNOWN_PROPERTY_TYPES = {
    "retail", "industrial", "multifamily", "office", "hotel-motel",
    "restaurant-bar", "other-bldg", "comm-ind-land", "res-land",
    "farm", "other-land", "all",
}

KNOWN_TRANSACTION_TYPES = {
    "Related Parties", "Portfolio", "Power of Sale", "Land Assembly",
    "Vesting Order", "Purchased Business", "Portfolio Sale",
    "Sale Leaseback", "Zero Cash", "Purchased by Tenant",
    "Purchase Agreement", "50% Interest", "Foreclosure",
    "Purchase & Sale", "Partial Interest", "25% Interest",
    "Assembly", "Caution", "Sale & Leaseback", "Property Swap",
    "Leasehold Interest", "% Interest", "75% Interest",
    "Business Only", "Purchased Leasehold",
}

KNOWN_SUFFIXES = {
    "ST", "AVE", "RD", "DR", "BLVD", "CRES", "CT", "CRT", "PL", "WAY",
    "CIR", "LANE", "LN", "TERR", "TRAIL", "TRL", "PKWY", "HWY",
    "LINE", "CONC", "SDRD", "SIDEROAD", "ROAD", "STREET", "AVENUE",
    "DRIVE", "BOULEVARD", "CRESCENT", "COURT", "PLACE", "CIRCLE",
    "TERRACE", "PARKWAY", "HIGHWAY", "GROVE", "GATE", "GDNS", "GARDENS",
    "SQUARE", "SQ", "MEWS", "PASS", "PATH", "WALK", "CLOSE", "ROW",
    "RISE", "RIDGE", "HEIGHTS", "HTS", "HILL", "RUN", "BEND",
    "CROSSING", "POINT", "PT", "LANDING", "GREEN", "GLEN", "COMMON",
    "COMMONS", "VILLAGE", "WOODS", "PARK", "MEADOW", "VALE",
}


# ---------------------------------------------------------------------------
# Check functions — each takes (value, record) → True if PASS
# ---------------------------------------------------------------------------

def _is_valid_iso_date(v: str, rec: Dict) -> bool:
    """Date is valid ISO format YYYY-MM-DD."""
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}$", v))


def _date_not_future(v: str, rec: Dict) -> bool:
    """Date is not in the future (beyond 2026)."""
    return v <= "2026-12-31"


def _date_after_1990(v: str, rec: Dict) -> bool:
    """Date is after 1990 (Realtrack data starts ~1996)."""
    return v >= "1990-01-01"


def _price_parseable(v: str, rec: Dict) -> bool:
    """Sale price can be parsed to a positive integer."""
    try:
        num = int(v.replace("$", "").replace(",", "").strip())
        return num > 0
    except (ValueError, AttributeError):
        return False


def _address_starts_with_number(v: str, rec: Dict) -> bool:
    """Address starts with a digit (street number)."""
    return bool(re.match(r"^\d", v.strip()))


def _no_orphan_dash(v: str, rec: Dict) -> bool:
    """No orphan dashes — space-dash-space that isn't a range.

    Legitimate ranges like '123 - 127' have digits on both sides.
    Orphan: '123 - MAIN ST' (dash followed by non-digit).
    """
    # Find all space-dash-space occurrences
    for m in re.finditer(r" [-–] ", v):
        start, end = m.start(), m.end()
        before = v[:start].rstrip()
        after = v[end:].lstrip()
        # Legitimate if digits on both sides (it's a range)
        if before and before[-1].isdigit() and after and after[0].isdigit():
            continue
        return False
    return True


def _no_html_tags(v: str, rec: Dict) -> bool:
    """No HTML tags in the value."""
    return "<" not in v and ">" not in v


def _known_property_type(v: str, rec: Dict) -> bool:
    """Property type is one of the known Realtrack categories."""
    return v in KNOWN_PROPERTY_TYPES


def _known_transaction_type(v: str, rec: Dict) -> bool:
    """Transaction type is in the known types enum."""
    return v in KNOWN_TRANSACTION_TYPES


def _phone_format(v: str, rec: Dict) -> bool:
    """Phone matches common formats: NNN-NNN-NNNN or (NNN) NNN-NNNN."""
    return bool(re.match(r"^[\d\(\)\- \.]+$", v) and len(re.findall(r"\d", v)) >= 10)


def _postal_format(v: str, rec: Dict) -> bool:
    """Canadian postal code format: A9A 9A9 or A9A9A9."""
    return bool(re.match(r"^[A-Z]\d[A-Z]\s?\d[A-Z]\d$", v.upper()))


def _pin_format(v: str, rec: Dict) -> bool:
    """Ontario PIN format: NNNNN-NNNN or 9-digit raw (NNNNNNNNN).

    Handles comma-separated multi-PIN strings (all must be valid).
    """
    pins = [p.strip() for p in v.split(",")]
    return all(
        re.match(r"^\d{5}-\d{4}$", p) or re.match(r"^\d{9}$", p)
        for p in pins if p
    )


def _positive_number(v: str, rec: Dict) -> bool:
    """Value is a positive number."""
    try:
        return float(v.replace(",", "")) > 0
    except (ValueError, AttributeError):
        return False


def _city_not_empty(v: str, rec: Dict) -> bool:
    """City is not empty."""
    return bool(v.strip())


def _name_not_empty(v: str, rec: Dict) -> bool:
    """Name is not empty."""
    return bool(v.strip())


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

RULES: List[FieldRule] = [
    # --- Transaction fields (address-critical → error) ---
    FieldRule("R001", "address_starts_with_number",
             "transaction.address.address",
             _address_starts_with_number,
             when_present=True,
             description="Property address should start with a street number",
             severity="error"),

    FieldRule("R002", "no_orphan_dash_in_address",
             "transaction.address.address",
             _no_orphan_dash,
             when_present=True,
             description="No orphan dashes (space-dash-space followed by non-digit)",
             severity="error"),

    FieldRule("R003", "city_not_empty",
             "transaction.address.city",
             _city_not_empty,
             description="City should not be empty",
             severity="error"),

    # --- Transaction fields (metadata → warning) ---
    FieldRule("R004", "price_parseable",
             "transaction.sale_price",
             _price_parseable,
             when_present=True,
             description="Sale price should parse to a positive integer"),

    FieldRule("R005", "valid_iso_date",
             "transaction.sale_date_iso",
             _is_valid_iso_date,
             when_present=True,
             description="Sale date should be valid ISO format"),

    FieldRule("R006", "date_not_future",
             "transaction.sale_date_iso",
             _date_not_future,
             when_present=True,
             description="Sale date should not be in the future"),

    FieldRule("R007", "date_after_1990",
             "transaction.sale_date_iso",
             _date_after_1990,
             when_present=True,
             description="Sale date should be after 1990"),

    # --- Party fields (metadata → warning) ---
    FieldRule("R008", "seller_name_present",
             "transferor.name",
             _name_not_empty,
             description="Seller name should not be empty"),

    FieldRule("R009", "buyer_name_present",
             "transferee.name",
             _name_not_empty,
             description="Buyer name should not be empty"),

    FieldRule("R010", "seller_phone_format",
             "transferor.phone",
             _phone_format,
             when_present=True,
             description="Seller phone should contain at least 10 digits"),

    FieldRule("R011", "buyer_phone_format",
             "transferee.phone",
             _phone_format,
             when_present=True,
             description="Buyer phone should contain at least 10 digits"),

    FieldRule("R012", "no_html_in_seller_name",
             "transferor.name",
             _no_html_tags,
             when_present=True,
             description="No HTML tags in seller name",
             severity="error"),

    FieldRule("R013", "no_html_in_buyer_name",
             "transferee.name",
             _no_html_tags,
             when_present=True,
             description="No HTML tags in buyer name",
             severity="error"),

    # --- Type fields (metadata → warning) ---
    FieldRule("R014", "known_property_type",
             "property_type",
             _known_property_type,
             when_present=True,
             description="Property type should be a known Realtrack category"),

    FieldRule("R015", "known_transaction_type",
             "transaction.transaction_type",
             _known_transaction_type,
             when_present=True,
             description="Transaction type should be in the known types list"),

    # --- Site fields (metadata → warning) ---
    FieldRule("R016", "pin_format",
             "site.pins",
             _pin_format,
             when_present=True,
             description="PIN should match NNNNN-NNNN format"),

    FieldRule("R017", "site_area_positive",
             "site.site_area",
             _positive_number,
             when_present=True,
             description="Site area should be a positive number"),

    # --- Address quality (address-critical → error) ---
    FieldRule("R018", "no_html_in_address",
             "transaction.address.address",
             _no_html_tags,
             when_present=True,
             description="No HTML tags in address",
             severity="error"),

    FieldRule("R019", "postal_code_format",
             "transaction.address.postal_code",
             _postal_format,
             when_present=True,
             description="Postal code should match A9A 9A9 format"),
]

# Build lookup by rule_id
RULES_BY_ID = {r.rule_id: r for r in RULES}
