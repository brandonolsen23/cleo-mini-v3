import re


def parse_site(soup):
    """
    Extract the numeric acreage immediately following the Site section.
    Returns a dict with SiteArea + SiteAreaUnits (always acres in RealTrack).
    """
    result = {
        "SiteArea": "",
        "SiteAreaUnits": "",
    }
    site_tag = soup.find('font', string='Site')
    if not site_tag:
        return result

    current = site_tag.find_next('p')
    acreage_pattern = re.compile(r'([0-9]+(?:\.[0-9]+)?)\s*acre', re.IGNORECASE)
    while current:
        text = ' '.join(current.stripped_strings)
        match = acreage_pattern.search(text)
        if match:
            result["SiteArea"] = match.group(1)
            result["SiteAreaUnits"] = "acres"
            return result
        current = current.find_next('p')

    return result
