#!/usr/bin/env python3
"""Simple CLI to run brand store scrapers.

Usage:
    python run.py food_basics         — single brand
    python run.py recipe_all          — all 5 Recipe Unlimited brands (one API pass)
    python run.py storelocate_all     — all 20 storelocate.ca brands
    python run.py auto_all            — all 21 automotive brands (DealerRater, slow)
    python run.py esso_all            — Esso + Mobil (single API pass)
    python run.py journie_all         — Pioneer + Ultramar (single API pass)
    python run.py loblaw_digital_all  — Valu-Mart + Independent Grocer (PCX API)
    python run.py all                 — run every scraper
    python run.py match               — match brand stores to property registry
    python run.py import              — import brands into property registry
"""

from __future__ import annotations

import sys
import time

from scrapers.food_basics import scrape as scrape_food_basics
from scrapers.dollarama import scrape as scrape_dollarama
from scrapers.freshco import scrape as scrape_freshco
from scrapers.longos import scrape as scrape_longos
from scrapers.teppermans import scrape as scrape_teppermans
from scrapers.goodwill import scrape as scrape_goodwill
from scrapers.recipe_unlimited import (
    scrape_harveys,
    scrape_swiss_chalet,
    scrape_kelseys,
    scrape_montanas,
    scrape_east_side_marios,
    scrape_all as scrape_recipe_all,
)
from scrapers.storelocate import (
    scrape_loblaws, scrape_no_frills, scrape_real_canadian_superstore,
    scrape_zehrs, scrape_fortinos, scrape_wholesale_club, scrape_shoppers_drug_mart,
    scrape_sobeys, scrape_foodland, scrape_safeway, scrape_metro,
    scrape_walmart, scrape_canadian_tire, scrape_home_depot, scrape_costco,
    scrape_homesense, scrape_best_buy, scrape_staples, scrape_sport_chek,
    scrape_toys_r_us,
    scrape_all as scrape_storelocate_all,
)
from scrapers.dealerrater import (
    scrape_brand as scrape_auto_brand,
    scrape_all as scrape_auto_all,
    BRANDS as AUTO_BRANDS,
)
from scrapers.jysk import scrape as scrape_jysk
from scrapers.petsmart import scrape as scrape_petsmart
from scrapers.giant_tiger import scrape as scrape_giant_tiger
from scrapers.lcbo import scrape as scrape_lcbo
from scrapers.dollar_tree import scrape as scrape_dollar_tree
from scrapers.farm_boy import scrape as scrape_farm_boy
from scrapers.mary_browns import scrape as scrape_mary_browns
from scrapers.st_louis import scrape as scrape_st_louis
from scrapers.wild_wing import scrape as scrape_wild_wing
from scrapers.mr_sub import scrape as scrape_mr_sub
from scrapers.yext_directory import (
    scrape_wendys,
    scrape_subway,
    scrape_five_guys,
    scrape_tim_hortons,
    scrape_chipotle,
    scrape_mucho_burrito,
    scrape_papa_johns,
    scrape_all as scrape_yext_directory_all,
    BRANDS as YEXT_DIRECTORY_BRANDS,
)
from scrapers.sunset_grill import scrape as scrape_sunset_grill
from scrapers.aw import scrape as scrape_aw
from scrapers.boston_pizza import scrape as scrape_boston_pizza
from scrapers.rens_pets import scrape as scrape_rens_pets
from scrapers.the_brick import scrape as scrape_the_brick
from scrapers.esso import scrape as scrape_esso, scrape_mobil, scrape_all as scrape_esso_all
from scrapers.indigo import scrape as scrape_indigo
from scrapers.mcdonalds import scrape as scrape_mcdonalds
from scrapers.journie import (
    scrape_pioneer,
    scrape_ultramar,
    scrape_all as scrape_journie_all,
)
from scrapers.loblaw_digital import (
    scrape_valumart,
    scrape_independent_grocer,
    scrape_all as scrape_loblaw_digital_all,
    BRANDS as LOBLAW_DIGITAL_BRANDS,
)
from scrapers.rbi import (
    scrape_burger_king,
    scrape_firehouse_subs,
    scrape_popeyes,
    scrape_all as scrape_rbi_all,
    BRANDS as RBI_BRANDS,
)
from scrapers.pita_pit import scrape as scrape_pita_pit
from scrapers.dominos import scrape as scrape_dominos
from scrapers.starbucks import scrape as scrape_starbucks
from scrapers.dairy_queen import scrape as scrape_dairy_queen
from scrapers.pizza_pizza import scrape as scrape_pizza_pizza
from scrapers.pizza_hut import scrape as scrape_pizza_hut
from scrapers.taco_bell import scrape as scrape_taco_bell

# Individual brand scrapers (non-batch)
SCRAPERS = {
    # Original 3
    "food_basics": scrape_food_basics,
    "dollarama": scrape_dollarama,
    "freshco": scrape_freshco,
    # Phase 1 trivials
    "longos": scrape_longos,
    "teppermans": scrape_teppermans,
    "goodwill": scrape_goodwill,
    # Recipe Unlimited
    "harveys": scrape_harveys,
    "swiss_chalet": scrape_swiss_chalet,
    "kelseys": scrape_kelseys,
    "montanas": scrape_montanas,
    "east_side_marios": scrape_east_side_marios,
    # storelocate.ca brands
    "loblaws": scrape_loblaws,
    "no_frills": scrape_no_frills,
    "real_canadian_superstore": scrape_real_canadian_superstore,
    "zehrs": scrape_zehrs,
    "fortinos": scrape_fortinos,
    "wholesale_club": scrape_wholesale_club,
    "shoppers_drug_mart": scrape_shoppers_drug_mart,
    "sobeys": scrape_sobeys,
    "foodland": scrape_foodland,
    "safeway": scrape_safeway,
    "metro": scrape_metro,
    "walmart": scrape_walmart,
    "canadian_tire": scrape_canadian_tire,
    "home_depot": scrape_home_depot,
    "costco": scrape_costco,
    "homesense": scrape_homesense,
    "best_buy": scrape_best_buy,
    "staples": scrape_staples,
    "sport_chek": scrape_sport_chek,
    "toys_r_us": scrape_toys_r_us,
    # Individual scrapers
    "jysk": scrape_jysk,
    "petsmart": scrape_petsmart,
    "giant_tiger": scrape_giant_tiger,
    "lcbo": scrape_lcbo,
    "dollar_tree": scrape_dollar_tree,
    "farm_boy": scrape_farm_boy,
    "mary_browns": scrape_mary_browns,
    "st_louis": scrape_st_louis,
    "wild_wing": scrape_wild_wing,
    "mr_sub": scrape_mr_sub,
    # Yext directory brands
    "wendys": scrape_wendys,
    "subway": scrape_subway,
    "five_guys": scrape_five_guys,
    "tim_hortons": scrape_tim_hortons,
    "chipotle": scrape_chipotle,
    "mucho_burrito": scrape_mucho_burrito,
    "papa_johns": scrape_papa_johns,
    # New individual scrapers
    "sunset_grill": scrape_sunset_grill,
    "aw": scrape_aw,
    "boston_pizza": scrape_boston_pizza,
    "rens_pets": scrape_rens_pets,
    "the_brick": scrape_the_brick,
    "esso": scrape_esso,
    "mobil": scrape_mobil,
    "indigo": scrape_indigo,
    "mcdonalds": scrape_mcdonalds,
    # Journie/Parkland brands
    "pioneer": scrape_pioneer,
    "ultramar": scrape_ultramar,
    # Loblaw Digital brands
    "valumart": scrape_valumart,
    "independent_grocer": scrape_independent_grocer,
    # RBI brands
    "burger_king": scrape_burger_king,
    "firehouse_subs": scrape_firehouse_subs,
    "popeyes": scrape_popeyes,
    # Tier 3 individual scrapers
    "pita_pit": scrape_pita_pit,
    "dominos": scrape_dominos,
    "starbucks": scrape_starbucks,
    "dairy_queen": scrape_dairy_queen,
    "pizza_pizza": scrape_pizza_pizza,
    "pizza_hut": scrape_pizza_hut,
    "taco_bell": scrape_taco_bell,
}

# Auto brands registered individually (for `run.py toyota`, `run.py honda`, etc.)
for _key in AUTO_BRANDS:
    SCRAPERS[_key] = lambda k=_key: scrape_auto_brand(k)

# Batch groups — brands covered by batch commands
RECIPE_BRANDS = {"harveys", "swiss_chalet", "kelseys", "montanas", "east_side_marios"}
STORELOCATE_BRANDS = {
    "loblaws", "no_frills", "real_canadian_superstore", "zehrs", "fortinos",
    "wholesale_club", "shoppers_drug_mart", "sobeys", "foodland", "safeway",
    "metro", "walmart", "canadian_tire", "home_depot", "costco", "homesense",
    "best_buy", "staples", "sport_chek", "toys_r_us",
}
AUTO_BRAND_KEYS = set(AUTO_BRANDS.keys())
YEXT_DIRECTORY_BRAND_KEYS = set(YEXT_DIRECTORY_BRANDS.keys())
ESSO_BRAND_KEYS = {"esso", "mobil"}
JOURNIE_BRAND_KEYS = {"pioneer", "ultramar"}
LOBLAW_DIGITAL_BRAND_KEYS = {"valumart", "independent_grocer"}
RBI_BRAND_KEYS = {"burger_king", "firehouse_subs", "popeyes"}


def run_one(name: str) -> None:
    func = SCRAPERS.get(name)
    if func is None:
        print(f"Unknown brand: {name}")
        print(f"Available: {', '.join(sorted(SCRAPERS))}")
        print("\nBatch commands: recipe_all, storelocate_all, yext_dir_all, esso_all, journie_all, auto_all, all")
        sys.exit(1)
    t0 = time.time()
    records, path = func()
    elapsed = time.time() - t0
    print(f"  {name}: {len(records)} stores -> {path}  ({elapsed:.1f}s)")


def run_recipe_all() -> None:
    """Run all Recipe Unlimited brands in a single API pass."""
    t0 = time.time()
    results = scrape_recipe_all()
    elapsed = time.time() - t0
    for slug, count, path in results:
        print(f"  {slug}: {count} stores -> {path}")
    print(f"  Recipe Unlimited total: {sum(c for _, c, _ in results)} stores ({elapsed:.1f}s)")


def run_storelocate_all() -> None:
    """Run all storelocate.ca brands."""
    t0 = time.time()
    results = scrape_storelocate_all()
    elapsed = time.time() - t0
    for slug, count, path in results:
        print(f"  {slug}: {count} stores -> {path}")
    print(f"  storelocate.ca total: {sum(c for _, c, _ in results)} stores ({elapsed:.1f}s)")


def run_yext_directory_all() -> None:
    """Run all Yext directory brands."""
    t0 = time.time()
    results = scrape_yext_directory_all()
    elapsed = time.time() - t0
    for slug, count, path in results:
        print(f"  {slug}: {count} stores -> {path}")
    print(f"  Yext directory total: {sum(c for _, c, _ in results)} stores ({elapsed:.1f}s)")


def run_esso_all() -> None:
    """Run Esso + Mobil in a single API pass."""
    t0 = time.time()
    results = scrape_esso_all()
    elapsed = time.time() - t0
    for slug, count, path in results:
        print(f"  {slug}: {count} stores -> {path}")
    print(f"  Esso/Mobil total: {sum(c for _, c, _ in results)} stores ({elapsed:.1f}s)")


def run_journie_all() -> None:
    """Run Pioneer + Ultramar in a single API pass."""
    t0 = time.time()
    results = scrape_journie_all()
    elapsed = time.time() - t0
    for slug, count, path in results:
        print(f"  {slug}: {count} stores -> {path}")
    print(f"  Journie/Parkland total: {sum(c for _, c, _ in results)} stores ({elapsed:.1f}s)")


def run_loblaw_digital_all() -> None:
    """Run Valu-Mart + Independent Grocer via PCX API."""
    t0 = time.time()
    results = scrape_loblaw_digital_all()
    elapsed = time.time() - t0
    for slug, count, path in results:
        print(f"  {slug}: {count} stores -> {path}")
    print(f"  Loblaw Digital total: {sum(c for _, c, _ in results)} stores ({elapsed:.1f}s)")


def run_rbi_all() -> None:
    """Run Burger King + Firehouse Subs via RBI GraphQL."""
    t0 = time.time()
    results = scrape_rbi_all()
    elapsed = time.time() - t0
    for slug, count, path in results:
        print(f"  {slug}: {count} stores -> {path}")
    print(f"  RBI total: {sum(c for _, c, _ in results)} stores ({elapsed:.1f}s)")


def run_auto_all() -> None:
    """Run all automotive brands via DealerRater (slow — ~30min)."""
    t0 = time.time()
    results = scrape_auto_all()
    elapsed = time.time() - t0
    print()
    for slug, count, path in results:
        print(f"  {slug}: {count} dealers -> {path}")
    print(f"  Automotive total: {sum(c for _, c, _ in results)} dealers ({elapsed:.1f}s)")


def run_geocode() -> None:
    """Coordinate store and Geocodio geocoding commands."""
    from coordinates import CoordinateStore
    from geocodio_client import DAILY_LIMIT, batch_forward

    store = CoordinateStore()
    flags = set(sys.argv[2:])

    if "--seed" in flags:
        print("Seeding coordinate store from existing caches...")
        mapbox_count = store.seed_from_geocode_cache()
        print(f"  Mapbox (geocode_cache.json): {mapbox_count:,} entries")
        scraper_count = store.seed_scraper_coords()
        print(f"  Scraper (brand store files): {scraper_count:,} entries")
        store.save()
        print(f"\nCoordinate store saved: {len(store.addresses):,} total addresses")
        stats = store.stats()
        print(f"By provider: {stats['by_provider']}")
        return

    if "--status" in flags:
        if not store.addresses:
            print("Coordinate store is empty. Run 'geocode --seed' first.")
            return
        stats = store.stats()
        pending = store.pending_geocodio()
        print(f"Coordinate store: {stats['total_addresses']:,} addresses")
        print(f"By provider: {stats['by_provider']}")
        print(f"Multi-provider: {stats['multi_provider']:,}")
        print(f"Pending Geocodio: {len(pending):,}")
        return

    # Default: geocode next batch via Geocodio
    if not store.addresses:
        print("Coordinate store is empty. Run 'geocode --seed' first.")
        return

    pending = store.pending_geocodio()
    if not pending:
        print("All addresses already have Geocodio results!")
        return

    batch = pending[:DAILY_LIMIT]
    print(f"Geocoding {len(batch):,} addresses via Geocodio ({len(pending):,} remaining)...")

    t0 = time.time()
    results = batch_forward(batch)
    elapsed = time.time() - t0

    added = store.add_geocodio_batch(batch, results)
    store.save()

    success_rate = (added / len(batch) * 100) if batch else 0
    remaining = len(pending) - len(batch)
    print(f"\nGeocoded {added:,}/{len(batch):,} ({success_rate:.0f}%) in {elapsed:.1f}s")
    print(f"Remaining: {remaining:,} addresses (~{remaining // DAILY_LIMIT + (1 if remaining % DAILY_LIMIT else 0)} days)")

    # Auto-audit: check for provider divergences in newly geocoded addresses
    divergences = store.divergence_report(threshold_m=500)
    if divergences:
        print(f"\n--- Audit: {len(divergences)} addresses with provider disagreement > 500m ---\n")
        for d in divergences[:10]:
            print(f"  {d['address']}")
            print(f"    {d['max_distance_m']:,.0f}m apart ({d['worst_pair'][0]} vs {d['worst_pair'][1]})")
            for p, coords in d["providers"].items():
                print(f"    {p:10s}: {coords['lat']:.6f}, {coords['lng']:.6f}")
            print()
        if len(divergences) > 10:
            print(f"  ... and {len(divergences) - 10} more (run 'proximity --audit' for full list)")
    else:
        print("\nAudit: No provider divergences > 500m")


def run_proximity() -> None:
    """Proximity matching commands."""
    from coordinates import CoordinateStore
    from proximity import run_proximity_match

    flags = set(sys.argv[2:])

    if "--audit" in flags:
        store = CoordinateStore()
        if not store.addresses:
            print("Coordinate store is empty. Run 'geocode --seed' first.")
            return
        threshold = 500
        print(f"Finding provider divergences > {threshold}m...")
        divergences = store.divergence_report(threshold_m=threshold)
        if not divergences:
            print("No divergences found.")
            return
        print(f"\n{len(divergences)} addresses with provider disagreement > {threshold}m:\n")
        for d in divergences[:50]:
            print(f"  {d['address']}")
            print(f"    Max distance: {d['max_distance_m']:,.0f}m ({d['worst_pair'][0]} vs {d['worst_pair'][1]})")
            for p, coords in d["providers"].items():
                print(f"    {p:10s}: {coords['lat']:.6f}, {coords['lng']:.6f}")
            print()
        if len(divergences) > 50:
            print(f"  ... and {len(divergences) - 50} more")
        return

    if "--merge" in flags:
        from match import merge_proximity_matches
        merge_proximity_matches()
        return

    # Default: run proximity matching
    store = CoordinateStore()
    if not store.addresses:
        print("Coordinate store is empty. Run 'geocode --seed' first.")
        return

    result = run_proximity_match(coord_store=store)
    stats = result["stats"]
    matches = result["matches"]

    print(f"\nProximity matching results:")
    print(f"  Total stores:       {stats['total_stores']:,}")
    print(f"  Already matched:    {stats['already_matched']:,}")
    print(f"  No coordinates:     {stats['no_coordinates']:,}")
    print(f"  No nearby property: {stats['no_nearby_property']:,}")
    print(f"  Proximity matches:  {stats['proximity_matches']:,}")

    if matches:
        print(f"\nTop proximity matches (by distance):")
        for m in matches[:20]:
            print(f"  {m['brand']:20s} {m['store_address'][:30]:30s} -> "
                  f"{m['prop_id']} {m['prop_address'][:30]:30s} ({m['distance_m']:.0f}m)")
        if len(matches) > 20:
            print(f"  ... and {len(matches) - 20} more")

    print(f"\nWrote {len(matches)} proximity matches to data/brand_proximity.json")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run.py [brand|batch|match|import]")
        print(f"\nAvailable brands ({len(SCRAPERS)}):")
        print(f"  {', '.join(sorted(SCRAPERS))}")
        print("\nBatch commands:")
        print("  recipe_all       — 5 Recipe Unlimited brands (Yext API)")
        print("  storelocate_all  — 20 brands (storelocate.ca)")
        print("  yext_dir_all     — 7 Yext directory brands")
        print("  esso_all         — Esso + Mobil (single API pass)")
        print("  journie_all      — Pioneer + Ultramar (single API pass)")
        print("  loblaw_dig_all   — Valu-Mart + Independent Grocer (PCX API)")
        print("  rbi_all          — Burger King + Firehouse Subs (RBI GraphQL)")
        print("  auto_all         — 21 automotive brands (DealerRater, ~30 min)")
        print("  all              — every scraper")
        print("\nCoordinates & proximity:")
        print("  geocode          — geocode next 2,300 addresses via Geocodio")
        print("  geocode --status — show geocoding progress")
        print("  geocode --seed   — seed coordinate store from existing caches")
        print("  proximity        — run proximity-based brand matching")
        print("  proximity --audit  — show provider coordinate divergences")
        print("  proximity --merge  — merge proximity matches into brand_matches.json")
        print("\nOther:")
        print("  match            — match brand stores to property registry")
        print("  import           — import brands into property registry")
        sys.exit(1)

    target = sys.argv[1].lower()

    if target == "geocode":
        run_geocode()
    elif target == "proximity":
        run_proximity()
    elif target == "match":
        from match import run_match
        run_match()
    elif target == "import":
        from match import import_to_registry
        import_to_registry()
    elif target == "recipe_all":
        run_recipe_all()
    elif target in ("storelocate_all", "loblaw_all"):
        run_storelocate_all()
    elif target == "yext_dir_all":
        run_yext_directory_all()
    elif target == "esso_all":
        run_esso_all()
    elif target == "journie_all":
        run_journie_all()
    elif target in ("loblaw_dig_all", "loblaw_digital_all"):
        run_loblaw_digital_all()
    elif target == "rbi_all":
        run_rbi_all()
    elif target == "auto_all":
        run_auto_all()
    elif target == "all":
        print("Running all scrapers...")
        run_recipe_all()
        run_storelocate_all()
        run_yext_directory_all()
        run_esso_all()
        run_journie_all()
        run_loblaw_digital_all()
        run_rbi_all()
        run_auto_all()
        # Individual non-batch scrapers
        batch_keys = (
            RECIPE_BRANDS | STORELOCATE_BRANDS | YEXT_DIRECTORY_BRAND_KEYS
            | AUTO_BRAND_KEYS | ESSO_BRAND_KEYS | JOURNIE_BRAND_KEYS
            | LOBLAW_DIGITAL_BRAND_KEYS | RBI_BRAND_KEYS
        )
        for name in SCRAPERS:
            if name in batch_keys:
                continue
            run_one(name)
    else:
        run_one(target)

    print("Done.")


if __name__ == "__main__":
    main()
