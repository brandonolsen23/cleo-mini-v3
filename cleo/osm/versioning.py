"""Versioned OSM POI snapshots: sandbox / promote / rollback / diff."""

from cleo.config import OSM_POIS_DIR
from cleo.versioning import VersionedStore

OSM_VOLATILE_FIELDS: set[str] = set()

store = VersionedStore(
    base_dir=OSM_POIS_DIR,
    volatile_fields=OSM_VOLATILE_FIELDS,
)
