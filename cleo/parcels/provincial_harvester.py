"""Provincial parcel harvester — reads coordinates.json, queries ArcGIS.

Iterates over all geocoded addresses in the coordinate store, deduplicates
by rounded lat/lng, queries the provincial Assessment Parcel MapServer at
each unique point, and stores results in parcels.json.

Does NOT read from properties.json or expanded. The coordinate store is
the single input. Dedup and compilation happen downstream.

Saves progress frequently so the run can resume after a token expiry.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from cleo.config import COORDINATES_PATH, PARCELS_DIR
from cleo.geocode.store import CoordinateStore
from cleo.parcels.provincial import ProvincialParcelClient, TokenExpiredError
from cleo.parcels.store import ParcelStore

logger = logging.getLogger(__name__)

QUERIED_POINTS_PATH = PARCELS_DIR / "queried_points.json"

# Round coords to 5 decimal places (~1m precision) for dedup.
# Two addresses in the same building will collapse to one ArcGIS query.
ROUND_PRECISION = 5


def _point_key(lat: float, lng: float) -> str:
    """Build a dedup key from rounded coordinates."""
    return f"{round(lat, ROUND_PRECISION)},{round(lng, ROUND_PRECISION)}"


def _load_queried_points() -> set[str]:
    """Load the set of already-queried point keys."""
    if QUERIED_POINTS_PATH.exists():
        data = json.loads(QUERIED_POINTS_PATH.read_text(encoding="utf-8"))
        return set(data.get("points", []))
    return set()


def _save_queried_points(points: set[str]) -> None:
    """Save the set of queried point keys."""
    QUERIED_POINTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"total": len(points), "points": sorted(points)}
    QUERIED_POINTS_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _arcgis_to_geojson(geometry: dict) -> Optional[dict]:
    """Convert ArcGIS rings geometry to GeoJSON Polygon."""
    if not geometry:
        return None
    rings = geometry.get("rings")
    if rings:
        return {"type": "Polygon", "coordinates": rings}
    if "type" in geometry and "coordinates" in geometry:
        return geometry
    return None


def collect_unique_points(
    coord_store: CoordinateStore,
) -> list[tuple[str, float, float]]:
    """Collect unique lat/lng points from the coordinate store.

    Returns list of (point_key, lat, lng) tuples, deduplicated by
    rounded coordinates.
    """
    seen: dict[str, tuple[float, float]] = {}

    for addr_key in coord_store.addresses:
        best = coord_store.best_coords(addr_key)
        if best is None:
            continue
        lat, lng = best

        # Skip points outside Ontario (lat ~42-56, lng ~-95 to -74)
        if not (42.0 <= lat <= 56.0 and -95.0 <= lng <= -74.0):
            continue

        pk = _point_key(lat, lng)
        if pk not in seen:
            seen[pk] = (lat, lng)

    points = [(pk, lat, lng) for pk, (lat, lng) in seen.items()]
    points.sort(key=lambda x: x[0])
    return points


def harvest_from_coords(
    coord_store: CoordinateStore,
    parcel_store: ParcelStore,
    client: ProvincialParcelClient,
    limit: Optional[int] = None,
    save_every: int = 50,
) -> dict:
    """Harvest parcel polygons for all geocoded addresses.

    Reads coordinates.json, deduplicates by rounded lat/lng, queries
    provincial ArcGIS at each unique point, stores in parcels.json.

    Resumes from where it left off using queried_points.json.

    Args:
        coord_store: CoordinateStore with geocoded addresses.
        parcel_store: ParcelStore to write parcel features to.
        client: ProvincialParcelClient with valid token.
        limit: Max number of new points to query (for testing).
        save_every: Save progress every N queries.

    Returns:
        Summary dict.
    """
    start = time.time()

    # Collect unique points
    all_points = collect_unique_points(coord_store)
    logger.info("Unique geocoded points in Ontario: %d", len(all_points))

    # Load already-queried points for resume
    queried = _load_queried_points()
    logger.info("Already queried: %d points", len(queried))

    # Filter to pending
    pending = [(pk, lat, lng) for pk, lat, lng in all_points if pk not in queried]
    logger.info("Pending: %d points", len(pending))

    if limit is not None and len(pending) > limit:
        pending = pending[:limit]
        logger.info("Limited to: %d points", len(pending))

    if not pending:
        return {
            "total_points": len(all_points),
            "already_queried": len(queried),
            "pending": 0,
            "queried": 0,
            "parcels_found": 0,
            "no_parcel": 0,
            "errors": 0,
            "elapsed": 0.0,
        }

    queried_this_run = 0
    parcels_found = 0
    no_parcel = 0
    errors = 0
    batch_features: list[dict] = []

    try:
        for i, (pk, lat, lng) in enumerate(pending):
            try:
                features = client.query_at_point(lat, lng)
            except TokenExpiredError:
                logger.error(
                    "Token expired after %d queries. Progress saved. "
                    "Refresh token and re-run to continue.",
                    queried_this_run,
                )
                break
            except Exception as e:
                logger.warning("Error querying point %s: %s", pk, e)
                errors += 1
                queried.add(pk)
                queried_this_run += 1
                continue

            queried.add(pk)
            queried_this_run += 1

            if not features:
                no_parcel += 1
            else:
                feat = client.pick_containing_parcel(features, lat, lng)
                if feat is None:
                    no_parcel += 1
                else:
                    attrs = feat.get("attributes", {})
                    geom = feat.get("geometry", {})
                    geojson_geom = _arcgis_to_geojson(geom)

                    if geojson_geom:
                        props = {
                            k: v for k, v in attrs.items() if v is not None
                        }
                        props["source"] = "provincial"
                        props["query_lat"] = lat
                        props["query_lng"] = lng

                        batch_features.append({
                            "geometry": geojson_geom,
                            "properties": props,
                        })
                        parcels_found += 1
                    else:
                        no_parcel += 1

            # Save periodically
            if queried_this_run % save_every == 0:
                if batch_features:
                    result = parcel_store.add_parcels("provincial", batch_features)
                    logger.info(
                        "Progress: %d/%d queried, %d parcels found "
                        "(+%d added, %d dups), %d no result, %d errors",
                        queried_this_run, len(pending), parcels_found,
                        result["added"], result["skipped_dups"],
                        no_parcel, errors,
                    )
                    batch_features = []
                parcel_store.save()
                _save_queried_points(queried)

            if limit is not None and queried_this_run >= limit:
                break

    except KeyboardInterrupt:
        logger.info("Interrupted. Saving progress...")

    # Final save
    if batch_features:
        parcel_store.add_parcels("provincial", batch_features)
    parcel_store.save()
    _save_queried_points(queried)

    elapsed = time.time() - start
    logger.info(
        "Done: %d queried, %d parcels, %d no result, %d errors in %.1fs",
        queried_this_run, parcels_found, no_parcel, errors, elapsed,
    )

    return {
        "total_points": len(all_points),
        "already_queried": len(queried),
        "pending_before": len(pending),
        "queried": queried_this_run,
        "parcels_found": parcels_found,
        "no_parcel": no_parcel,
        "errors": errors,
        "elapsed": round(elapsed, 1),
    }
