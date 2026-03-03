"""Official Ontario municipality list — loaded from data/municipalities.json.

This is the canonical source of truth for city name validation.
The list comes from AMO (Association of Municipalities of Ontario)
and contains all 414 lower-tier and single-tier municipalities.

Usage:
    from cleo.normalize.municipalities import is_official, get_canonical, get_info

    is_official("LONDON")          # True
    get_canonical("LONDON")        # "London"
    get_canonical("XYZVILLE")      # None
    get_info("LONDON")             # {"canonical": "London", "tier": "lower", ...}
"""

import json
from pathlib import Path
from typing import Dict, Optional

from cleo.config import DATA_DIR

_MUNICIPALITIES_PATH = DATA_DIR / "municipalities.json"

# Lazy-loaded cache
_cache: Optional[Dict[str, dict]] = None


def _load() -> Dict[str, dict]:
    """Load municipalities.json and return the municipalities dict."""
    global _cache
    if _cache is not None:
        return _cache
    if not _MUNICIPALITIES_PATH.exists():
        _cache = {}
        return _cache
    with open(_MUNICIPALITIES_PATH) as f:
        data = json.load(f)
    _cache = data.get("municipalities", {})
    return _cache


def is_official(city_upper: str) -> bool:
    """Check if an uppercase city name is an official municipality."""
    return city_upper in _load()


def get_canonical(city_upper: str) -> Optional[str]:
    """Get the canonical (properly-cased) name for an official municipality.

    Returns None if not found.
    """
    entry = _load().get(city_upper)
    return entry["canonical"] if entry else None


def get_info(city_upper: str) -> Optional[dict]:
    """Get full municipality info (canonical, tier, upper_tier, upper_tier_type).

    Returns None if not found.
    """
    return _load().get(city_upper)


def all_canonical_names() -> set[str]:
    """Return the set of all canonical municipality names (proper case)."""
    return {v["canonical"] for v in _load().values()}


def reload():
    """Force reload from disk (useful after updating municipalities.json)."""
    global _cache
    _cache = None
    _load()
