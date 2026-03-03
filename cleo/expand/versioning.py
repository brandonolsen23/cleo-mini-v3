"""Versioned expansion output: sandbox / promote / rollback / diff."""

from cleo.config import EXPANDED_DIR, EXPAND_REVIEWS_PATH
from cleo.versioning import VersionedStore

EXPAND_VOLATILE_FIELDS = {"source_version"}

store = VersionedStore(
    base_dir=EXPANDED_DIR,
    volatile_fields=EXPAND_VOLATILE_FIELDS,
    reviews_path=EXPAND_REVIEWS_PATH,
)
