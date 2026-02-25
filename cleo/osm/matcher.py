"""Address cross-reference matcher for OSM tenant data.

Takes existing proximity-based tenant data and classifies each tenant
as "confirmed" (address matches property) or "nearby" (different address).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from cleo.config import PROPERTIES_PATH
from cleo.osm.store import TenantStore, OSM_TENANTS_PATH
from cleo.properties.registry import load_registry

logger = logging.getLogger(__name__)


def _normalize_street(s: str) -> str:
    """Normalize street name for comparison."""
    s = s.upper().strip()
    for full, abbr in [
        ("STREET", "ST"), ("AVENUE", "AVE"), ("DRIVE", "DR"),
        ("ROAD", "RD"), ("BOULEVARD", "BLVD"), ("CRESCENT", "CRES"),
        ("COURT", "CT"), ("PLACE", "PL"), ("LANE", "LN"),
        ("CIRCLE", "CIR"), ("HIGHWAY", "HWY"), ("PARKWAY", "PKWY"),
        ("TERRACE", "TERR"), ("TRAIL", "TRL"),
        ("NORTH", "N"), ("SOUTH", "S"), ("EAST", "E"), ("WEST", "W"),
    ]:
        s = re.sub(rf'\b{full}\b', abbr, s)
        s = re.sub(rf'\b{abbr}\.\b', abbr, s)
    # Remove extra whitespace
    s = re.sub(r'\s+', ' ', s)
    return s


def _extract_street_number(address: str) -> tuple[str, str]:
    """Extract street number and street name from an address like '1063 Talbot St'."""
    m = re.match(r'^(\d+[\w-]*)\s+(.+)', address.strip())
    if m:
        return m.group(1).upper(), _normalize_street(m.group(2))
    return "", _normalize_street(address)


def _streets_match(prop_street: str, tenant_street: str) -> bool:
    """Check if two normalized street names are the same."""
    if not prop_street or not tenant_street:
        return False
    # Direct match
    if prop_street == tenant_street:
        return True
    # One contains the other (handles "Queen St" vs "Queen Queen Street" quirks)
    words_p = set(prop_street.split())
    words_t = set(tenant_street.split())
    # If they share the main street word(s) and differ only in direction/type
    shared = words_p & words_t
    if len(shared) >= 1:
        # Check the main name word (not just N/S/E/W/ST/AVE etc)
        filler = {"N", "S", "E", "W", "ST", "AVE", "DR", "RD", "BLVD", "CRES", "CT", "PL", "LN", "HWY"}
        main_p = words_p - filler
        main_t = words_t - filler
        if main_p and main_t and main_p & main_t:
            return True
    return False


def run_address_match() -> dict:
    """Classify existing tenants as confirmed vs nearby based on address matching.

    Updates osm_tenants.json in place, adding 'match_type' to each tenant.
    """
    store = TenantStore()
    reg = load_registry(PROPERTIES_PATH)
    props = reg.get("properties", {})

    confirmed_count = 0
    nearby_count = 0
    no_data_count = 0

    for pid, entry in store.properties.items():
        prop = props.get(pid, {})
        prop_addr = prop.get("address", "")
        if not prop_addr:
            no_data_count += 1
            continue

        prop_num, prop_street = _extract_street_number(prop_addr)

        for tenant in entry.get("tenants", []):
            tenant_street_raw = tenant.get("address", "")
            tenant_num = tenant.get("housenumber", "")

            if tenant_street_raw:
                tenant_street = _normalize_street(tenant_street_raw)

                if _streets_match(prop_street, tenant_street):
                    # Street matches — check if number matches or is close
                    if prop_num and tenant_num:
                        # Same number or within a small range (same block)
                        try:
                            p = int(re.match(r'\d+', prop_num).group())
                            t = int(re.match(r'\d+', tenant_num).group())
                            # Same block: within 100 of each other
                            if abs(p - t) <= 100:
                                tenant["match_type"] = "confirmed"
                                confirmed_count += 1
                                continue
                        except (ValueError, AttributeError):
                            pass
                        # Different number but same street
                        tenant["match_type"] = "nearby"
                        nearby_count += 1
                    else:
                        # Street matches but no number to compare
                        tenant["match_type"] = "confirmed"
                        confirmed_count += 1
                else:
                    tenant["match_type"] = "nearby"
                    nearby_count += 1
            else:
                # No address on tenant — can't confirm, mark as nearby
                tenant["match_type"] = "nearby"
                nearby_count += 1

    store.save()

    logger.info(
        "Address match: %d confirmed, %d nearby, %d properties without address",
        confirmed_count, nearby_count, no_data_count,
    )

    return {
        "confirmed": confirmed_count,
        "nearby": nearby_count,
        "properties_without_address": no_data_count,
    }
