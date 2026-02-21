import re
from bs4 import BeautifulSoup, NavigableString, Tag
from .parse_seller_phone import is_phone_number, extract_phone_number
from .parse_seller_address import is_address

# Enable or disable debugging
DEBUG = False

def debug_print(message, level=1):
    """Print debug messages if debugging is enabled."""
    if DEBUG:
        indent = "  " * (level - 1)
        print(f"DEBUG: {indent}{message}")

def looks_like_company_name(text):
    """Check if text appears to be a company name."""
    # Company identifiers and business terms
    company_identifiers = ['Inc', 'Ltd', 'LLC', 'Corp', 'Limited', 'Corporation', 'Company', 'LLP', 'REIT']
    business_terms = ['Holdings', 'Investments', 'Enterprises', 'Group', 'Partners', 'Properties', 'Realty', 'Capital',
                     'College', 'Transportation', 'Transport', 'Services', 'Management', 'Development', 'Portfolio',
                     'Business', 'Health', 'Technology', 'Education', 'Institute', 'Academy', 'School',
                     'Primaris', 'Trust', 'Fund']
    
    # Normalize text for checking
    text = ' '.join(text.split())
    
    # Basic checks
    has_company_identifier = any(f" {identifier}" in f" {text}" for identifier in company_identifiers)
    has_business_term = any(f" {term}" in f" {text}" for term in business_terms)
    is_business_entity = bool(re.search(r'REIT|Trust|Fund|Association|Federation|Organization', text))
    reasonable_length = 5 <= len(text) <= 100
    
    # Check for numbered company pattern (e.g., "1234567 Ontario Inc")
    is_numbered_company = bool(re.search(r'^\d{6,}\s+[A-Za-z]+\s+(Inc|Ltd|Corp|Limited)$', text))
    
    # Check for special company patterns that might include address-like components
    company_with_address = bool(re.search(r'^[A-Za-z]+\s+(of|at|on)\s+[A-Za-z\s]+$', text))
    
    # Check for educational institutions
    is_educational = any(term in text for term in ['College', 'University', 'School', 'Institute', 'Academy'])
    
    # Check for transportation companies
    is_transport = any(term in text for term in ['Transport', 'Transportation'])
    
    # Check for REITs and similar entities
    is_reit = 'REIT' in text or any(term in text for term in ['Trust', 'Fund'])
    
    # Check for address-like patterns but allow for company names that might contain numbers
    looks_like_address = bool(re.search(r'\d+\s+[A-Za-z]+\s+(St|Ave|Rd|Dr|Blvd|Lane|Highway)', text, re.IGNORECASE))
    has_postal_code = bool(re.search(r'[A-Z]\d[A-Z]\s*\d[A-Z]\d', text))
    
    # Professional designations
    has_professional_designation = "Dr " in text + " " or "Professional Corporation" in text
    
    result = ((has_company_identifier or has_business_term or is_business_entity or is_numbered_company or 
              company_with_address or is_educational or has_professional_designation or is_transport or is_reit) and 
            reasonable_length and (not looks_like_address or company_with_address) and not has_postal_code)
    
    if DEBUG:
        debug_print(f"Company name check details for '{text}':", 2)
        debug_print(f"has_company_identifier: {has_company_identifier}", 3)
        debug_print(f"has_business_term: {has_business_term}", 3)
        debug_print(f"is_business_entity: {is_business_entity}", 3)
        debug_print(f"is_numbered_company: {is_numbered_company}", 3)
        debug_print(f"company_with_address: {company_with_address}", 3)
        debug_print(f"is_educational: {is_educational}", 3)
        debug_print(f"is_transport: {is_transport}", 3)
        debug_print(f"is_reit: {is_reit}", 3)
        debug_print(f"looks_like_address: {looks_like_address}", 3)
        debug_print(f"has_postal_code: {has_postal_code}", 3)
        debug_print(f"reasonable_length: {reasonable_length}", 3)
        debug_print(f"RESULT: {result}", 2)
    
    return result

def is_definitely_address(text):
    """Check more thoroughly if text is definitely an address component."""
    if DEBUG:
        debug_print(f"Checking if '{text}' is definitely an address", 1)
    
    # Check for postal code pattern
    if re.search(r'[A-Z]\d[A-Z]\s*\d[A-Z]\d', text):
        if DEBUG:
            debug_print("Contains postal code", 2)
        return True
    
    # Check for province/state
    provinces = ['Ontario', 'Quebec', 'Alberta', 'BC', 'Manitoba', 'Saskatchewan', 
                'Nova Scotia', 'New Brunswick', 'PEI', 'Newfoundland', 'Yukon', 
                'Northwest Territories', 'Nunavut']
    for province in provinces:
        if f", {province}" in text or f" {province}," in text:
            if DEBUG:
                debug_print(f"Contains province: {province}", 2)
            return True
            
    # Check for common address words
    address_keywords = ['Street', 'Avenue', 'Road', 'Drive', 'Boulevard', 'Lane', 'Highway', 
                      'St,', 'Ave,', 'Rd,', 'Dr,', 'Blvd,', 'Ln,', 'Hwy,', 'rue', 'Square']
    for keyword in address_keywords:
        if f" {keyword}" in f" {text}":
            if DEBUG:
                debug_print(f"Contains address keyword: {keyword}", 2)
            return True
            
    if DEBUG:
        debug_print("Not an address", 2)
    return False

def is_same_as_seller(text, seller_name):
    """Check if the text is essentially the same as the seller name."""
    if DEBUG:
        debug_print(f"Checking if '{text}' is same as seller '{seller_name}'", 1)
    
    if not text or not seller_name:
        if DEBUG:
            debug_print("One of the names is empty", 2)
        return False
        
    # Normalize both texts
    text_norm = ' '.join(text.replace('\xa0', ' ').split()).lower()
    seller_norm = ' '.join(seller_name.replace('\xa0', ' ').split()).lower()
    
    # Direct match
    if text_norm == seller_norm:
        if DEBUG:
            debug_print("Direct match", 2)
        return True
        
    # Remove phone numbers
    phone_pattern = re.compile(r'\d{3}-\d{3}-\d{4}')
    text_no_phone = re.sub(phone_pattern, '', text_norm).strip()
    seller_no_phone = re.sub(phone_pattern, '', seller_norm).strip()
    
    # Check again after phone removal
    if text_no_phone == seller_no_phone:
        if DEBUG:
            debug_print("Match after phone removal", 2)
        return True
        
    # Check if one contains the other completely
    if text_no_phone in seller_no_phone or seller_no_phone in text_no_phone:
        # Make sure it's a substantial match (not just a short substring)
        shorter = min(len(text_no_phone), len(seller_no_phone))
        longer = max(len(text_no_phone), len(seller_no_phone))
        if shorter > 5 and shorter / longer > 0.7:  # 70% match ratio
            if DEBUG:
                debug_print(f"Substantial substring match, ratio: {shorter/longer:.2f}", 2)
            return True
    
    if DEBUG:
        debug_print("Not the same as seller", 2)
    return False

def are_equivalent_company_names(name1, name2):
    """Check if two company names are essentially the same entity."""
    if DEBUG:
        debug_print(f"Checking if '{name1}' and '{name2}' are equivalent company names", 1)
    
    if not name1 or not name2:
        if DEBUG:
            debug_print("One of the names is empty", 2)
        return False
    
    # Normalize names
    name1_norm = ' '.join(name1.replace('\xa0', ' ').split()).lower()
    name2_norm = ' '.join(name2.replace('\xa0', ' ').split()).lower()
    
    # Direct match
    if name1_norm == name2_norm:
        if DEBUG:
            debug_print("Direct match", 2)
        return True
    
    # Check if one is a substring of the other (indicating potential truncation)
    if name1_norm in name2_norm:
        if DEBUG:
            debug_print(f"'{name1_norm}' is substring of '{name2_norm}'", 2)
        return True
    
    if name2_norm in name1_norm:
        if DEBUG:
            debug_print(f"'{name2_norm}' is substring of '{name1_norm}'", 2)
        return True
    
    # Special case for "REIT" differences
    if "reit" in name1_norm and "reit" in name2_norm:
        # Extract the main part of the name before "REIT"
        name1_base = name1_norm.split("reit")[0].strip()
        name2_base = name2_norm.split("reit")[0].strip()
        if name1_base == name2_base and len(name1_base) > 3:  # Ensure it's not just a very short match
            if DEBUG:
                debug_print(f"REIT name match: '{name1_base}'", 2)
            return True
            
    if DEBUG:
        debug_print("Not equivalent company names", 2)
    return False

def clean_company_name(text):
    """Clean and normalize company name for better matching."""
    if DEBUG:
        debug_print(f"Cleaning company name: '{text}'", 1)
    
    if not text:
        return ""
    
    # Normalize whitespace and non-breaking spaces
    clean_text = ' '.join(text.replace('\xa0', ' ').split())
    
    # Remove trailing punctuation
    clean_text = clean_text.rstrip(',.:;')
    
    if DEBUG:
        if clean_text != text:
            debug_print(f"Cleaned to: '{clean_text}'", 2)
    
    return clean_text

def parse_seller_alternate_names(soup):
    """
    Extract alternate seller names from the Transferor(s) section.
    Returns a dict with SellerAlternateName1, SellerAlternateName2, and SellerAlternateName3.
    """
    if DEBUG:
        debug_print("Starting parse_seller_alternate_names")

    result = {
        "SellerAlternateName1": "",
        "SellerAlternateName2": "",
        "SellerAlternateName3": "",
        "SellerAlternateName4": "",
        "SellerAlternateName5": "",
        "SellerAlternateName6": "",
    }

    # Step 1: Locate the 'Transferor(s)' font tag
    transferor_tag = soup.find('font', string=re.compile(r'Transferor\(s\)'))
    if not transferor_tag:
        if DEBUG:
            debug_print("No Transferor(s) tag found")
        return result

    # Step 2: Find the first <br> after the 'Transferor(s)' font tag
    br_tag = transferor_tag.find_next('br')
    if not br_tag:
        if DEBUG:
            debug_print("No <br> tag after Transferor(s)")
        return result

    # Step 3: Collect all text nodes until the next <p> tag
    text_nodes = []
    current_node = br_tag.next_sibling

    while current_node:
        if isinstance(current_node, NavigableString):
            text = current_node.strip()
            if text:
                # Split on &nbsp; sequences and take first part
                parts = text.split('\xa0')
                clean_text = parts[0].strip()
                if clean_text:
                    text_nodes.append(clean_text)
        elif isinstance(current_node, Tag):
            if current_node.name == "p":
                break  # Stop at the next <p> or self-closing <p /> tag
            if current_node.name == "em" and current_node.text.strip():
                text_nodes.append(current_node.text.strip())
            elif current_node.name == "br":
                # If we hit another <br>, check if the next node is a <p>
                next_node = current_node.next_sibling
                if isinstance(next_node, Tag) and next_node.name == "p":
                    break
        current_node = current_node.next_sibling

    if DEBUG:
        debug_print(f"Found {len(text_nodes)} text nodes:")
        for i, node in enumerate(text_nodes):
            debug_print(f"Node {i}: '{node}'", 2)

    # Step 4: Extract alternate names (skip first node as it's the seller name)
    for offset in range(1, 7):
        key = f"SellerAlternateName{offset}"
        if offset < len(text_nodes) and key in result:
            result[key] = text_nodes[offset]

    if DEBUG:
        debug_print("Final result:")
        for offset in range(1, 7):
            key = f"SellerAlternateName{offset}"
            debug_print(f"{key}: '{result[key]}'", 2)

    return result
