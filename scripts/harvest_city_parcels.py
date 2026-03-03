"""Harvest branded parcels for a municipality.

Pipeline:
  1. Overpass query for all branded/named POIs in the city bbox
  2. For each POI, query ArcGIS for the containing parcel
  3. Deduplicate parcels (many POIs on one parcel)
  4. Query addresses and zoning for each unique parcel
  5. Save: parcel polygons + POI brands + addresses + zoning

Usage:
    # Using municipal ArcGIS endpoints (requires service in services.json):
    .venv/bin/python scripts/harvest_city_parcels.py london
    .venv/bin/python scripts/harvest_city_parcels.py london --dry-run

    # Using provincial Assessment Parcel (requires AGMAPS_TOKEN in .env):
    .venv/bin/python scripts/harvest_city_parcels.py london --provincial
    .venv/bin/python scripts/harvest_city_parcels.py hamilton --provincial
    .venv/bin/python scripts/harvest_city_parcels.py --provincial --bbox 43.20,-79.95,43.30,-79.75 --name hamilton
"""

import argparse
import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cleo.parcels.client import ArcGISClient
from cleo.parcels.provincial import ProvincialParcelClient, TokenExpiredError
from cleo.parcels.registry import ServiceRegistry

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "branded_parcels"

# City bounding boxes: (south, west, north, east)
# Generous bounds to catch outskirts
CITY_BBOX = {
    # === Original 32 cities ===
    "london": (42.85, -81.42, 43.10, -81.08),
    "barrie": (44.30, -79.80, 44.46, -79.55),
    "brantford": (43.08, -80.35, 43.20, -80.18),
    "oxford": (42.95, -80.95, 43.28, -80.50),  # county-wide
    "grey": (44.15, -81.20, 44.82, -80.40),     # county-wide
    "elgin": (42.55, -81.40, 42.85, -80.80),    # county-wide
    "hamilton": (43.18, -80.00, 43.32, -79.72),
    "windsor": (42.25, -83.15, 42.38, -82.88),
    "kingston": (44.18, -76.62, 44.30, -76.40),
    "peterborough": (44.25, -78.40, 44.36, -78.26),
    "sudbury": (46.42, -81.10, 46.56, -80.88),
    "cornwall": (44.98, -74.84, 45.06, -74.70),
    "north-bay": (46.26, -79.54, 46.36, -79.40),
    "brampton": (43.63, -79.84, 43.80, -79.65),
    "st-catharines": (43.12, -79.30, 43.22, -79.16),
    "niagara-falls": (43.03, -79.14, 43.14, -79.00),
    "cambridge": (43.31, -80.40, 43.44, -80.26),
    "waterloo": (43.42, -80.60, 43.52, -80.46),
    "kitchener": (43.38, -80.58, 43.50, -80.40),
    "oshawa": (43.83, -78.94, 43.94, -78.80),
    "guelph": (43.48, -80.34, 43.60, -80.18),
    "belleville": (44.12, -77.44, 44.22, -77.30),
    "sarnia": (42.93, -82.48, 43.04, -82.32),
    "chatham": (42.36, -82.24, 42.46, -82.14),
    "orangeville": (43.87, -80.14, 43.96, -80.04),
    "st-thomas": (42.74, -81.24, 42.82, -81.14),
    "woodstock": (43.08, -80.82, 43.18, -80.70),
    "owen-sound": (44.53, -80.98, 44.62, -80.88),
    "burlington": (43.28, -79.90, 43.42, -79.70),
    "oakville": (43.38, -79.78, 43.50, -79.60),
    "thunder-bay": (48.34, -89.34, 48.48, -89.16),
    "sault-ste-marie": (46.46, -84.40, 46.58, -84.26),
    # === Tier 1 — GTA suburbs (high property count) ===
    "mississauga": (43.50, -79.78, 43.66, -79.50),
    "markham": (43.82, -79.44, 43.98, -79.22),
    "vaughan": (43.76, -79.60, 43.92, -79.38),
    "richmond-hill": (43.84, -79.50, 43.94, -79.36),
    "whitby": (43.82, -78.98, 43.94, -78.86),
    "newmarket": (44.02, -79.50, 44.08, -79.40),
    "ajax": (43.82, -79.10, 43.90, -78.96),
    "pickering": (43.80, -79.16, 43.92, -79.02),
    "aurora": (43.98, -79.50, 44.02, -79.42),
    "clarington": (43.85, -78.72, 44.00, -78.50),  # includes Bowmanville, Courtice, Newcastle
    "caledon": (43.80, -80.00, 43.95, -79.80),     # includes Bolton
    "halton-hills": (43.58, -80.00, 43.68, -79.86), # includes Georgetown, Acton
    "milton": (43.48, -80.00, 43.56, -79.82),
    "innisfil": (44.24, -79.68, 44.34, -79.50),
    # === Tier 2 — Mid-Ontario core territory ===
    "orillia": (44.58, -79.46, 44.66, -79.38),
    "welland": (42.96, -79.28, 43.02, -79.20),
    "stratford": (43.34, -81.02, 43.40, -80.92),
    "collingwood": (44.48, -80.26, 44.52, -80.18),
    "midland": (44.72, -79.92, 44.76, -79.86),     # includes Penetanguishene nearby
    "wasaga-beach": (44.50, -80.04, 44.56, -79.94),
    "bradford": (44.10, -79.60, 44.16, -79.52),     # Bradford West Gwillimbury
    "new-tecumseth": (44.04, -79.78, 44.14, -79.68), # includes Alliston, Tottenham
    "simcoe": (42.82, -80.34, 42.88, -80.28),       # Norfolk County hub
    "cobourg": (43.94, -78.20, 44.00, -78.12),
    "port-hope": (43.92, -78.32, 43.98, -78.26),
    "brockville": (44.56, -75.72, 44.62, -75.64),
    "lindsay": (44.32, -78.78, 44.38, -78.70),      # Kawartha Lakes hub
    "leamington": (42.02, -82.64, 42.10, -82.54),
    "kingsville": (42.02, -82.78, 42.08, -82.70),
    "amherstburg": (42.08, -83.14, 42.14, -83.06),
    "essex": (42.16, -82.86, 42.22, -82.78),
    "tecumseh": (42.28, -82.92, 42.34, -82.86),
    "lasalle": (42.22, -83.10, 42.28, -83.02),
    "lakeshore": (42.24, -82.72, 42.32, -82.52),    # wide — includes Tilbury, Stoney Point
    "tillsonburg": (42.84, -80.76, 42.90, -80.70),
    "strathroy": (42.94, -81.66, 43.00, -81.58),
    "napanee": (44.22, -76.98, 44.28, -76.90),
    "fort-erie": (42.88, -79.08, 42.96, -79.00),
    "port-colborne": (42.86, -79.28, 42.92, -79.20),
    "lincoln": (43.12, -79.52, 43.20, -79.38),      # includes Beamsville, Vineland
    "pelham": (43.02, -79.38, 43.08, -79.28),       # includes Fonthill
    "thorold": (43.08, -79.22, 43.12, -79.16),
    "grimsby": (43.18, -79.58, 43.22, -79.50),
    "niagara-on-the-lake": (43.18, -79.14, 43.28, -79.02),
    "stoney-creek": (43.18, -79.72, 43.26, -79.62),
    # === Tier 2 — Southwestern Ontario ===
    "goderich": (43.72, -81.74, 43.76, -81.68),
    "kincardine": (44.16, -81.66, 44.20, -81.62),
    "port-elgin": (44.42, -81.42, 44.46, -81.38),
    "hanover": (44.14, -81.04, 44.18, -80.98),
    "listowel": (43.72, -80.98, 43.76, -80.92),
    "st-marys": (43.24, -81.18, 43.28, -81.12),
    "ingersoll": (43.02, -80.92, 43.06, -80.86),
    "paris": (43.18, -80.42, 43.22, -80.36),
    "fergus": (43.86, -80.40, 43.90, -80.34),       # Centre Wellington
    "shelburne": (44.06, -80.22, 44.10, -80.18),
    # === Tier 2 — Eastern Ontario ===
    "hawkesbury": (45.58, -74.62, 45.62, -74.58),
    "smiths-falls": (44.88, -76.04, 44.92, -75.98),
    "pembroke": (45.80, -77.14, 45.84, -77.08),
    "perth": (44.88, -76.28, 44.92, -76.22),
    "carleton-place": (45.12, -76.18, 45.16, -76.12),
    "renfrew": (45.46, -76.70, 45.50, -76.66),
    "brighton": (44.04, -77.78, 44.08, -77.72),
    "trenton": (44.08, -77.60, 44.12, -77.54),      # Quinte West
    # === Tier 2 — Cottage country / Muskoka ===
    "bracebridge": (44.98, -79.34, 45.02, -79.28),
    "gravenhurst": (44.90, -79.40, 44.94, -79.34),
    "huntsville": (45.30, -79.24, 45.34, -79.18),
    "parry-sound": (45.32, -80.06, 45.36, -80.00),
}


def fetch_city_pois(city: str, bbox: tuple) -> list[dict]:
    """Fetch branded/named POIs for a city from Overpass."""
    south, west, north, east = bbox
    query = f"""
[out:json][timeout:60];
(
  node["name"]["shop"]({south},{west},{north},{east});
  node["name"]["amenity"~"restaurant|fast_food|cafe|bar|bank|fuel|pharmacy|dentist|doctors|veterinary"]({south},{west},{north},{east});
  node["brand"]({south},{west},{north},{east});
  way["name"]["shop"]({south},{west},{north},{east});
  way["name"]["amenity"~"restaurant|fast_food|cafe|bar|bank|fuel|pharmacy|dentist|doctors|veterinary"]({south},{west},{north},{east});
  way["brand"]({south},{west},{north},{east});
);
out center tags;
"""

    for url in OVERPASS_URLS:
        try:
            logger.info("Querying Overpass for %s POIs (%s)...", city, url.split("/")[2])
            resp = httpx.post(url, data={"data": query}, timeout=90)
            resp.raise_for_status()
            data = resp.json()
            elements = data.get("elements", [])
            logger.info("Got %d POIs", len(elements))

            pois = []
            for el in elements:
                tags = el.get("tags", {})
                if el["type"] == "node":
                    lat, lng = el.get("lat"), el.get("lon")
                elif "center" in el:
                    lat, lng = el["center"].get("lat"), el["center"].get("lon")
                else:
                    continue
                if lat is None or lng is None:
                    continue

                pois.append({
                    "osm_id": f"{el['type']}/{el['id']}",
                    "name": tags.get("name", ""),
                    "brand": tags.get("brand", tags.get("operator", "")),
                    "type": tags.get("shop") or tags.get("amenity") or "other",
                    "lat": lat,
                    "lng": lng,
                    "addr_street": tags.get("addr:street", ""),
                    "addr_number": tags.get("addr:housenumber", ""),
                    "addr_city": tags.get("addr:city", ""),
                })
            return pois

        except Exception as e:
            logger.warning("Overpass %s failed: %s", url, e)
            continue

    raise RuntimeError("All Overpass servers failed")


def _point_in_ring(px: float, py: float, ring: list) -> bool:
    """Ray-casting point-in-polygon test for a single ring."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _pick_containing_parcel(features: list[dict], lat: float, lng: float) -> dict:
    """Pick the ArcGIS feature whose polygon contains the point.

    Returns the containing feature, or the first feature if none contain the point.
    """
    for feat in features:
        rings = feat.get("geometry", {}).get("rings", [])
        if not rings:
            continue
        # Check outer ring (first ring); coordinates are [lng, lat]
        if _point_in_ring(lng, lat, rings[0]):
            return feat
    return features[0]


def harvest_parcels(
    pois: list[dict],
    service_config,
    arcgis: ArcGISClient,
    fetch_addresses: bool = True,
    fetch_zoning: bool = True,
) -> dict:
    """For each POI, find the containing parcel via ArcGIS.

    Returns {
        parcels: {gis_id: {polygon, attributes, addresses, zoning, brands}},
        stats: {...}
    }
    """
    parcels = {}  # gis_id -> parcel data
    poi_to_parcel = {}  # poi osm_id -> gis_id
    no_parcel = []

    logger.info("\nQuerying ArcGIS for parcel at each POI (%d total)...", len(pois))

    for i, poi in enumerate(pois):
        if (i + 1) % 50 == 0:
            logger.info("  Progress: %d/%d POIs (found %d unique parcels)", i + 1, len(pois), len(parcels))

        features = arcgis.query_at_point(
            service_config.parcels_url,
            lat=poi["lat"],
            lng=poi["lng"],
            srid=service_config.srid,
            buffer_m=15.0,
        )

        if not features:
            no_parcel.append(poi)
            continue

        # Pick the feature whose polygon actually contains the POI point.
        # Fall back to the first result if none contain the point.
        feat = _pick_containing_parcel(features, poi["lat"], poi["lng"])
        attrs = feat.get("attributes", {})
        geom = feat.get("geometry", {})

        # Get a stable parcel identifier
        gis_id = attrs.get("GIS_ID") or attrs.get("OBJECTID") or attrs.get("PARCELID")
        if gis_id is None:
            no_parcel.append(poi)
            continue

        gis_id = str(gis_id)
        poi_to_parcel[poi["osm_id"]] = gis_id

        if gis_id not in parcels:
            # New parcel — extract polygon
            rings = geom.get("rings", [])
            parcels[gis_id] = {
                "gis_id": gis_id,
                "attributes": {k: v for k, v in attrs.items() if v is not None},
                "geometry": {"type": "Polygon", "coordinates": rings} if rings else None,
                "brands": [],
                "addresses": [],
                "zoning": None,
            }

        # Add brand to parcel
        brand_name = poi.get("brand") or poi.get("name")
        if brand_name and brand_name not in [b["name"] for b in parcels[gis_id]["brands"]]:
            parcels[gis_id]["brands"].append({
                "name": brand_name,
                "type": poi.get("type", ""),
                "lat": poi["lat"],
                "lng": poi["lng"],
            })

    logger.info("Found %d unique parcels from %d POIs (%d had no parcel)",
                len(parcels), len(pois), len(no_parcel))

    # Step 2: Fetch addresses for each unique parcel
    if fetch_addresses and service_config.address_url and service_config.parcel_link_field:
        logger.info("\nFetching addresses for %d parcels...", len(parcels))
        link_field = service_config.parcel_link_field
        addr_field = service_config.address_field or "FullAddress"

        for i, (gis_id, parcel) in enumerate(parcels.items()):
            if (i + 1) % 50 == 0:
                logger.info("  Progress: %d/%d parcels", i + 1, len(parcels))

            features = arcgis.query_by_where(
                service_config.address_url,
                where=f"{link_field}={gis_id}",
                out_fields=f"{addr_field},{link_field}",
                return_geometry=True,
            )
            for feat in features:
                addr_attrs = feat.get("attributes", {})
                geom = feat.get("geometry", {})
                parcel["addresses"].append({
                    "address": addr_attrs.get(addr_field, ""),
                    "lat": geom.get("y"),
                    "lng": geom.get("x"),
                })

        total_addrs = sum(len(p["addresses"]) for p in parcels.values())
        logger.info("Found %d addresses across %d parcels", total_addrs, len(parcels))

    # Step 3: Fetch zoning for each unique parcel
    if fetch_zoning and service_config.zoning_url:
        logger.info("\nFetching zoning for %d parcels...", len(parcels))

        for i, (gis_id, parcel) in enumerate(parcels.items()):
            if (i + 1) % 50 == 0:
                logger.info("  Progress: %d/%d parcels", i + 1, len(parcels))

            if not parcel.get("geometry") or not parcel["geometry"].get("coordinates"):
                continue

            # Use centroid of parcel
            rings = parcel["geometry"]["coordinates"]
            all_pts = [pt for ring in rings for pt in ring]
            if not all_pts:
                continue
            center_lng = sum(p[0] for p in all_pts) / len(all_pts)
            center_lat = sum(p[1] for p in all_pts) / len(all_pts)

            zoning = arcgis.query_zoning_at_point(
                service_config.zoning_url,
                lat=center_lat,
                lng=center_lng,
                srid=service_config.srid,
            )
            if zoning:
                parcel["zoning"] = {k: v for k, v in zoning.items() if v is not None}

        with_zoning = sum(1 for p in parcels.values() if p.get("zoning"))
        logger.info("Got zoning for %d/%d parcels", with_zoning, len(parcels))

    return {
        "parcels": parcels,
        "stats": {
            "total_pois": len(pois),
            "unique_parcels": len(parcels),
            "no_parcel": len(no_parcel),
            "total_brands": sum(len(p["brands"]) for p in parcels.values()),
            "total_addresses": sum(len(p["addresses"]) for p in parcels.values()),
        },
    }


def harvest_parcels_provincial(
    pois: list[dict],
    client: ProvincialParcelClient,
) -> dict:
    """For each POI, find the containing parcel via the provincial MapServer.

    Uses the MPAC Assessment Parcel layer which provides province-wide coverage
    with ARN/PIN data and proper parcel polygons.

    Returns {
        parcels: {parcel_key: {polygon, attributes, brands}},
        stats: {...}
    }
    """
    parcels = {}  # parcel_key -> parcel data
    no_parcel = []

    logger.info("\nQuerying provincial Assessment Parcel MapServer for %d POIs...", len(pois))

    for i, poi in enumerate(pois):
        if (i + 1) % 50 == 0:
            logger.info(
                "  Progress: %d/%d POIs (found %d unique parcels, %d requests)",
                i + 1, len(pois), len(parcels), client.request_count,
            )

        features = client.query_at_point(poi["lat"], poi["lng"])

        if not features:
            no_parcel.append(poi)
            continue

        feat = client.pick_containing_parcel(features, poi["lat"], poi["lng"])
        if feat is None:
            no_parcel.append(poi)
            continue

        attrs = feat.get("attributes", {})
        geom = feat.get("geometry", {})

        # Build a stable key from ARN or PIN or OBJECTID
        arn = attrs.get("ARN") or attrs.get("ASSESSMENT_ROLL_NUMBER") or ""
        pin = attrs.get("PIN") or attrs.get("PropertyIdentificationNumber") or ""
        obj_id = attrs.get("OBJECTID") or attrs.get("FID") or ""
        parcel_key = str(arn or pin or obj_id)

        if not parcel_key:
            no_parcel.append(poi)
            continue

        if parcel_key not in parcels:
            rings = geom.get("rings", [])
            parcels[parcel_key] = {
                "gis_id": parcel_key,
                "arn": str(arn) if arn else None,
                "pin": str(pin) if pin else None,
                "source": "provincial",
                "attributes": {k: v for k, v in attrs.items() if v is not None},
                "geometry": {"type": "Polygon", "coordinates": rings} if rings else None,
                "brands": [],
                "addresses": [],
                "zoning": None,
            }

        # Add brand to parcel
        brand_name = poi.get("brand") or poi.get("name")
        if brand_name and brand_name not in [b["name"] for b in parcels[parcel_key]["brands"]]:
            parcels[parcel_key]["brands"].append({
                "name": brand_name,
                "type": poi.get("type", ""),
                "lat": poi["lat"],
                "lng": poi["lng"],
            })

    logger.info(
        "Found %d unique parcels from %d POIs (%d had no parcel, %d requests)",
        len(parcels), len(pois), len(no_parcel), client.request_count,
    )

    return {
        "parcels": parcels,
        "stats": {
            "total_pois": len(pois),
            "unique_parcels": len(parcels),
            "no_parcel": len(no_parcel),
            "total_brands": sum(len(p["brands"]) for p in parcels.values()),
            "total_addresses": sum(len(p["addresses"]) for p in parcels.values()),
            "source": "provincial",
        },
    }


def save_results(city: str, pois: list[dict], harvest: dict):
    """Save harvest results as JSON + GeoJSON."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    parcels = harvest["parcels"]
    stats = harvest["stats"]

    # 1. Full data JSON
    out_data = {
        "city": city,
        "harvested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "stats": stats,
        "parcels": parcels,
    }
    data_path = OUTPUT_DIR / f"{city}.json"
    data_path.write_text(json.dumps(out_data, indent=2, ensure_ascii=False))
    logger.info("\nSaved data: %s", data_path)

    # 2. GeoJSON for map rendering
    features = []
    for gis_id, parcel in parcels.items():
        if not parcel.get("geometry"):
            continue

        brand_names = [b["name"] for b in parcel["brands"]]
        addresses = [a["address"] for a in parcel["addresses"]]

        props = {
            "type": "parcel",
            "gis_id": gis_id,
            "brand_count": len(brand_names),
            "brands": ", ".join(brand_names),
            "brand_list": brand_names,
            "address_count": len(addresses),
            "addresses": ", ".join(addresses),
            "zoning": (parcel.get("zoning") or {}).get("GIS_FeatureKey") or (parcel.get("zoning") or {}).get("GeneralizedLandUse", ""),
        }
        # Include ARN/PIN from provincial data
        if parcel.get("arn"):
            props["arn"] = parcel["arn"]
        if parcel.get("pin"):
            props["pin"] = parcel["pin"]
        if parcel.get("source"):
            props["source"] = parcel["source"]

        features.append({
            "type": "Feature",
            "properties": props,
            "geometry": parcel["geometry"],
        })

        # Add POI dots
        for brand in parcel["brands"]:
            features.append({
                "type": "Feature",
                "properties": {
                    "type": "poi",
                    "name": brand["name"],
                    "poi_type": brand["type"],
                    "parcel_gis_id": gis_id,
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [brand["lng"], brand["lat"]],
                },
            })

    geojson = {"type": "FeatureCollection", "features": features}
    geo_path = OUTPUT_DIR / f"{city}.geojson"
    geo_path.write_text(json.dumps(geojson, indent=2, ensure_ascii=False))
    logger.info("Saved GeoJSON: %s (%d features)", geo_path, len(features))

    # 3. Print summary
    logger.info("\n" + "=" * 60)
    logger.info("HARVEST SUMMARY: %s", city.upper())
    logger.info("=" * 60)
    logger.info("  POIs queried:       %d", stats["total_pois"])
    logger.info("  Unique parcels:     %d", stats["unique_parcels"])
    logger.info("  POIs without parcel: %d", stats["no_parcel"])
    logger.info("  Total brands:       %d", stats["total_brands"])
    logger.info("  Total addresses:    %d", stats["total_addresses"])

    # Brand frequency
    brand_counts = defaultdict(int)
    for parcel in parcels.values():
        for b in parcel["brands"]:
            brand_counts[b["name"]] += 1

    logger.info("\n  Top brands:")
    for brand, count in sorted(brand_counts.items(), key=lambda x: -x[1])[:20]:
        logger.info("    %-30s %d parcels", brand, count)


def main():
    parser = argparse.ArgumentParser(description="Harvest branded parcels for a municipality")
    parser.add_argument("city", nargs="?", help="Municipality key (e.g., london, barrie, hamilton)")
    parser.add_argument("--dry-run", action="store_true", help="Just fetch POIs, don't query ArcGIS")
    parser.add_argument("--provincial", action="store_true",
                        help="Use provincial Assessment Parcel MapServer (requires AGMAPS_TOKEN)")
    parser.add_argument("--token", help="AgMaps token (or set AGMAPS_TOKEN in .env)")
    parser.add_argument("--bbox", help="Custom bbox: south,west,north,east (e.g., 43.20,-79.95,43.30,-79.75)")
    parser.add_argument("--name", help="City name for output (used with --bbox)")
    parser.add_argument("--list", action="store_true", help="List available cities")
    args = parser.parse_args()

    if args.list:
        logger.info("Available city bounding boxes:")
        for key in sorted(CITY_BBOX.keys()):
            bbox = CITY_BBOX[key]
            logger.info("  %-20s (%.2f, %.2f, %.2f, %.2f)", key, *bbox)
        registry = ServiceRegistry()
        logger.info("\nCities with municipal ArcGIS service: %s", ", ".join(registry.list_municipalities()))
        logger.info("Cities without service can use --provincial flag")
        return

    # Resolve city and bbox
    if args.bbox:
        parts = [float(x.strip()) for x in args.bbox.split(",")]
        if len(parts) != 4:
            logger.error("--bbox must be south,west,north,east (4 values)")
            sys.exit(1)
        bbox = tuple(parts)
        city = (args.name or args.city or "custom").lower().replace(" ", "-")
    elif args.city:
        city = args.city.lower().replace(" ", "-")
        if city not in CITY_BBOX:
            logger.error("No bounding box defined for '%s'", city)
            logger.info("Available: %s", ", ".join(sorted(CITY_BBOX.keys())))
            logger.info("Or use --bbox south,west,north,east --name cityname")
            sys.exit(1)
        bbox = CITY_BBOX[city]
    else:
        parser.print_help()
        sys.exit(1)

    logger.info("Harvesting branded parcels for %s", city)
    logger.info("Bbox: %s", bbox)

    if args.provincial:
        logger.info("Mode: PROVINCIAL (Ontario Assessment Parcel MapServer)")
    else:
        # Need a municipal service
        registry = ServiceRegistry()
        svc = registry.get(city)
        if not svc:
            logger.error("No municipal ArcGIS service configured for '%s'", city)
            logger.info("Available municipal services: %s", ", ".join(registry.list_municipalities()))
            logger.info("\nTip: Use --provincial to query the province-wide parcel layer instead.")
            sys.exit(1)
        logger.info("Mode: MUNICIPAL (%s)", svc.parcels_url)

    # Step 1: Fetch POIs from Overpass
    pois = fetch_city_pois(city, bbox)
    if not pois:
        logger.info("No POIs found")
        return

    if args.dry_run:
        logger.info("\nDry run — %d POIs found. Skipping parcel queries.", len(pois))
        return

    # Step 2-4: Harvest parcels
    start = time.time()

    if args.provincial:
        try:
            client = ProvincialParcelClient(token=args.token, throttle=0.4)
        except ValueError as e:
            logger.error(str(e))
            sys.exit(1)

        # Test token first
        try:
            info = client.test_connection()
            logger.info("Provincial service connected: %s", info.get("name", "OK"))
            logger.info("Fields: %s", ", ".join(info.get("fields", [])[:10]))
        except TokenExpiredError as e:
            logger.error("Token expired: %s", e)
            sys.exit(1)

        try:
            harvest = harvest_parcels_provincial(pois, client)
        except TokenExpiredError as e:
            logger.error("\nToken expired during harvest: %s", e)
            logger.error("Re-visit AgMaps to get a new token and rerun.")
            sys.exit(1)
        finally:
            client.close()
    else:
        arcgis = ArcGISClient(throttle=0.3)
        try:
            harvest = harvest_parcels(
                pois, svc, arcgis,
                fetch_addresses=svc.address_url is not None,
                fetch_zoning=svc.zoning_url is not None,
            )
        finally:
            arcgis.close()

    elapsed = time.time() - start
    logger.info("\nTotal harvest time: %.1f minutes", elapsed / 60)

    # Step 5: Save
    save_results(city, pois, harvest)


if __name__ == "__main__":
    main()
