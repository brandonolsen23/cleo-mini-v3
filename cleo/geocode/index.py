"""Address index: maps geocoded addresses to locations and RT ID references."""

import logging
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .cache import GeocodeCache
from .collector import collect_addresses

logger = logging.getLogger(__name__)


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate haversine distance in meters between two coordinates."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# --- Union-Find for clustering ---

class _UnionFind:
    """Simple union-find (disjoint set) for merging location clusters."""

    def __init__(self):
        self.parent: Dict[str, str] = {}
        self.rank: Dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x: str, y: str) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1


def _grid_key(lat: float, lng: float, cell_size: float = 0.0005) -> Tuple[int, int]:
    """Convert lat/lng to grid cell coordinates (~50m cells at Ontario latitudes)."""
    return (int(lat / cell_size), int(lng / cell_size))


def build_address_index(
    extracted_dir: Path,
    reviews_path: Path,
    cache: GeocodeCache,
    proximity_meters: float = 50.0,
) -> Dict:
    """Build an address-to-location-to-RT index from extracted data + geocode cache.

    Steps:
    1. Collect all addresses from extracted data (with overrides)
    2. Look up each address in geocode cache
    3. Cluster geocoded addresses within proximity_meters into locations
    4. Build three indexes: locations, address_to_location, rt_to_locations

    Returns a dict ready for JSON serialization.
    """
    address_refs, unique_addresses = collect_addresses(extracted_dir, reviews_path)

    # Look up each address in cache and build raw location list
    geocoded: List[Tuple[str, float, float, str]] = []  # (addr, lat, lng, formatted)
    ungeocodable: List[str] = []

    for addr in unique_addresses:
        result = cache.get(addr)
        if result is None or result.get("failed"):
            ungeocodable.append(addr)
            continue
        lat = result.get("lat")
        lng = result.get("lng")
        if lat is None or lng is None:
            ungeocodable.append(addr)
            continue
        geocoded.append((addr, lat, lng, result.get("formatted_address", "")))

    logger.info(
        "Index: %d geocoded, %d ungeocodable out of %d unique addresses",
        len(geocoded), len(ungeocodable), len(unique_addresses),
    )

    # Cluster geocoded addresses by proximity using grid + union-find
    uf = _UnionFind()
    grid: Dict[Tuple[int, int], List[str]] = defaultdict(list)

    # Place each address into a grid cell
    addr_coords: Dict[str, Tuple[float, float, str]] = {}
    for addr, lat, lng, formatted in geocoded:
        key = addr.strip().upper()
        addr_coords[key] = (lat, lng, formatted)
        cell = _grid_key(lat, lng)
        grid[cell].append(key)
        uf.find(key)  # Initialize in union-find

    # For each cell, check against same cell + neighbors for proximity
    offsets = [
        (-1, -1), (-1, 0), (-1, 1),
        (0, -1),  (0, 0),  (0, 1),
        (1, -1),  (1, 0),  (1, 1),
    ]

    for cell, addrs_in_cell in grid.items():
        # Collect all addresses in neighboring cells
        neighbors = []
        for dr, dc in offsets:
            neighbor_cell = (cell[0] + dr, cell[1] + dc)
            if neighbor_cell in grid and neighbor_cell != cell:
                neighbors.extend(grid[neighbor_cell])

        # Check proximity between addresses in this cell and neighbors
        for a1 in addrs_in_cell:
            lat1, lng1, _ = addr_coords[a1]
            for a2 in neighbors:
                if uf.find(a1) == uf.find(a2):
                    continue  # Already in same cluster
                lat2, lng2, _ = addr_coords[a2]
                dist = haversine_meters(lat1, lng1, lat2, lng2)
                if dist <= proximity_meters:
                    uf.union(a1, a2)

        # Also check within the same cell
        for i, a1 in enumerate(addrs_in_cell):
            lat1, lng1, _ = addr_coords[a1]
            for a2 in addrs_in_cell[i + 1:]:
                if uf.find(a1) == uf.find(a2):
                    continue
                lat2, lng2, _ = addr_coords[a2]
                dist = haversine_meters(lat1, lng1, lat2, lng2)
                if dist <= proximity_meters:
                    uf.union(a1, a2)

    # Build location clusters from union-find
    clusters: Dict[str, List[str]] = defaultdict(list)  # root -> [addresses]
    for key in addr_coords:
        root = uf.find(key)
        clusters[root].append(key)

    # Create location entries
    locations: Dict[str, Dict] = {}
    address_to_location: Dict[str, str] = {}
    loc_counter = 0

    for root, members in clusters.items():
        loc_counter += 1
        loc_id = f"loc_{loc_counter:05d}"

        # Compute centroid
        lats = [addr_coords[m][0] for m in members]
        lngs = [addr_coords[m][1] for m in members]
        avg_lat = sum(lats) / len(lats)
        avg_lng = sum(lngs) / len(lngs)

        # Use the formatted address of the first member
        formatted = addr_coords[members[0]][2]

        # Collect all references
        refs = []
        for m in members:
            # Look up refs using both the upper-cased key and original addresses
            for addr_key, ref_list in address_refs.items():
                if addr_key.strip().upper() == m:
                    for ref in ref_list:
                        refs.append({
                            **ref,
                            "original_address": addr_key,
                        })

        locations[loc_id] = {
            "lat": round(avg_lat, 7),
            "lng": round(avg_lng, 7),
            "formatted_address": formatted,
            "address_variants": sorted(set(members)),
            "references": refs,
        }

        for m in members:
            address_to_location[m] = loc_id

    # Build rt_to_locations reverse index
    rt_to_locations: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: {"property": [], "seller": [], "buyer": []}
    )

    for loc_id, loc_data in locations.items():
        for ref in loc_data["references"]:
            rt_id = ref["rt_id"]
            role = ref["role"]
            if loc_id not in rt_to_locations[rt_id][role]:
                rt_to_locations[rt_id][role].append(loc_id)

    # Stats
    multi_ref_locations = sum(
        1 for loc in locations.values()
        if len(set(r["rt_id"] for r in loc["references"])) > 1
    )

    stats = {
        "total_unique_addresses": len(unique_addresses),
        "geocoded": len(geocoded),
        "ungeocodable": len(ungeocodable),
        "locations": len(locations),
        "multi_rt_locations": multi_ref_locations,
        "rt_records_indexed": len(rt_to_locations),
        "proximity_meters": proximity_meters,
    }

    logger.info(
        "Index built: %d locations (%d multi-RT), %d RT records",
        len(locations), multi_ref_locations, len(rt_to_locations),
    )

    return {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "stats": stats,
        "locations": locations,
        "address_to_location": address_to_location,
        "rt_to_locations": dict(rt_to_locations),
    }
