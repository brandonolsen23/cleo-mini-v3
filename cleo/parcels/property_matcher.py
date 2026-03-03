"""Property-to-parcel matching via ARN, PIN bridge, and spatial containment.

Matches properties from the registry to branded parcel boundaries harvested
from the provincial Assessment Parcel MapServer.

Matching priority (first match wins):
  1. ARN direct   — RT transaction.arn (15-digit) padded to 20 → branded parcel lookup
  2. PIN bridge   — RT PIN → GW record with same PIN → GW ARN → pad to 20 → lookup
  3. Spatial       — property (lat, lng) → point-in-polygon against all branded parcels

Output: data/parcels/property_parcel_index.json
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from cleo.config import (
    BRANDED_PARCELS_DIR,
    GW_PARSED_DIR,
    PARSED_DIR,
    PROPERTIES_PATH,
    PROPERTY_PARCEL_INDEX_PATH,
)

logger = logging.getLogger(__name__)


def _pad_arn(arn_15: str) -> str:
    """Pad a 15-digit ARN to 20-digit provincial format."""
    return arn_15 + "00000"


def _normalize_pin(pin: str) -> str:
    """Normalize PIN to bare 9-digit format (strip dashes)."""
    return pin.replace("-", "").strip()


class BrandedParcelIndex:
    """Unified index over all branded_parcels/*.json files.

    Provides:
    - ARN-keyed lookup (O(1) dict)
    - Spatial STRtree for point-in-polygon queries
    """

    def __init__(self, branded_dir: Path | None = None):
        self._dir = branded_dir or BRANDED_PARCELS_DIR
        self._arn_index: dict[str, dict] = {}  # 20-digit ARN -> parcel dict
        self._arn_to_city: dict[str, str] = {}  # 20-digit ARN -> city slug
        self._polys: list = []
        self._poly_arns: list[str] = []
        self._tree: Optional[STRtree] = None
        self._loaded = False

    def load(self) -> int:
        """Load all branded parcel files. Returns total parcel count."""
        if self._loaded:
            return len(self._arn_index)

        if not self._dir.exists():
            logger.warning("Branded parcels dir not found: %s", self._dir)
            self._loaded = True
            return 0

        total = 0
        polys = []
        poly_arns = []

        for f in sorted(self._dir.iterdir()):
            if not f.name.endswith(".json") or f.name == "london-test.json":
                continue

            city = f.stem
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load %s: %s", f, exc)
                continue

            parcels = data.get("parcels", {})
            for arn, parcel in parcels.items():
                self._arn_index[arn] = parcel
                self._arn_to_city[arn] = city

                # Build polygon for spatial index
                geom = parcel.get("geometry")
                if geom:
                    try:
                        poly = shape(geom)
                        if not poly.is_valid:
                            poly = poly.buffer(0)
                        if poly.is_valid and not poly.is_empty:
                            polys.append(poly)
                            poly_arns.append(arn)
                    except Exception:
                        pass

                total += 1

        self._polys = polys
        self._poly_arns = poly_arns
        if polys:
            self._tree = STRtree(polys)

        self._loaded = True
        logger.info(
            "Loaded %d branded parcels from %d cities (%d with geometry)",
            total,
            len(set(self._arn_to_city.values())),
            len(polys),
        )
        return total

    def get_by_arn(self, arn_20: str) -> Optional[dict]:
        """Look up a parcel by 20-digit ARN."""
        return self._arn_index.get(arn_20)

    def get_city(self, arn_20: str) -> str:
        """Get the city slug for a 20-digit ARN."""
        return self._arn_to_city.get(arn_20, "")

    def find_containing(self, lat: float, lng: float) -> Optional[str]:
        """Find the branded parcel ARN containing a point. Returns 20-digit ARN or None."""
        if self._tree is None:
            return None

        point = Point(lng, lat)
        candidates = self._tree.query(point)
        for idx in candidates:
            if self._polys[idx].contains(point):
                return self._poly_arns[idx]
        return None

    @property
    def total(self) -> int:
        return len(self._arn_index)

    @property
    def city_count(self) -> int:
        return len(set(self._arn_to_city.values()))


class PropertyParcelMatcher:
    """Match properties to branded parcels via ARN, PIN bridge, and spatial."""

    def __init__(self, branded_index: BrandedParcelIndex | None = None):
        self._index = branded_index or BrandedParcelIndex()
        self._properties: dict = {}
        self._parsed_cache: dict[str, dict] = {}
        self._gw_pin_to_arn: dict[str, str] = {}  # normalized PIN -> 15-digit ARN

    def _load_properties(self) -> dict:
        """Load properties registry."""
        if self._properties:
            return self._properties
        if not PROPERTIES_PATH.exists():
            return {}
        reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
        self._properties = reg.get("properties", {})
        return self._properties

    def _load_parsed(self, rt_id: str) -> dict:
        """Load a parsed RT record, with caching."""
        if rt_id in self._parsed_cache:
            return self._parsed_cache[rt_id]

        active = PARSED_DIR / "active"
        path = active / f"{rt_id}.json"
        if not path.exists():
            self._parsed_cache[rt_id] = {}
            return {}

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        self._parsed_cache[rt_id] = data
        return data

    def _build_gw_pin_bridge(self) -> dict[str, str]:
        """Build PIN → ARN mapping from GeoWarehouse records."""
        if self._gw_pin_to_arn:
            return self._gw_pin_to_arn

        gw_dir = GW_PARSED_DIR / "v001"
        if not gw_dir.exists():
            return {}

        for f in gw_dir.iterdir():
            if not f.name.endswith(".json"):
                continue
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            pin = rec.get("pin", "") or rec.get("registry", {}).get("pin", "")
            arn = rec.get("site_structure", {}).get("arn", "")
            if pin and arn and len(arn) >= 15:
                self._gw_pin_to_arn[_normalize_pin(pin)] = arn

        logger.info("Built GW PIN bridge: %d entries", len(self._gw_pin_to_arn))
        return self._gw_pin_to_arn

    def _get_rt_identifiers(self, prop: dict) -> tuple[list[str], list[str]]:
        """Extract ARNs (15-digit) and PINs (normalized) from all RT records for a property."""
        arns = []
        pins = []
        seen_arns = set()
        seen_pins = set()

        for rt_id in prop.get("rt_ids", []):
            parsed = self._load_parsed(rt_id)
            if not parsed:
                continue

            # Transaction ARN (the good one)
            txn = parsed.get("transaction", {})
            arn = txn.get("arn", "")
            if arn and len(arn) >= 15 and arn not in seen_arns:
                arns.append(arn)
                seen_arns.add(arn)

            # Transaction PINs
            for pin in txn.get("pins", []):
                norm = _normalize_pin(pin)
                if norm and len(norm) >= 9 and norm not in seen_pins:
                    pins.append(norm)
                    seen_pins.add(norm)

            # Site PINs (string, comma-separated or single)
            site_pins = parsed.get("site", {}).get("pins", "")
            if site_pins:
                for sp in str(site_pins).split(","):
                    norm = _normalize_pin(sp)
                    if norm and len(norm) >= 9 and norm not in seen_pins:
                        pins.append(norm)
                        seen_pins.add(norm)

        return arns, pins

    def match_all(self, dry_run: bool = False, limit: int | None = None) -> dict:
        """Run the full matching pipeline.

        Returns summary with match results and stats.
        """
        # Load everything
        self._index.load()
        props = self._load_properties()
        gw_bridge = self._build_gw_pin_bridge()

        if not props:
            return {"error": "No properties.json found"}
        if self._index.total == 0:
            return {"error": "No branded parcels loaded"}

        matches: dict[str, dict] = {}
        stats = {
            "arn_direct": 0,
            "pin_bridge": 0,
            "spatial": 0,
            "unmatched": 0,
            "no_identifiers_no_coords": 0,
        }

        items = list(props.items())
        if limit:
            items = items[:limit]

        for pid, prop in items:
            arns, pins = self._get_rt_identifiers(prop)

            # --- Method 1: ARN direct ---
            matched = False
            for arn in arns:
                padded = _pad_arn(arn)
                parcel = self._index.get_by_arn(padded)
                if parcel:
                    matches[pid] = self._build_match(
                        pid, padded, parcel, "arn_direct", prop
                    )
                    stats["arn_direct"] += 1
                    matched = True
                    break

            if matched:
                continue

            # --- Method 2: PIN bridge via GW ---
            for pin in pins:
                gw_arn = gw_bridge.get(pin)
                if not gw_arn:
                    continue
                padded = _pad_arn(gw_arn)
                parcel = self._index.get_by_arn(padded)
                if parcel:
                    matches[pid] = self._build_match(
                        pid, padded, parcel, "pin_bridge", prop
                    )
                    stats["pin_bridge"] += 1
                    matched = True
                    break

            if matched:
                continue

            # --- Method 3: Spatial containment ---
            lat = prop.get("lat")
            lng = prop.get("lng")
            if lat and lng:
                arn = self._index.find_containing(float(lat), float(lng))
                if arn:
                    parcel = self._index.get_by_arn(arn)
                    if parcel:
                        matches[pid] = self._build_match(
                            pid, arn, parcel, "spatial", prop
                        )
                        stats["spatial"] += 1
                        matched = True

            if not matched:
                if not arns and not pins and not (lat and lng):
                    stats["no_identifiers_no_coords"] += 1
                stats["unmatched"] += 1

        # Build result
        result = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "total_properties": len(items),
                "total_matched": len(matches),
                "match_rate": round(len(matches) / len(items) * 100, 1) if items else 0,
                "branded_parcels_loaded": self._index.total,
                "branded_parcel_cities": self._index.city_count,
                "gw_pin_bridge_size": len(gw_bridge),
                **stats,
            },
            "matches": matches,
        }

        if not dry_run:
            self._save(result)

        return result

    def _build_match(
        self,
        pid: str,
        arn_20: str,
        parcel: dict,
        method: str,
        prop: dict,
    ) -> dict:
        """Build a match record for one property."""
        brands = parcel.get("brands", [])
        brand_names = sorted(set(
            b["name"] if isinstance(b, dict) else str(b)
            for b in brands
        )) if brands else []

        return {
            "parcel_arn": arn_20,
            "city": self._index.get_city(arn_20),
            "method": method,
            "brands": brand_names,
            "brand_count": len(brand_names),
            "zoning": parcel.get("zoning"),
            "address": prop.get("address", ""),
            "prop_city": prop.get("city", ""),
        }

    def _save(self, result: dict) -> None:
        """Write property_parcel_index.json atomically."""
        PROPERTY_PARCEL_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = PROPERTY_PARCEL_INDEX_PATH.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        tmp.rename(PROPERTY_PARCEL_INDEX_PATH)
        logger.info(
            "Saved %d matches to %s",
            len(result["matches"]),
            PROPERTY_PARCEL_INDEX_PATH,
        )

    def status(self) -> dict:
        """Return current matching stats from disk."""
        if not PROPERTY_PARCEL_INDEX_PATH.exists():
            return {"matched": False}

        data = json.loads(PROPERTY_PARCEL_INDEX_PATH.read_text(encoding="utf-8"))
        return {
            "matched": True,
            **data.get("stats", {}),
            "generated_at": data.get("generated_at", ""),
        }


def match_properties(dry_run: bool = False, limit: int | None = None) -> dict:
    """Convenience function for CLI usage."""
    matcher = PropertyParcelMatcher()
    return matcher.match_all(dry_run=dry_run, limit=limit)
