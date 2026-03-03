"""Versioned parcel resolution output: sandbox / promote / rollback / diff."""

from cleo.config import PARCELLED_DIR, PARCELLED_REVIEWS_PATH
from cleo.versioning import VersionedStore

PARCELLED_VOLATILE_FIELDS = {"source_version", "cached_at"}

store = VersionedStore(
    base_dir=PARCELLED_DIR,
    volatile_fields=PARCELLED_VOLATILE_FIELDS,
    reviews_path=PARCELLED_REVIEWS_PATH,
)
