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

def get_dom_position(node):
    """
    Get the position of a node in document order.
    This can be used to check if one node appears before another.
    """
    return list(node.parent.children).index(node) if node.parent else -1
    
def is_at_or_past_boundary(current, boundary_node, boundary_position):
    """
    Check if the current node is at or past the boundary node.
    This is a robust check that considers DOM structure.
    """
    # Direct match with boundary
    if current == boundary_node:
        return True
        
    # Check if current contains the boundary (is a parent/ancestor)
    if isinstance(current, Tag) and boundary_node in current.descendants:
        return True
        
    # Check if current is a sibling after the boundary
    if current.parent == boundary_node.parent:
        current_position = get_dom_position(current)
        if current_position >= boundary_position:
            return True
            
    # Check if any parent of current is a sibling after the boundary's parent
    parent = current.parent
    while parent:
        if parent == boundary_node.parent:
            break
        if parent.parent == boundary_node.parent.parent:
            parent_pos = get_dom_position(parent)
            boundary_parent_pos = get_dom_position(boundary_node.parent)
            if parent_pos > boundary_parent_pos:
                return True
        parent = parent.parent
        
    return False

def parse_buyer_address(soup):
    """Get buyer address located after the Transferee(s) tag and before Description or Site"""
    result = {"BuyerAddress": ""}
    
    # Find the transferee tag
    transferee_font = soup.find('font', {'color': '#848484'}, string=re.compile('Transferee\\(s\\)'))
    if not transferee_font:
        return result

    # Find boundary tag: prefer Description, fallback to Site (which is always present)
    description_tag = soup.find('font', {'color': '#848484'}, string=re.compile('Description'))
    site_tag = soup.find('font', {'color': '#848484'}, string=re.compile('Site'))
    
    # Set the boundary tag to Description if it exists, otherwise use Site
    boundary_tag = description_tag if description_tag else site_tag
    if not boundary_tag:
        return result

    # Create a boundary position for accurate checking
    boundary_position = get_dom_position(boundary_tag)
    
    # Find the first br tag after Transferee(s)
    br_tag = transferee_font.find_next('br')
    if not br_tag:
        return result
    
    # Start looking for postal code after the transferee tag
    current = br_tag
    
    while current:
        # Check if we've reached or passed the boundary
        if is_at_or_past_boundary(current, boundary_tag, boundary_position):
            break
            
        if isinstance(current, NavigableString) and is_postal_code(current.strip()):
            # Found postal code, collect lines backwards until p tag or transferee tag
            lines = [current.strip()]
            prev = current.previous_element
            
            while prev and prev != transferee_font:
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
                result["BuyerAddress"] = ", ".join(lines)
            break
            
        current = current.next_element

    return result 
