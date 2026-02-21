import re
from typing import Tuple

POSTAL_CODE_PATTERN = re.compile(r"[A-Z]\d[A-Z]\s?\d[A-Z]\d", re.IGNORECASE)
CITY_LINE_PATTERN = re.compile(r"^[A-Za-z0-9 .'-]+,\s*[A-Za-z .'-]+$")
NUMBERED_COMPANY_PATTERN = re.compile(
    r"^\d{4,}\s+[A-Za-z0-9 .'-]+?(INC|LTD|CORP|CORPORATION|LIMITED)\b",
    re.IGNORECASE,
)
COMPANY_KEYWORDS = {
    "INC",
    "LIMITED",
    "LTD",
    "LLC",
    "LP",
    "LLP",
    "ULC",
    "ULC",
    "CORP",
    "CORPORATION",
    "COMPANY",
    "HOLDINGS",
    "HOLDING",
    "TRUST",
    "FUND",
    "PROPERTIES",
    "PROPERTY",
    "REALTY",
    "REIT",
    "PARTNERS",
    "PARTNERSHIP",
    "ENTERPRISES",
    "GROUP",
    "INVESTMENTS",
    "INVESTMENT",
    "CAPITAL",
    "CONTRACTOR",
    "CONTRACTORS",
    "MANAGEMENT",
    "DEVELOPMENT",
    "DEVELOPMENTS",
    "SERVICES",
    "COLLEGE",
    "SCHOOL",
    "ASSOCIATION",
    "CO",
    "CO.",
}
PROVINCE_KEYWORDS = {
    "ONTARIO",
    "QUEBEC",
    "ALBERTA",
    "BRITISH COLUMBIA",
    "MANITOBA",
    "SASKATCHEWAN",
    "NOVA SCOTIA",
    "NEW BRUNSWICK",
    "NEWFOUNDLAND",
    "PRINCE EDWARD ISLAND",
    "PEI",
    "NUNAVUT",
    "YUKON",
    "NORTHWEST TERRITORIES",
    "ON",
    "QC",
    "AB",
    "BC",
    "MB",
    "SK",
    "NS",
    "NB",
    "NL",
    "NT",
    "NU",
    "YT",
}
PROVINCE_KEYWORDS_LOWER = {keyword.lower() for keyword in PROVINCE_KEYWORDS}
PHONE_SUFFIX_PATTERN = re.compile(r"(?:\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4})$")
CARE_OF_PATTERN = re.compile(r"^(?:c[/\\0]\s*o|c\.\s*o\.|care\s+of)\s*[:\-]?\s*", re.IGNORECASE)
CONTACT_PREFIXES = (
    "attn:",
    "attention:",
    "pres:",
    "president:",
    "pres.:",
    "aso:",
    "asst:",
    "assistant:",
    "aso.:",
    "dir:",
    "vp:",
    "vp's:",
    "vp’s:",
    "vice president:",
    "officer:",
    "asst vp:",
    "assistant vp:",
    "ceo:",
    "cfo:",
    "coo:",
    "director:",
    "chair:",
    "chairman:",
)
ADDRESS_LEAD_KEYWORDS = (
    "suite",
    "suites",
    "ste",
    "unit",
    "units",
    "lvl",
    "level",
    "floor",
    "flr",
    "university",
    "building",
    "tower",
    "apt",
    "apartment",
)
ADDRESS_FOLLOWUP_KEYWORDS = (
    "building",
    "tower",
    "mall",
    "plaza",
    "block",
    "complex",
    "square",
    "terminal",
)


def normalize_line(text: str) -> str:
    cleaned = " ".join(text.replace("\xa0", " ").strip().split())
    cleaned = (
        cleaned.replace("c/0", "c/o")
        .replace("C/0", "C/O")
        .replace("C/0", "C/O")
    )
    return cleaned


def looks_like_company(text: str) -> bool:
    upper = text.upper()
    tokens = [token for token in re.split(r"[^A-Z0-9]+", upper) if token]
    if not tokens:
        return False
    for token in tokens:
        if token in COMPANY_KEYWORDS:
            return True
    # Firm-name pattern: "Surname(s) & Surname" — single word after &
    # Catches: "McElderry & Morris", "Goodman Phillips & Vineberg"
    # Skips person pairs: "Scott Bellinger & Henry Cheng" (multi-word after &)
    # Skips initials: "C. Grant & S. Poulton" (periods present)
    if "&" in text:
        parts = text.split("&")
        after = parts[-1].strip()
        before = parts[0].strip()
        if (after and " " not in after and "." not in after
                and before and "." not in before
                and re.match(r"[A-Za-z]", after)):
            return True
    return False


def looks_like_address(text: str) -> bool:
    lowered = text.lower()
    stripped = text.strip()
    if looks_like_company(text):
        return False
    if lowered.startswith("po box") or lowered.startswith("p.o box"):
        return True
    if lowered.startswith("box "):
        return True
    if NUMBERED_COMPANY_PATTERN.search(text):
        return False
    if text[:1].isdigit():
        return True
    if POSTAL_CODE_PATTERN.search(text):
        return True
    if CITY_LINE_PATTERN.match(stripped):
        return True
    if "," in stripped:
        parts = [p.strip() for p in stripped.split(",")]
        if len(parts) >= 2:
            has_location_hint = False
            for part in parts:
                if not part:
                    continue
                if any(ch.isdigit() for ch in part):
                    has_location_hint = True
                    break
                lowered_part = part.lower()
                if lowered_part in PROVINCE_KEYWORDS_LOWER:
                    has_location_hint = True
                    break
                if any(keyword in lowered_part for keyword in ADDRESS_FOLLOWUP_KEYWORDS):
                    has_location_hint = True
                    break
            if has_location_hint:
                return True
    for keyword in ADDRESS_LEAD_KEYWORDS:
        if lowered.startswith(keyword + " ") or lowered.startswith(keyword + "."):
            return True
    for keyword in ADDRESS_FOLLOWUP_KEYWORDS:
        if f" {keyword}" in lowered:
            return True
    for keyword in PROVINCE_KEYWORDS:
        if len(keyword) <= 3:
            pattern = rf"\b{re.escape(keyword)}\b"
            haystack = stripped
        else:
            pattern = rf"\b{re.escape(keyword.lower())}\b"
            haystack = lowered
        if re.search(pattern, haystack):
            if "," in stripped or any(ch.isdigit() for ch in stripped) or len(stripped.split()) > 1:
                return True
    return False


def looks_like_plain_name(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if "," in stripped:
        return False
    if any(char.isdigit() for char in stripped):
        return False
    lowered = stripped.lower()
    if lowered.startswith(("po box", "p.o box", "suite", "unit", "floor", "flr", "ste", "apt")):
        return False
    return True


def strip_contact_prefix(text: str) -> Tuple[bool, str]:
    lowered = text.lower()
    for prefix in CONTACT_PREFIXES:
        if lowered.startswith(prefix):
            return True, text[len(prefix):].strip()
    return False, text


def strip_care_of(text: str) -> Tuple[bool, str]:
    match = CARE_OF_PATTERN.match(text.strip())
    if not match:
        return False, text
    return True, text[match.end():].strip()


def strip_trailing_phone(text: str) -> Tuple[str, bool]:
    match = PHONE_SUFFIX_PATTERN.search(text)
    if match:
        return text[:match.start()].strip(), True
    return text, False


def address_priority(text: str) -> int:
    stripped = text.strip()
    lowered = stripped.lower()
    if stripped[:1].isdigit():
        return 0
    if lowered.startswith("po box") or lowered.startswith("p.o box"):
        return 0
    for keyword in ADDRESS_LEAD_KEYWORDS:
        if lowered.startswith(keyword + " ") or lowered.startswith(keyword + "."):
            return 1
    # Named buildings/towers precede numbered street addresses
    for keyword in ("building", "tower"):
        if keyword in lowered:
            return -1
    return 2
