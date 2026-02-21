"""Versioned extraction output: sandbox / promote / rollback / diff."""

from cleo.config import EXTRACTED_DIR, EXTRACT_REVIEWS_PATH
from cleo.versioning import VersionedStore

EXTRACT_VOLATILE_FIELDS = {"source_version"}

store = VersionedStore(
    base_dir=EXTRACTED_DIR,
    volatile_fields=EXTRACT_VOLATILE_FIELDS,
    reviews_path=EXTRACT_REVIEWS_PATH,
)
