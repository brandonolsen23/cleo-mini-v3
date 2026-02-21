"""GeoWarehouse HTML parser.

Extracts property data from saved GeoWarehouse detail pages using stable
HTML id attributes on Angular-rendered DOM elements.
"""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def parse_gw_html(html: str, filename: str) -> Optional[dict]:
    """Parse a GeoWarehouse HTML file into structured data.

    Returns None for non-detail pages (search results, collaboration pages, etc.).
    """
    soup = BeautifulSoup(html, "lxml")

    # Only property detail pages have this element
    if not soup.find(id="pr-expansion-panel-registry"):
        return None

    record = {
        "gw_source_file": filename,
        "summary": _parse_summary(soup),
        "registry": _parse_registry(soup),
        "site_structure": _parse_site_structure(soup),
        "sales_history": _parse_sales_history(soup),
    }

    # PIN comes from registry section
    record["pin"] = record["registry"].get("pin", "")

    return record


def _get_text(soup: BeautifulSoup, element_id: str) -> str:
    """Find element by id, return stripped text or empty string."""
    el = soup.find(id=element_id)
    if el is None:
        return ""
    return el.get_text(strip=True)


def _parse_summary(soup: BeautifulSoup) -> dict:
    """Extract fields from the summary section (sum-* IDs)."""
    return {
        "address": _get_text(soup, "sum-h1-address"),
        "owner_names": _get_text(soup, "sum-owner-names"),
        "last_sale_price": _get_text(soup, "sum-lastsale-value"),
        "last_sale_date": _get_text(soup, "sum-lastsale-date"),
        "lot_size_area": _get_text(soup, "sum-lotsize-area"),
        "lot_size_perimeter": _get_text(soup, "sum-lotsize-perimeter"),
        "party_to": _get_text(soup, "sum-partyto-value"),
        "legal_description": _get_text(soup, "sum-legal-desc"),
    }


def _parse_registry(soup: BeautifulSoup) -> dict:
    """Extract fields from the registry section (reg-* IDs)."""
    return {
        "gw_address": _get_text(soup, "reg-gw-address"),
        "land_registry_office": _get_text(soup, "reg-lro"),
        "owner_names": _get_text(soup, "reg-on"),
        "ownership_type": _get_text(soup, "reg-ot"),
        "land_registry_status": _get_text(soup, "reg-lrs"),
        "property_type": _get_text(soup, "reg-pt"),
        "registration_type": _get_text(soup, "reg-rt"),
        "pin": _get_text(soup, "reg-pin"),
    }


def _parse_site_structure(soup: BeautifulSoup) -> dict:
    """Extract fields from the Site & Structure section (ss-*-{ARN} IDs).

    The ARN suffix is discovered dynamically by finding the first ss-an-arn-* element.
    """
    result = {
        "arn": "",
        "frontage": "",
        "zoning": "",
        "depth": "",
        "property_description": "",
        "property_code": "",
        "current_assessed_value": "",
        "valuation_date": "",
        "assessment_legal_description": "",
        "site_area": "",
        "property_address": "",
        "municipality": "",
        "owner_names_mpac": "",
        "owner_mailing_address": "",
    }

    # Find the ARN by looking for any element with id starting with ss-an-arn-
    arn_el = soup.find(id=re.compile(r"^ss-an-arn-"))
    if arn_el is None:
        return result

    arn_text = arn_el.get_text(strip=True)
    # Strip "ARN : " prefix that GW renders
    arn = arn_text.removeprefix("ARN :").strip() or arn_text
    result["arn"] = arn

    # Use the ARN as suffix to look up all fields
    suffix = arn_el["id"].removeprefix("ss-an-arn-")

    result["frontage"] = _get_text(soup, f"ss-site-frontage-{suffix}")
    result["zoning"] = _get_text(soup, f"ss-site-sa-{suffix}")
    result["depth"] = _get_text(soup, f"ss-site-depth-{suffix}")
    result["property_description"] = _get_text(soup, f"ss-struct-pd-{suffix}")
    result["property_code"] = _get_text(soup, f"ss-struct-pc-{suffix}")
    result["current_assessed_value"] = _get_text(soup, f"ss-ad-cav-{suffix}")
    result["valuation_date"] = _get_text(soup, f"ss-ad-vd-{suffix}")
    result["assessment_legal_description"] = _get_text(soup, f"ss-msed-ld-{suffix}")
    result["site_area"] = _get_text(soup, f"ss-msed-sa-{suffix}")
    result["property_address"] = _get_text(soup, f"ss-msap-pa-{suffix}")
    result["municipality"] = _get_text(soup, f"ss-msap-muni-{suffix}")
    result["owner_names_mpac"] = _get_text(soup, f"ss-msap-on-{suffix}")
    result["owner_mailing_address"] = _get_text(soup, f"ss-msap-oma-{suffix}")

    return result


def _parse_sales_history(soup: BeautifulSoup) -> list[dict]:
    """Extract the sales history table rows.

    Iterates all vs-tbl-row-* elements (skipping the header row) rather than
    looking up by date ID, since duplicate dates produce duplicate IDs.
    """
    rows = []

    # Find all elements whose id starts with vs-tbl-row- but skip the header
    for el in soup.find_all(id=re.compile(r"^vs-tbl-row-")):
        row_id = el.get("id", "")
        if row_id == "vs-tbl-row-hdr":
            continue

        # Extract the date suffix from the row id
        date_suffix = row_id.removeprefix("vs-tbl-row-")

        # Read cell values — look within the row element itself
        sale_date = _get_text_within(el, f"vs-tbl-data-sd-{date_suffix}")
        sale_amount = _get_text_within(el, f"vs-tbl-data-sa-{date_suffix}")
        txn_type = _get_text_within(el, f"vs-tbl-data-type-{date_suffix}")
        party_to = _get_text_within(el, f"vs-tbl-data-pt-{date_suffix}")

        # Notes field can have "empty" inserted before the date
        notes = _get_text_within(el, f"vs-tbl-data-notes-{date_suffix}")
        if not notes:
            notes = _get_text_within(el, f"vs-tbl-data-notes-empty-{date_suffix}")

        # Fall back to reading date from text if ID lookup missed
        if not sale_date:
            sale_date = date_suffix

        rows.append({
            "sale_date": sale_date,
            "sale_amount": sale_amount,
            "type": txn_type,
            "party_to": party_to,
            "notes": notes,
        })

    return rows


def _get_text_within(parent, element_id: str) -> str:
    """Find element by id within a parent element, return stripped text or empty string."""
    el = parent.find(id=element_id)
    if el is None:
        return ""
    return el.get_text(strip=True)
