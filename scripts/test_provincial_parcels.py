"""Test the provincial Assessment Parcel client.

Usage:
    # Test with token from .env:
    .venv/bin/python scripts/test_provincial_parcels.py

    # Test with explicit token:
    .venv/bin/python scripts/test_provincial_parcels.py --token YOUR_TOKEN_HERE

    # Test a specific coordinate (default: 3074 Wonderland Rd S, London):
    .venv/bin/python scripts/test_provincial_parcels.py --lat 42.9318 --lng -81.2818

    # Query by ARN:
    .venv/bin/python scripts/test_provincial_parcels.py --arn 393608005021700

    # Compare provincial vs municipal for a POI:
    .venv/bin/python scripts/test_provincial_parcels.py --compare
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cleo.parcels.provincial import ProvincialParcelClient, TokenExpiredError


def print_feature(feat: dict, label: str = ""):
    """Pretty-print an ArcGIS feature."""
    attrs = feat.get("attributes", {})
    geom = feat.get("geometry", {})
    rings = geom.get("rings", [])

    if label:
        print(f"\n--- {label} ---")

    print(f"  Attributes ({len(attrs)} fields):")
    for k, v in sorted(attrs.items()):
        if v is not None and v != "":
            print(f"    {k}: {v}")

    if rings:
        total_pts = sum(len(r) for r in rings)
        print(f"  Geometry: {len(rings)} ring(s), {total_pts} vertices")

        # Compute rough area from outer ring
        ring = rings[0]
        if len(ring) >= 3:
            # Rough bbox
            lngs = [p[0] for p in ring]
            lats = [p[1] for p in ring]
            print(f"  Bbox: ({min(lats):.6f}, {min(lngs):.6f}) - ({max(lats):.6f}, {max(lngs):.6f})")
    else:
        print("  Geometry: none")


def test_connection(client: ProvincialParcelClient):
    """Test that the token works."""
    print("Testing connection to provincial Assessment Parcel MapServer...")
    try:
        info = client.test_connection()
        print(f"  Service: {info['name']}")
        print(f"  Description: {info.get('description', 'N/A')}")
        print(f"  Max records: {info.get('max_record_count', 'N/A')}")
        print(f"  Geometry type: {info.get('geometry_type', 'N/A')}")
        print(f"  Fields ({len(info.get('fields', []))}):")
        for f in info.get("fields", []):
            print(f"    - {f}")
        print("\n  Token is VALID.")
        return True
    except TokenExpiredError as e:
        print(f"\n  TOKEN ERROR: {e}")
        print("  Visit AgMaps viewer to get a new token.")
        return False
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return False


def test_point_query(client: ProvincialParcelClient, lat: float, lng: float):
    """Query for parcels at a point."""
    print(f"\nQuerying provincial parcels at ({lat}, {lng})...")

    features = client.query_at_point(lat, lng)
    print(f"Got {len(features)} features")

    if features:
        # Pick the one that contains the point
        best = client.pick_containing_parcel(features, lat, lng)
        if best:
            print_feature(best, "Containing parcel")

        # Show others if multiple
        if len(features) > 1:
            print(f"\n  ({len(features) - 1} other overlapping features)")
            for i, f in enumerate(features):
                if f is not best:
                    attrs = f.get("attributes", {})
                    arn = attrs.get("ARN") or attrs.get("ASSESSMENT_ROLL_NUMBER") or "?"
                    print(f"    [{i}] ARN={arn}")
    else:
        print("  No parcels found at this location")

    return features


def test_arn_query(client: ProvincialParcelClient, arn: str):
    """Query by assessment roll number."""
    print(f"\nQuerying by ARN: {arn}")
    features = client.query_by_arn(arn)
    print(f"Got {len(features)} features")
    for i, f in enumerate(features):
        print_feature(f, f"Result {i+1}")
    return features


def test_compare(client: ProvincialParcelClient):
    """Compare provincial vs municipal data for known London locations."""
    test_points = [
        ("3074 Wonderland Rd S (Power Centre)", 42.9318, -81.2818),
        ("Shoppers @ Gardenwood Dr", 42.9395, -81.2300),
        ("Tim Hortons @ Commissioners Rd W", 42.9520, -81.2750),
        ("Shoppers @ Cherryhill Mall", 42.9788, -81.2775),
    ]

    print("\n" + "=" * 60)
    print("COMPARING PROVINCIAL PARCELS FOR KNOWN LOCATIONS")
    print("=" * 60)

    for name, lat, lng in test_points:
        print(f"\n{'─' * 60}")
        print(f"  {name} ({lat}, {lng})")
        features = client.query_at_point(lat, lng)
        print(f"  Provincial results: {len(features)} features")

        if features:
            best = client.pick_containing_parcel(features, lat, lng)
            if best:
                attrs = best.get("attributes", {})
                rings = best.get("geometry", {}).get("rings", [])
                arn = attrs.get("ARN") or attrs.get("ASSESSMENT_ROLL_NUMBER") or "?"
                pin = attrs.get("PIN") or attrs.get("PropertyIdentificationNumber") or "?"
                total_pts = sum(len(r) for r in rings) if rings else 0
                print(f"  ARN: {arn}")
                print(f"  PIN: {pin}")
                print(f"  Vertices: {total_pts}")
                # Show all non-null attributes
                for k, v in sorted(attrs.items()):
                    if v is not None and v != "" and k not in ("ARN", "PIN", "ASSESSMENT_ROLL_NUMBER"):
                        print(f"  {k}: {v}")

    print(f"\n\nTotal queries: {client.request_count}")


def main():
    parser = argparse.ArgumentParser(description="Test provincial Assessment Parcel client")
    parser.add_argument("--token", help="AgMaps token (or set AGMAPS_TOKEN in .env)")
    parser.add_argument("--lat", type=float, default=42.9318, help="Latitude (default: 3074 Wonderland)")
    parser.add_argument("--lng", type=float, default=-81.2818, help="Longitude (default: 3074 Wonderland)")
    parser.add_argument("--arn", help="Query by Assessment Roll Number")
    parser.add_argument("--compare", action="store_true", help="Compare provincial data for known locations")
    parser.add_argument("--save", help="Save results to JSON file")
    args = parser.parse_args()

    try:
        client = ProvincialParcelClient(token=args.token)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    try:
        # Always test connection first
        if not test_connection(client):
            sys.exit(1)

        results = {}

        if args.arn:
            features = test_arn_query(client, args.arn)
            results["arn_query"] = features
        elif args.compare:
            test_compare(client)
        else:
            features = test_point_query(client, args.lat, args.lng)
            results["point_query"] = features

        if args.save and results:
            out_path = Path(args.save)
            out_path.write_text(json.dumps(results, indent=2))
            print(f"\nSaved to {out_path}")

        print(f"\nTotal requests: {client.request_count}")

    except TokenExpiredError as e:
        print(f"\nTOKEN EXPIRED: {e}")
        print("Visit AgMaps viewer to get a new token.")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
