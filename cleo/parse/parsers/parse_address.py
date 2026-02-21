from bs4 import BeautifulSoup
import re

SUITE_PATTERN = re.compile(
    r"\b(?:(?:unit|suite|ste|apt|apartment|floor|flr|level|lvl|room|rm)s?|#|no\.)\b",
    re.IGNORECASE,
)

INSTRUCTION_PATTERN = re.compile(r'^(?:this\s+)?field\b', re.IGNORECASE)


def clean_text(text):
    # Remove HTML comments and instructional notes from the source HTML.
    lower = text.lower()
    if text.startswith("<!--") or "tag contains" in lower:
        return ""
    if INSTRUCTION_PATTERN.search(lower):
        return ""
    # Remove extra whitespace and normalize spaces.
    return re.sub(r"\s+", " ", text).strip()

def parse_address(soup):
    result = {
        'Address': '',
        'AlternateAddresses': [],
    }

    address_tag = soup.find('strong', id='address')
    if not address_tag:
        return result

    # Get all text nodes, filtering out comments and empty strings
    addresses = []
    for content in address_tag.stripped_strings:
        text = clean_text(content)
        if text:
            addresses.append(text)

    # Filter out any remaining HTML instructions (avoid false positives like "Bloomfield").
    addresses = [
        addr
        for addr in addresses
        if not any(
            marker in addr.lower()
            for marker in ('tag contains', '<!--', '-->')
        )
    ]

    if not addresses:
        return result

    result['Address'] = addresses[0]

    alternate_lines = []
    for line in addresses[1:]:
        if SUITE_PATTERN.search(line):
            continue
        alternate_lines.append(line)

    result['AlternateAddresses'] = alternate_lines

    return result
