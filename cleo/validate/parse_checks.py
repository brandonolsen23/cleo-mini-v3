"""Parse-level validation checks for structured JSON output.

Each check tests ONE thing about the parsed data. These complement the
HTML-level checks (H-flags) by verifying that the parsers extracted data
correctly from valid HTML.

Adding a new flag:
    1. Add an entry to PARSE_FLAG_DEFS
    2. Add a check function to _CHECKS
    3. Re-run: cleo parse-check
"""

from typing import Any, Callable, Dict, List


# Flag definitions: id → short description
PARSE_FLAG_DEFS = {
    "P001": "MISSING_ADDRESS — No address extracted",
    "P002": "MISSING_PRICE — No sale price extracted",
    "P003": "MISSING_DATE — No sale date extracted",
    "P004": "MISSING_SELLER — No seller name extracted",
    "P005": "MISSING_BUYER — No buyer name extracted",
    "P006": "MISSING_CITY — No city extracted",
    "P007": "SELLER_PHONE_TYPE — Seller phone is dict, not string",
    "P008": "BUYER_PHONE_TYPE — Buyer phone is dict, not string",
    "P009": "SELLER_ADDRESS_TYPE — Seller address is dict, not string",
    "P010": "BUYER_ADDRESS_TYPE — Buyer address is dict, not string",
}


# ---------------------------------------------------------------------------
# Individual check functions
# Each takes a parsed JSON dict, returns True if the flag should fire.
# ---------------------------------------------------------------------------

def _p001(data: Dict) -> bool:
    """No address extracted."""
    return not data.get("transaction", {}).get("address", {}).get("address", "").strip()


def _p002(data: Dict) -> bool:
    """No sale price."""
    return not data.get("transaction", {}).get("sale_price", "").strip()


def _p003(data: Dict) -> bool:
    """No sale date."""
    return not data.get("transaction", {}).get("sale_date", "").strip()


def _p004(data: Dict) -> bool:
    """No seller name."""
    return not data.get("transferor", {}).get("name", "").strip()


def _p005(data: Dict) -> bool:
    """No buyer name."""
    return not data.get("transferee", {}).get("name", "").strip()


def _p006(data: Dict) -> bool:
    """No city."""
    return not data.get("transaction", {}).get("address", {}).get("city", "").strip()


def _p007(data: Dict) -> bool:
    """Seller phone is dict instead of string."""
    return isinstance(data.get("transferor", {}).get("phone"), dict)


def _p008(data: Dict) -> bool:
    """Buyer phone is dict instead of string."""
    return isinstance(data.get("transferee", {}).get("phone"), dict)


def _p009(data: Dict) -> bool:
    """Seller address is dict instead of string."""
    return isinstance(data.get("transferor", {}).get("address"), dict)


def _p010(data: Dict) -> bool:
    """Buyer address is dict instead of string."""
    return isinstance(data.get("transferee", {}).get("address"), dict)


# Registry: flag_id → check function
_CHECKS: Dict[str, Callable[[Dict], bool]] = {
    "P001": _p001,
    "P002": _p002,
    "P003": _p003,
    "P004": _p004,
    "P005": _p005,
    "P006": _p006,
    "P007": _p007,
    "P008": _p008,
    "P009": _p009,
    "P010": _p010,
}


def check_parsed(data: Dict) -> List[str]:
    """Run all parse-level checks against a single parsed record.

    Args:
        data: Parsed JSON dict (from a single RT file).

    Returns:
        List of flag IDs that fired (empty = clean record).
    """
    flags = []
    for flag_id, check_fn in _CHECKS.items():
        if check_fn(data):
            flags.append(flag_id)
    return flags
