"""Baseline HTML validation checks for Realtrack detail pages.

Each check tests ONE thing about the raw HTML source. These are source
truth checks — they tell us about the quality of the HTML itself, not
about parser behavior.

Every Realtrack detail page has a fixed structure:

    <div id="headerNav">...</div>
    <strong id="address">ADDRESS LINE(S)</strong>
    <br/>City : Municipality
    <br/>DD Mon YYYY      $PRICE      <font color="#CC0000">...</font>
    <p/>
    <p/><font color="#848484">Transferor(s)</font><br/>SELLER...
    <p/><font color="#848484">Transferee(s)</font><br/>BUYER...
    ...
    <font color="#848484">N / TOTAL      RTXXXXXX</font>
"""

import re
from typing import List

from bs4 import BeautifulSoup

# Patterns for header line extraction
DATE_PATTERN = re.compile(r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}")
PRICE_PATTERN = re.compile(r"\$[\d,]+")
RT_ID_PATTERN = re.compile(r"RT\d+")

# Flag definitions: (id, name, description)
FLAG_DEFS = {
    "H001": "TAG_MISSING — No <strong id='address'> tag found",
    "H002": "TAG_EMPTY — Address tag found but contains no text",
    "H003": "ADDRESS_NO_DIGIT — First address line does not start with a digit",
    "H004": "NO_TRANSFEROR — No Transferor(s) section found",
    "H005": "NO_TRANSFEREE — No Transferee(s) section found",
    "H006": "NO_CITY_MUNICIPALITY — No 'City : Municipality' line found",
    "H007": "NO_PRICE — No dollar amount found in header line",
    "H008": "NO_DATE — No date pattern found in header line",
    "H009": "NO_RT_ID — No RT ID found in last gray font tag",
    "H010": "NO_SITE — No Site section found",
    "H011": "NO_ARN — No Assessment Roll Number section found",
    "H012": "NO_DESCRIPTION — No Description section found",
    "H013": "NO_BROKER — No Broker/Agent section found",
    "H014": "NO_PHOTOS — No street or aerial photos found",
}


def check_html(html_content: str) -> List[str]:
    """Run all baseline HTML checks against a single detail page.

    Args:
        html_content: Raw HTML string from a Realtrack detail page.

    Returns:
        List of flag IDs that fired (empty list = clean record).
    """
    flags = []
    soup = BeautifulSoup(html_content, "lxml")

    # --- H001: Address tag exists ---
    addr_tag = soup.find("strong", id="address")
    if not addr_tag:
        flags.append("H001")
        # Can't check H002/H003 without the tag
    else:
        # --- H002: Address tag has content ---
        lines = [line.strip() for line in addr_tag.stripped_strings]
        if not lines:
            flags.append("H002")
        else:
            # --- H003: First line starts with a digit ---
            if not lines[0][0].isdigit():
                flags.append("H003")

    # --- H004: Transferor section exists ---
    transferor_found = False
    for font in soup.find_all("font", color="#848484"):
        if "Transferor" in font.get_text():
            transferor_found = True
            break
    if not transferor_found:
        flags.append("H004")

    # --- H005: Transferee section exists ---
    transferee_found = False
    for font in soup.find_all("font", color="#848484"):
        if "Transferee" in font.get_text():
            transferee_found = True
            break
    if not transferee_found:
        flags.append("H005")

    # --- H006, H007, H008: Header line (city, price, date) ---
    # The header line is the text between </strong> and the first <p> tag.
    # Structure: <br/>City : Municipality<br/>DD Mon YYYY   $PRICE
    if addr_tag:
        header_text = _extract_header_text(addr_tag)

        # H006: City : Municipality
        if " : " not in header_text:
            flags.append("H006")

        # H007: Price
        if not PRICE_PATTERN.search(header_text):
            flags.append("H007")

        # H008: Date
        if not DATE_PATTERN.search(header_text):
            flags.append("H008")

    # --- H009: RT ID in last gray font tag ---
    gray_fonts = soup.find_all("font", color="#848484")
    rt_found = False
    if gray_fonts:
        last_gray = gray_fonts[-1].get_text()
        if RT_ID_PATTERN.search(last_gray):
            rt_found = True
    if not rt_found:
        flags.append("H009")

    # --- H010–H014: Optional section presence ---
    section_texts = [f.get_text(strip=True) for f in gray_fonts]

    if not any(t == "Site" for t in section_texts):
        flags.append("H010")

    if not any("Assessment Roll Number" in t for t in section_texts):
        flags.append("H011")

    if not any(t == "Description" for t in section_texts):
        flags.append("H012")

    if not any("Broker" in t for t in section_texts):
        flags.append("H013")

    if not any("photos" in t.lower() for t in section_texts):
        flags.append("H014")

    return flags


def _extract_header_text(addr_tag) -> str:
    """Extract the header line text after the address tag.

    Walks siblings of <strong id="address"> collecting text until
    we hit a <p> tag (which marks the start of the next section).
    """
    parts = []
    for sibling in addr_tag.next_siblings:
        # Stop at first <p> tag
        if getattr(sibling, "name", None) == "p":
            break
        text = sibling.string if sibling.string else sibling.get_text() if hasattr(sibling, "get_text") else str(sibling)
        text = text.strip()
        if text:
            parts.append(text)
    return " ".join(parts)
