"""Versioned compiled output: sandbox / promote / rollback / diff."""

from cleo.config import COMPILED_DIR, COMPILED_REVIEWS_PATH
from cleo.versioning import VersionedStore

# source_versions changes whenever upstream stages are promoted — not a real diff
COMPILED_VOLATILE_FIELDS = {"source_versions"}

store = VersionedStore(
    base_dir=COMPILED_DIR,
    volatile_fields=COMPILED_VOLATILE_FIELDS,
    reviews_path=COMPILED_REVIEWS_PATH,
)
