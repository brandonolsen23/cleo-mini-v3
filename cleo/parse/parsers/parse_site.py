import re
from bs4 import NavigableString, Tag


def parse_site(soup):
    """
    Extract the numeric acreage following the Site section.
    Returns a dict with SiteArea + SiteAreaUnits.

    Uses next_element traversal (document order) to find acreage text
    between the Site header and Consideration header. This handles both
    layouts: bare text nodes between <p></p> tags (farm/land types) and
    text inside <p> elements (retail/commercial types).
    """
    result = {
        "SiteArea": "",
        "SiteAreaUnits": "",
    }
    site_tag = soup.find('font', string='Site')
    if not site_tag:
        return result

    acreage_pattern = re.compile(
        r'([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(?:acres?|ac\.)',
        re.IGNORECASE,
    )
    sq_ft_pattern = re.compile(
        r'([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(?:sq\.?\s*ft\.?|square\s*feet|sf)',
        re.IGNORECASE,
    )

    # Walk document tree in order, checking only text nodes
    node = site_tag.next_element
    while node:
        # Stop at Consideration section
        if isinstance(node, Tag) and node.name == 'font':
            if 'Consideration' in node.get_text(strip=True):
                break

        if isinstance(node, NavigableString):
            text = node.strip()
            if text:
                match = acreage_pattern.search(text)
                if match:
                    result["SiteArea"] = match.group(1).replace(',', '')
                    result["SiteAreaUnits"] = "acres"
                    return result

                match = sq_ft_pattern.search(text)
                if match:
                    result["SiteArea"] = match.group(1).replace(',', '')
                    result["SiteAreaUnits"] = "sq ft"
                    return result

        node = node.next_element

    return result
