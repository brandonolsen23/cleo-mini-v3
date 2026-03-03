"""Versioned geocoded output: sandbox / promote / rollback / diff."""

from cleo.config import GEOCODED_DIR, GEO_REVIEWS_PATH
from cleo.versioning import VersionedStore

# Fields that can change without constituting a "regression" on reviewed-clean records.
# source_version: changes whenever upstream expand is re-promoted
# geocoded_at: timestamp of coordinate lookup
# provider_details: raw provider metadata (accuracy strings, match codes)
GEO_VOLATILE_FIELDS = {"source_version", "geocoded_at", "provider_details"}

store = VersionedStore(
    base_dir=GEOCODED_DIR,
    volatile_fields=GEO_VOLATILE_FIELDS,
    reviews_path=GEO_REVIEWS_PATH,
)
