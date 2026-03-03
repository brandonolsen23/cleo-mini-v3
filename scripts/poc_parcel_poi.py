"""Proof-of-concept: GeoWarehouse + ArcGIS parcel + Overpass POIs.

Demonstrates the full pipeline for a single property:
  1. Parse GeoWarehouse HTML for property details
  2. Query London ArcGIS for the parcel polygon by GIS_ID
  3. Query London address layer for all addresses on the parcel
  4. Query Overpass for all branded POIs within the parcel bbox
  5. Output combined JSON + GeoJSON for map rendering

Usage:
    .venv/bin/python scripts/poc_parcel_poi.py
"""

import json
import sys
from pathlib import Path

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cleo.geowarehouse.parser import parse_gw_html
from cleo.parcels.client import ArcGISClient

# --- Config ---

GW_HTML_PATH = Path.home() / "Downloads/GeoWarehouse/gw-ingest-data/geowarehouse-2026-02-26T21-58-25-008Z.html"

# London ArcGIS endpoints
LONDON_PARCELS_URL = "https://maps.london.ca/arcgisa/rest/services/OpenData/OpenData_BaseMaps/MapServer/53"
LONDON_ADDRESS_URL = "https://maps.london.ca/arcgisa/rest/services/Addresses/MapServer/0"
LONDON_ZONING_URL = "https://maps.london.ca/arcgisa/rest/services/OpenData/OpenData_Community/MapServer/16"
LONDON_SRID = 26917

# From user's London zoning map lookup
GIS_ID = 103963

# Overpass API
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "poc_parcel"


def step1_parse_gw():
    """Parse the GeoWarehouse HTML."""
    print("\n=== STEP 1: Parse GeoWarehouse HTML ===")
    html = GW_HTML_PATH.read_text(encoding="utf-8")
    result = parse_gw_html(html, GW_HTML_PATH.name)
    if not result:
        print("  ERROR: Could not parse GW HTML")
        return None

    ss = result.get("site_structure", {})
    print(f"  PIN:          {result.get('pin')}")
    print(f"  ARN:          {ss.get('arn')}")
    print(f"  Address:      {ss.get('property_address')}")
    print(f"  Municipality: {ss.get('municipality')}")
    print(f"  Owner:        {ss.get('owner_names_mpac')}")
    print(f"  Assessed:     {ss.get('current_assessed_value')}")
    print(f"  Zoning:       {ss.get('zoning')}")
    print(f"  Site Area:    {ss.get('site_area')}")
    print(f"  Description:  {ss.get('property_description')}")
    print(f"  Sales History: {len(result.get('sales_history', []))} records")

    return result


def step2_get_parcel(client: ArcGISClient):
    """Query London ArcGIS for the parcel polygon by GIS_ID."""
    print(f"\n=== STEP 2: Query ArcGIS parcel (GIS_ID={GIS_ID}) ===")

    features = client.query_by_where(
        LONDON_PARCELS_URL,
        where=f"GIS_ID={GIS_ID}",
        out_fields="*",
        return_geometry=True,
    )

    if not features:
        print("  ERROR: No parcel found")
        return None

    feature = features[0]
    attrs = feature.get("attributes", {})
    geom = feature.get("geometry", {})
    rings = geom.get("rings", [])

    print(f"  Found parcel with {len(rings)} ring(s)")
    print(f"  Attributes: {json.dumps(attrs, indent=4)}")

    if rings:
        # Count total vertices
        total_verts = sum(len(r) for r in rings)
        print(f"  Total vertices: {total_verts}")

        # Get bounding box
        all_pts = [pt for ring in rings for pt in ring]
        lngs = [p[0] for p in all_pts]
        lats = [p[1] for p in all_pts]
        bbox = {
            "south": min(lats),
            "west": min(lngs),
            "north": max(lats),
            "east": max(lngs),
        }
        print(f"  Bbox: {bbox['south']:.6f},{bbox['west']:.6f} to {bbox['north']:.6f},{bbox['east']:.6f}")

        # Build GeoJSON polygon
        geojson_polygon = {
            "type": "Feature",
            "properties": {
                "gis_id": GIS_ID,
                "source": "london_arcgis",
                **{k: v for k, v in attrs.items() if v is not None},
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": rings,
            },
        }

        return geojson_polygon, bbox

    return None, None


def step3_get_addresses(client: ArcGISClient):
    """Query London address layer for all addresses on this parcel."""
    print(f"\n=== STEP 3: Query addresses (Parcel_ID={GIS_ID}) ===")

    features = client.query_by_where(
        LONDON_ADDRESS_URL,
        where=f"Parcel_ID={GIS_ID}",
        out_fields="FullAddress,Parcel_ID,OBJECTID",
        return_geometry=True,
    )

    if not features:
        print("  No addresses found via Parcel_ID, trying GIS_ID...")
        features = client.query_by_where(
            LONDON_ADDRESS_URL,
            where=f"GIS_ID={GIS_ID}",
            out_fields="*",
            return_geometry=True,
        )

    addresses = []
    for f in features:
        attrs = f.get("attributes", {})
        geom = f.get("geometry", {})
        addr = {
            "address": attrs.get("FullAddress", ""),
            "lat": geom.get("y"),
            "lng": geom.get("x"),
        }
        # Include any other interesting fields
        for k, v in attrs.items():
            if v is not None and k not in ("FullAddress", "OBJECTID", "Shape"):
                addr[k] = v
        addresses.append(addr)

    print(f"  Found {len(addresses)} address(es):")
    for a in addresses:
        print(f"    - {a['address']}")

    return addresses


def step4_get_zoning(client: ArcGISClient, bbox: dict):
    """Query zoning at the parcel centroid."""
    print(f"\n=== STEP 4: Query zoning ===")

    center_lat = (bbox["south"] + bbox["north"]) / 2
    center_lng = (bbox["west"] + bbox["east"]) / 2

    zoning = client.query_zoning_at_point(
        LONDON_ZONING_URL,
        lat=center_lat,
        lng=center_lng,
        srid=LONDON_SRID,
    )

    if zoning:
        print(f"  Zoning: {json.dumps(zoning, indent=4)}")
    else:
        print("  No zoning data found")

    return zoning


def step5_get_pois(bbox: dict):
    """Query Overpass for branded POIs within the parcel bounding box."""
    print(f"\n=== STEP 5: Query Overpass for POIs ===")

    # Expand bbox slightly (~50m) to catch POIs at the edge
    lat_buf = 0.0005
    lng_buf = 0.0007
    south = bbox["south"] - lat_buf
    north = bbox["north"] + lat_buf
    west = bbox["west"] - lng_buf
    east = bbox["east"] + lng_buf

    # Query for all POIs with a name in the bbox area
    query = f"""
[out:json][timeout:30];
(
  node["name"]["shop"]({south},{west},{north},{east});
  node["name"]["amenity"]({south},{west},{north},{east});
  node["name"]["brand"]({south},{west},{north},{east});
  way["name"]["shop"]({south},{west},{north},{east});
  way["name"]["amenity"]({south},{west},{north},{east});
  way["name"]["brand"]({south},{west},{north},{east});
);
out center tags;
"""

    try:
        resp = httpx.post(OVERPASS_URL, data={"data": query}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  ERROR: Overpass query failed: {e}")
        return []

    elements = data.get("elements", [])
    pois = []
    for el in elements:
        tags = el.get("tags", {})
        # Get coordinates (nodes have lat/lon, ways have center)
        if el["type"] == "node":
            lat, lng = el["lat"], el["lon"]
        elif "center" in el:
            lat, lng = el["center"]["lat"], el["center"]["lon"]
        else:
            continue

        poi = {
            "name": tags.get("name", ""),
            "brand": tags.get("brand", tags.get("operator", "")),
            "type": tags.get("shop") or tags.get("amenity") or tags.get("cuisine") or "unknown",
            "lat": lat,
            "lng": lng,
            "osm_id": el["id"],
            "osm_type": el["type"],
        }
        # Add extra useful tags
        for tag_key in ("cuisine", "phone", "website", "opening_hours", "addr:street", "addr:housenumber"):
            if tag_key in tags:
                poi[tag_key.replace(":", "_")] = tags[tag_key]

        pois.append(poi)

    print(f"  Found {len(pois)} POI(s):")
    for p in pois:
        brand_label = p["brand"] or p["name"]
        print(f"    - {brand_label} ({p['type']}) at ({p['lat']:.6f}, {p['lng']:.6f})")

    return pois


def build_output(gw_data, parcel_geojson, addresses, zoning, pois):
    """Combine everything into output files."""
    print(f"\n=== OUTPUT ===")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Combined summary JSON
    ss = gw_data.get("site_structure", {}) if gw_data else {}
    summary = {
        "property": {
            "pin": gw_data.get("pin") if gw_data else None,
            "arn": ss.get("arn"),
            "address": ss.get("property_address"),
            "municipality": ss.get("municipality"),
            "owner": ss.get("owner_names_mpac"),
            "assessed_value": ss.get("current_assessed_value"),
            "zoning_gw": ss.get("zoning"),
            "zoning_arcgis": zoning,
            "site_area": ss.get("site_area"),
            "description": ss.get("property_description"),
            "sales_history": gw_data.get("sales_history", []) if gw_data else [],
        },
        "parcel": {
            "gis_id": GIS_ID,
            "address_count": len(addresses),
            "addresses": [a["address"] for a in addresses],
        },
        "brands": [
            {
                "name": p["brand"] or p["name"],
                "type": p["type"],
                "lat": p["lat"],
                "lng": p["lng"],
            }
            for p in pois
        ],
        "brand_count": len(pois),
        "brand_names": sorted(set(p["brand"] or p["name"] for p in pois)),
    }

    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"  Summary: {summary_path}")

    # 2. GeoJSON with parcel polygon + POI points for map rendering
    features = []
    if parcel_geojson:
        features.append(parcel_geojson)

    # Add address points
    for addr in addresses:
        if addr.get("lat") and addr.get("lng"):
            features.append({
                "type": "Feature",
                "properties": {
                    "type": "address",
                    "address": addr["address"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [addr["lng"], addr["lat"]],
                },
            })

    # Add POI points
    for poi in pois:
        features.append({
            "type": "Feature",
            "properties": {
                "type": "poi",
                "name": poi["name"],
                "brand": poi["brand"],
                "poi_type": poi["type"],
            },
            "geometry": {
                "type": "Point",
                "coordinates": [poi["lng"], poi["lat"]],
            },
        })

    geojson_fc = {
        "type": "FeatureCollection",
        "features": features,
    }

    geojson_path = OUTPUT_DIR / "parcel_pois.geojson"
    geojson_path.write_text(json.dumps(geojson_fc, indent=2, ensure_ascii=False))
    print(f"  GeoJSON: {geojson_path}")

    # 3. Print brand summary
    print(f"\n  --- BRAND SUMMARY ---")
    print(f"  Total brands found: {len(pois)}")
    print(f"  Unique brands: {', '.join(summary['brand_names']) or 'None'}")
    print(f"  Municipal addresses on parcel: {len(addresses)}")
    for a in addresses:
        print(f"    {a['address']}")


def main():
    print("=" * 60)
    print("POC: GeoWarehouse + ArcGIS Parcel + Overpass POIs")
    print("Property: 3074 Wonderland Rd S, London ON")
    print("=" * 60)

    # Step 1: Parse GW
    gw_data = step1_parse_gw()

    # Steps 2-4: ArcGIS queries
    client = ArcGISClient(throttle=0.3)
    try:
        parcel_result = step2_get_parcel(client)
        parcel_geojson, bbox = parcel_result if parcel_result else (None, None)

        addresses = step3_get_addresses(client)

        zoning = None
        if bbox:
            zoning = step4_get_zoning(client, bbox)
    finally:
        client.close()

    # Step 5: Overpass POIs
    pois = []
    if bbox:
        pois = step5_get_pois(bbox)
    else:
        print("\n  SKIPPING Overpass — no parcel bbox available")

    # Combine output
    build_output(gw_data, parcel_geojson, addresses, zoning, pois)

    print("\nDone!")


if __name__ == "__main__":
    main()
