import re
from bs4 import BeautifulSoup, NavigableString, Tag

def parse_buyer_info(soup):
    """
    Parse only the Buyer field - the text that appears immediately after the Transferee(s) tag and br.
    The Buyer field ends at the first occurrence of any HTML element, tag, or entity.
    """
    result = {
        "Buyer": "",
        "BuyerContact": ""
    }
    
    # Find the Transferee(s) tag
    transferee_tag = soup.find('font', string=re.compile('Transferee\\(s\\)'))
    if not transferee_tag:
        return result

    # Get the first br tag after Transferee(s)
    br_tag = transferee_tag.find_next('br')
    if not br_tag:
        return result

    # Get only the immediate text node after the br tag
    next_element = br_tag.next_element
    if isinstance(next_element, NavigableString):
        # Split on &nbsp; and take only the first part
        text = str(next_element)
        parts = text.split('\xa0')  # \xa0 is the unicode character for &nbsp;
        result["Buyer"] = parts[0].strip() if parts else ""

    # Find boundary tag: prefer Description, fallback to Site (which is always present)
    description_tag = soup.find('font', string=re.compile('Description'))
    site_tag = soup.find('font', string=re.compile('Site'))
    
    # Set the boundary tag to Description if it exists, otherwise use Site
    boundary_tag = description_tag if description_tag else site_tag
    if not boundary_tag:
        return result

    # Get all text nodes between Transferee(s) and boundary
    current = transferee_tag
    contact_prefixes = ('attn:', 'aso:', 'asst vp:', 'assistant vp:', 'asst:', 'aso')
    while current and current != boundary_tag:
        if isinstance(current, NavigableString):
            text = str(current).strip()
            lowered = text.lower()

            if lowered.startswith('c/o'):
                current = current.next_element
                continue

            for prefix in contact_prefixes:
                if lowered.startswith(prefix):
                    parts = text.split(':', 1)
                    if len(parts) > 1:
                        contact = parts[1].strip()
                        if contact:
                            result["BuyerContact"] = contact
                            return result
                    break

            if 'Attn:' in text:
                parts = text.split('Attn:')
                if len(parts) > 1:
                    contact = parts[1].strip()
                    if contact:
                        result["BuyerContact"] = contact
                        return result

        current = current.next_element

    return result
    
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
