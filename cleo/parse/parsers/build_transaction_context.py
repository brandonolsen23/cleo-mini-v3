"""
Comprehensive transaction context builder for RealTrack.
Creates a complete transaction context from parsed HTML including:
- Transaction header (address, city, municipality, date, price)
- Transferor/Transferee (companies, contacts, phones, addresses)
- Site facts (legal, PIN, acreage, frontage, zoning)
- Consideration (cash, debt, chattels, chargees)
- Broker info
- Export extras (postal code, building sf, etc.)
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .parse_building_size import parse_building_size
from .parse_address import parse_address
from .parse_address_suite import parse_address_suite
from .parse_city import parse_city
from .parse_sale_details import parse_sale_date_and_price
from .parse_seller import parse_seller
from .parse_seller_alternate_names import parse_seller_alternate_names
from .parse_seller_phone import parse_seller_phone
from .parse_seller_address import parse_seller_address
from .parse_seller_structured import parse_seller_structured
from .parse_buyer import parse_buyer_info
from .parse_buyer_alternate_names import parse_buyer_alternate_names
from .parse_buyer_phone import parse_buyer_phone
from .parse_buyer_address import parse_buyer_address
from .parse_buyer_structured import parse_buyer_structured
from .parse_brokerage import parse_brokerage
from .parse_pin import parse_pin
from .parse_rt import parse_rt
from .parse_arn import parse_arn
from .parse_site import parse_site
from .parse_site_dimensions import parse_site_dimensions
from .parse_consideration import parse_consideration
from .parse_description import parse_description
from .parse_photos import parse_photos
from .parse_site_facts import extract_site_facts
from .parse_party_identity import parse_all_party_identities, looks_like_company
from .parser_utils import looks_like_address as _looks_like_address


@dataclass
class TransactionAddress:
    """Subject property address with expansion support."""
    address: str = ""
    address_suite: str = ""
    city: str = ""
    municipality: str = ""
    province: str = "Ontario"
    postal_code: str = ""
    alternate_addresses: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TransactionHeader:
    """Transaction header with address, date, price."""
    address: TransactionAddress = field(default_factory=TransactionAddress)
    sale_date: str = ""
    sale_date_iso: str = ""
    sale_price: str = ""
    sale_price_raw: str = ""
    rt_number: str = ""
    arn: str = ""
    pins: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "address": self.address.to_dict(),
            "sale_date": self.sale_date,
            "sale_date_iso": self.sale_date_iso,
            "sale_price": self.sale_price,
            "sale_price_raw": self.sale_price_raw,
            "rt_number": self.rt_number,
            "arn": self.arn,
            "pins": self.pins,
        }


@dataclass
class PartyInfo:
    """Party (buyer/seller) information."""
    name: str = ""
    contact: str = ""
    phone: str = ""
    address: str = ""
    alternate_names: List[str] = field(default_factory=list)
    company_lines: List[str] = field(default_factory=list)
    contact_lines: List[str] = field(default_factory=list)
    address_lines: List[str] = field(default_factory=list)
    phones: List[str] = field(default_factory=list)
    officer_titles: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    attention: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SiteFacts:
    """Site legal and physical facts."""
    legal_description: str = ""
    site_area: str = ""
    site_area_units: str = ""
    site_frontage: str = ""
    site_frontage_units: str = ""
    site_depth: str = ""
    site_depth_units: str = ""
    zoning: str = ""
    pins: str = ""
    arn: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class Consideration:
    """Consideration breakdown."""
    cash: str = ""
    assumed_debt: str = ""
    chattels: str = ""
    verbatim: str = ""
    chargees: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BrokerInfo:
    """Broker/agent information."""
    brokerage: str = ""
    phone: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ExportExtras:
    """Extra fields from export TSV (postal code, building sf, etc.)."""
    postal_code: str = ""
    building_sf: str = ""
    additional_fields: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TransactionContext:
    """
    Complete transaction context combining all parsed data.
    
    Key fields for the mermaid flowchart:
    - rt_id: RealTrack ID
    - skip_index: Position in export listing
    - html_path: Path to saved HTML
    - ingest_timestamp: When this was ingested
    - transaction: Transaction header
    - transferor: Seller info
    - transferee: Buyer info
    - site: Site facts
    - consideration: Financial details
    - broker: Broker info
    - export_extras: Additional export data
    """
    rt_id: str = ""
    skip_index: int = 0
    html_path: str = ""
    ingest_timestamp: str = ""
    
    transaction: TransactionHeader = field(default_factory=TransactionHeader)
    transferor: PartyInfo = field(default_factory=PartyInfo)
    transferee: PartyInfo = field(default_factory=PartyInfo)
    site: SiteFacts = field(default_factory=SiteFacts)
    consideration: Consideration = field(default_factory=Consideration)
    broker: BrokerInfo = field(default_factory=BrokerInfo)
    export_extras: ExportExtras = field(default_factory=ExportExtras)
    description: str = ""
    photos: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "rt_id": self.rt_id,
            "skip_index": self.skip_index,
            "html_path": self.html_path,
            "ingest_timestamp": self.ingest_timestamp,
            "transaction": self.transaction.to_dict(),
            "transferor": self.transferor.to_dict(),
            "transferee": self.transferee.to_dict(),
            "site": self.site.to_dict(),
            "consideration": self.consideration.to_dict(),
            "broker": self.broker.to_dict(),
            "export_extras": self.export_extras.to_dict(),
            "description": self.description,
            "photos": self.photos,
        }


def expand_address_ranges(address: str) -> List[str]:
    """Expand address ranges like '123-127 Main St' to individual addresses."""
    # Pattern for address ranges
    range_pattern = re.compile(r"(\d+)[-–](\d+)\s+([A-Za-z]+)")
    match = range_pattern.search(address)
    if match:
        start, end, street = match.groups()
        addresses = []
        try:
            start_num = int(start)
            end_num = int(end)
            for num in range(start_num, end_num + 1):
                addresses.append(f"{num} {street}")
            # Return expanded addresses (replace range)
            return addresses
        except ValueError:
            pass
    return [address]


def deduplicate_addresses(addresses: List[str]) -> List[str]:
    """Remove duplicate addresses (case-insensitive)."""
    seen = set()
    unique = []
    for addr in addresses:
        normalized = addr.strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(addr)
    return unique


_TITLE_PREFIX_PATTERN = re.compile(
    r"^(?:pres|president|vp|vice\s*president|dir|director|aso|sec|secretary"
    r"|treas|treasurer|mgr|manager|partner|trustee|executor|executrix)"
    r":\s",
    re.IGNORECASE,
)

_CO_PATTERN = re.compile(r"^c/o\s+(.+)", re.IGNORECASE)


def _extract_co_from_address(address: str, alternate_names: List[str]) -> tuple:
    """Extract c/o entries from address and route appropriately.

    Only processes c/o at the START of the address string.  Scans forward
    through comma-separated parts to find where the street address begins
    (first part starting with a digit or PO Box pattern).

    Cases for the value after c/o:
    1. Starts with digit → it is an address; strip "c/o " prefix, keep rest
    2. Entity that looks like a company → route to alternate_names
    3. Entity that looks like a person → strip silently (handled elsewhere)

    Returns (cleaned_address, updated_alternate_names).
    """
    m = _CO_PATTERN.match(address)
    if not m:
        return address, alternate_names

    after_co = m.group(1).strip()

    # Case 1: c/o followed immediately by an address (starts with digit)
    if re.match(r"^\d", after_co):
        return after_co, alternate_names

    # Cases 2 & 3: c/o followed by an entity name.
    # Find where the street address starts.
    parts = [p.strip() for p in after_co.split(", ")]
    entity_parts = []
    address_start_idx = None
    for i, part in enumerate(parts):
        if (re.match(r"^\d", part)
                or re.match(r"^(?:po\s+box|p\.o|box\s)", part, re.IGNORECASE)
                or re.match(r"^(?:suite|ste|unit|floor|flr|lvl|level|apt)\b", part, re.IGNORECASE)):
            address_start_idx = i
            break
        entity_parts.append(part)

    if address_start_idx is not None:
        entity_name = ", ".join(entity_parts)
        remaining_address = ", ".join(parts[address_start_idx:])
    else:
        # No street address found; entire value after c/o is entity
        entity_name = after_co
        remaining_address = ""

    # Route the entity
    if entity_name:
        if looks_like_company(entity_name):
            if entity_name not in alternate_names:
                alternate_names = alternate_names + [entity_name]
        # else: person name — stripped from address, contact handled by party identity

    return remaining_address, alternate_names


def build_transaction_context(
    html_content: str,
    rt_id: str = "",
    skip_index: int = 0,
    html_path: str = "",
    ingest_timestamp: Optional[str] = None,
    export_extras: Optional[Dict] = None,
) -> TransactionContext:
    """
    Build a complete TransactionContext from HTML content.
    
    Args:
        html_content: Raw HTML from RealTrack detail page
        rt_id: RealTrack ID
        skip_index: Position in export listing
        html_path: Path to saved HTML file
        ingest_timestamp: When this was ingested (ISO format)
        export_extras: Additional fields from export TSV
    
    Returns:
        Complete TransactionContext
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    if not soup.find('font'):
        soup = BeautifulSoup(html_content, 'lxml')
    
    if ingest_timestamp is None:
        ingest_timestamp = datetime.now().isoformat()
    
    ctx = TransactionContext(
        rt_id=rt_id,
        skip_index=skip_index,
        html_path=html_path,
        ingest_timestamp=ingest_timestamp,
    )
    
    # === Transaction Header ===
    
    # Address parsing
    address_block = parse_address(soup)
    if isinstance(address_block, dict):
        ctx.transaction.address.address = address_block.get("Address", "")
        ctx.transaction.address.alternate_addresses = list(
            address_block.get("AlternateAddresses", [])
        )
    else:
        ctx.transaction.address.address = str(address_block)
    
    # Expand and deduplicate addresses (exclude the primary address)
    primary = ctx.transaction.address.address
    expanded = expand_address_ranges(primary)
    expanded.extend(ctx.transaction.address.alternate_addresses)
    deduped = deduplicate_addresses(expanded)
    ctx.transaction.address.alternate_addresses = [
        a for a in deduped if a != primary
    ]
    
    # City/Municipality
    city_data = parse_city(soup)
    ctx.transaction.address.city = city_data.get("City", "")
    ctx.transaction.address.municipality = city_data.get("Region", "") or city_data.get("Municipality", "")
    
    # Address suite
    suite_data = parse_address_suite(soup)
    if isinstance(suite_data, dict):
        ctx.transaction.address.address_suite = suite_data.get("AddressSuite", "")

    # Postal code from AddressBlock if available
    if isinstance(address_block, dict):
        ctx.transaction.address.postal_code = address_block.get("PostalCode", "")
    
    # Sale date and price
    sale_details = parse_sale_date_and_price(soup)
    if isinstance(sale_details, dict):
        ctx.transaction.sale_date = sale_details.get("SaleDate", "")
        ctx.transaction.sale_date_iso = sale_details.get("SaleDateISO", "")
        ctx.transaction.sale_price = sale_details.get("SalePrice", "")
        ctx.transaction.sale_price_raw = sale_details.get("SalePrice", "")
    
    # RT Number
    rt_data = parse_rt(soup)
    if isinstance(rt_data, dict):
        ctx.transaction.rt_number = rt_data.get("RTNumber", "")
    elif rt_data:
        ctx.transaction.rt_number = str(rt_data)
    
    # ARN
    ctx.transaction.arn = parse_arn(soup)
    
    # PINs
    pin_data = parse_pin(soup)
    if isinstance(pin_data, dict):
        pins = [pin_data.get("PIN", "")]
        ctx.transaction.pins = [p for p in pins if p]
    else:
        ctx.transaction.pins = [str(pin_data)] if pin_data else []
    
    # === Transferor (Seller) ===
    
    seller = parse_seller(soup)
    if isinstance(seller, dict):
        ctx.transferor.name = seller.get("Seller", "")
        ctx.transferor.contact = seller.get("SellerContact", "")
    
    seller_alts = parse_seller_alternate_names(soup)
    if isinstance(seller_alts, dict):
        ctx.transferor.alternate_names = [
            seller_alts.get(f"SellerAlternateName{i}", "")
            for i in range(1, 7)
            if seller_alts.get(f"SellerAlternateName{i}")
            and not _TITLE_PREFIX_PATTERN.match(seller_alts.get(f"SellerAlternateName{i}", ""))
        ]
    
    seller_structured = parse_seller_structured(soup)
    if isinstance(seller_structured, dict):
        ctx.transferor.company_lines = seller_structured.get("SellerStructuredCompanyLines", [])
        ctx.transferor.contact_lines = seller_structured.get("SellerStructuredContactLines", [])
        ctx.transferor.address_lines = seller_structured.get("SellerStructuredAddressLines", [])
    
    seller_phone = parse_seller_phone(soup)
    ctx.transferor.phone = seller_phone.get("SellerPhone", "") if isinstance(seller_phone, dict) else str(seller_phone)
    seller_addr = parse_seller_address(soup)
    ctx.transferor.address = seller_addr.get("SellerAddress", "") if isinstance(seller_addr, dict) else str(seller_addr)

    # Extract c/o company names from address → alternate_names
    ctx.transferor.address, ctx.transferor.alternate_names = _extract_co_from_address(
        ctx.transferor.address, ctx.transferor.alternate_names
    )

    # Fallback: if address parser returned empty, build from structured address_lines
    if not ctx.transferor.address and ctx.transferor.address_lines:
        ctx.transferor.address = ", ".join(ctx.transferor.address_lines)

    # Enhanced party identity
    party_identity = parse_all_party_identities(soup)
    ctx.transferor.phones = party_identity.get("seller_phones", [])
    ctx.transferor.officer_titles = party_identity.get("seller_officer_titles", [])
    ctx.transferor.aliases = party_identity.get("seller_aliases", [])
    ctx.transferor.attention = party_identity.get("seller_attention", "")
    if ctx.transferor.contact and looks_like_company(ctx.transferor.contact) and ctx.transferor.attention:
        ctx.transferor.contact = ctx.transferor.attention
    elif ctx.transferor.contact and _looks_like_address(ctx.transferor.contact) and ctx.transferor.attention:
        ctx.transferor.contact = ctx.transferor.attention
    elif not ctx.transferor.contact and ctx.transferor.attention:
        ctx.transferor.contact = ctx.transferor.attention

    # === Transferee (Buyer) ===
    
    buyer = parse_buyer_info(soup)
    if isinstance(buyer, dict):
        ctx.transferee.name = buyer.get("Buyer", "")
        ctx.transferee.contact = buyer.get("BuyerContact", "")
    
    buyer_alts = parse_buyer_alternate_names(soup)
    if isinstance(buyer_alts, dict):
        ctx.transferee.alternate_names = [
            buyer_alts.get(f"BuyerAlternateName{i}", "")
            for i in range(1, 7)
            if buyer_alts.get(f"BuyerAlternateName{i}")
            and not _TITLE_PREFIX_PATTERN.match(buyer_alts.get(f"BuyerAlternateName{i}", ""))
        ]
    
    buyer_structured = parse_buyer_structured(soup)
    if isinstance(buyer_structured, dict):
        ctx.transferee.company_lines = buyer_structured.get("BuyerStructuredCompanyLines", [])
        ctx.transferee.contact_lines = buyer_structured.get("BuyerStructuredContactLines", [])
        ctx.transferee.address_lines = buyer_structured.get("BuyerStructuredAddressLines", [])
    
    buyer_phone = parse_buyer_phone(soup)
    ctx.transferee.phone = buyer_phone.get("BuyerPhone", "") if isinstance(buyer_phone, dict) else str(buyer_phone)
    buyer_addr = parse_buyer_address(soup)
    ctx.transferee.address = buyer_addr.get("BuyerAddress", "") if isinstance(buyer_addr, dict) else str(buyer_addr)

    # Extract c/o company names from address → alternate_names
    ctx.transferee.address, ctx.transferee.alternate_names = _extract_co_from_address(
        ctx.transferee.address, ctx.transferee.alternate_names
    )

    # Fallback: if address parser returned empty, build from structured address_lines
    if not ctx.transferee.address and ctx.transferee.address_lines:
        ctx.transferee.address = ", ".join(ctx.transferee.address_lines)

    # Enhanced party identity for buyer
    ctx.transferee.phones = party_identity.get("buyer_phones", [])
    ctx.transferee.officer_titles = party_identity.get("buyer_officer_titles", [])
    ctx.transferee.aliases = party_identity.get("buyer_aliases", [])
    ctx.transferee.attention = party_identity.get("buyer_attention", "")
    if ctx.transferee.contact and looks_like_company(ctx.transferee.contact) and ctx.transferee.attention:
        ctx.transferee.contact = ctx.transferee.attention
    elif ctx.transferee.contact and _looks_like_address(ctx.transferee.contact) and ctx.transferee.attention:
        ctx.transferee.contact = ctx.transferee.attention
    elif not ctx.transferee.contact and ctx.transferee.attention:
        ctx.transferee.contact = ctx.transferee.attention

    # === Site Facts ===
    
    # Basic site data
    site = parse_site(soup)
    if isinstance(site, dict):
        ctx.site.site_area = site.get("SiteArea", "")
        ctx.site.site_area_units = site.get("SiteAreaUnits", "")
    
    # Site dimensions
    dimensions = parse_site_dimensions(soup)
    if isinstance(dimensions, dict):
        ctx.site.site_frontage = dimensions.get("SiteFrontage", "")
        ctx.site.site_frontage_units = dimensions.get("SiteFrontageUnits", "")
        ctx.site.site_depth = dimensions.get("SiteDepth", "")
        ctx.site.site_depth_units = dimensions.get("SiteDepthUnits", "")
    
    # Enhanced site facts
    enhanced_facts = extract_site_facts(soup)
    ctx.site.legal_description = enhanced_facts.get("legal_description", "")
    ctx.site.zoning = enhanced_facts.get("zoning", "")
    ctx.site.pins = enhanced_facts.get("pins", "")
    ctx.site.arn = enhanced_facts.get("arn", "")
    
    # Fill in from enhanced facts if not already set
    if not ctx.site.site_area:
        ctx.site.site_area = enhanced_facts.get("site_area", "")
        ctx.site.site_area_units = enhanced_facts.get("site_area_units", "")
    if not ctx.site.site_frontage:
        ctx.site.site_frontage = enhanced_facts.get("site_frontage", "")
        ctx.site.site_frontage_units = enhanced_facts.get("site_frontage_units", "")
    if not ctx.site.site_depth:
        ctx.site.site_depth = enhanced_facts.get("site_depth", "")
        ctx.site.site_depth_units = enhanced_facts.get("site_depth_units", "")
    
    # === Consideration ===
    
    consideration_raw = parse_consideration(soup)
    ctx.consideration.verbatim = consideration_raw
    
    # Parse consideration breakdown
    consideration_text = consideration_raw.lower() if consideration_raw else ""
    
    # Cash amount
    cash_match = re.search(r"cash[:\s]*\$?([\d,]+)", consideration_text)
    if cash_match:
        ctx.consideration.cash = cash_match.group(1).replace(",", "")
    
    # Assumed debt
    debt_match = re.search(r"(?:assumed|debt)[:\s]*\$?([\d,]+)", consideration_text)
    if debt_match:
        ctx.consideration.assumed_debt = debt_match.group(1).replace(",", "")
    
    # Chattels
    chattels_match = re.search(r"(?:chattels|inventory)[:\s]*\$?([\d,]+)", consideration_text)
    if chattels_match:
        ctx.consideration.chattels = chattels_match.group(1).replace(",", "")
    
    # Chargee/lender names (look for chargee patterns)
    chargee_pattern = re.compile(r"(?:chargee|lender|mortgagee)[:\s]*([A-Za-z\s,]+?)(?:\.|$|and)", re.IGNORECASE)
    for match in chargee_pattern.finditer(consideration_raw):
        chargee = match.group(1).strip()
        if chargee and chargee not in ctx.consideration.chargees:
            ctx.consideration.chargees.append(chargee)
    
    # === Broker Info ===
    
    brokerage = parse_brokerage(soup)
    if isinstance(brokerage, dict):
        ctx.broker.brokerage = brokerage.get("Brokerage", "")
        ctx.broker.phone = brokerage.get("BrokeragePhone", "")
    
    # === Description ===

    ctx.description = parse_description(soup)

    if ctx.description:
        extracted_sf = parse_building_size(ctx.description)
        if extracted_sf:
            ctx.export_extras.building_sf = extracted_sf

    # === Photos ===

    ctx.photos = parse_photos(soup)

    # === Export Extras ===
    
    if export_extras:
        ctx.export_extras.postal_code = export_extras.get("postal_code", "")
        ctx.export_extras.building_sf = export_extras.get("building_sf", "")
        # Store additional fields
        for key, value in export_extras.items():
            if key not in ("postal_code", "building_sf"):
                ctx.export_extras.additional_fields[key] = value
    
    return ctx


def parse_html_to_context(
    html_path: Path,
    rt_id: str = "",
    skip_index: int = 0,
    export_extras: Optional[Dict] = None,
) -> TransactionContext:
    """
    Parse HTML file to TransactionContext.
    
    Args:
        html_path: Path to HTML file
        rt_id: RealTrack ID (defaults to extracting from filename)
        skip_index: Position in export listing
        export_extras: Additional fields from export TSV
    
    Returns:
        Complete TransactionContext
    """
    html_content = html_path.read_text(encoding="utf-8")
    
    # Extract RT ID from filename if not provided
    if not rt_id:
        rt_id = html_path.stem.split("_")[0]
    
    ingest_timestamp = datetime.now().isoformat()
    
    return build_transaction_context(
        html_content=html_content,
        rt_id=rt_id,
        skip_index=skip_index,
        html_path=str(html_path),
        ingest_timestamp=ingest_timestamp,
        export_extras=export_extras,
    )


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    if len(sys.argv) > 1:
        html_path = Path(sys.argv[1])
        if html_path.exists():
            ctx = parse_html_to_context(html_path)
            print(json.dumps(ctx.to_dict(), indent=2))
        else:
            print(f"File not found: {html_path}")
    else:
        print("Usage: python build_transaction_context.py <html_file>")
