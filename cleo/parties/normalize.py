"""Name and address normalization for party clustering."""

import re


# Company suffixes to strip for alias/display purposes only — NOT for clustering
_SUFFIX_RE = re.compile(
    r"\s*\b(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|LLC|LLP|LP|ULC)\b\.?\s*$",
    re.IGNORECASE,
)

# Common address abbreviations
_ADDR_ABBREVS = [
    (re.compile(r"\bSTE\b\.?", re.I), "SUITE"),
    (re.compile(r"\bST\b\.?(?!\s)", re.I), "STREET"),
    (re.compile(r"\bAVE\b\.?", re.I), "AVENUE"),
    (re.compile(r"\bBLVD\b\.?", re.I), "BOULEVARD"),
    (re.compile(r"\bDR\b\.?", re.I), "DRIVE"),
    (re.compile(r"\bRD\b\.?", re.I), "ROAD"),
    (re.compile(r"\bCRT\b\.?", re.I), "COURT"),
    (re.compile(r"\bCRES\b\.?", re.I), "CRESCENT"),
    (re.compile(r"\bPL\b\.?", re.I), "PLACE"),
    (re.compile(r"\bPKWY\b\.?", re.I), "PARKWAY"),
]


def normalize_name(name: str) -> str:
    """Normalize a party name for clustering.

    Uppercase, collapse whitespace, strip trailing punctuation.
    Does NOT strip INC/LTD/CORP — conservative matching.
    """
    s = name.upper().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:")
    return s


def normalize_address(address: str) -> str:
    """Normalize an address for clustering.

    Uppercase, collapse whitespace, normalize common abbreviations.
    """
    s = address.upper().strip()
    s = re.sub(r"\s+", " ", s)
    for pattern, replacement in _ADDR_ABBREVS:
        s = pattern.sub(replacement, s)
    return s


def normalize_phone(phone: str) -> str:
    """Strip to digits only for comparison."""
    return re.sub(r'\D', '', phone)


def normalize_contact(contact: str) -> str:
    """Normalize a contact name for grouping. Uppercase, collapse whitespace."""
    s = contact.upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def make_alias(name: str) -> str:
    """Strip company suffixes to create a short alias for display."""
    s = name.strip()
    s = _SUFFIX_RE.sub("", s)
    s = s.rstrip(".,;: ")
    return s
