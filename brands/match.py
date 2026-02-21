"""Brand-to-property matching engine.

Strategy: street-number + normalized-city lookup, with fuzzy street-name
tiebreaker when multiple properties share the same number and city.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BRANDS_DATA_DIR = Path(__file__).resolve().parent / "data"
PROPERTIES_PATH = DATA_DIR / "properties.json"
BRAND_MATCHES_PATH = DATA_DIR / "brand_matches.json"
BRAND_UNMATCHED_PATH = DATA_DIR / "brand_unmatched.json"

# City aliases — grow as unmatched list reveals gaps
CITY_ALIASES: dict[str, str] = {
    "N. YORK": "NORTH YORK",
    "N.YORK": "NORTH YORK",
    "ST. CATHARINES": "ST CATHARINES",
    "ST.CATHARINES": "ST CATHARINES",
    "SAINT CATHARINES": "ST CATHARINES",
    "ST. THOMAS": "ST THOMAS",
    "ST.THOMAS": "ST THOMAS",
    "SAINT THOMAS": "ST THOMAS",
    "STE. MARIE": "STE MARIE",
    "SAULT STE MARIE": "SAULT STE. MARIE",
}

_NUMBER_RE = re.compile(r"^(\d+)")
# Matches suite/unit prefixes like "B03-", "B-4 ", "G3-", "K1-", "B-10-1-"
_SUITE_PREFIX_RE = re.compile(r"^[A-Za-z]\d*(?:-\d+)*[-\s]+")


def normalize_city(city: str) -> str:
    """Normalize city for matching: uppercase, collapse whitespace, apply aliases."""
    c = city.upper().strip()
    c = re.sub(r"\s+", " ", c)
    # Apply alias map
    return CITY_ALIASES.get(c, c)


def extract_street_number(address: str) -> str | None:
    """Extract leading digits from an address string.

    Handles suite/unit prefixes like "B03-70 King William St" -> "70".
    """
    addr = address.strip()
    m = _NUMBER_RE.match(addr)
    if m:
        return m.group(1)
    # Try stripping suite prefix
    addr = _SUITE_PREFIX_RE.sub("", addr)
    m = _NUMBER_RE.match(addr)
    return m.group(1) if m else None


# Normalize street suffixes to canonical short form
_SUFFIX_MAP = {
    "STREET": "ST", "AVENUE": "AVE", "BOULEVARD": "BLVD", "DRIVE": "DR",
    "ROAD": "RD", "CRESCENT": "CRES", "COURT": "CRT", "PLACE": "PL",
    "LANE": "LN", "CIRCLE": "CIR", "TERRACE": "TER", "TRAIL": "TRL",
    "PARKWAY": "PKY", "HIGHWAY": "HWY", "WAY": "WAY", "LINE": "LINE",
    "GATE": "GATE", "PATH": "PATH", "GROVE": "GRV", "GARDENS": "GDNS",
    "SQUARE": "SQ", "HEIGHTS": "HTS", "RIDGE": "RDG",
    # Direction expansions
    "EAST": "E", "WEST": "W", "NORTH": "N", "SOUTH": "S",
    "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
    # Already abbreviated forms with period
    "ST.": "ST", "AVE.": "AVE", "BLVD.": "BLVD", "DR.": "DR",
    "RD.": "RD", "CRES.": "CRES", "CRT.": "CRT", "PL.": "PL",
    "N.": "N", "S.": "S", "E.": "E", "W.": "W",
}


def street_name_tokens(address: str) -> list[str]:
    """Extract street name tokens after the leading number, with suffix normalization."""
    addr = address.strip().upper()
    # Strip suite prefix if present
    addr = _SUITE_PREFIX_RE.sub("", addr)
    # Remove leading number and dash/space
    addr = _NUMBER_RE.sub("", addr).strip().lstrip("- ")
    tokens = addr.split()
    # Normalize suffixes
    normalized = []
    for t in tokens:
        clean = t.rstrip(".,")
        mapped = _SUFFIX_MAP.get(clean, clean)
        if mapped:
            normalized.append(mapped)
    return normalized


def street_similarity(addr_a: str, addr_b: str) -> float:
    """Compare two addresses by street name similarity (0-1)."""
    tokens_a = street_name_tokens(addr_a)
    tokens_b = street_name_tokens(addr_b)
    if not tokens_a or not tokens_b:
        return 0.0
    str_a = " ".join(tokens_a)
    str_b = " ".join(tokens_b)
    return SequenceMatcher(None, str_a, str_b).ratio()


def build_property_index(properties: dict) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """Build (street_number, norm_city) -> [(prop_id, full_address)] index."""
    index: dict[tuple[str, str], list[tuple[str, str]]] = {}
    for pid, prop in properties.items():
        address = prop.get("address", "")
        city = prop.get("city", "")
        num = extract_street_number(address)
        if not num:
            continue
        norm_city = normalize_city(city)
        key = (num, norm_city)
        index.setdefault(key, []).append((pid, address))
    return index


def load_brand_stores() -> list[dict]:
    """Load all brand store JSON files."""
    stores = []
    for path in sorted(BRANDS_DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        stores.extend(data)
    return stores


def match_brands() -> tuple[dict, list]:
    """Run brand-to-property matching.

    Returns:
        (matches, unmatched) where:
        - matches: {prop_id: [{brand, store_name, address, city, method}]}
        - unmatched: [{brand, store_name, address, city, reason}]
    """
    # Load property registry
    reg = json.loads(PROPERTIES_PATH.read_text(encoding="utf-8"))
    properties = reg.get("properties", {})

    # Build index
    prop_index = build_property_index(properties)

    # Load brand stores
    stores = load_brand_stores()

    matches: dict[str, list[dict]] = {}
    unmatched: list[dict] = []

    for store in stores:
        brand = store.get("brand", "")
        store_name = store.get("store_name", "")
        store_addr = store.get("address", "")
        store_city = store.get("city", "")

        num = extract_street_number(store_addr)
        if not num:
            unmatched.append({
                "brand": brand,
                "store_name": store_name,
                "address": store_addr,
                "city": store_city,
                "reason": "no_street_number",
            })
            continue

        norm_city = normalize_city(store_city)
        key = (num, norm_city)
        candidates = prop_index.get(key, [])

        if len(candidates) == 0:
            unmatched.append({
                "brand": brand,
                "store_name": store_name,
                "address": store_addr,
                "city": store_city,
                "reason": "no_match",
            })
        else:
            # Score all candidates by street similarity
            scored = []
            for pid, prop_addr in candidates:
                score = street_similarity(store_addr, prop_addr)
                scored.append((pid, prop_addr, score))
            scored.sort(key=lambda x: -x[2])
            best_pid, best_addr, best_score = scored[0]

            if best_score >= 0.6:
                method = "exact" if len(candidates) == 1 else f"fuzzy ({best_score:.2f})"
                entry = {
                    "brand": brand,
                    "store_name": store_name,
                    "address": store_addr,
                    "city": store_city,
                    "method": method,
                }
                matches.setdefault(best_pid, []).append(entry)
            else:
                unmatched.append({
                    "brand": brand,
                    "store_name": store_name,
                    "address": store_addr,
                    "city": store_city,
                    "reason": f"low_similarity ({len(candidates)} candidates, best={best_score:.2f})",
                })

    return matches, unmatched


def run_match() -> None:
    """Run matching and write output files."""
    print("Loading brands and properties...")
    matches, unmatched = match_brands()

    # Count stats
    total_stores = sum(len(v) for v in matches.values()) + len(unmatched)
    brand_counts: dict[str, int] = {}
    for entries in matches.values():
        for e in entries:
            brand_counts[e["brand"]] = brand_counts.get(e["brand"], 0) + 1

    print(f"\nMatched: {sum(len(v) for v in matches.values())} stores -> {len(matches)} properties")
    for brand, count in sorted(brand_counts.items()):
        print(f"  {brand}: {count}")
    print(f"Unmatched: {len(unmatched)} stores")
    print(f"Total: {total_stores} stores")

    # Write output
    with open(BRAND_MATCHES_PATH, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {BRAND_MATCHES_PATH}")

    with open(BRAND_UNMATCHED_PATH, "w", encoding="utf-8") as f:
        json.dump(unmatched, f, indent=2, ensure_ascii=False)
    print(f"Wrote {BRAND_UNMATCHED_PATH}")

    # Show unmatched breakdown
    if unmatched:
        reasons: dict[str, int] = {}
        for u in unmatched:
            r = u["reason"].split(" (")[0]
            reasons[r] = reasons.get(r, 0) + 1
        print("\nUnmatched breakdown:")
        for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")


def import_to_registry() -> None:
    """Import all brand stores into the property registry.

    Step 1: Enrich already-matched properties (add 'brand' source, backfill fields).
    Step 2: Fuzzy-match remaining unmatched stores against the full registry.
    Step 3: Create new properties for truly unmatched stores.
    Step 4: Orphan cleanup — merge brand-only props that duplicate an existing entry.
    Step 5: Re-run matching so brand_matches.json reflects all linkages.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from cleo.properties.registry import load_registry, save_registry

    # --- Load registry ---
    reg = load_registry(PROPERTIES_PATH)
    properties = reg.get("properties", {})
    print(f"Registry: {len(properties)} properties before import")

    # --- Load brand matches (from previous run_match) ---
    if not BRAND_MATCHES_PATH.exists():
        print("No brand_matches.json found. Run 'python run.py match' first.")
        return
    matches = json.loads(BRAND_MATCHES_PATH.read_text(encoding="utf-8"))

    # --- Step 1: Enrich already-matched properties ---
    enriched = 0
    for pid, entries in matches.items():
        if pid not in properties:
            continue
        prop = properties[pid]
        # Add 'brand' to sources
        sources = prop.setdefault("sources", [])
        if "brand" not in sources:
            sources.append("brand")
        # Backfill postal_code, lat, lng from brand data
        for entry in entries:
            store = _find_store(entry)
            if not store:
                continue
            if not prop.get("postal_code") and store.get("postal_code"):
                prop["postal_code"] = store["postal_code"]
            if prop.get("lat") is None and store.get("lat") is not None:
                prop["lat"] = store["lat"]
            if prop.get("lng") is None and store.get("lng") is not None:
                prop["lng"] = store["lng"]
        enriched += 1
    print(f"Step 1: Enriched {enriched} already-matched properties")

    # --- Step 2+3: Process unmatched stores ---
    if not BRAND_UNMATCHED_PATH.exists():
        print("No brand_unmatched.json found.")
        return
    unmatched = json.loads(BRAND_UNMATCHED_PATH.read_text(encoding="utf-8"))
    print(f"Processing {len(unmatched)} unmatched stores...")

    # Rebuild property index against the full registry for fuzzy matching
    prop_index = build_property_index(properties)
    used_ids = set(properties.keys())

    fuzzy_matched = 0
    created = 0
    new_matches: dict[str, list[dict]] = {}  # pid -> [entry, ...]

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")

    for store_info in unmatched:
        brand = store_info.get("brand", "")
        store_name = store_info.get("store_name", "")
        store_addr = store_info.get("address", "")
        store_city = store_info.get("city", "")

        if not store_addr:
            continue

        num = extract_street_number(store_addr)
        norm_city = normalize_city(store_city) if store_city else ""

        # Try fuzzy match against registry
        matched_pid = None
        if num and norm_city:
            key = (num, norm_city)
            candidates = prop_index.get(key, [])
            if candidates:
                scored = []
                for pid, prop_addr in candidates:
                    score = street_similarity(store_addr, prop_addr)
                    scored.append((pid, prop_addr, score))
                scored.sort(key=lambda x: -x[2])
                best_pid, _, best_score = scored[0]
                if best_score >= 0.6:
                    matched_pid = best_pid

        if matched_pid:
            # Fuzzy match found — enrich existing property
            prop = properties[matched_pid]
            sources = prop.setdefault("sources", [])
            if "brand" not in sources:
                sources.append("brand")
            store = _find_store_by_addr(store_addr, store_city, brand)
            if store:
                if not prop.get("postal_code") and store.get("postal_code"):
                    prop["postal_code"] = store["postal_code"]
                if prop.get("lat") is None and store.get("lat") is not None:
                    prop["lat"] = store["lat"]
                if prop.get("lng") is None and store.get("lng") is not None:
                    prop["lng"] = store["lng"]
            entry = {
                "brand": brand,
                "store_name": store_name,
                "address": store_addr,
                "city": store_city,
                "method": "fuzzy_import",
            }
            new_matches.setdefault(matched_pid, []).append(entry)
            fuzzy_matched += 1
        else:
            # No match — create new brand-only property
            pid = _next_prop_id(used_ids)
            used_ids.add(pid)
            store = _find_store_by_addr(store_addr, store_city, brand)
            properties[pid] = {
                "address": store_addr,
                "city": store_city,
                "municipality": "",
                "province": store.get("province", "ON") if store else "ON",
                "postal_code": store.get("postal_code", "") if store else "",
                "lat": store.get("lat") if store else None,
                "lng": store.get("lng") if store else None,
                "rt_ids": [],
                "transaction_count": 0,
                "sources": ["brand"],
                "created": today,
                "updated": today,
            }
            entry = {
                "brand": brand,
                "store_name": store_name,
                "address": store_addr,
                "city": store_city,
                "method": "new_property",
            }
            new_matches.setdefault(pid, []).append(entry)
            # Add to index for subsequent stores
            if num and norm_city:
                prop_index.setdefault((num, norm_city), []).append((pid, store_addr))
            created += 1

    print(f"Step 2: Fuzzy-matched {fuzzy_matched} previously-unmatched stores")
    print(f"Step 3: Created {created} new brand-only properties")

    # --- Step 4: Orphan cleanup ---
    # Scan for brand-only properties whose dedup key matches another property
    from cleo.properties.normalize import make_dedup_key
    key_to_pids: dict[str, list[str]] = {}
    for pid, prop in properties.items():
        key = make_dedup_key(prop.get("address", ""), prop.get("city", ""))
        key_to_pids.setdefault(key, []).append(pid)

    orphans_removed = 0
    for key, pids in key_to_pids.items():
        if len(pids) < 2:
            continue
        # Find the "real" property (has rt_ids) and orphans (brand-only)
        real_pids = [p for p in pids if properties[p].get("rt_ids")]
        brand_only_pids = [p for p in pids if not properties[p].get("rt_ids") and properties[p].get("sources") == ["brand"]]
        if not real_pids or not brand_only_pids:
            continue
        target_pid = real_pids[0]
        for orphan_pid in brand_only_pids:
            # Transfer brand source to real property
            target_sources = properties[target_pid].setdefault("sources", [])
            if "brand" not in target_sources:
                target_sources.append("brand")
            # Backfill from orphan
            orphan = properties[orphan_pid]
            target = properties[target_pid]
            if not target.get("postal_code") and orphan.get("postal_code"):
                target["postal_code"] = orphan["postal_code"]
            if target.get("lat") is None and orphan.get("lat") is not None:
                target["lat"] = orphan["lat"]
            if target.get("lng") is None and orphan.get("lng") is not None:
                target["lng"] = orphan["lng"]
            # Move brand match entries from orphan to target
            if orphan_pid in new_matches:
                new_matches.setdefault(target_pid, []).extend(new_matches.pop(orphan_pid))
            # Remove orphan
            del properties[orphan_pid]
            orphans_removed += 1

    print(f"Step 4: Removed {orphans_removed} orphan duplicates")

    # --- Save registry ---
    properties = dict(sorted(properties.items()))
    total = len(properties)
    total_rt = sum(len(p.get("rt_ids", [])) for p in properties.values())
    multi = sum(1 for p in properties.values() if len(p.get("rt_ids", [])) > 1)
    reg["properties"] = properties
    reg["meta"] = {
        "built": datetime.now().isoformat(timespec="seconds"),
        "total_properties": total,
        "total_transactions_linked": total_rt,
        "multi_transaction_properties": multi,
    }
    save_registry(reg, PROPERTIES_PATH)
    print(f"\nRegistry saved: {total} properties")

    # --- Step 5: Merge new matches into brand_matches.json ---
    for pid, entries in new_matches.items():
        matches.setdefault(pid, []).extend(entries)
    with open(BRAND_MATCHES_PATH, "w", encoding="utf-8") as f:
        json.dump(matches, f, indent=2, ensure_ascii=False)

    total_matched = sum(len(v) for v in matches.values())
    print(f"brand_matches.json updated: {total_matched} stores -> {len(matches)} properties")


def _next_prop_id(used_ids: set[str]) -> str:
    """Generate the next P-prefixed ID."""
    max_num = 0
    for pid in used_ids:
        if pid.startswith("P") and pid[1:].isdigit():
            max_num = max(max_num, int(pid[1:]))
    return f"P{max_num + 1:05d}"


# Cache loaded stores for lookup during import
_all_stores_cache: list[dict] | None = None


def _load_all_stores() -> list[dict]:
    global _all_stores_cache
    if _all_stores_cache is None:
        _all_stores_cache = load_brand_stores()
    return _all_stores_cache


def _find_store(match_entry: dict) -> dict | None:
    """Find the original store record matching a brand_matches entry."""
    return _find_store_by_addr(
        match_entry.get("address", ""),
        match_entry.get("city", ""),
        match_entry.get("brand", ""),
    )


def _find_store_by_addr(address: str, city: str, brand: str) -> dict | None:
    """Find a store by address/city/brand from the scraped data."""
    stores = _load_all_stores()
    addr_up = address.upper().strip()
    city_up = city.upper().strip()
    brand_up = brand.upper().strip()
    for s in stores:
        if (s.get("address", "").upper().strip() == addr_up
                and s.get("city", "").upper().strip() == city_up
                and s.get("brand", "").upper().strip() == brand_up):
            return s
    return None


def merge_proximity_matches() -> None:
    """Merge confirmed proximity matches from brand_proximity.json into brand_matches.json."""
    proximity_path = DATA_DIR / "brand_proximity.json"
    if not proximity_path.exists():
        print("No brand_proximity.json found. Run 'python run.py proximity' first.")
        return

    prox_data = json.loads(proximity_path.read_text(encoding="utf-8"))
    prox_matches = prox_data.get("matches", [])

    if not prox_matches:
        print("No proximity matches to merge.")
        return

    # Load existing brand matches
    existing: dict[str, list[dict]] = {}
    if BRAND_MATCHES_PATH.exists():
        existing = json.loads(BRAND_MATCHES_PATH.read_text(encoding="utf-8"))

    # Build set of already-matched (brand, address) to avoid duplicates
    already = set()
    for entries in existing.values():
        for e in entries:
            already.add((e.get("brand", "").upper(), e.get("address", "").upper()))

    added = 0
    for m in prox_matches:
        brand = m.get("brand", "")
        addr = m.get("store_address", "")
        if (brand.upper(), addr.upper()) in already:
            continue

        pid = m["prop_id"]
        entry = {
            "brand": brand,
            "store_name": m.get("store_name", ""),
            "address": addr,
            "city": m.get("store_city", ""),
            "method": f"proximity ({m['distance_m']:.0f}m)",
        }
        existing.setdefault(pid, []).append(entry)
        already.add((brand.upper(), addr.upper()))
        added += 1

    with open(BRAND_MATCHES_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    total = sum(len(v) for v in existing.values())
    print(f"Merged {added} proximity matches into brand_matches.json")
    print(f"Total: {total} store-to-property matches across {len(existing)} properties")


if __name__ == "__main__":
    run_match()
