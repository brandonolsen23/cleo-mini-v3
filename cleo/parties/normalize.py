"""Name and address normalization for party clustering."""

import re


# Company suffixes to strip for alias/display purposes only — NOT for clustering
_SUFFIX_RE = re.compile(
    r"\s*\b(?:INC|INCORPORATED|LTD|LIMITED|CORP|CORPORATION|CO|COMPANY|LLC|LLP|LP|ULC)\b\.?\s*$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Brand token extraction
# ---------------------------------------------------------------------------

# Multi-word brands that would be destroyed by generic word removal
_BRAND_PRESERVES = {
    "CANADIAN TIRE", "HOME DEPOT", "HOME HARDWARE", "BANK OF MONTREAL",
    "BANK OF NOVA SCOTIA", "FIRST CAPITAL", "FIRST NATIONAL", "CREDIT UNION",
}

# Words that are generic business descriptors, not brand-distinctive
_GENERIC_WORDS = {
    # Legal (belt-and-suspenders — _SUFFIX_RE handles most, but some slip through)
    "INC", "INCORPORATED", "LTD", "LIMITED", "CORP", "CORPORATION",
    "CO", "COMPANY", "LLC", "LLP", "LP", "ULC",
    # Business type
    "HOLDINGS", "HOLDING", "PROPERTIES", "PROPERTY", "REALTY",
    "INVESTMENTS", "INVESTMENT", "MANAGEMENT", "DEVELOPMENTS", "DEVELOPMENT",
    "ENTERPRISES", "ASSOCIATES", "PARTNERSHIP", "PARTNERS", "GROUP",
    "CAPITAL", "CONSTRUCTION", "SERVICES", "SOLUTIONS", "CONSULTING",
    "VENTURES", "BUILDERS", "FINANCIAL", "MORTGAGE", "TRUST", "REIT",
    "PORTFOLIO", "LEASING", "COMMERCIAL", "RETAIL", "SHOPPING",
    "CENTRE", "CENTRES", "CENTER", "CENTERS", "MALL", "PLAZA",
    "LAND", "ESTATES", "ESTATE", "INDUSTRIES", "INTERNATIONAL",
    "NATIONAL", "GLOBAL", "WORLDWIDE", "ACQUISITIONS", "ACQUISITION",
    "EQUITIES", "EQUITY", "OPERATING", "OPERATIONS",
    # Deal structure
    "GP", "SUBCO", "HOLDCO", "REALCO",
    # Geographic
    "ONTARIO", "CANADA", "CANADIAN",
    # Filler
    "THE", "OF", "AND", "NO", "A",
    # Insurance / financial
    "INSURANCE", "ASSURANCE", "LIFE", "SECURITY", "SECURITIES",
    # Ordinals
    "I", "II", "III", "IV", "V",
}

_PAREN_RE = re.compile(r"\s*\(.*?\)\s*")
_ADDRESS_PATTERN_RE = re.compile(r"^\d+\s+[A-Z]")
_TRAILING_NUMBERS_RE = re.compile(r"\s+\d+$")


def extract_brand_token(name: str) -> str | None:
    """Extract the distinctive brand portion of a company name.

    Returns the uppercased brand token, or None if the name is a numbered
    company, address-pattern SPV, or reduces to nothing distinctive.
    """
    if not name:
        return None

    # 1. Strip parenthetical content
    s = _PAREN_RE.sub(" ", name)

    # 2. Strip legal suffixes (up to 3 passes for stacked suffixes)
    for _ in range(3):
        prev = s
        s = _SUFFIX_RE.sub("", s)
        if s == prev:
            break

    # 3. Uppercase and clean
    s = s.upper().strip()
    s = re.sub(r"\s+", " ", s)

    # 4. Check for preserved multi-word brands BEFORE generic word removal
    for brand in _BRAND_PRESERVES:
        if brand in s:
            return brand

    # 5. Strip "REAL ESTATE" as a phrase
    s = s.replace("REAL ESTATE", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # 6. Remove generic words
    words = s.split()
    distinctive = [w for w in words if w not in _GENERIC_WORDS]
    s = " ".join(distinctive).strip()

    # 7. Strip trailing numbers (SPV identifiers)
    s = _TRAILING_NUMBERS_RE.sub("", s).strip()

    # 8. Strip leading "THE"
    if s.startswith("THE "):
        s = s[4:].strip()

    # 9. Reject: empty, <3 chars, purely numeric, address patterns
    if not s or len(s) < 3:
        return None
    if s.replace(" ", "").isdigit():
        return None
    if _ADDRESS_PATTERN_RE.match(s):
        return None

    return s

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
