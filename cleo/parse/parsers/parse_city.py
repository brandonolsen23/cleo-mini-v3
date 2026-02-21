from typing import Dict, Optional, Union
from bs4 import NavigableString, Tag


def parse_city(soup) -> Dict[str, str]:
    """
    Extract the city and region text located immediately after the
    <strong id="address"> block (formatted as 'City : Region'). Property
    listings are always located in Ontario, Canada so we return those values
    alongside the parsed city/region to ensure downstream outputs keep the
    geographic context without additional processing.
    """
    result = {
        "City": "",
        "Region": "",
        "Province": "Ontario",
        "Country": "Canada",
    }
    address_tag: Optional[Tag] = soup.find("strong", id="address")
    if not address_tag:
        return result

    current: Union[NavigableString, Tag, None] = address_tag.next_sibling
    while current:
        if isinstance(current, NavigableString):
            text = current.strip()
            if ":" in text:
                city_part, region_part = text.split(":", 1)
                result["City"] = city_part.strip()
                result["Region"] = region_part.strip()
                return result
        current = current.next_sibling
    return result
