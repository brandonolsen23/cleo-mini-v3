"""Shared text normalization utilities.

Migrated from cleo/parties/normalize.py and cleo/parties/registry.py
during the anchor layer cleanup (2026-03-05).
"""

import re

# ── Address abbreviation expansions ──────────────────────────────────

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

# ── Company name detection ───────────────────────────────────────────

_COMPANY_INDICATORS = re.compile(
    r"\b(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|LLC|LLP|LP|ULC"
    r"|TRUST|REIT|HOLDINGS|PROPERTIES|REAL ESTATE|INVESTMENTS|MANAGEMENT"
    r"|DEVELOPMENT|DEVELOPMENTS|ENTERPRISES|ASSOCIATES|PARTNERSHIP|PARTNERS"
    r"|GROUP|CAPITAL|REALTY|CONSTRUCTION|SERVICES|SOLUTIONS|CONSULTING"
    r"|VENTURES|BUILDERS|FINANCIAL|MORTGAGE|BANK|CREDIT UNION"
    r"|ONTARIO|CANADA|NAMED INDIVIDUAL"
    r"|INDUSTRIES|FOUNDATION|INSTITUTE|SOCIETY|COUNCIL|AUTHORITY|MINISTRY"
    r"|COMMISSION|BUREAU|AGENCY|GUILD|LEAGUE|FEDERATION|ASSOCIATION|MUSEUM"
    r"|LIBRARY|HOSPITAL|CLINIC|COOPERATIVE|CO-OP|COOP"
    r"|SCHOOL|COLLEGE|UNIVERSITY|ACADEMY"
    r"|CHURCH|TEMPLE|CENTRE|CENTER|BAPTIST|BUDDHIST|CHRISTIAN|CATHOLIC"
    r"|ISLAMIC|JEWISH|LUTHERAN|PRESBYTERIAN|PENTECOSTAL|METHODIST|EVANGELICAL"
    r"|BV|AG|GMBH|SA|SAS|SPRL|NV|PLC|PTY|SARL|OY|AB"
    r"|PLAZA|MALL|MARKET|STORE|STORES|RESTAURANT|HOTEL|MOTEL"
    r"|INTERNATIONAL|NATIONAL|GLOBAL|WORLDWIDE)\b",
    re.IGNORECASE,
)

_NUMBER_COMPANY_RE = re.compile(r"^\d{4,}")


# ── Public functions ─────────────────────────────────────────────────


def normalize_name(name: str) -> str:
    """Normalize a name for matching.

    Uppercase, collapse whitespace, strip trailing punctuation.
    Does NOT strip INC/LTD/CORP — conservative matching.
    """
    s = name.upper().strip()
    s = re.sub(r"\s+", " ", s)
    s = s.rstrip(".,;:")
    return s


def normalize_address(address: str) -> str:
    """Normalize an address for matching.

    Uppercase, collapse whitespace, expand common abbreviations.
    """
    s = address.upper().strip()
    s = re.sub(r"\s+", " ", s)
    for pattern, replacement in _ADDR_ABBREVS:
        s = pattern.sub(replacement, s)
    return s


def normalize_contact(contact: str) -> str:
    """Normalize a contact name for matching. Uppercase, collapse whitespace."""
    s = contact.upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def is_company_name(name: str) -> bool:
    """Heuristic: is this name a company rather than a person?"""
    if not name:
        return True
    if _COMPANY_INDICATORS.search(name):
        return True
    if _NUMBER_COMPANY_RE.match(name):
        return True
    words = name.split()
    if len(words) < 2 or len(words) > 3:
        return True
    if any(c.isdigit() for c in name):
        return True
    return False
