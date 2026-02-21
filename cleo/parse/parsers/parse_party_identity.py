"""
Enhanced party identity parser for RealTrack detail pages.
Extracts company names with aliases, officer titles, ASO (authorized signing officer),
contact information, and phone numbers for both buyers and sellers.
"""

import re
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag


# Officer title patterns
OFFICER_TITLE_PATTERNS = [
    re.compile(r"\b(president|ceo|chief\s*executive\s*officer)\b", re.IGNORECASE),
    re.compile(r"\b(vice\s*president|vp)\b", re.IGNORECASE),
    re.compile(r"\b(secretary|sec\.?)\b", re.IGNORECASE),
    re.compile(r"\b(treasurer|treas\.?)\b", re.IGNORECASE),
    re.compile(r"\b(director|dir\.?)\b", re.IGNORECASE),
    re.compile(r"\b(partner)\b", re.IGNORECASE),
    re.compile(r"\b(owner)\b", re.IGNORECASE),
    re.compile(r"\b(manager)\b", re.IGNORECASE),
    re.compile(r"\b(authorized\s*sign(?:ing)?\s*officer|aso)\b", re.IGNORECASE),
    re.compile(r"\b(signing\s*officer)\b", re.IGNORECASE),
    re.compile(r"\b(trustee)\b", re.IGNORECASE),
    re.compile(r"\b(executor|executrix)\b", re.IGNORECASE),
]

# Company suffix patterns
COMPANY_SUFFIXES = [
    r"\bINC\.?\b",
    r"\bINCORPORATED\b",
    r"\bLTD\.?\b",
    r"\bLIMITED\b",
    r"\bLLC\.?\b",
    r"\bLLP\.?\b",
    r"\bCORP\.?\b",
    r"\bCORPORATION\b",
    r"\bCO\.?\b",
    r"\bCOMPANY\b",
    r"\bHOLDINGS?\b",
    r"\bINVESTMENTS?\b",
    r"\bPROPERTIES?\b",
    r"\bREALTY\b",
    r"\bCAPITAL\b",
    r"\bENTERPRISES?\b",
    r"\bGROUP\b",
    r"\bPARTNERS?\b",
    r"\bTRUST\b",
    r"\bFUND\b",
    r"\bMANAGEMENT\b",
    r"\bDEVELOPMENTS?\b",
    r"\bSERVICES?\b",
]

# Common name patterns that indicate a person (not a company)
PERSON_NAME_PATTERNS = [
    re.compile(r"^\s*[A-Z][a-z]+\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)?$"),
]

# Phone pattern
PHONE_PATTERN = re.compile(
    r"(?:tel[:\s#]*|phone[:\s#]*|t\.?[:\s#]*)?"
    r"(?:\+?1[-.\s]?)?"
    r"[\(]?\d{3}[-.\s\)]?\d{3}[-.\s]?\d{4}"
    r"(?:\s*(?:ext|x|ex|extension)[:\s#]*\d+)?",
    re.IGNORECASE
)

# Attention patterns (includes officer title prefixes)
ATTN_PATTERN = re.compile(
    r"(?:attn[:\s#]*|attention[:\s#]*|c/o[:\s#]*|aso[:\s]+|pres[:\s]+|dir[:\s]+|vp[:\s]+|sec[:\s]+|treas[:\s]+|mgr[:\s]+|officer[:\s]+|trustee[:\s]+)",
    re.IGNORECASE
)


def looks_like_company(name: str) -> bool:
    """Check if a name looks like a company (has company suffixes)."""
    upper_name = name.upper()
    for suffix in COMPANY_SUFFIXES:
        if re.search(suffix, upper_name):
            return True
    # Firm-name pattern: "Surname(s) & Surname" — single word after &
    # Catches: "McElderry & Morris", "Goodman Phillips & Vineberg"
    # Skips person pairs: "Scott Bellinger & Henry Cheng" (multi-word after &)
    # Skips initials: "C. Grant & S. Poulton" (periods present)
    if "&" in name:
        parts = name.split("&")
        after = parts[-1].strip()
        before = parts[0].strip()
        if (after and " " not in after and "." not in after
                and before and "." not in before
                and re.match(r"[A-Za-z]", after)):
            return True
    return False


def looks_like_person(name: str) -> bool:
    """Check if a name looks like a person name."""
    # Check for person name patterns
    for pattern in PERSON_NAME_PATTERNS:
        if pattern.match(name):
            return True
    return False


def extract_officer_titles(text: str) -> List[str]:
    """Extract officer titles from text."""
    titles = []
    for pattern in OFFICER_TITLE_PATTERNS:
        matches = pattern.findall(text)
        for match in matches:
            if isinstance(match, tuple):
                titles.append(" ".join(m for m in match if m).strip())
            else:
                titles.append(match.strip())
    return sorted(set(titles))


def extract_phone_numbers(text: str) -> List[str]:
    """Extract phone numbers from text."""
    matches = PHONE_PATTERN.findall(text)
    phones = []
    for match in matches:
        # Clean up the phone number
        phone = re.sub(r"\s+", " ", match.strip())
        phone = re.sub(r"^[a-zA-Z]+[:\s#]*", "", phone, flags=re.IGNORECASE)
        if phone and len(phone.replace(" ", "").replace("-", "").replace(".", "").replace("(", "").replace(")", "")) >= 10:
            phones.append(phone)
    return sorted(set(phones))


def extract_attention_line(text: str) -> Optional[str]:
    """Extract attention/ATTN line."""
    match = ATTN_PATTERN.search(text)
    if match:
        # Get text after ATTN
        after = text[match.end():].strip()
        # Take first line or first comma-separated part
        lines = after.split("\n")
        if lines:
            attn = lines[0].strip()
            # Remove leading punctuation
            attn = re.sub(r"^[,:\s]+", "", attn)
            return attn
    return None


def parse_party_identity(
    soup: BeautifulSoup,
    party_type: str  # "buyer" or "seller"
) -> Dict:
    """
    Extract comprehensive party identity information.
    
    Args:
        soup: BeautifulSoup parsed HTML
        party_type: "buyer" or "seller"
    
    Returns:
        Dictionary with party identity information
    """
    if party_type.lower() == "buyer":
        header_pattern = re.compile(r"Transferee\(s\)", re.IGNORECASE)
        company_key = "BuyerStructuredCompanyLines"
        contact_key = "BuyerStructuredContactLines"
        address_key = "BuyerStructuredAddressLines"
        simple_field = "Buyer"
    else:
        header_pattern = re.compile(r"Transferor\(s\)", re.IGNORECASE)
        company_key = "SellerStructuredCompanyLines"
        contact_key = "SellerStructuredContactLines"
        address_key = "SellerStructuredAddressLines"
        simple_field = "Seller"
    
    # Find the party section
    header_tag = soup.find("font", string=header_pattern)
    if not header_tag:
        return {
            f"{party_type}_companies": [],
            f"{party_type}_contacts": [],
            f"{party_type}_phones": [],
            f"{party_type}_officer_titles": [],
            f"{party_type}_aliases": [],
            f"{party_type}_attention": "",
            f"{party_type}_raw_companies": [],
            f"{party_type}_raw_contacts": [],
        }
    
    # Collect structured lines
    company_lines = []
    contact_lines = []
    address_lines = []
    
    # Parse the section
    from .parse_buyer_structured import _collect_buyer_section_lines
    from .parse_seller_structured import _collect_seller_section_lines
    
    if party_type.lower() == "buyer":
        raw_lines = _collect_buyer_section_lines(soup)
    else:
        raw_lines = _collect_seller_section_lines(soup)
    
    # Classify lines
    for line in raw_lines:
        text = line[0] if isinstance(line, tuple) else line
        text = text.strip()
        if not text:
            continue
        
        # Skip phone numbers and ATTN at end of lines
        if PHONE_PATTERN.search(text):
            continue
        
        # Classify based on content
        if looks_like_company(text):
            company_lines.append(text)
        else:
            contact_lines.append(text)
    
    # Get simple field as fallback company
    simple_field_value = soup.find(text=re.compile(simple_field, re.IGNORECASE))
    if simple_field_value:
        parent = simple_field_value.find_parent("p")
        if parent:
            # Get text after the label
            parent_text = parent.get_text(" ", strip=True)
            match = re.search(rf"{simple_field}[:\s]*([^\n]+)", parent_text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value and looks_like_company(value):
                    company_lines.insert(0, value)
                elif value:
                    contact_lines.insert(0, value)
    
    # Extract phones from contact lines
    all_phones = []
    cleaned_contacts = []
    for line in contact_lines:
        phones = extract_phone_numbers(line)
        all_phones.extend(phones)
        # Remove phone from line
        clean_line = PHONE_PATTERN.sub("", line).strip()
        if clean_line:
            cleaned_contacts.append(clean_line)
    
    # Extract attention
    attention = extract_attention_line("\n".join(contact_lines))
    
    # Extract officer titles from all lines
    all_text = " ".join(company_lines + contact_lines)
    officer_titles = extract_officer_titles(all_text)
    
    # Generate aliases (simplified company name variations)
    aliases = []
    for company in company_lines[:5]:  # Limit to first 5
        # Add common variations
        upper = company.upper()
        # Remove common suffixes for potential matching
        for suffix in COMPANY_SUFFIXES:
            upper = re.sub(suffix, "", upper)
        cleaned = upper.strip()
        if cleaned and cleaned not in aliases:
            aliases.append(cleaned)
    
    return {
        f"{party_type}_companies": company_lines,
        f"{party_type}_contacts": cleaned_contacts,
        f"{party_type}_phones": all_phones,
        f"{party_type}_officer_titles": sorted(set(officer_titles)),
        f"{party_type}_aliases": aliases[:10],  # Max 10 aliases
        f"{party_type}_attention": attention or "",
        f"{party_type}_raw_companies": company_lines,
        f"{party_type}_raw_contacts": contact_lines,
    }


def parse_all_party_identities(soup: BeautifulSoup) -> Dict:
    """
    Parse both buyer and seller identities.
    
    Returns:
        Combined dictionary of buyer and seller identity information
    """
    buyer_identity = parse_party_identity(soup, "buyer")
    seller_identity = parse_party_identity(soup, "seller")
    
    return {**buyer_identity, **seller_identity}


if __name__ == "__main__":
    # Test with sample HTML
    import sys
    import json
    from pathlib import Path
    
    if len(sys.argv) > 1:
        html_path = Path(sys.argv[1])
        if html_path.exists():
            soup = BeautifulSoup(html_path.read_text(), "html.parser")
            identity = parse_all_party_identities(soup)
            print(json.dumps(identity, indent=2))
        else:
            print(f"File not found: {html_path}")
    else:
        print("Usage: python parse_party_identity.py <html_file>")
