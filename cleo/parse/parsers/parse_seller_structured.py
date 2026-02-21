import re
from typing import Dict, List, Tuple, Union
from bs4 import NavigableString, Tag

from .parser_utils import (
    address_priority,
    looks_like_address,
    looks_like_company,
    looks_like_plain_name,
    normalize_line,
    strip_care_of,
    strip_contact_prefix,
    strip_trailing_phone,
)

LEGAL_DESCRIPTOR_KEYWORDS = (
    "barrister",
    "barristers",
    "solicitor",
    "solicitors",
    "law office",
    "law offices",
    "trust",
    "in trust",
)
LEGAL_DESCRIPTOR_REGEX = re.compile(r"\b(llp|llc|ulc)\b", re.IGNORECASE)


def _collect_seller_section_lines(soup) -> List[Tuple[str, bool]]:
    seller_tag = soup.find("font", string=re.compile(r"Transferor\(s\)"))
    if not seller_tag:
        return []
    transferee_tag = soup.find("font", string=re.compile(r"Transferee\(s\)"))
    br_tag = seller_tag.find_next("br")
    if not br_tag:
        return []

    section_paragraph = seller_tag.find_parent("p")
    stop_paragraph = transferee_tag.parent if transferee_tag else None
    lines: List[Tuple[str, bool]] = []

    current = br_tag.next_sibling
    while current:
        # Stop at section headers (handles <p />-style HTML where tags are siblings, not nested)
        if isinstance(current, Tag) and current.name == "font" and current.get("color") == "#848484":
            break
        if isinstance(current, NavigableString):
            text = normalize_line(str(current))
            if text:
                lines.append((text, False))
        elif isinstance(current, Tag) and current.name == "em":
            text = current.get_text(strip=True)
            if text:
                lines.append((normalize_line(text), True))
        current = current.next_sibling

    next_paragraph = section_paragraph.find_next_sibling("p") if section_paragraph else None
    while next_paragraph and next_paragraph is not stop_paragraph:
        pieces = [normalize_line(piece) for piece in next_paragraph.stripped_strings]
        lower_text = " ".join(pieces).lower()
        if "more info:" in lower_text:
            break
        if next_paragraph.find("font", {"color": "#848484"}):
            break
        for piece in pieces:
            if piece:
                lines.append((piece, False))
        next_paragraph = next_paragraph.find_next_sibling("p")

    return lines


def parse_seller_structured(soup) -> Dict[str, List[str]]:
    lines = _collect_seller_section_lines(soup)
    result = {
        "SellerStructuredCompanyLines": [],
        "SellerStructuredContactLines": [],
        "SellerStructuredAddressLines": [],
    }
    address_entries: List[tuple] = []
    seq = 0
    first_company_added = False
    address_mode = False
    last_added: Tuple[str, int] | None = None
    for raw, from_em in lines:
        line = normalize_line(raw)
        line, _ = strip_trailing_phone(line)
        if not line:
            continue

        if not first_company_added:
            result["SellerStructuredCompanyLines"].append(line)
            first_company_added = True
            last_added = ("company", len(result["SellerStructuredCompanyLines"]) - 1)
            continue

        lowered = line.lower()
        is_contact, contact_value = strip_contact_prefix(line)
        if is_contact and contact_value:
            result["SellerStructuredContactLines"].append(contact_value)
            address_mode = True
            last_added = ("contact", len(result["SellerStructuredContactLines"]) - 1)
            continue

        has_care_of, cleaned = strip_care_of(line)
        if has_care_of:
            line = cleaned
            if not line:
                continue
            address_mode = True

        descriptor = any(keyword in lowered for keyword in LEGAL_DESCRIPTOR_KEYWORDS) or LEGAL_DESCRIPTOR_REGEX.search(line)
        ampersand_alias = "&" in line and not looks_like_address(line)
        if descriptor or ampersand_alias:
            company_name = line
            if last_added and last_added[0] == "address":
                idx = last_added[1]
                if 0 <= idx < len(address_entries):
                    _, _, prev_line = address_entries[idx]
                    if looks_like_plain_name(prev_line):
                        address_entries.pop(idx)
                        company_name = f"{prev_line} {company_name}".strip()
                        last_added = None
            result["SellerStructuredCompanyLines"].append(company_name)
            last_added = ("company", len(result["SellerStructuredCompanyLines"]) - 1)
            continue

        if from_em:
            if looks_like_address(line) and (address_mode or line[:1].isdigit()):
                address_entries.append((address_priority(line), seq, line))
                seq += 1
                address_mode = True
                last_added = ("address", len(address_entries) - 1)
            else:
                result["SellerStructuredCompanyLines"].append(line)
                last_added = ("company", len(result["SellerStructuredCompanyLines"]) - 1)
            continue

        if has_care_of:
            if looks_like_company(line):
                result["SellerStructuredCompanyLines"].append(line)
                last_added = ("company", len(result["SellerStructuredCompanyLines"]) - 1)
                continue
            if not looks_like_address(line):
                result["SellerStructuredContactLines"].append(line)
                last_added = ("contact", len(result["SellerStructuredContactLines"]) - 1)
                continue

        if looks_like_company(line) and not looks_like_address(line):
            result["SellerStructuredCompanyLines"].append(line)
            last_added = ("company", len(result["SellerStructuredCompanyLines"]) - 1)
        elif looks_like_address(line) or address_mode:
            address_entries.append((address_priority(line), seq, line))
            seq += 1
            address_mode = True
            last_added = ("address", len(address_entries) - 1)
        else:
            result["SellerStructuredContactLines"].append(line)
            last_added = ("contact", len(result["SellerStructuredContactLines"]) - 1)

    if address_entries:
        result["SellerStructuredAddressLines"] = [
            line for _, _, line in sorted(address_entries, key=lambda item: (item[0], item[1]))
        ]

    return result
