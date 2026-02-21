import re
from bs4 import BeautifulSoup, NavigableString, Tag

def is_postal_code(text):
    """Check if text matches Canadian postal code pattern"""
    return bool(re.match(r'^[A-Z]\d[A-Z]\s*\d[A-Z]\d$', text.strip()))

def is_city_province(text):
    """Check if text matches city, province pattern"""
    provinces = (
        'Ontario|ON|Quebec|QC|Alberta|AB|British Columbia|BC|Manitoba|MB|'
        'New Brunswick|NB|Newfoundland|NL|Nova Scotia|NS|Saskatchewan|SK|'
        'Prince Edward Island|PE|Northwest Territories|NT|Nunavut|NU|Yukon|YT'
    )
    return bool(re.match(rf'^[A-Za-z\s]+,\s*(?:{provinces})$', text.strip()))

def is_address(text):
    """Check if text looks like an address component - used by parse_seller_alternate_names.py"""
    text = text.strip()
    # Check for postal code
    if is_postal_code(text):
        return True
    # Check for city, province
    if is_city_province(text):
        return True
    # Check for street number pattern
    if bool(re.match(r'^\d+\s+[A-Za-z\s]+', text)):
        return True
    # Check for unit/suite pattern
    if bool(re.match(r'^(?:Unit|Suite|Ste|Floor|Flr)\s+\d+', text, re.IGNORECASE)):
        return True
    return False

def parse_seller_address(soup):
    """Get text between seller name and Transferee(s)"""
    result = {"SellerAddress": ""}
    
    # Find the transferor and transferee tags
    transferor_font = soup.find('font', {'color': '#848484'}, string=re.compile('Transferor\\(s\\)'))
    transferee_font = soup.find('font', {'color': '#848484'}, string=re.compile('Transferee\\(s\\)'))
    if not transferor_font or not transferee_font:
        return result

    # Find postal code between transferor and transferee
    current = transferor_font
    while current:
        current = current.next_element
        # Stop if we hit the transferee section
        if current == transferee_font:
            break
            
        if isinstance(current, NavigableString) and is_postal_code(current.strip()):
            # Found postal code, collect lines backwards until p tag
            lines = [current.strip()]
            prev = current.previous_element
            
            while prev and prev != transferor_font:
                if isinstance(prev, Tag) and prev.name == 'p':
                    break
                    
                if isinstance(prev, NavigableString) and prev.strip():
                    lines.insert(0, prev.strip())
                    
                prev = prev.previous_element
                
            if lines:
                # Strip leading non-address lines (names, officer titles)
                # but keep c/o and PO Box lines for downstream processing
                while len(lines) > 1:
                    first = lines[0].strip()
                    has_digits = any(char.isdigit() for char in first)
                    lower_first = first.lower()
                    is_mail_line = lower_first.startswith("po box") or lower_first.startswith("p.o") or lower_first.startswith("c/o")
                    if has_digits or is_mail_line:
                        break
                    lines.pop(0)
                result["SellerAddress"] = ", ".join(lines)
            break

    return result
