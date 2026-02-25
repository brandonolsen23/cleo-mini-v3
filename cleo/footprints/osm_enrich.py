"""Enrich Microsoft building footprints with OSM metadata.

Queries the Overpass API for building footprints in areas where we have
Microsoft buildings, matches by polygon overlap, and enriches with OSM
tags (building type, name, address fields).
"""

from __future__ import annotations

import json
import logging
import math
import time
from typing import Optional

import httpx

from shapely.geometry import shape, Polygon
from shapely.strtree import STRtree

from cleo.config import FOOTPRINTS_PATH

logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

# Rate limit: ~1 req/2s
_DELAY = 2.0


def _bbox_query(south: float, west: float, north: float, east: float) -> str:
    """Build an Overpass query for building footprints in a bounding box."""
    return f"""
[out:json][timeout:60];
(
  way["building"]({south},{west},{north},{east});
);
out geom tags;
"""


def _query_overpass(query: str) -> list[dict]:
    """Execute an Overpass query with server failover."""
    for url in OVERPASS_URLS:
        try:
            client = httpx.Client(timeout=90)
            resp = client.post(url, data={"data": query})
            resp.raise_for_status()
            data = resp.json()
            client.close()
            return data.get("elements", [])
        except Exception as e:
            logger.warning("Overpass %s failed: %s", url, e)
            continue
    raise RuntimeError("All Overpass servers failed")


def _element_to_polygon(el: dict) -> Optional[Polygon]:
    """Convert an Overpass way element with geom to a Shapely Polygon."""
    geom = el.get("geometry", [])
    if len(geom) < 3:
        return None
    coords = [(pt["lon"], pt["lat"]) for pt in geom]
    # Close ring if needed
    if coords[0] != coords[-1]:
        coords.append(coords[0])
    try:
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly if poly.is_valid and not poly.is_empty else None
    except Exception:
        return None


def _cluster_footprints(features: list[dict], cell_deg: float = 0.01) -> dict[tuple[int, int], list[int]]:
    """Group building footprint indices by grid cell for area-based querying."""
    clusters: dict[tuple[int, int], list[int]] = {}
    for i, feat in enumerate(features):
        props = feat.get("properties", {})
        lat = props.get("centroid_lat")
        lng = props.get("centroid_lng")
        if lat is None or lng is None:
            continue
        cell = (int(lat / cell_deg), int(lng / cell_deg))
        clusters.setdefault(cell, []).append(i)
    return clusters


def _cell_bbox(cell: tuple[int, int], cell_deg: float = 0.01, pad: float = 0.001) -> tuple[float, float, float, float]:
    """Convert a grid cell to a bounding box (south, west, north, east) with padding."""
    cy, cx = cell
    south = cy * cell_deg - pad
    north = (cy + 1) * cell_deg + pad
    west = cx * cell_deg - pad
    east = (cx + 1) * cell_deg + pad
    return (south, west, north, east)


def enrich_with_osm(limit: int | None = None) -> dict:
    """Enrich filtered Microsoft footprints with OSM building metadata.

    For each cluster of Microsoft buildings, queries Overpass for OSM
    buildings in the same area, matches by polygon overlap, and copies
    OSM tags into the Microsoft features.

    Args:
        limit: Max number of area clusters to query (for testing).

    Returns:
        Summary stats dict.
    """
    if not FOOTPRINTS_PATH.exists():
        raise FileNotFoundError(f"Run 'cleo footprints' first: {FOOTPRINTS_PATH}")

    data = json.loads(FOOTPRINTS_PATH.read_text(encoding="utf-8"))
    features = data.get("features", [])
    if not features:
        return {"enriched": 0, "clusters_queried": 0, "osm_buildings_fetched": 0}

    # Cluster footprints by area
    clusters = _cluster_footprints(features)
    logger.info(
        "Enriching %d buildings across %d area clusters",
        len(features),
        len(clusters),
    )

    enriched = 0
    osm_total = 0
    osm_only_added = 0
    clusters_queried = 0
    t0 = time.time()

    cluster_keys = sorted(clusters.keys())
    if limit:
        cluster_keys = cluster_keys[:limit]

    for ci, cell in enumerate(cluster_keys):
        indices = clusters[cell]
        bbox = _cell_bbox(cell)

        # Query Overpass for this area
        query = _bbox_query(*bbox)
        try:
            time.sleep(_DELAY)
            elements = _query_overpass(query)
        except RuntimeError:
            logger.warning("Skipping cluster %s after Overpass failure", cell)
            continue

        clusters_queried += 1
        osm_total += len(elements)

        if not elements:
            continue

        # Build Shapely polygons for Microsoft buildings in this cluster
        ms_polys = []
        ms_indices = []
        for idx in indices:
            feat = features[idx]
            try:
                poly = shape(feat["geometry"])
                if poly.is_valid and not poly.is_empty:
                    ms_polys.append(poly)
                    ms_indices.append(idx)
            except Exception:
                continue

        if not ms_polys:
            continue

        # Build STRtree for fast spatial matching
        tree = STRtree(ms_polys)

        # Match OSM buildings to Microsoft buildings
        for el in elements:
            osm_poly = _element_to_polygon(el)
            if osm_poly is None:
                continue

            tags = el.get("tags", {})
            osm_tags = {
                "building_type": tags.get("building", ""),
                "building_name": tags.get("name", ""),
                "addr_street": tags.get("addr:street", ""),
                "addr_housenumber": tags.get("addr:housenumber", ""),
                "addr_city": tags.get("addr:city", ""),
                "addr_postcode": tags.get("addr:postcode", ""),
                "osm_id": f"way/{el['id']}",
            }

            # Find intersecting Microsoft buildings
            candidates = tree.query(osm_poly)
            best_overlap = 0
            best_idx = None

            for ci_idx in candidates:
                ms_poly = ms_polys[ci_idx]
                try:
                    overlap = ms_poly.intersection(osm_poly).area
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_idx = ms_indices[ci_idx]
                except Exception:
                    continue

            if best_idx is not None and best_overlap > 0:
                # Enrich the Microsoft feature with OSM tags
                props = features[best_idx].get("properties", {})
                for key, val in osm_tags.items():
                    if val:
                        props[key] = val
                features[best_idx]["properties"] = props
                enriched += 1

        if (ci + 1) % 50 == 0:
            elapsed = time.time() - t0
            logger.info(
                "  %d/%d clusters (%.0fs), %d enriched, %d OSM buildings",
                ci + 1,
                len(cluster_keys),
                elapsed,
                enriched,
                osm_total,
            )

    elapsed = time.time() - t0

    # Update meta
    data["meta"]["osm_enriched"] = enriched
    data["meta"]["osm_clusters_queried"] = clusters_queried
    data["meta"]["osm_buildings_fetched"] = osm_total
    data["meta"]["osm_enrich_elapsed_s"] = round(elapsed, 1)

    # Save back
    tmp = FOOTPRINTS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.rename(FOOTPRINTS_PATH)

    logger.info(
        "Enriched %d buildings from %d OSM buildings across %d clusters (%.1fs)",
        enriched,
        osm_total,
        clusters_queried,
        elapsed,
    )

    return {
        "enriched": enriched,
        "clusters_queried": clusters_queried,
        "osm_buildings_fetched": osm_total,
        "elapsed_s": round(elapsed, 1),
    }
