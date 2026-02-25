"""Download and filter Microsoft Canadian Building Footprints for Ontario.

Downloads the bulk GeoJSON, stream-parses it with ijson, and keeps only
buildings within 200m of our geocoded properties.  Uses a spatial grid
index (0.002-deg cells, ~220m at Ontario latitudes) for fast proximity
checks during the streaming pass.
"""

from __future__ import annotations

import json
import logging
import math
import time
import zipfile
from decimal import Decimal
from pathlib import Path

import httpx
import ijson

from cleo.config import (
    FOOTPRINTS_DIR,
    FOOTPRINTS_PATH,
    FOOTPRINTS_RAW_DIR,
    PROPERTIES_PATH,
)

logger = logging.getLogger(__name__)

MS_FOOTPRINTS_URL = (
    "https://minedbuildings.z5.web.core.windows.net/"
    "legacy/canadian-buildings-v2/Ontario.zip"
)

PROXIMITY_M = 50  # 50m — tight to catch only buildings at/near the property
CELL_DEG = 0.001  # ~110m at 44N — tight grid for fast filtering


def _decimal_to_float(obj):
    """Recursively convert decimal.Decimal values to float (ijson outputs Decimal)."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(v) for v in obj]
    return obj


def _grid_key(lat: float, lng: float) -> tuple[int, int]:
    return (int(lat / CELL_DEG), int(lng / CELL_DEG))


def _nearby_cells(lat: float, lng: float) -> list[tuple[int, int]]:
    cy, cx = _grid_key(lat, lng)
    return [(cy + dy, cx + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _polygon_centroid(coords: list) -> tuple[float, float] | None:
    """Compute centroid of a GeoJSON polygon ring (list of [lng, lat])."""
    ring = coords[0] if coords else []
    if len(ring) < 3:
        return None
    # Simple average of vertices (good enough for building footprints)
    n = len(ring) - 1  # last == first in GeoJSON rings
    if n < 1:
        return None
    sum_lat = sum(float(pt[1]) for pt in ring[:n])
    sum_lng = sum(float(pt[0]) for pt in ring[:n])
    return (sum_lat / n, sum_lng / n)


def _build_property_grid() -> tuple[dict[tuple[int, int], list[tuple[float, float]]], int]:
    """Build spatial grid index from geocoded properties.

    Returns (grid, count) where grid maps cell -> list of (lat, lng).
    """
    if not PROPERTIES_PATH.exists():
        return {}, 0

    reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    props = reg.get("properties", {})

    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    count = 0
    for prop in props.values():
        lat, lng = prop.get("lat"), prop.get("lng")
        if lat is None or lng is None:
            continue
        cell = _grid_key(lat, lng)
        grid.setdefault(cell, []).append((lat, lng))
        count += 1

    return grid, count


def _is_near_property(
    centroid_lat: float,
    centroid_lng: float,
    grid: dict[tuple[int, int], list[tuple[float, float]]],
) -> bool:
    """Check if a centroid is within PROXIMITY_M of any property in the grid."""
    for cell in _nearby_cells(centroid_lat, centroid_lng):
        for plat, plng in grid.get(cell, []):
            if _haversine_m(centroid_lat, centroid_lng, plat, plng) <= PROXIMITY_M:
                return True
    return False


def download_footprints(force: bool = False) -> Path:
    """Download Ontario.zip from Microsoft if not already present."""
    zip_path = FOOTPRINTS_RAW_DIR / "Ontario.zip"
    if zip_path.exists() and not force:
        size_mb = zip_path.stat().st_size / 1_048_576
        logger.info("Ontario.zip already exists (%.1f MB). Use force=True to re-download.", size_mb)
        return zip_path

    logger.info("Downloading Microsoft Building Footprints for Ontario...")
    logger.info("URL: %s", MS_FOOTPRINTS_URL)

    with httpx.stream("GET", MS_FOOTPRINTS_URL, timeout=600, follow_redirects=True) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        last_report = 0

        tmp = zip_path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1_048_576):
                f.write(chunk)
                downloaded += len(chunk)
                if total and (downloaded - last_report) > 10_000_000:
                    pct = 100 * downloaded / total
                    logger.info("  %.0f%% (%.1f / %.1f MB)", pct, downloaded / 1e6, total / 1e6)
                    last_report = downloaded

        tmp.rename(zip_path)

    size_mb = zip_path.stat().st_size / 1_048_576
    logger.info("Downloaded %.1f MB to %s", size_mb, zip_path)
    return zip_path


def filter_footprints(zip_path: Path | None = None) -> dict:
    """Stream-parse Ontario GeoJSON and filter to buildings near properties.

    Writes filtered buildings to FOOTPRINTS_PATH as a GeoJSON FeatureCollection.
    Returns summary stats.
    """
    if zip_path is None:
        zip_path = FOOTPRINTS_RAW_DIR / "Ontario.zip"

    if not zip_path.exists():
        raise FileNotFoundError(f"Download first: {zip_path}")

    # Build property grid
    grid, prop_count = _build_property_grid()
    if prop_count == 0:
        raise RuntimeError("No geocoded properties found. Run 'cleo properties' first.")
    logger.info("Built grid from %d geocoded properties (%d cells)", prop_count, len(grid))

    # Find the GeoJSON file inside the zip
    with zipfile.ZipFile(zip_path) as zf:
        geojson_names = [n for n in zf.namelist() if n.endswith(".geojson") or n.endswith(".json")]
        if not geojson_names:
            raise RuntimeError(f"No GeoJSON file found in {zip_path}")
        geojson_name = geojson_names[0]
        logger.info("Streaming %s from zip...", geojson_name)

        kept_features: list[dict] = []
        total_scanned = 0
        t0 = time.time()

        with zf.open(geojson_name) as gf:
            # ijson streams through the "features" array
            for feature in ijson.items(gf, "features.item"):
                total_scanned += 1
                if total_scanned % 500_000 == 0:
                    elapsed = time.time() - t0
                    logger.info(
                        "  Scanned %dk buildings, kept %d (%.0fs)",
                        total_scanned // 1000,
                        len(kept_features),
                        elapsed,
                    )

                geom = feature.get("geometry", {})
                geom_type = geom.get("type", "")
                coords = geom.get("coordinates", [])

                if geom_type == "Polygon":
                    centroid = _polygon_centroid(coords)
                elif geom_type == "MultiPolygon":
                    # Use first polygon's centroid
                    centroid = _polygon_centroid(coords[0]) if coords else None
                else:
                    continue

                if centroid is None:
                    continue

                clat, clng = centroid
                if _is_near_property(clat, clng, grid):
                    # Convert Decimal coords to float for JSON serialization
                    feature = _decimal_to_float(feature)
                    # Assign a stable ID based on position in source
                    feature["properties"] = feature.get("properties", {})
                    feature["properties"]["fp_id"] = f"ms_{total_scanned}"
                    feature["properties"]["centroid_lat"] = round(clat, 7)
                    feature["properties"]["centroid_lng"] = round(clng, 7)
                    kept_features.append(feature)

    elapsed = time.time() - t0

    # Write filtered output
    output = {
        "type": "FeatureCollection",
        "features": kept_features,
        "meta": {
            "source": "microsoft-canadian-buildings-v2",
            "total_scanned": total_scanned,
            "kept": len(kept_features),
            "proximity_m": PROXIMITY_M,
            "property_count": prop_count,
            "elapsed_s": round(elapsed, 1),
        },
    }

    tmp = FOOTPRINTS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False)
    tmp.rename(FOOTPRINTS_PATH)

    logger.info(
        "Filtered %d buildings from %d total (%.1fs). Saved to %s",
        len(kept_features),
        total_scanned,
        elapsed,
        FOOTPRINTS_PATH,
    )

    return {
        "total_scanned": total_scanned,
        "kept": len(kept_features),
        "property_count": prop_count,
        "elapsed_s": round(elapsed, 1),
    }


def load_footprints() -> dict:
    """Load filtered footprints from disk."""
    if not FOOTPRINTS_PATH.exists():
        return {"type": "FeatureCollection", "features": [], "meta": {}}
    return json.loads(FOOTPRINTS_PATH.read_text(encoding="utf-8"))


def footprint_status() -> dict:
    """Return status info about footprint data."""
    zip_path = FOOTPRINTS_RAW_DIR / "Ontario.zip"
    status = {
        "zip_exists": zip_path.exists(),
        "zip_size_mb": round(zip_path.stat().st_size / 1e6, 1) if zip_path.exists() else 0,
        "buildings_file_exists": FOOTPRINTS_PATH.exists(),
        "building_count": 0,
        "meta": {},
    }

    if FOOTPRINTS_PATH.exists():
        data = json.loads(FOOTPRINTS_PATH.read_text(encoding="utf-8"))
        status["building_count"] = len(data.get("features", []))
        status["meta"] = data.get("meta", {})

    return status
