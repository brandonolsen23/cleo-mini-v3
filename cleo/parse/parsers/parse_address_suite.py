import re

SUITE_PATTERN = re.compile(
    r"\b(?:(?:unit|suite|ste|apt|apartment|floor|flr|level|lvl|room|rm)s?|#|no\.)\b",
    re.IGNORECASE,
)


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.strip())


def is_suite_line(text: str) -> bool:
    if not text:
        return False

    normalized = text.strip()
    if not normalized:
        return False

    if normalized.startswith("#"):
        return True

    if SUITE_PATTERN.search(normalized):
        return True

    return False


def parse_address_suite(soup):
    """
    Extract suite/unit line associated with the main property address.
    """
    result = {"AddressSuite": ""}

    address_tag = soup.find("strong", id="address")
    if not address_tag:
        return result

    lines = [clean_text(text) for text in address_tag.stripped_strings]
    if not lines:
        return result

    for line in lines[1:]:
        if is_suite_line(line):
            result["AddressSuite"] = line
            break

    return result
