from bs4 import BeautifulSoup, NavigableString, Tag


def parse_consideration(soup: BeautifulSoup) -> str:
    """
    Extract the verbatim Consideration paragraph (cash + debt + chargee info).

    Locates the `Consideration` header and captures every textual node until
    the next section header (`<font color="#848484">`) or the navigation links.
    """
    header = soup.find("font", string="Consideration")
    if not header:
        return ""

    text_parts = []
    current = header.next_sibling
    while current:
        # Stop once the next section header begins
        if isinstance(current, Tag) and current.name == "font":
            break
        if isinstance(current, Tag) and current.name == "a":
            break

        if isinstance(current, NavigableString):
            stripped = current.strip()
            if stripped:
                text_parts.append(stripped)
        elif isinstance(current, Tag):
            stripped = " ".join(current.stripped_strings)
            if stripped:
                text_parts.append(stripped)

        current = current.next_sibling

    return " ".join(text_parts).strip()
