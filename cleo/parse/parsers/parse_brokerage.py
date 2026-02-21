import re
from bs4 import BeautifulSoup, NavigableString, Tag

def extract_phone_number(text):
    """Extract phone number from text"""
    pattern = r'(?:1-)?(?:\d{3}-|\(\d{3}\)\s?)\d{3}-\d{4}'
    match = re.search(pattern, text)
    return match.group(0) if match else ""

def parse_brokerage(soup):
    """
    Extracts Brokerage and BrokeragePhone details from the HTML content.
    Finds text between the 'Broker/Agent' section and the first <a> tag.
    """
    result = {
        "Brokerage": "",
        "BrokeragePhone": ""
    }
    
    # Locate the 'Broker/Agent' tag
    broker_tag = soup.find('font', {'color': '#848484'}, string=re.compile('Broker/Agent', re.IGNORECASE))
    if not broker_tag:
        return result
    
    # Find the next <br> tag after 'Broker/Agent'
    start_element = broker_tag.find_next('br')
    if not start_element:
        return result
    
    # Traverse through the elements until we find an <a> tag
    current = start_element.next_sibling
    brokerage_text = []
    while current and not (isinstance(current, Tag) and current.name == 'a'):
        if isinstance(current, NavigableString):
            text = current.strip()
            if text:
                brokerage_text.append(text)
        current = current.next_sibling
    
    # Join collected text and extract phone number if present
    cleaned_text = ' '.join(brokerage_text)
    phone_number = extract_phone_number(cleaned_text)
    if phone_number:
        cleaned_text = cleaned_text.replace(phone_number, '').strip()
    
    result["Brokerage"] = cleaned_text
    result["BrokeragePhone"] = phone_number
    
    return result