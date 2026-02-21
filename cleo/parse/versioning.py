"""Versioned parse output: sandbox / promote / rollback / diff.

Thin wrapper around the generic VersionedStore for parse data.
"""

from pathlib import Path
from typing import Dict, List, Optional

from cleo.config import DATA_DIR, PARSED_DIR
from cleo.versioning import VersionedStore

# Fields that change between runs but don't represent real diffs
VOLATILE_FIELDS = {"ingest_timestamp", "html_path", "skip_index"}

_store = VersionedStore(
    base_dir=PARSED_DIR,
    volatile_fields=VOLATILE_FIELDS,
    reviews_path=DATA_DIR / "reviews.json",
)


# Re-export all functions for backward compatibility
def sandbox_path() -> Path:
    return _store.sandbox_path()


def active_symlink() -> Path:
    return _store.active_symlink()


def sandbox_exists() -> bool:
    return _store.sandbox_exists()


def ensure_sandbox() -> Path:
    return _store.ensure_sandbox()


def discard_sandbox() -> bool:
    return _store.discard_sandbox()


def list_versions() -> List[str]:
    return _store.list_versions()


def active_version() -> Optional[str]:
    return _store.active_version()


def active_dir() -> Optional[Path]:
    return _store.active_dir()


def promote() -> str:
    return _store.promote()


def rollback(version: str) -> None:
    _store.rollback(version)


def diff_sandbox_vs_active() -> Dict:
    return _store.diff_sandbox_vs_active()
