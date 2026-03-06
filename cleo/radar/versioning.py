"""Versioned Radar POI snapshots: sandbox / promote / rollback / diff."""

from cleo.config import RADAR_POIS_DIR
from cleo.versioning import VersionedStore

RADAR_VOLATILE_FIELDS: set[str] = set()

store = VersionedStore(
    base_dir=RADAR_POIS_DIR,
    volatile_fields=RADAR_VOLATILE_FIELDS,
)
