import re

def parse_pin(soup):
    # Find text containing 'PIN:'
    for text in soup.stripped_strings:
        if 'PIN:' in text:
            # Extract only digits after PIN:
            pin_text = text.split('PIN:')[1].strip()
            return ''.join(c for c in pin_text if c.isdigit())
    return ''
