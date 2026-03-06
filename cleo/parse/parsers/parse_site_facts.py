"""
Enhanced site/facts parser for RealTrack detail pages.
Extracts legal descriptions, PIN, acreage, frontage, zoning, and other site-level facts.
"""

import re
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag


# Zoning pattern variations
ZONING_PATTERNS = [
    re.compile(r"(?:zoning|zoned|zoning:?)\s*[:\-]?\s*([A-Z0-9\-]+)", re.IGNORECASE),
    re.compile(r"([A-Z]{1,3})\s*zone", re.IGNORECASE),
    re.compile(r"zone\s*[:\-]?\s*([A-Z0-9\-]+)", re.IGNORECASE),
]

# Frontage patterns
FRONTAGE_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:ft\.?|feet|foot)\s*(?:of\s*)?frontage", re.IGNORECASE),
    re.compile(r"frontage\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*(?:ft\.?|feet|foot)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:ft\.?|feet|foot)\s*(?:front|frontage|wid(?:th|e?))", re.IGNORECASE),
]

# Depth patterns
DEPTH_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:ft\.?|feet|foot)\s*(?:of\s*)?depth", re.IGNORECASE),
    re.compile(r"depth\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*(?:ft\.?|feet|foot)", re.IGNORECASE),
]

# Acreage patterns (more comprehensive than parse_site.py)
ACREAGE_PATTERNS = [
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:acres?|ac\.|acreage)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:ha|hectares?)", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:sq\.?\s*ft\.?|square\s*feet)", re.IGNORECASE),
    re.compile(r"(\d+(?:\.\d+)?)\s*(?:sq\.?\s*m\.?|square\s*meters?)", re.IGNORECASE),
]

# Legal description patterns
LEGAL_DESC_PATTERNS = [
    re.compile(r"(?:legal|legal\s*description)[:\s]*([^\n]+(?:\n[^\n]+){0,3})", re.IGNORECASE),
    re.compile(r"(?:part\s*(?:of\s*)?(?:lot|block|pid|pin)|lot\s*\d+[,\s]*plan\s*\d+[^\n]*)", re.IGNORECASE),
    re.compile(r"(?:pid|pin)[:\s]*(\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{3})", re.IGNORECASE),
]

# PIN patterns (more comprehensive)
PIN_PATTERNS = [
    re.compile(r"(?:pin|pid)[:\s#]*(\d{5}-\d{4})", re.IGNORECASE),  # RT format: PIN: 71180-0090
    re.compile(r"\b(\d{5}-\d{4})\b"),                                 # bare 5-4 format
    re.compile(r"\b(\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{3})\b"),
    re.compile(r"(?:pin|pid)[:\s#]*(\d{9,10})", re.IGNORECASE),
    re.compile(r"\b(\d{2}\s*\d{2}\s*\d{2}\s*\d{3}[-\s]?\d{4})\b"),
]

# ARN patterns
ARN_PATTERNS = [
    re.compile(r"\b(\d{4}[-\s]?\d{4}[-\s]?\d{4})\b"),
    re.compile(r"(?:arn|assessment\s*roll\s*number)[:\s#]*(\d+)", re.IGNORECASE),
]


def extract_zoning(soup: BeautifulSoup) -> str:
    """Extract zoning information from the page."""
    # Search in Description section first
    desc_tag = soup.find("font", string=re.compile(r"Description", re.IGNORECASE))
    if desc_tag:
        parent = desc_tag.find_parent("p")
        if parent:
            text = parent.get_text(" ", strip=True)
            for pattern in ZONING_PATTERNS:
                match = pattern.search(text)
                if match:
                    return match.group(1).strip().upper()
    
    # Search in Site section
    site_tag = soup.find("font", string=re.compile(r"Site", re.IGNORECASE))
    if site_tag:
        parent = site_tag.find_parent("p")
        if parent:
            text = parent.get_text(" ", strip=True)
            for pattern in ZONING_PATTERNS:
                match = pattern.search(text)
                if match:
                    return match.group(1).strip().upper()
    
    return ""


def extract_frontage(soup: BeautifulSoup) -> Tuple[str, str]:
    """Extract frontage measurement (value, units)."""
    # Search in Site section
    site_tag = soup.find("font", string=re.compile(r"Site", re.IGNORECASE))
    if site_tag:
        parent = site_tag.find_parent("p")
        if parent:
            text = parent.get_text(" ", strip=True)
            for pattern in FRONTAGE_PATTERNS:
                match = pattern.search(text)
                if match:
                    return match.group(1), "feet"
    
    # Search in Description section
    desc_tag = soup.find("font", string=re.compile(r"Description", re.IGNORECASE))
    if desc_tag:
        parent = desc_tag.find_parent("p")
        if parent:
            text = parent.get_text(" ", strip=True)
            for pattern in FRONTAGE_PATTERNS:
                match = pattern.search(text)
                if match:
                    return match.group(1), "feet"
    
    return "", ""


def extract_depth(soup: BeautifulSoup) -> Tuple[str, str]:
    """Extract depth measurement (value, units)."""
    site_tag = soup.find("font", string=re.compile(r"Site", re.IGNORECASE))
    if site_tag:
        parent = site_tag.find_parent("p")
        if parent:
            text = parent.get_text(" ", strip=True)
            for pattern in DEPTH_PATTERNS:
                match = pattern.search(text)
                if match:
                    return match.group(1), "feet"
    
    return "", ""


def extract_acreage(soup: BeautifulSoup) -> Tuple[str, str]:
    """Extract acreage or total site area."""
    site_tag = soup.find("font", string=re.compile(r"Site", re.IGNORECASE))
    if site_tag:
        parent = site_tag.find_parent("p")
        if parent:
            text = parent.get_text(" ", strip=True)
            
            # Try acres first
            for pattern in ACREAGE_PATTERNS[:2]:  # acres patterns
                match = pattern.search(text)
                if match:
                    return match.group(1), "acres"
            
            # Try square feet
            match = ACREAGE_PATTERNS[2].search(text)
            if match:
                sq_ft = float(match.group(1))
                acres = sq_ft / 43560
                return f"{acres:.4f}", "acres"
            
            # Try square meters
            match = ACREAGE_PATTERNS[3].search(text)
            if match:
                sq_m = float(match.group(1))
                acres = sq_m * 0.000247105
                return f"{acres:.4f}", "acres"
    
    return "", ""


_LEGAL_STOP = re.compile(
    r"^(?:PIN|P\.I\.N|Assessment Roll|ARN|A\.R\.N|\d+(?:\.\d+)?\s*acre"
    r"|\d+(?:,\d{3})*\s*(?:sq\.?\s*ft|sf)|[NSEW]\s*side\s|[NSEW]/[SN])",
    re.IGNORECASE,
)


def extract_legal_description(soup: BeautifulSoup) -> str:
    """Extract legal description from the Site section.

    Walks text nodes after the Site header, collecting lines until a
    PIN, acreage, location, or ARN line is reached.  Works whether the
    Site <font> is inside a <p> or a direct child of <body>.
    """
    site_tag = soup.find("font", string=re.compile(r"^Site$", re.IGNORECASE))
    if not site_tag:
        return ""

    lines: list[str] = []
    node = site_tag.next_element
    while node:
        # Stop at next section header
        if isinstance(node, Tag) and node.name == "font":
            label = node.get_text(strip=True)
            if label and label != "Site":
                break

        if isinstance(node, NavigableString):
            text = node.strip()
            if text and text != "Site":
                # Stop if this looks like a non-legal-desc line
                if _LEGAL_STOP.match(text):
                    break
                lines.append(text)

        node = node.next_element

    result = " ".join(lines).strip()
    if len(result) > 500:
        result = result[:500] + "..."
    return result


def extract_pins(soup: BeautifulSoup) -> List[str]:
    """Extract all PINs from the page."""
    pins = set()
    
    # Search in PIN section
    pin_tag = soup.find("font", string=re.compile(r"P\.?I\.?N\.?", re.IGNORECASE))
    if pin_tag:
        parent = pin_tag.find_parent("p")
        if parent:
            text = parent.get_text(" ", strip=True)
            for pattern in PIN_PATTERNS:
                for match in pattern.finditer(text):
                    pin = match.group(1).replace("-", "").replace(" ", "")
                    if 9 <= len(pin) <= 10:
                        pins.add(pin)
    
    # Also search entire page for PINs
    page_text = soup.get_text(" ", strip=True)
    for pattern in PIN_PATTERNS:
        for match in pattern.finditer(page_text):
            pin = match.group(1).replace("-", "").replace(" ", "")
            if 9 <= len(pin) <= 10:
                pins.add(pin)
    
    return list(pins)


def extract_arn(soup: BeautifulSoup) -> str:
    """Extract ARN from the page.

    Handles both "ARN" and "Assessment Roll Number" labels, and ARN
    values with spaces (e.g. '19 08 013 320 00750').
    """
    # Find the ARN/Assessment Roll Number header
    arn_tag = soup.find("font", string=re.compile(
        r"(?:A\.?R\.?N\.?|Assessment\s*Roll\s*Number)", re.IGNORECASE
    ))
    if arn_tag:
        # Walk text nodes after the header to find the ARN value
        node = arn_tag.next_element
        while node:
            if isinstance(node, Tag) and node.name == "font":
                # Hit next section header
                label = node.get_text(strip=True)
                if label and not re.match(r"(?:ARN|Assessment)", label, re.IGNORECASE):
                    break
            if isinstance(node, NavigableString):
                text = node.strip()
                # Skip the header label itself
                if text and not re.match(r"(?:ARN|Assessment\s*Roll)", text, re.IGNORECASE):
                    # Extract digits (possibly separated by spaces/dashes)
                    digits = re.sub(r"[\s\-]", "", text)
                    if re.match(r"^\d{12,20}$", digits):
                        return digits
            node = node.next_element

    return ""


def extract_site_facts(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Comprehensive site facts extraction.
    
    Returns:
        Dictionary with:
        - site_area: Total acreage
        - site_area_units: Units (acres, hectares, sq ft)
        - site_frontage: Frontage measurement
        - site_frontage_units: feet
        - site_depth: Depth measurement  
        - site_depth_units: feet
        - zoning: Zoning designation
        - legal_description: Legal description text
        - pins: List of PINs (comma-separated)
        - arn: Assessment Roll Number
    """
    return {
        "site_area": extract_acreage(soup)[0],
        "site_area_units": extract_acreage(soup)[1],
        "site_frontage": extract_frontage(soup)[0],
        "site_frontage_units": extract_frontage(soup)[1],
        "site_depth": extract_depth(soup)[0],
        "site_depth_units": extract_depth(soup)[1],
        "zoning": extract_zoning(soup),
        "legal_description": extract_legal_description(soup),
        "pins": ", ".join(extract_pins(soup)),
        "arn": extract_arn(soup),
    }


if __name__ == "__main__":
    # Test with sample HTML
    import sys
    from pathlib import Path
    
    if len(sys.argv) > 1:
        html_path = Path(sys.argv[1])
        if html_path.exists():
            soup = BeautifulSoup(html_path.read_text(), "html.parser")
            facts = extract_site_facts(soup)
            import json
            print(json.dumps(facts, indent=2))
        else:
            print(f"File not found: {html_path}")
    else:
        print("Usage: python parse_site_facts.py <html_file>")
