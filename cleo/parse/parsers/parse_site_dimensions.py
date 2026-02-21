from typing import Dict
from bs4 import BeautifulSoup


def parse_site_dimensions(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Extract site area, frontage, and depth (with units) from the Site section.
    """
    site_font = soup.find("font", string="Site")
    result = {
        "SiteFrontage": "",
        "SiteFrontageUnits": "",
        "SiteDepth": "",
        "SiteDepthUnits": "",
    }
    if not site_font:
        return result

    current = site_font.parent
    while current:
        # Stop when we hit the next section header
        if current.name == "font" and current is not site_font:
            break

        text = " ".join(current.stripped_strings).lower()
        if not text:
            current = current.next_sibling
            continue

        if "frontage" in text and not result["SiteFrontage"]:
            tokens = text.split()
            for idx, token in enumerate(tokens):
                if "frontage" in token and idx > 0:
                    value = tokens[idx - 1]
                    if value.replace(".", "", 1).isdigit():
                        result["SiteFrontage"] = value
                        if idx + 1 < len(tokens):
                            result["SiteFrontageUnits"] = tokens[idx + 1]
                        break

        if "depth" in text and not result["SiteDepth"]:
            tokens = text.split()
            for idx, token in enumerate(tokens):
                if "depth" in token and idx > 0:
                    value = tokens[idx - 1]
                    if value.replace(".", "", 1).isdigit():
                        result["SiteDepth"] = value
                        if idx + 1 < len(tokens):
                            result["SiteDepthUnits"] = tokens[idx + 1]
                        break

        current = current.next_sibling

    return result
