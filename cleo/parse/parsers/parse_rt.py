import re
from bs4 import Tag


def parse_rt(soup):
    """
    Extract the canonical RT transaction identifier (e.g., RT182053)
    by reading the last footer <font color="#848484"> tag which always
    contains the pagination + RT number.
    """
    result = {"RTNumber": ""}
    pattern = re.compile(r"RT\d{5,6}")

    # The footer paragraph is consistently the final <p> on the page.
    footer_paragraph: Tag | None = None
    paragraphs = soup.find_all("p")
    if paragraphs:
        footer_paragraph = paragraphs[-1]

    if footer_paragraph:
        footer_font = footer_paragraph.find("font", {"color": "#848484"})
        if footer_font:
            text = footer_font.get_text(strip=True)
            match = pattern.search(text)
            if match:
                result["RTNumber"] = match.group(0)
                return result

    # Fallback safety: search the entire document if structure changes.
    text = soup.get_text(" ", strip=True)
    match = pattern.search(text)
    if match:
        result["RTNumber"] = match.group(0)

    return result
