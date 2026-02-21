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

def parse_buyer_phone(soup):
    """
    Parse buyer phone number STRICTLY between Transferee(s) and Description/Site sections.
    Will ONLY search the text nodes between these two markers, not including the markers themselves.
    """
    result = {
        "BuyerPhone": ""
    }

    # Find the Transferee(s) tag
    transferee_font = soup.find('font', string=re.compile('Transferee\\(s\\)'))
    if not transferee_font:
        return result

    # Find boundary tags: prefer Description, fallback to Site (which is always present)
    description_font = soup.find('font', string=re.compile('Description'))
    site_font = soup.find('font', string=re.compile('Site'))
    boundary_font = description_font if description_font else site_font
    if not boundary_font:
        return result

    # Get the first br tag after Transferee(s)
    first_br = transferee_font.find_next('br')
    if not first_br:
        return result

    # CRUCIAL CHANGE: Look at the text node immediately after Transferee(s) br tag
    # This contains the buyer name AND potentially a phone number
    next_node = first_br.next_sibling
    if isinstance(next_node, NavigableString):
        # Split on multiple &nbsp; sequences
        parts = str(next_node).split('\xa0\xa0')
        # Check the last part for phone number
        if len(parts) > 1:
            last_part = parts[-1].strip()
            if is_phone_number(last_part):
                result["BuyerPhone"] = last_part
                return result
            phone = extract_phone_number(last_part)
            if phone:
                result["BuyerPhone"] = phone
                return result

    # If no phone on first line, continue searching until boundary
    current = first_br
    while current and current != boundary_font:
        if isinstance(current, NavigableString):
            text = str(current).strip()
            if is_phone_number(text):
                result["BuyerPhone"] = text
                break
            phone = extract_phone_number(text)
            if phone:
                result["BuyerPhone"] = phone
                break
        current = current.next_sibling

    return result 