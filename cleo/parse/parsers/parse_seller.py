import re
from bs4 import BeautifulSoup, NavigableString, Tag

def parse_seller(soup):
    """
    Parse only the Seller field - the text that appears immediately after the Transferor(s) tag and br.
    The Seller field ends at the first occurrence of any HTML element, tag, or entity.
    """
    result = {
        "Seller": "",
        "SellerContact": "",
    }
    
    # Find the Transferor(s) tag
    seller_tag = soup.find('font', string=re.compile('Transferor\\(s\\)'))
    if not seller_tag:
        return result

    # Get the first br tag after Transferor(s)
    br_tag = seller_tag.find_next('br')
    if not br_tag:
        return result

    # Get only the immediate text node after the br tag
    next_element = br_tag.next_element
    if isinstance(next_element, NavigableString):
        # Split on &nbsp; and take only the first part
        text = str(next_element)
        parts = text.split('\xa0')  # \xa0 is the unicode character for &nbsp;
        result["Seller"] = parts[0].strip() if parts else ""

    # Find the Transferee(s) tag to establish boundary
    transferee_tag = soup.find('font', string=re.compile('Transferee\\(s\\)'))
    if not transferee_tag:
        return result

    current = seller_tag.next_element
    while current:
        if current == transferee_tag:
            break

        if isinstance(current, NavigableString):
            text = str(current).strip()
            if text:
                lowered = text.lower()
                contact_text = ""
                if lowered.startswith('attn:'):
                    contact_text = text.split(':', 1)[1].strip()
                elif lowered.startswith('c/o'):
                    contact_text = text.split(None, 1)[1].strip() if ' ' in text else ""

                if contact_text and not result["SellerContact"]:
                    result["SellerContact"] = contact_text

        current = current.next_element

    return result
