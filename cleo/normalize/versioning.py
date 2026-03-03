"""Versioned normalization output: sandbox / promote / rollback / diff."""

from cleo.config import NORMALIZED_DIR, NORM_REVIEWS_PATH
from cleo.versioning import VersionedStore

NORM_VOLATILE_FIELDS = {
    "source_version", "source", "source_file",
    "city_status", "unit_type", "po_box", "rural_route", "building_name",
    "address_scope", "property_alt",
    # Brand-specific
    "brand", "brand_id", "store_name", "raw_coords",
    # GW-specific
    "gw_id", "pin",
}

store = VersionedStore(
    base_dir=NORMALIZED_DIR,
    volatile_fields=NORM_VOLATILE_FIELDS,
    reviews_path=NORM_REVIEWS_PATH,
)
