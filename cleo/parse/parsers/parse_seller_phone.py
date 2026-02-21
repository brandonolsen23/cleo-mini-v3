import re
from bs4 import BeautifulSoup, NavigableString, Tag

def is_phone_number(text):
    """Check if text matches phone number pattern"""
    # Only match standard phone number formats
    pattern = r'^\s*(?:1-)?(?:\d{3}-|\(\d{3}\)\s?)\d{3}-\d{4}\s*$'
    return bool(re.match(pattern, text))

def extract_phone_number(text):
    """Extract phone number from text"""
    # Only match standard phone number formats
    pattern = r'(?:1-)?(?:\d{3}-|\(\d{3}\)\s?)\d{3}-\d{4}'
    match = re.search(pattern, text)
    return match.group(0) if match else ""

def parse_seller_phone(soup):
    """
    Parse seller phone number STRICTLY between Transferor(s) and Transferee(s) sections.
    Will ONLY search the text nodes between these two markers, not including the markers themselves.
    """
    result = {
        "SellerPhone": ""
    }

    # Find the Transferor(s) tag
    transferor_font = soup.find('font', string=re.compile('Transferor\\(s\\)'))
    if not transferor_font:
        return result

    # Find the Transferee(s) tag
    transferee_font = soup.find('font', string=re.compile('Transferee\\(s\\)'))
    if not transferee_font:
        return result

    # Get the first br tag after Transferor(s)
    first_br = transferor_font.find_next('br')
    if not first_br:
        return result

    # CRUCIAL CHANGE: Look at the text node immediately after Transferor(s) br tag
    # This contains the seller name AND potentially a phone number
    next_node = first_br.next_sibling
    if isinstance(next_node, NavigableString):
        # Split on multiple &nbsp; sequences
        parts = str(next_node).split('\xa0\xa0')
        # Check the last part for phone number
        if len(parts) > 1:
            last_part = parts[-1].strip()
            if is_phone_number(last_part):
                result["SellerPhone"] = last_part
                return result
            phone = extract_phone_number(last_part)
            if phone:
                result["SellerPhone"] = phone
                return result

    # If no phone on first line, continue searching until Transferee(s)
    current = first_br
    while current and current != transferee_font:
        if isinstance(current, NavigableString):
            text = str(current).strip()
            if is_phone_number(text):
                result["SellerPhone"] = text
                break
            phone = extract_phone_number(text)
            if phone:
                result["SellerPhone"] = phone
                break
        current = current.next_sibling

    return result
