"""Enrich properties.json with parcel boundary and consolidation data.

Delegates to consolidate.consolidate() which handles parcel attribute
enrichment, parcel grouping, and brand spatial matching in one pass.
"""

from __future__ import annotations

from cleo.parcels.consolidate import consolidate


def enrich_properties(dry_run: bool = False) -> dict:
    """Add parcel fields and consolidation data to properties.json.

    This is a thin wrapper around consolidate() for backward compatibility.
    """
    return consolidate(dry_run=dry_run)
