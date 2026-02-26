"""Cleo Mini V3 CLI."""

import json
import logging
import time
from datetime import datetime

import click

from cleo.config import DATA_DIR, HTML_DIR, get_credentials
from cleo.ingest.fetcher import fetch_detail_page
from cleo.ingest.html_index import HtmlIndex
from cleo.ingest.scraper import (
    PROPERTY_TYPES,
    discover_property_types,
    get_total_results,
    make_search_params,
    submit_search_and_get_links,
)
from cleo.ingest.session import AuthenticationError, RealtrackSession
from cleo.ingest.tracker import IngestTracker
from cleo.validate.html_checks import FLAG_DEFS
from cleo.parse.engine import parse_all
from cleo.parse.versioning import (
    sandbox_path,
    sandbox_exists,
    ensure_sandbox,
    discard_sandbox,
    active_version,
    active_dir,
    list_versions,
    promote,
    rollback,
    diff_sandbox_vs_active,
)
from cleo.parse.diff_report import format_diff_report
from cleo.extract.engine import extract_all
from cleo.extract import versioning as extract_ver
from cleo.validate.parse_checks import PARSE_FLAG_DEFS
from cleo.validate.parse_runner import (
    run_parse_checks,
    save_parse_flags,
    load_parse_flags,
    cross_reference_html_flags,
    PARSE_FLAGS_PATH,
)
from cleo.validate.runner import (
    run_all_checks,
    save_flags,
    load_flags,
    load_determinations,
    save_determinations,
    HTML_FLAGS_PATH,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@click.group()
def main():
    """Cleo Mini V3 — Realtrack.com transaction ingestion."""


@main.command()
@click.option("--delay", default=0.75, help="Seconds between detail page requests.")
@click.option("--type", "prop_type", default="retail",
              type=click.Choice(sorted(PROPERTY_TYPES.keys()), case_sensitive=False),
              help="Property type to scrape.")
def scrape(delay: float, prop_type: str):
    """Scrape new transactions from Realtrack.com.

    Logs in, searches for the specified property type (default: retail),
    visits up to 50 detail pages, and saves HTML for any new RT IDs
    not already in the local store.
    """
    # Step 1: Get credentials
    try:
        username, password = get_credentials()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    # Step 2: Login
    try:
        session = RealtrackSession(username, password)
    except AuthenticationError as e:
        click.echo(f"Login failed: {e}", err=True)
        raise SystemExit(1)

    try:
        # Step 3: Submit search, get detail links
        skip_indices = submit_search_and_get_links(session, prop_type=prop_type)
        if not skip_indices:
            click.echo("No results found. Exiting.")
            return

        # Step 4: Fetch each detail page and extract RT ID
        click.echo(f"Visiting {len(skip_indices)} detail pages...")
        results = []  # List of (rt_id, html_content)

        for i, skip in enumerate(skip_indices):
            rt_id, html = fetch_detail_page(session, skip)
            if rt_id:
                results.append((rt_id, html))
            else:
                logger.warning("Skipping detail page skip=%d (no RT ID found).", skip)

            if delay > 0 and i < len(skip_indices) - 1:
                time.sleep(delay)

        click.echo(f"Extracted {len(results)} RT IDs from {len(skip_indices)} pages.")

        # Step 5: Check which RT IDs are new
        tracker = IngestTracker()
        all_rt_ids = [rt_id for rt_id, _ in results]
        new_rt_ids = tracker.find_new(all_rt_ids)

        if not new_rt_ids:
            click.echo("No new transactions. Everything is up to date.")
            return

        # Step 6: Save HTML for new RT IDs into type subdirectory
        type_dir = HTML_DIR / prop_type
        type_dir.mkdir(parents=True, exist_ok=True)
        html_index = HtmlIndex()

        new_rt_set = set(new_rt_ids)
        saved = 0
        for rt_id, html in results:
            if rt_id in new_rt_set:
                path = type_dir / f"{rt_id}.html"
                path.write_text(html, encoding="utf-8")
                html_index.register(rt_id, prop_type)
                saved += 1
                logger.info("Saved %s", path.name)

        # Step 7: Update tracker and HTML index
        tracker.mark_seen(new_rt_ids, prop_type=prop_type)
        html_index.save()

        click.echo(
            f"Done! Saved {saved} new {prop_type} transactions. "
            f"Total known: {tracker.count}."
        )

    finally:
        session.close()


@main.command()
@click.option("--type", "prop_type", default="retail",
              type=click.Choice(sorted(PROPERTY_TYPES.keys()), case_sensitive=False),
              help="Property type to check gap for.")
@click.option("--all", "check_all", is_flag=True, help="Check gaps for all known property types.")
def check(prop_type: str, check_all: bool):
    """Compare local RT ID count against Realtrack's total result count."""
    try:
        username, password = get_credentials()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    try:
        session = RealtrackSession(username, password)
    except AuthenticationError as e:
        click.echo(f"Login failed: {e}", err=True)
        raise SystemExit(1)

    try:
        tracker = IngestTracker()
        types_to_check = sorted(PROPERTY_TYPES.keys()) if check_all else [prop_type]

        for i, ptype in enumerate(types_to_check):
            if i > 0:
                click.echo()

            total = get_total_results(session, prop_type=ptype)
            if total is None:
                click.echo(f"[{ptype}] Could not extract total from Realtrack.", err=True)
                continue

            local = tracker.count_by_type(ptype)
            gap = total - local

            click.echo(f"[{ptype}]")
            click.echo(f"  Realtrack total:  {total:,}")
            click.echo(f"  Local RT IDs:     {local:,}")
            click.echo(f"  Gap:              {gap:,}")

            if gap == 0:
                click.echo("  Perfect — fully synced.")
            elif gap > 0:
                click.echo(f"  Missing {gap:,} transactions.")
            else:
                click.echo(f"  Local has {abs(gap):,} more than Realtrack (possible dupes or type overlap).")
    finally:
        session.close()


@main.command(name="parse")
@click.option("--sandbox", "action", flag_value="sandbox", help="Parse all HTML → sandbox.")
@click.option("--diff", "action", flag_value="diff", help="Compare sandbox vs active.")
@click.option("--promote", "action", flag_value="promote", help="Promote sandbox → next version.")
@click.option("--discard", "action", flag_value="discard", help="Delete sandbox.")
@click.option("--rollback-to", "rollback_version", default=None, help="Point active to a specific version.")
@click.option("--status", "action", flag_value="status", help="Show current version info.")
@click.option("--force", is_flag=True, help="Force promote even with regressions.")
def parse_cmd(action: str, rollback_version: str, force: bool):
    """Manage parsed JSON output with versioned snapshots.

    Parse all HTML into a sandbox, diff against the current active version,
    then promote or discard.
    """
    if rollback_version:
        action = "rollback"

    if not action:
        click.echo("Specify one of: --sandbox, --diff, --promote, --discard, --rollback-to, --status")
        raise SystemExit(1)

    if action == "status":
        ver = active_version()
        versions = list_versions()
        has_sandbox = sandbox_exists()
        click.echo(f"Active version:  {ver or '(none)'}")
        click.echo(f"All versions:    {', '.join(versions) or '(none)'}")
        click.echo(f"Sandbox:         {'exists' if has_sandbox else '(none)'}")

    elif action == "sandbox":
        if sandbox_exists():
            click.echo("Sandbox already exists. Use --discard first.", err=True)
            raise SystemExit(1)
        sb = ensure_sandbox()
        click.echo(f"Parsing HTML files → {sb}\n")
        summary = parse_all(output_dir=sb)
        click.echo(
            f"\nDone: {summary['parsed']:,} parsed, "
            f"{summary['errors']:,} errors in {summary['elapsed']}s"
        )
        if summary["error_ids"]:
            click.echo(f"Errors: {', '.join(summary['error_ids'][:10])}")
            if len(summary["error_ids"]) > 10:
                click.echo(f"  ... and {len(summary['error_ids']) - 10} more")

    elif action == "diff":
        try:
            diff_result = diff_sandbox_vs_active()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(format_diff_report(diff_result))

    elif action == "promote":
        # Regression check before promoting
        if active_dir() and sandbox_exists() and not force:
            try:
                diff_result = diff_sandbox_vs_active()
                regressions = diff_result.get("regressions", [])
                if regressions:
                    click.echo(f"\nBLOCKED: {len(regressions)} reviewed-Clean record(s) would change:\n")
                    for r in regressions[:10]:
                        fields = ", ".join(r["changed_fields"][:5])
                        click.echo(f"  {r['rt_id']}  →  {fields}")
                    if len(regressions) > 10:
                        click.echo(f"  ... and {len(regressions) - 10} more")
                    click.echo(f"\nUpdate reviews or use --force to override.")
                    raise SystemExit(1)
            except FileNotFoundError:
                pass  # No active to diff against — first promote is fine
        try:
            version = promote()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        # Clear sandbox_accepted flags — sandbox is now active
        _clear_sandbox_accepted()
        click.echo(f"Promoted to {version}")

    elif action == "discard":
        if discard_sandbox():
            click.echo("Sandbox discarded.")
        else:
            click.echo("No sandbox to discard.")

    elif action == "rollback":
        try:
            rollback(rollback_version)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(f"Active → {rollback_version}")


@main.command(name="extract")
@click.option("--sandbox", "action", flag_value="sandbox", help="Extract parsed addresses → sandbox.")
@click.option("--diff", "action", flag_value="diff", help="Compare extraction sandbox vs active.")
@click.option("--promote", "action", flag_value="promote", help="Promote extraction sandbox → next version.")
@click.option("--discard", "action", flag_value="discard", help="Delete extraction sandbox.")
@click.option("--rollback-to", "rollback_version", default=None, help="Point active to a specific version.")
@click.option("--status", "action", flag_value="status", help="Show extraction version info.")
@click.option("--force", is_flag=True, help="Force promote even with regressions.")
def extract_cmd(action: str, rollback_version: str, force: bool):
    """Manage extracted address data with versioned snapshots.

    Reads parsed JSON from parsed/active, expands compound addresses into
    geocodable variations, and writes to extracted/sandbox. Then diff,
    promote, or discard.
    """
    store = extract_ver.store

    if rollback_version:
        action = "rollback"

    if not action:
        click.echo("Specify one of: --sandbox, --diff, --promote, --discard, --rollback-to, --status")
        raise SystemExit(1)

    if action == "status":
        ver = store.active_version()
        versions = store.list_versions()
        has_sandbox = store.sandbox_path().is_dir()
        click.echo(f"Active version:  {ver or '(none)'}")
        click.echo(f"All versions:    {', '.join(versions) or '(none)'}")
        click.echo(f"Sandbox:         {'exists' if has_sandbox else '(none)'}")

    elif action == "sandbox":
        if store.sandbox_path().is_dir():
            click.echo("Sandbox already exists. Use --discard first.", err=True)
            raise SystemExit(1)

        # Need parsed/active as source
        parse_active = active_dir()
        if parse_active is None:
            click.echo("No active parse version. Run 'cleo parse --sandbox' then '--promote' first.", err=True)
            raise SystemExit(1)

        sb = store.ensure_sandbox()
        source_ver = active_version() or ""
        click.echo(f"Extracting addresses from {parse_active.name} → {sb}\n")

        summary = extract_all(
            source_dir=parse_active,
            output_dir=sb,
            source_version=source_ver,
        )
        click.echo(
            f"\nDone: {summary['extracted']:,} extracted, "
            f"{summary['errors']:,} errors in {summary['elapsed']:.1f}s"
        )
        if summary["error_ids"]:
            click.echo(f"Errors: {', '.join(summary['error_ids'][:10])}")
            if len(summary["error_ids"]) > 10:
                click.echo(f"  ... and {len(summary['error_ids']) - 10} more")

    elif action == "diff":
        try:
            diff_result = store.diff_sandbox_vs_active()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(format_diff_report(diff_result))

    elif action == "promote":
        if store.active_dir() and store.sandbox_path().is_dir() and not force:
            try:
                diff_result = store.diff_sandbox_vs_active()
                regressions = diff_result.get("regressions", [])
                if regressions:
                    click.echo(f"\nBLOCKED: {len(regressions)} reviewed-Clean record(s) would change:\n")
                    for r in regressions[:10]:
                        fields = ", ".join(r["changed_fields"][:5])
                        click.echo(f"  {r['rt_id']}  →  {fields}")
                    if len(regressions) > 10:
                        click.echo(f"  ... and {len(regressions) - 10} more")
                    click.echo(f"\nUpdate reviews or use --force to override.")
                    raise SystemExit(1)
            except FileNotFoundError:
                pass  # No active to diff against — first promote is fine
        try:
            version = store.promote()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(f"Promoted to {version}")
        _clear_extract_sandbox_accepted()

    elif action == "discard":
        if store.discard_sandbox():
            click.echo("Sandbox discarded.")
        else:
            click.echo("No sandbox to discard.")

    elif action == "rollback":
        try:
            store.rollback(rollback_version)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(f"Active → {rollback_version}")


@main.command(name="geocode")
@click.option("--dry-run", is_flag=True, help="Show what would be geocoded without calling API.")
@click.option("--limit", type=int, default=None, help="Max addresses to geocode in this run.")
@click.option("--status", "show_status", is_flag=True, help="Show per-provider coverage from coordinates.json.")
@click.option("--build-index", is_flag=True, help="Build address index from cache + extracted data.")
@click.option("--collect", "do_collect", is_flag=True, help="Collect all addresses (RT+GW+brand) into coordinates.json.")
@click.option("--sync", "do_sync", is_flag=True, help="One-time: seed coordinates.json from geocode_cache.json + brand scrapers.")
@click.option("--batch-size", type=int, default=50, help="Addresses per batch API call.")
@click.option("--delay", type=float, default=0.15, help="Seconds between batch API calls.")
@click.option("--provider", type=click.Choice(["mapbox", "here", "geocodio"]), default="mapbox", help="Geocoding provider.")
def geocode_cmd(dry_run, limit, show_status, build_index, do_collect, do_sync, batch_size, delay, provider):
    """Geocode addresses from all sources using Mapbox, HERE, or Geocodio.

    Uses data/coordinates.json as the unified multi-provider store.
    Collects addresses from RT extracted data, GeoWarehouse, and brand scrapers.

    \b
    Examples:
        cleo geocode --status                       # Per-provider coverage
        cleo geocode --collect                       # Register all addresses in store
        cleo geocode --sync                          # Seed from geocode_cache.json
        cleo geocode --provider mapbox               # Geocode pending via Mapbox
        cleo geocode --provider geocodio --limit 2300 # Daily Geocodio batch
        cleo geocode --provider here                 # Geocode pending via HERE
        cleo geocode --build-index                   # Build address index
    """
    from cleo.config import (
        MAPBOX_TOKEN, HERE_API_KEY, GEOCODIO_KEY,
        GEOCODE_CACHE_PATH, COORDINATES_PATH, ADDRESS_INDEX_PATH,
        EXTRACTED_DIR, EXTRACT_REVIEWS_PATH, GW_PARSED_DIR, BRANDS_DATA_DIR,
    )
    from cleo.geocode.store import CoordinateStore

    store = CoordinateStore(COORDINATES_PATH)

    # --- --status: show per-provider coverage ---
    if show_status:
        stats = store.stats()
        click.echo(f"Coordinate store: {COORDINATES_PATH}")
        click.echo(f"  Total addresses:   {stats['total_addresses']:,}")
        for prov, count in sorted(stats["by_provider"].items()):
            pct = 100 * count / stats["total_addresses"] if stats["total_addresses"] else 0
            click.echo(f"  {prov:>10s}:       {count:,}  ({pct:.1f}%)")
        click.echo(f"  Multi-provider:    {stats['multi_provider']:,}")

        # Also show legacy cache stats
        if GEOCODE_CACHE_PATH.exists():
            from cleo.geocode.cache import GeocodeCache
            cache = GeocodeCache(GEOCODE_CACHE_PATH)
            cstats = cache.stats()
            click.echo(f"\nLegacy geocode cache: {GEOCODE_CACHE_PATH}")
            click.echo(f"  Total entries:  {cstats['total']:,}")
            click.echo(f"  Successes:      {cstats['successes']:,}")
            click.echo(f"  Failures:       {cstats['failures']:,}")
        return

    # --- --sync: one-time seed from geocode_cache.json + brand scrapers ---
    if do_sync:
        click.echo("Seeding coordinates.json from existing data sources...\n")
        mapbox_count = store.seed_from_geocode_cache()
        click.echo(f"  Imported from geocode_cache.json (mapbox):  {mapbox_count:,}")
        scraper_count = store.seed_scraper_coords()
        click.echo(f"  Imported from brand scrapers (scraper):     {scraper_count:,}")
        store.save()
        click.echo(f"\n  Total addresses in store: {len(store.addresses):,}")
        click.echo(f"  Saved to {COORDINATES_PATH}")
        return

    # --- --collect: register all addresses from RT+GW+brands ---
    if do_collect:
        from cleo.geocode.unified_collector import collect_all, register_in_store, stats_summary

        ext_store = extract_ver.store
        ext_active = ext_store.active_dir()
        gw_store = _gw_versioned_store()
        gw_active = gw_store.active_dir() if gw_store else None

        click.echo("Collecting addresses from all sources...\n")
        addresses = collect_all(
            extracted_dir=ext_active,
            reviews_path=EXTRACT_REVIEWS_PATH,
            gw_parsed_dir=gw_active,
            brands_data_dir=BRANDS_DATA_DIR,
        )
        added = register_in_store(store, addresses)
        store.save()

        summary = stats_summary(addresses)
        click.echo(f"  Total unique addresses:  {summary['total']:,}")
        click.echo(f"  By source:")
        for src, count in sorted(summary["by_source"].items()):
            click.echo(f"    {src:>10s}: {count:,}")
        click.echo(f"  By role:")
        for role, count in sorted(summary["by_role"].items()):
            click.echo(f"    {role:>10s}: {count:,}")
        click.echo(f"  Newly added to store:    {added:,}")
        click.echo(f"  Total in store:          {len(store.addresses):,}")
        click.echo(f"  Saved to {COORDINATES_PATH}")
        return

    # --- --build-index ---
    if build_index:
        from cleo.geocode.cache import GeocodeCache
        from cleo.geocode.index import build_address_index
        cache = GeocodeCache(GEOCODE_CACHE_PATH)
        ext_store = extract_ver.store
        ext_active = ext_store.active_dir()
        if ext_active is None:
            click.echo("No active extraction version.", err=True)
            raise SystemExit(1)

        click.echo(f"Building address index from {ext_active.name} + geocode cache...")
        index_data = build_address_index(
            extracted_dir=ext_active,
            reviews_path=EXTRACT_REVIEWS_PATH,
            cache=cache,
        )
        import json
        ADDRESS_INDEX_PATH.write_text(
            json.dumps(index_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        loc_count = len(index_data.get("locations", {}))
        rt_count = len(index_data.get("rt_to_locations", {}))
        click.echo(f"Done: {loc_count:,} locations, {rt_count:,} RT records indexed.")
        click.echo(f"Saved to {ADDRESS_INDEX_PATH}")
        return

    # --- Geocoding mode: geocode pending addresses for chosen provider ---
    from cleo.geocode.runner import run_geocode
    from cleo.geocode.cache import GeocodeCache

    # Optionally collect first if store is empty
    if not store.addresses:
        click.echo("Coordinate store is empty. Running --collect first...\n")
        from cleo.geocode.unified_collector import collect_all, register_in_store
        ext_store = extract_ver.store
        ext_active = ext_store.active_dir()
        gw_store = _gw_versioned_store()
        gw_active = gw_store.active_dir() if gw_store else None
        addresses = collect_all(
            extracted_dir=ext_active,
            reviews_path=EXTRACT_REVIEWS_PATH,
            gw_parsed_dir=gw_active,
            brands_data_dir=BRANDS_DATA_DIR,
        )
        register_in_store(store, addresses)
        store.save()
        click.echo(f"  Registered {len(store.addresses):,} addresses.\n")

    # Set up legacy cache for backward compat (Mapbox/HERE)
    cache = GeocodeCache(GEOCODE_CACHE_PATH) if GEOCODE_CACHE_PATH.exists() else None

    client = None
    if not dry_run:
        if provider == "geocodio":
            from cleo.geocode.geocodio_client import GeocodioClient
            if not GEOCODIO_KEY:
                click.echo("GEOCODIO_KEY not set. Add it to your .env file.", err=True)
                raise SystemExit(1)
            client = GeocodioClient(GEOCODIO_KEY)
            if batch_size == 50:  # default wasn't overridden
                batch_size = 2300  # Geocodio supports up to 10K, use daily limit
            click.echo(f"Using Geocodio provider (batch size {batch_size})")
        elif provider == "here":
            from cleo.geocode.here_client import HereClient
            if not HERE_API_KEY:
                click.echo("HERE_API_KEY not set. Add it to your .env file.", err=True)
                raise SystemExit(1)
            client = HereClient(HERE_API_KEY)
            if delay == 0.15:  # default wasn't overridden
                delay = 0.22  # safe under HERE's 5/sec limit
            click.echo(f"Using HERE provider ({delay:.2f}s delay)")
        else:
            from cleo.geocode.client import MapboxClient
            if not MAPBOX_TOKEN:
                click.echo("MAPBOX_TOKEN not set. Add it to your .env file.", err=True)
                raise SystemExit(1)
            client = MapboxClient(MAPBOX_TOKEN)

    try:
        summary = run_geocode(
            provider=provider,
            store=store,
            client=client,
            dry_run=dry_run,
            limit=limit,
            batch_size=batch_size,
            delay=delay,
            cache=cache,
        )
    finally:
        if client and hasattr(client, "close"):
            client.close()

    click.echo(f"\nGeocode summary ({provider}):")
    click.echo(f"  Total in store:          {summary['total_in_store']:,}")
    click.echo(f"  Pending for {provider:>8s}:  {summary['pending_for_provider']:,}")
    click.echo(f"  To geocode:              {summary['to_geocode']:,}")
    if not dry_run and summary['to_geocode'] > 0:
        click.echo(f"  Geocoded:                {summary['geocoded']:,}")
        click.echo(f"    Successes:             {summary['successes']:,}")
        click.echo(f"    Failures:              {summary['failures']:,}")
        click.echo(f"  Batch API requests:      {summary['batch_requests']:,}")
        click.echo(f"  Elapsed:                 {summary['elapsed']:.1f}s")


def _gw_versioned_store():
    """Get the GW VersionedStore, or None if not set up."""
    from cleo.config import GW_PARSED_DIR
    from cleo.versioning import VersionedStore
    if not GW_PARSED_DIR.is_dir():
        return None
    return VersionedStore(base_dir=GW_PARSED_DIR)


@main.command()
@click.option("--status", "show_status", is_flag=True, help="Show property registry stats.")
@click.option("--dry-run", is_flag=True, help="Preview what would change without writing.")
@click.option("--apply-geocodes", is_flag=True, help="Backfill lat/lng from geocode cache into properties.")
@click.option("--refresh", is_flag=True, help="With --apply-geocodes: re-compute ALL coords using best multi-provider median.")
def properties(show_status: bool, dry_run: bool, apply_geocodes: bool, refresh: bool):
    """Build or update the canonical property registry.

    Scans all active parsed records, deduplicates by (address, city),
    assigns stable P-IDs, and saves to data/properties.json.

    Existing entries are preserved — RT ID lists are updated, manually
    added properties and edits are kept.

    \b
    Examples:
        cleo properties --status     # Show registry stats
        cleo properties --dry-run    # Preview without writing
        cleo properties              # Build/update the registry
    """
    from cleo.config import PROPERTIES_PATH
    from cleo.properties.registry import build_registry, save_registry, load_registry

    if show_status:
        reg = load_registry(PROPERTIES_PATH)
        meta = reg.get("meta", {})
        props = reg.get("properties", {})
        if not props:
            click.echo("No property registry found. Run 'cleo properties' to build it.")
            return
        click.echo(f"Property registry: {PROPERTIES_PATH}")
        click.echo(f"  Built:                {meta.get('built', 'unknown')}")
        click.echo(f"  Source:               {meta.get('source_dir', 'unknown')}")
        click.echo(f"  Total properties:     {meta.get('total_properties', len(props)):,}")
        click.echo(f"  Transactions linked:  {meta.get('total_transactions_linked', 0):,}")
        click.echo(f"  Multi-transaction:    {meta.get('multi_transaction_properties', 0):,}")
        sources = set()
        for p in props.values():
            sources.update(p.get("sources", []))
        click.echo(f"  Sources:              {', '.join(sorted(sources))}")
        return

    if apply_geocodes:
        from cleo.config import COORDINATES_PATH, GEOCODE_CACHE_PATH, EXTRACTED_DIR
        from cleo.properties.registry import load_registry, save_registry, backfill_geocodes

        if not PROPERTIES_PATH.exists():
            click.echo("No property registry found. Run 'cleo properties' first.", err=True)
            raise SystemExit(1)

        registry = load_registry(PROPERTIES_PATH)

        ext_active = None
        ext_store = extract_ver.store
        ext_active = ext_store.active_dir()

        # Use CoordinateStore if available, fall back to legacy cache
        coord_store = None
        if COORDINATES_PATH.exists():
            from cleo.geocode.store import CoordinateStore
            coord_store = CoordinateStore(COORDINATES_PATH)
            mode = "refresh all" if refresh else "backfill missing"
            click.echo(f"Applying geocode coordinates ({mode}) from coordinates.json...")
        elif GEOCODE_CACHE_PATH.exists():
            click.echo("Backfilling geocode coordinates from geocode_cache.json (legacy)...")
            if refresh:
                click.echo("  (--refresh requires coordinates.json, ignoring)", err=True)
        else:
            click.echo("No coordinate data found. Run 'cleo geocode --sync' first.", err=True)
            raise SystemExit(1)

        result = backfill_geocodes(
            registry=registry,
            cache_path=GEOCODE_CACHE_PATH if not coord_store else None,
            extracted_dir=ext_active,
            coord_store=coord_store,
            refresh_all=refresh and coord_store is not None,
        )

        click.echo(f"  Already had coords:  {result['already_had']:,}")
        click.echo(f"  Newly filled:        {result['updated']:,}")
        click.echo(f"  Refreshed (changed): {result.get('refreshed', 0):,}")
        click.echo(f"  No match:            {result['no_match']:,}")

        changed = result["updated"] + result.get("refreshed", 0)

        if changed > 0 and not dry_run:
            save_registry(registry, PROPERTIES_PATH)
            click.echo(f"\nSaved to {PROPERTIES_PATH}")
        elif dry_run:
            click.echo(f"\nDry run — no changes written.")
        else:
            click.echo(f"\nNo coordinate changes to apply.")

        # Run divergence report if using CoordinateStore
        if coord_store is not None:
            import json as _json
            divergences = coord_store.divergence_report(threshold_m=500)
            if divergences:
                report_path = DATA_DIR / "geocode_divergences.json"
                report_path.write_text(
                    _json.dumps(divergences, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                click.echo(f"\nProvider divergence report (>500m):")
                click.echo(f"  {len(divergences):,} addresses with provider disagreement")
                click.echo(f"  Worst: {divergences[0]['address'][:60]} ({divergences[0]['max_distance_m']:,.0f}m)")
                click.echo(f"  Saved to {report_path}")
            else:
                click.echo(f"\nNo provider divergences >500m found.")

        return

    act = active_dir()
    if act is None:
        click.echo("No active parse version. Run 'cleo parse --sandbox' then '--promote' first.", err=True)
        raise SystemExit(1)

    # Check for active extracted dir (enables compound address matching)
    ext_active = None
    ext_store = extract_ver.store
    ext_active = ext_store.active_dir()

    existing_path = PROPERTIES_PATH if PROPERTIES_PATH.exists() else None
    action = "Updating" if existing_path else "Building"
    click.echo(f"{action} property registry from {act.name}...")
    if ext_active:
        click.echo(f"  (with expanded address matching from {ext_active.name})")

    registry = build_registry(
        parsed_dir=act,
        existing_registry_path=existing_path,
        extracted_dir=ext_active,
    )
    meta = registry["meta"]

    click.echo(f"\n  Total properties:     {meta['total_properties']:,}")
    click.echo(f"  Transactions linked:  {meta['total_transactions_linked']:,}")
    click.echo(f"  Multi-transaction:    {meta['multi_transaction_properties']:,}")

    if dry_run:
        click.echo(f"\nDry run — no changes written.")
    else:
        save_registry(registry, PROPERTIES_PATH)
        click.echo(f"\nSaved to {PROPERTIES_PATH}")


@main.command()
@click.option("--status", "show_status", is_flag=True, help="Show party registry stats.")
@click.option("--dry-run", is_flag=True, help="Preview what would change without writing.")
def parties(show_status: bool, dry_run: bool):
    """Build or update the party group registry.

    Scans all active parsed records, clusters related companies by
    normalized name and address using union-find, assigns stable G-IDs,
    and saves to data/parties.json.

    Manual overrides (merges, display name overrides) are preserved
    on rebuild.

    \b
    Examples:
        cleo parties --status     # Show registry stats
        cleo parties --dry-run    # Preview without writing
        cleo parties              # Build/update the registry
    """
    from cleo.config import PARTIES_PATH
    from cleo.parties.registry import build_registry, save_registry, load_registry

    if show_status:
        reg = load_registry(PARTIES_PATH)
        meta = reg.get("meta", {})
        parties_data = reg.get("parties", {})
        if not parties_data:
            click.echo("No party registry found. Run 'cleo parties' to build it.")
            return
        click.echo(f"Party registry: {PARTIES_PATH}")
        click.echo(f"  Built:             {meta.get('built', 'unknown')}")
        click.echo(f"  Source:            {meta.get('source_dir', 'unknown')}")
        click.echo(f"  Total groups:      {meta.get('total_groups', len(parties_data)):,}")
        click.echo(f"  Company groups:    {meta.get('total_company_groups', 0):,}")
        click.echo(f"  Person groups:     {meta.get('total_person_groups', 0):,}")
        click.echo(f"  Total appearances: {meta.get('total_appearances', 0):,}")
        # Top parties by transaction count
        top = sorted(parties_data.values(), key=lambda p: p.get("transaction_count", 0), reverse=True)[:5]
        if top:
            click.echo(f"\n  Top parties:")
            for p in top:
                dn = p.get("display_name_override") or p.get("display_name", "")
                click.echo(f"    {p.get('transaction_count', 0):>4} txns  {dn}")
        return

    act = active_dir()
    if act is None:
        click.echo("No active parse version. Run 'cleo parse --sandbox' then '--promote' first.", err=True)
        raise SystemExit(1)

    existing_path = PARTIES_PATH if PARTIES_PATH.exists() else None
    action = "Updating" if existing_path else "Building"
    click.echo(f"{action} party registry from {act.name}...")

    registry = build_registry(parsed_dir=act, existing_registry_path=existing_path)
    meta = registry["meta"]

    click.echo(f"\n  Total groups:      {meta['total_groups']:,}")
    click.echo(f"  Company groups:    {meta['total_company_groups']:,}")
    click.echo(f"  Person groups:     {meta['total_person_groups']:,}")
    click.echo(f"  Total appearances: {meta['total_appearances']:,}")

    if dry_run:
        click.echo(f"\nDry run — no changes written.")
    else:
        save_registry(registry, PARTIES_PATH)
        click.echo(f"\nSaved to {PARTIES_PATH}")


@main.command("auto-confirm")
@click.option("--dry-run", is_flag=True, help="Preview what would be confirmed without writing.")
def auto_confirm_cmd(dry_run: bool):
    """Auto-confirm party names based on high-confidence signals.

    Rules applied:
    1. Single-name groups (the name IS the group — no ambiguity)
    2. Alias in transaction data matches group display name
    3. Names sharing a phone number within the group
    4. Names sharing a contact person within the group

    Rules 3-4 use transitivity: if A shares a phone with B, and B shares
    a contact with C, all three are confirmed.

    \b
    Examples:
        cleo auto-confirm --dry-run   # Preview what would be confirmed
        cleo auto-confirm             # Run auto-confirmation
    """
    from cleo.config import PARTIES_PATH
    from cleo.parties.registry import load_registry, save_registry
    from cleo.parties.auto_confirm import auto_confirm, apply_auto_confirm

    if not PARTIES_PATH.exists():
        click.echo("No party registry found. Run 'cleo parties' first.", err=True)
        raise SystemExit(1)

    act = active_dir()
    if act is None:
        click.echo("No active parse version.", err=True)
        raise SystemExit(1)

    reg = load_registry(PARTIES_PATH)
    parties_data = reg.get("parties", {})
    overrides = reg.get("overrides", {})

    # Current stats
    already = overrides.get("confirmed", {})
    already_groups = sum(1 for names in already.values() if names)
    already_names = sum(len(names) for names in already.values())

    click.echo(f"Currently confirmed: {already_groups:,} groups, {already_names:,} names")
    click.echo(f"Scanning {len(parties_data):,} groups against {act.name}...\n")

    confirmations = auto_confirm(parties_data, overrides, act)

    new_groups = len(confirmations)
    new_names = sum(len(norms) for norms in confirmations.values())

    # Count by rule type for reporting
    single_name_groups = {gid for gid, p in parties_data.items() if len(p.get("names", [])) == 1}
    single_count = sum(len(norms) for gid, norms in confirmations.items() if gid in single_name_groups)
    multi_count = new_names - single_count

    click.echo(f"Auto-confirmable:")
    click.echo(f"  Single-name groups:    {single_count:,} names")
    click.echo(f"  Multi-name (evidence): {multi_count:,} names")
    click.echo(f"  Total new:             {new_names:,} names in {new_groups:,} groups")
    click.echo(f"  Grand total after:     {already_names + new_names:,} names")

    if dry_run:
        click.echo(f"\nDry run — no changes written.")
        # Show some examples
        multi_examples = [(gid, norms) for gid, norms in confirmations.items() if gid not in single_name_groups]
        if multi_examples:
            click.echo(f"\nSample multi-name confirmations:")
            for gid, norms in multi_examples[:5]:
                p = parties_data[gid]
                dn = p.get("display_name_override") or p.get("display_name", "")
                total_names = len(p.get("names", []))
                click.echo(f"  {gid} {dn} — {len(norms)}/{total_names} names confirmed")
    else:
        count = apply_auto_confirm(reg, confirmations)
        save_registry(reg, PARTIES_PATH)
        click.echo(f"\nConfirmed {count:,} names. Saved to {PARTIES_PATH}")


@main.command()
@click.option("--port", default=8099, help="Port to run on.")
@click.option("--pipeline", is_flag=True, help="Open the pipeline inspector instead of the review app.")
def web(port: int, pipeline: bool):
    """Launch the review web app.

    Opens a browser with the three-column review interface:
    HTML source | Active (verified) | Sandbox (unverified)

    Use --pipeline to open the 4-column pipeline inspector:
    HTML Source | Parsed | Extracted | Geocoded
    """
    import uvicorn
    import webbrowser
    import threading

    page = "/pipeline" if pipeline else ""
    url = f"http://localhost:{port}{page}"
    label = "Pipeline Inspector" if pipeline else "Cleo Review"
    click.echo(f"Starting {label} at {url}")
    click.echo("Press Ctrl+C to stop.\n")

    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run("cleo.web.app:app", host="127.0.0.1", port=port, log_level="warning")


@main.command(name="parse-check")
@click.option("--use-sandbox", is_flag=True, help="Check sandbox instead of active version.")
def parse_check(use_sandbox: bool):
    """Run parse-level validation checks on parsed JSON.

    Scans every JSON file in the active version (or sandbox with
    --use-sandbox), runs parse-level quality checks, cross-references
    with HTML flags, and saves results to data/parse_flags.json.
    """
    if use_sandbox:
        sb = sandbox_path()
        if not sb.is_dir():
            click.echo("No sandbox found. Run 'cleo parse --sandbox' first.", err=True)
            raise SystemExit(1)
        target_dir = sb
        label = "sandbox"
    else:
        act = active_dir()
        if act is None:
            click.echo("No active version. Run 'cleo parse --sandbox' then '--promote' first.", err=True)
            raise SystemExit(1)
        target_dir = act
        label = active_version()

    click.echo(f"Running parse-level checks on {label}...\n")

    flags_by_rt, summary = run_parse_checks(target_dir)
    save_parse_flags(flags_by_rt)

    total_files = len(flags_by_rt)
    flagged_count = sum(1 for flags in flags_by_rt.values() if flags)
    clean_count = total_files - flagged_count

    # Summary table
    click.echo(f"Checked {total_files:,} parsed records\n")
    for flag_id in sorted(PARSE_FLAG_DEFS):
        count = summary.get(flag_id, 0)
        name = PARSE_FLAG_DEFS[flag_id]
        marker = f"  <- {count:,} to review" if count > 0 else ""
        click.echo(f"  {flag_id}  {name:<55s}  {count:>6,}{marker}")

    click.echo(f"\nClean:   {clean_count:,} / {total_files:,} ({100*clean_count/total_files:.1f}%)")
    click.echo(f"Flagged: {flagged_count:,} / {total_files:,}")

    # Cross-reference with HTML flags (informational only)
    html_flags = load_flags()
    if html_flags:
        xref = cross_reference_html_flags(
            {rt: f for rt, f in flags_by_rt.items() if f},
            html_flags,
        )
        html_also = sum(1 for v in xref.values() if v["html_also_flagged"])
        html_clean = sum(1 for v in xref.values() if not v["html_also_flagged"])
        click.echo(f"\nCross-reference with HTML flags:")
        click.echo(f"  HTML also flagged:  {html_also:>6,}  (source may have issues)")
        click.echo(f"  HTML clean:         {html_clean:>6,}  (source looks good)")

    click.echo(f"\nSaved to {PARSE_FLAGS_PATH}")


@main.command()
def validate():
    """Run HTML validation checks on all local HTML files.

    Scans every file in data/html/, runs the 9 baseline checks against
    the raw HTML, and saves results to data/html_flags.json.
    """
    click.echo("Running HTML validation checks...\n")

    flags_by_rt, summary = run_all_checks()
    save_flags(flags_by_rt)

    total_files = len(flags_by_rt)
    flagged_count = sum(1 for flags in flags_by_rt.values() if flags)
    clean_count = total_files - flagged_count

    # Print summary table
    click.echo(f"Scanned {total_files:,} HTML files\n")
    for flag_id in sorted(FLAG_DEFS):
        count = summary.get(flag_id, 0)
        name = FLAG_DEFS[flag_id]
        marker = f"  ← {count:,} to review" if count > 0 else ""
        click.echo(f"  {flag_id}  {name:<55s}  {count:>6,}{marker}")

    click.echo(f"\nClean:   {clean_count:,} / {total_files:,} ({100*clean_count/total_files:.1f}%)")
    click.echo(f"Flagged: {flagged_count:,} / {total_files:,}")

    # Cross-reference with determinations
    determinations = load_determinations()
    if determinations:
        determined_count = sum(
            1 for rt_id in flags_by_rt
            if flags_by_rt[rt_id] and rt_id in determinations
        )
        unreviewed = flagged_count - determined_count
        click.echo(f"\nDetermined:  {determined_count:,} (reviewed)")
        click.echo(f"Unreviewed:  {unreviewed:,}")

    click.echo(f"\nSaved to {HTML_FLAGS_PATH}")


@main.command()
@click.option("--flag", default=None, help="Filter to a specific flag ID (e.g. H003).")
def review(flag: str):
    """Interactively review flagged HTML records.

    Shows each flagged record with the raw HTML source alongside the flag
    that fired. For each record, decide: [b]ad_source or [s]kip.
    """
    flags_by_rt = load_flags()
    determinations = load_determinations()

    if not flags_by_rt:
        click.echo("No flags found. Run 'cleo validate' first.")
        return

    # Build list of unreviewed flagged records
    to_review = []
    for rt_id, flags in sorted(flags_by_rt.items()):
        if not flags:
            continue
        if rt_id in determinations:
            continue
        if flag and flag not in flags:
            continue
        to_review.append((rt_id, flags))

    if not to_review:
        click.echo("All flagged records have been reviewed!")
        return

    total_flagged = sum(1 for f in flags_by_rt.values() if f)
    click.echo(
        f"{len(to_review)} unreviewed flagged records "
        f"({total_flagged} total flagged, "
        f"{len(determinations)} determined)\n"
    )

    reviewed_this_session = 0

    for rt_id, flags in to_review:
        click.echo(f"{'─' * 60}")
        click.echo(f"  {rt_id}  ──  Flags: {', '.join(flags)}")
        click.echo(f"{'─' * 60}")

        # Show the relevant HTML snippet
        html_path = HtmlIndex().resolve(rt_id)
        if html_path.exists():
            _show_html_snippet(html_path)
        else:
            click.echo(f"  [HTML file not found: {html_path}]")

        click.echo()
        choice = click.prompt(
            "  [b]ad_source  [s]kip  [q]uit",
            type=click.Choice(["b", "s", "q"], case_sensitive=False),
            show_choices=False,
        )

        if choice == "q":
            break
        elif choice == "b":
            reason = click.prompt("  Reason", default="", show_default=False)
            determinations[rt_id] = {
                "determination": "bad_source",
                "flags": flags,
                "reason": reason,
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
            save_determinations(determinations)
            reviewed_this_session += 1
            click.echo(f"  ✓ Marked as bad_source\n")
        elif choice == "s":
            click.echo(f"  Skipped\n")

    click.echo(f"\nReviewed {reviewed_this_session} records this session.")
    click.echo(f"Total determinations: {len(determinations)}")


def _clear_sandbox_accepted():
    """Remove sandbox_accepted flags from reviews after promotion."""
    reviews_path = DATA_DIR / "reviews.json"
    if not reviews_path.exists():
        return
    reviews = json.loads(reviews_path.read_text(encoding="utf-8"))
    changed = False
    for r in reviews.values():
        if "sandbox_accepted" in r:
            del r["sandbox_accepted"]
            changed = True
    if changed:
        with open(reviews_path, "w", encoding="utf-8") as f:
            json.dump(reviews, f, indent=2, sort_keys=True)


def _clear_extract_sandbox_accepted():
    """Remove sandbox_accepted flags from extraction reviews after promotion."""
    from cleo.config import EXTRACT_REVIEWS_PATH
    if not EXTRACT_REVIEWS_PATH.exists():
        return
    reviews = json.loads(EXTRACT_REVIEWS_PATH.read_text(encoding="utf-8"))
    changed = False
    for r in reviews.values():
        if "sandbox_accepted" in r:
            del r["sandbox_accepted"]
            changed = True
    if changed:
        with open(EXTRACT_REVIEWS_PATH, "w", encoding="utf-8") as f:
            json.dump(reviews, f, indent=2, sort_keys=True)


def _show_html_snippet(html_path):
    """Display the key HTML sections for review."""
    from bs4 import BeautifulSoup

    html = html_path.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    # Address
    addr_tag = soup.find("strong", id="address")
    if addr_tag:
        lines = [line.strip() for line in addr_tag.stripped_strings]
        click.echo(f"\n  ADDRESS TAG:")
        for line in lines:
            click.echo(f"    {line}")

        # Header line (city, date, price)
        header_parts = []
        for sibling in addr_tag.next_siblings:
            if getattr(sibling, "name", None) == "p":
                break
            text = sibling.get_text() if hasattr(sibling, "get_text") else str(sibling)
            text = text.strip()
            if text:
                header_parts.append(text)
        if header_parts:
            click.echo(f"\n  HEADER LINE:")
            click.echo(f"    {' | '.join(header_parts)}")
    else:
        click.echo(f"\n  ADDRESS TAG: [NOT FOUND]")

    # Transferor
    click.echo()
    for font in soup.find_all("font", color="#848484"):
        text = font.get_text()
        if "Transferor" in text:
            # Get text until next section
            seller_parts = []
            for sib in font.next_siblings:
                if getattr(sib, "name", None) == "p":
                    break
                t = sib.get_text() if hasattr(sib, "get_text") else str(sib)
                t = t.strip()
                if t:
                    seller_parts.append(t)
            click.echo(f"  TRANSFEROR: {' '.join(seller_parts)[:80]}")
            break

    # Transferee
    for font in soup.find_all("font", color="#848484"):
        text = font.get_text()
        if "Transferee" in text:
            buyer_parts = []
            for sib in font.next_siblings:
                if getattr(sib, "name", None) == "p":
                    break
                t = sib.get_text() if hasattr(sib, "get_text") else str(sib)
                t = t.strip()
                if t:
                    buyer_parts.append(t)
            click.echo(f"  TRANSFEREE: {' '.join(buyer_parts)[:80]}")
            break

    # RT ID
    gray_fonts = soup.find_all("font", color="#848484")
    if gray_fonts:
        last = gray_fonts[-1].get_text().strip()
        click.echo(f"  RT ID LINE: {last}")


@main.command()
@click.argument("rt_id", required=False)
@click.option("--flagged", is_flag=True, help="Walk through parse-flagged records.")
@click.option("--flag", default=None, help="Filter to a specific parse flag (e.g. P004).")
@click.option("--random", "show_random", is_flag=True, help="Show a random clean record for spot-checking.")
def inspect(rt_id: str, flagged: bool, flag: str, show_random: bool):
    """Inspect parsed data alongside HTML source.

    View a single record by RT ID, or walk through flagged records
    for manual review.

    \b
    Examples:
        cleo inspect RT100008          # Single record
        cleo inspect --flagged         # Walk parse-flagged records
        cleo inspect --flag P004       # Only records with specific flag
        cleo inspect --random          # Spot-check a random clean record
    """
    import json
    import random as rand_mod

    act = active_dir()
    if act is None:
        click.echo("No active version. Run 'cleo parse --sandbox' then '--promote' first.", err=True)
        raise SystemExit(1)

    if rt_id:
        _inspect_one(rt_id, act)
        return

    if show_random:
        json_files = [f for f in act.glob("*.json") if f.stem != "_meta"]
        parse_flags = load_parse_flags()
        clean = [f for f in json_files if f.stem not in parse_flags]
        if not clean:
            click.echo("No clean records found.")
            return
        chosen = rand_mod.choice(clean)
        _inspect_one(chosen.stem, act)
        return

    if flagged or flag:
        parse_flags = load_parse_flags()
        html_flags = load_flags()

        if not parse_flags:
            click.echo("No parse flags found. Run 'cleo parse-check' first.")
            return

        to_review = []
        for rid, flags in sorted(parse_flags.items()):
            if not flags:
                continue
            if flag and flag not in flags:
                continue
            to_review.append((rid, flags))

        if not to_review:
            click.echo("No matching flagged records.")
            return

        click.echo(f"{len(to_review)} flagged records to inspect\n")

        for i, (rid, flags) in enumerate(to_review):
            h_flags = html_flags.get(rid, [])
            click.echo(f"{'=' * 70}")
            click.echo(f"  [{i+1}/{len(to_review)}]  {rid}")
            click.echo(f"  Parse flags: {', '.join(flags)}")
            if h_flags:
                click.echo(f"  HTML flags:  {', '.join(h_flags)}  (source may have issues)")
            click.echo(f"{'=' * 70}")

            _inspect_one(rid, act, show_header=False)

            click.echo()
            choice = click.prompt(
                "  [n]ext  [q]uit",
                type=click.Choice(["n", "q"], case_sensitive=False),
                default="n",
                show_choices=False,
            )
            if choice == "q":
                break
            click.echo()

        return

    click.echo("Specify an RT ID, or use --flagged / --random.")


def _inspect_one(rt_id: str, json_dir, show_header: bool = True):
    """Display parsed data and HTML snippet for one record."""
    import json

    json_path = json_dir / f"{rt_id}.json"
    if not json_path.exists():
        click.echo(f"  No parsed JSON for {rt_id}")
        return

    data = json.loads(json_path.read_text(encoding="utf-8"))

    if show_header:
        parse_flags = load_parse_flags()
        html_flags = load_flags()
        p_flags = parse_flags.get(rt_id, [])
        h_flags = html_flags.get(rt_id, [])
        click.echo(f"{'=' * 70}")
        click.echo(f"  {rt_id}")
        if p_flags:
            click.echo(f"  Parse flags: {', '.join(p_flags)}")
        if h_flags:
            click.echo(f"  HTML flags:  {', '.join(h_flags)}")
        if not p_flags and not h_flags:
            click.echo(f"  Flags: (clean)")
        click.echo(f"{'=' * 70}")

    t = data.get("transaction", {})
    addr = t.get("address", {})

    # Parsed data summary
    click.echo(f"\n  PARSED DATA:")
    click.echo(f"    Address:      {addr.get('address', '')}")
    if addr.get("address_suite"):
        click.echo(f"    Suite:        {addr['address_suite']}")
    click.echo(f"    City:         {addr.get('city', '')}")
    click.echo(f"    Municipality: {addr.get('municipality', '')}")
    click.echo(f"    Sale Date:    {t.get('sale_date', '')}")
    click.echo(f"    Sale Price:   {t.get('sale_price', '')}")
    click.echo(f"    RT Number:    {t.get('rt_number', '')}")

    xferor = data.get("transferor", {})
    click.echo(f"    Seller:       {xferor.get('name', '')}")
    if xferor.get("contact"):
        click.echo(f"    Seller Contact: {xferor['contact']}")
    if xferor.get("phone"):
        click.echo(f"    Seller Phone: {xferor['phone']}")
    if xferor.get("address"):
        click.echo(f"    Seller Addr:  {xferor['address']}")

    xferee = data.get("transferee", {})
    click.echo(f"    Buyer:        {xferee.get('name', '')}")
    if xferee.get("contact"):
        click.echo(f"    Buyer Contact: {xferee['contact']}")
    if xferee.get("phone"):
        click.echo(f"    Buyer Phone:  {xferee['phone']}")
    if xferee.get("address"):
        click.echo(f"    Buyer Addr:   {xferee['address']}")

    desc = data.get("description", "")
    if desc:
        click.echo(f"    Description:  {desc[:100]}{'...' if len(desc) > 100 else ''}")

    photos = data.get("photos", [])
    if photos:
        click.echo(f"    Photos:       {len(photos)}")

    # HTML source snippet
    html_path = HtmlIndex().resolve(rt_id)
    if html_path.exists():
        click.echo(f"\n  HTML SOURCE:")
        _show_html_snippet(html_path)
    else:
        click.echo(f"\n  HTML SOURCE: [file not found]")


# ---------------------------------------------------------------------------
# GeoWarehouse commands
# ---------------------------------------------------------------------------

@main.command(name="gw-ingest")
@click.option("--source-dir", default=None, type=click.Path(exists=True, file_okay=False),
              help="Source directory of GW HTML files (default: ~/Downloads/GeoWarehouse/gw-ingest-data).")
@click.option("--dry-run", is_flag=True, help="Show what would be copied without copying.")
def gw_ingest_cmd(source_dir: str, dry_run: bool):
    """Copy GeoWarehouse HTML files into data/gw_html/.

    Reads browser-extension-saved HTML files from the source directory
    and copies geowarehouse-* files (property detail pages) into the
    local data store. Skips collaboration-* and other prefixes.

    \b
    Examples:
        cleo gw-ingest --dry-run     # Preview what would be copied
        cleo gw-ingest               # Copy files
    """
    from pathlib import Path as P
    from cleo.config import GW_SOURCE_DIR, GW_HTML_DIR
    from cleo.geowarehouse.ingest import ingest_files

    src = P(source_dir) if source_dir else GW_SOURCE_DIR

    label = "Dry run: " if dry_run else ""
    click.echo(f"{label}Ingesting GW files from {src} → {GW_HTML_DIR}\n")

    try:
        stats = ingest_files(src, GW_HTML_DIR, dry_run=dry_run)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"  Total HTML files found:  {stats['total_found']:,}")
    click.echo(f"  GW detail pages:         {stats['gw_detail']:,}")
    click.echo(f"  Skipped (non-GW):        {stats['skipped']:,}")
    click.echo(f"  Already present:         {stats['already_present']:,}")
    verb = "Would copy" if dry_run else "Copied"
    click.echo(f"  {verb}:                  {stats['copied']:,}")


@main.command(name="gw-parse")
@click.option("--sandbox", "action", flag_value="sandbox", help="Parse all GW HTML → sandbox.")
@click.option("--diff", "action", flag_value="diff", help="Compare sandbox vs active.")
@click.option("--promote", "action", flag_value="promote", help="Promote sandbox → next version.")
@click.option("--discard", "action", flag_value="discard", help="Delete sandbox.")
@click.option("--rollback-to", "rollback_version", default=None, help="Point active to a specific version.")
@click.option("--status", "action", flag_value="status", help="Show current version info.")
@click.option("--force", is_flag=True, help="Force promote even with regressions.")
def gw_parse_cmd(action: str, rollback_version: str, force: bool):
    """Manage GeoWarehouse parsed JSON with versioned snapshots.

    Parse GW HTML into a sandbox, diff against the current active version,
    then promote or discard.

    \b
    Examples:
        cleo gw-parse --sandbox      # Parse all GW HTML → sandbox
        cleo gw-parse --diff         # Compare sandbox vs active
        cleo gw-parse --status       # Show version info
        cleo gw-parse --promote      # Promote sandbox → v001
        cleo gw-parse --discard      # Delete sandbox
    """
    from cleo.config import GW_HTML_DIR, GW_PARSED_DIR
    from cleo.versioning import VersionedStore
    from cleo.geowarehouse.engine import run_parse

    store = VersionedStore(
        base_dir=GW_PARSED_DIR,
        volatile_fields={"gw_source_file"},
    )

    if rollback_version:
        action = "rollback"

    if not action:
        click.echo("Specify one of: --sandbox, --diff, --promote, --discard, --rollback-to, --status")
        raise SystemExit(1)

    if action == "status":
        ver = store.active_version()
        versions = store.list_versions()
        has_sandbox = store.sandbox_exists()
        click.echo(f"Active version:  {ver or '(none)'}")
        click.echo(f"All versions:    {', '.join(versions) or '(none)'}")
        click.echo(f"Sandbox:         {'exists' if has_sandbox else '(none)'}")

    elif action == "sandbox":
        if store.sandbox_exists():
            click.echo("Sandbox already exists. Use --discard first.", err=True)
            raise SystemExit(1)

        if not GW_HTML_DIR.is_dir() or not any(GW_HTML_DIR.glob("*.html")):
            click.echo("No GW HTML files found. Run 'cleo gw-ingest' first.", err=True)
            raise SystemExit(1)

        sb = store.ensure_sandbox()
        click.echo(f"Parsing GW HTML files → {sb}\n")

        summary = run_parse(html_dir=GW_HTML_DIR, output_dir=sb)

        click.echo(f"\n  Total HTML files:  {summary['total_html']:,}")
        click.echo(f"  Parsed (unique):   {summary['parsed']:,}")
        click.echo(f"  Skipped:           {summary['skipped']:,}")
        click.echo(f"  Duplicates:        {summary['duplicates']:,}")
        click.echo(f"  Errors:            {summary['errors']:,}")
        click.echo(f"  Elapsed:           {summary['elapsed']}s")

        if summary["error_files"]:
            click.echo(f"\n  Error files:")
            for f in summary["error_files"][:10]:
                click.echo(f"    {f}")
            if len(summary["error_files"]) > 10:
                click.echo(f"    ... and {len(summary['error_files']) - 10} more")

    elif action == "diff":
        try:
            diff_result = store.diff_sandbox_vs_active()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(format_diff_report(diff_result))

    elif action == "promote":
        if store.active_dir() and store.sandbox_exists() and not force:
            try:
                diff_result = store.diff_sandbox_vs_active()
                regressions = diff_result.get("regressions", [])
                if regressions:
                    click.echo(f"\nBLOCKED: {len(regressions)} record(s) would regress:\n")
                    for r in regressions[:10]:
                        fields = ", ".join(r["changed_fields"][:5])
                        click.echo(f"  {r['rt_id']}  ->  {fields}")
                    if len(regressions) > 10:
                        click.echo(f"  ... and {len(regressions) - 10} more")
                    click.echo(f"\nUse --force to override.")
                    raise SystemExit(1)
            except FileNotFoundError:
                pass
        try:
            version = store.promote()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(f"Promoted to {version}")

    elif action == "discard":
        if store.discard_sandbox():
            click.echo("Sandbox discarded.")
        else:
            click.echo("No sandbox to discard.")

    elif action == "rollback":
        try:
            store.rollback(rollback_version)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(f"Active -> {rollback_version}")


@main.command(name="gw-match")
@click.option("--status", "show_status", is_flag=True, help="Show current GW match stats.")
@click.option("--dry-run", is_flag=True, help="Preview matches without applying.")
def gw_match_cmd(show_status: bool, dry_run: bool):
    """Match GeoWarehouse records to the property registry.

    Parses MPAC addresses from GW records, creates dedup keys using
    existing normalization, and matches against the property registry.
    Matched properties are enriched with GW data. Unmatched GW records
    become new properties.

    \b
    Examples:
        cleo gw-match --status     # Show current GW match stats
        cleo gw-match --dry-run    # Preview matches without writing
        cleo gw-match              # Apply matches to properties.json
    """
    from cleo.config import GW_PARSED_DIR, PROPERTIES_PATH
    from cleo.versioning import VersionedStore
    from cleo.properties.registry import load_registry, save_registry
    from cleo.geowarehouse.match import match_gw_to_registry, apply_matches

    if show_status:
        reg = load_registry(PROPERTIES_PATH)
        props = reg.get("properties", {})
        with_gw = sum(1 for p in props.values() if p.get("gw_ids"))
        total_gw_links = sum(len(p.get("gw_ids", [])) for p in props.values())
        gw_only = sum(1 for p in props.values() if p.get("sources") == ["gw"])
        with_postal = sum(1 for p in props.values() if p.get("gw_ids") and p.get("postal_code"))
        click.echo(f"GW Match Status:")
        click.echo(f"  Properties with GW data:   {with_gw:,}")
        click.echo(f"  Total GW links:            {total_gw_links:,}")
        click.echo(f"  GW-only properties:        {gw_only:,}")
        click.echo(f"  With postal code:          {with_postal:,}")
        return

    # Find GW active dir
    store = VersionedStore(base_dir=GW_PARSED_DIR)
    gw_dir = store.active_dir()
    if gw_dir is None:
        click.echo("No active GW version. Run 'cleo gw-parse --sandbox' and promote first.", err=True)
        raise SystemExit(1)

    if not PROPERTIES_PATH.exists():
        click.echo("No property registry found. Run 'cleo properties' first.", err=True)
        raise SystemExit(1)

    reg = load_registry(PROPERTIES_PATH)
    click.echo(f"Matching GW records from {gw_dir.name} against property registry...\n")

    result = match_gw_to_registry(gw_dir, reg)
    stats = result["stats"]

    click.echo(f"  Total GW records:    {stats['total_gw']:,}")
    click.echo(f"  Matched:             {stats['matched']:,}")
    click.echo(f"  Unmatched:           {stats['unmatched']:,}")

    # Show sample matches
    if result["matched"]:
        click.echo(f"\n  Sample matches:")
        for m in result["matched"][:5]:
            click.echo(f"    {m['gw_id']} → {m['prop_id']}  ({m['street']}, {m['city']})")
        if len(result["matched"]) > 5:
            click.echo(f"    ... and {len(result['matched']) - 5} more")

    # Show sample unmatched
    if result["unmatched"]:
        click.echo(f"\n  Sample unmatched:")
        for u in result["unmatched"][:5]:
            click.echo(f"    {u['gw_id']}  ({u['street']}, {u['city']})")
        if len(result["unmatched"]) > 5:
            click.echo(f"    ... and {len(result['unmatched']) - 5} more")

    if dry_run:
        click.echo("\nDry run — no changes written.")
        return

    # Apply matches
    apply_result = apply_matches(reg, result, gw_dir)
    save_registry(reg, PROPERTIES_PATH)

    click.echo(f"\n  Enriched:            {apply_result['enriched']:,}")
    click.echo(f"  New properties:      {apply_result['created']:,}")
    click.echo(f"  Postal codes filled: {apply_result['postal_filled']:,}")
    click.echo(f"\n  Saved to {PROPERTIES_PATH}")


@main.command(name="gw-inspect")
@click.argument("gw_id")
def gw_inspect_cmd(gw_id: str):
    """Inspect a single GeoWarehouse parsed record.

    Prints the full JSON for the given GW ID (e.g. GW00001).

    \b
    Examples:
        cleo gw-inspect GW00001
    """
    from cleo.config import GW_PARSED_DIR
    from cleo.versioning import VersionedStore

    store = VersionedStore(base_dir=GW_PARSED_DIR)
    act = store.active_dir()

    # Try active first, fall back to sandbox
    target = act
    label = store.active_version() or ""
    if target is None:
        sb = store.sandbox_path()
        if sb.is_dir():
            target = sb
            label = "sandbox"

    if target is None:
        click.echo("No active version or sandbox. Run 'cleo gw-parse --sandbox' first.", err=True)
        raise SystemExit(1)

    # Normalize the ID
    gw_id_upper = gw_id.upper()
    json_path = target / f"{gw_id_upper}.json"

    if not json_path.exists():
        click.echo(f"No record found for {gw_id_upper} in {label}.", err=True)
        raise SystemExit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Operator commands
# ---------------------------------------------------------------------------

@main.command(name="op-config")
@click.option("--add", "action", flag_value="add", help="Add a new operator.")
@click.option("--list", "action", flag_value="list", help="List configured operators.")
@click.option("--remove", "action", flag_value="remove", help="Remove an operator by slug.")
@click.option("--name", default=None, help="Operator display name.")
@click.option("--url", default=None, help="Operator website URL.")
@click.option("--slug", default=None, help="Operator slug (auto-generated from name if omitted).")
def op_config_cmd(action: str, name: str, url: str, slug: str):
    """Manage the operator configuration list.

    \b
    Examples:
        cleo op-config --list
        cleo op-config --add --name "RioCan REIT" --url https://www.riocan.com
        cleo op-config --remove --slug riocan
    """
    import re
    from cleo.config import OPERATORS_CONFIG_PATH

    if not action:
        click.echo("Specify --add, --list, or --remove")
        raise SystemExit(1)

    # Load existing config
    if OPERATORS_CONFIG_PATH.exists():
        config = json.loads(OPERATORS_CONFIG_PATH.read_text(encoding="utf-8"))
    else:
        config = []

    if action == "list":
        if not config:
            click.echo("No operators configured. Use --add to add one.")
            return
        click.echo(f"{'Slug':<30} {'Name':<40} {'Enabled':<8} URL")
        click.echo("-" * 110)
        for op in config:
            enabled = "yes" if op.get("enabled", True) else "no"
            click.echo(f"{op['slug']:<30} {op['name']:<40} {enabled:<8} {op['url']}")
        click.echo(f"\n{len(config)} operators configured")

    elif action == "add":
        if not name or not url:
            click.echo("--name and --url are required with --add", err=True)
            raise SystemExit(1)
        if not slug:
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        # Check for duplicates
        existing_slugs = {op["slug"] for op in config}
        if slug in existing_slugs:
            click.echo(f"Operator '{slug}' already exists.", err=True)
            raise SystemExit(1)
        config.append({
            "slug": slug,
            "name": name,
            "url": url,
            "enabled": True,
        })
        OPERATORS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        OPERATORS_CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        click.echo(f"Added operator: {slug} ({name})")

    elif action == "remove":
        if not slug:
            click.echo("--slug is required with --remove", err=True)
            raise SystemExit(1)
        before = len(config)
        config = [op for op in config if op["slug"] != slug]
        if len(config) == before:
            click.echo(f"No operator with slug '{slug}' found.", err=True)
            raise SystemExit(1)
        OPERATORS_CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        click.echo(f"Removed operator: {slug}")


@main.command(name="op-crawl")
@click.option("--slug", default=None, help="Crawl a specific operator by slug.")
@click.option("--all", "crawl_all", is_flag=True, help="Crawl all enabled operators.")
@click.option("--max-pages", type=int, default=100, help="Max pages per site.")
@click.option("--delay", type=float, default=1.0, help="Seconds between requests.")
def op_crawl_cmd(slug: str, crawl_all: bool, max_pages: int, delay: float):
    """Crawl operator websites and save HTML pages.

    \b
    Examples:
        cleo op-crawl --slug riocan
        cleo op-crawl --all
        cleo op-crawl --slug riocan --max-pages 50
    """
    from cleo.config import OPERATORS_CONFIG_PATH, OPERATORS_CRAWL_DIR
    from cleo.operators.crawler import crawl_site

    if not slug and not crawl_all:
        click.echo("Specify --slug or --all", err=True)
        raise SystemExit(1)

    if not OPERATORS_CONFIG_PATH.exists():
        click.echo("No operators configured. Use 'cleo op-config --add' first.", err=True)
        raise SystemExit(1)

    config = json.loads(OPERATORS_CONFIG_PATH.read_text(encoding="utf-8"))

    if slug:
        ops = [op for op in config if op["slug"] == slug]
        if not ops:
            click.echo(f"No operator with slug '{slug}' found.", err=True)
            raise SystemExit(1)
    else:
        ops = [op for op in config if op.get("enabled", True)]

    for op in ops:
        output_dir = OPERATORS_CRAWL_DIR / op["slug"] / "html"
        click.echo(f"\nCrawling {op['name']} ({op['url']})")
        click.echo(f"  Output: {output_dir}")

        summary = crawl_site(
            base_url=op["url"],
            output_dir=output_dir,
            max_pages=max_pages,
            delay=delay,
        )

        click.echo(f"  Saved:    {summary['saved']}")
        click.echo(f"  Visited:  {summary['visited']}")
        click.echo(f"  Errors:   {summary['errors']}")
        click.echo(f"  Skipped:  {summary['skipped']}")
        if summary["queued_remaining"]:
            click.echo(f"  Queued (not crawled): {summary['queued_remaining']}")


@main.command(name="op-extract")
@click.option("--sandbox", "action", flag_value="sandbox", help="Extract from crawled pages → sandbox.")
@click.option("--diff", "action", flag_value="diff", help="Compare sandbox vs active.")
@click.option("--promote", "action", flag_value="promote", help="Promote sandbox → next version.")
@click.option("--discard", "action", flag_value="discard", help="Delete sandbox.")
@click.option("--status", "action", flag_value="status", help="Show extraction version info.")
@click.option("--model", default="claude-haiku-4-5-20251001", help="Claude model for extraction.")
@click.option("--slug", default=None, help="Extract a single operator only.")
@click.option("--force", is_flag=True, help="Force promote.")
def op_extract_cmd(action: str, model: str, slug: str, force: bool):
    """AI-powered extraction from crawled operator websites.

    Uses Claude to classify pages and extract structured data
    (contacts, properties, photos, tenant lists).

    \b
    Examples:
        cleo op-extract --sandbox
        cleo op-extract --sandbox --slug riocan
        cleo op-extract --diff
        cleo op-extract --promote
        cleo op-extract --status
    """
    from cleo.operators.engine import store, run_extraction

    if not action:
        click.echo("Specify one of: --sandbox, --diff, --promote, --discard, --status")
        raise SystemExit(1)

    if action == "status":
        ver = store.active_version()
        versions = store.list_versions()
        has_sandbox = store.sandbox_exists()
        click.echo(f"Active version:  {ver or '(none)'}")
        click.echo(f"All versions:    {', '.join(versions) or '(none)'}")
        click.echo(f"Sandbox:         {'exists' if has_sandbox else '(none)'}")

    elif action == "sandbox":
        if store.sandbox_exists():
            click.echo("Sandbox already exists. Use --discard first.", err=True)
            raise SystemExit(1)

        # Suppress noisy httpx/anthropic retry logs — the SDK handles 429s internally
        import logging as _logging
        _logging.getLogger("httpx").setLevel(_logging.WARNING)
        _logging.getLogger("anthropic").setLevel(_logging.WARNING)

        sb = store.ensure_sandbox()
        click.echo(f"Extracting operator data → {sb}\n")

        try:
            summary = run_extraction(output_dir=sb, model=model, slug_filter=slug)
        except ValueError as e:
            store.discard_sandbox()
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)

        click.echo(f"\n  Operators processed:  {summary['total_operators']}")
        click.echo(f"  Extracted:            {summary['extracted_operators']}")
        click.echo(f"  Total pages scanned:  {summary['total_pages']}")
        click.echo(f"  Relevant pages:       {summary['relevant_pages']}")
        click.echo(f"  Errors:               {summary['errors']}")

    elif action == "diff":
        try:
            diff_result = store.diff_sandbox_vs_active()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(format_diff_report(diff_result))

    elif action == "promote":
        try:
            version = store.promote()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            raise SystemExit(1)
        click.echo(f"Promoted to {version}")

    elif action == "discard":
        if store.discard_sandbox():
            click.echo("Sandbox discarded.")
        else:
            click.echo("No sandbox to discard.")


@main.command(name="op-match")
@click.option("--status", "show_status", is_flag=True, help="Show current match stats.")
@click.option("--dry-run", is_flag=True, help="Preview matches without writing.")
def op_match_cmd(show_status: bool, dry_run: bool):
    """Match extracted operator data against property and party registries.

    \b
    Examples:
        cleo op-match --dry-run
        cleo op-match --status
        cleo op-match
    """
    from cleo.operators.engine import store
    from cleo.operators.match import run_matching
    from cleo.operators.registry import load_registry, save_registry, build_registry

    if show_status:
        reg = load_registry()
        operators = reg.get("operators", {})
        if not operators:
            click.echo("No operator registry. Run 'cleo op-match' first.")
            return
        total_prop_matches = 0
        total_prop_confirmed = 0
        total_party_matches = 0
        total_party_confirmed = 0
        for op in operators.values():
            for m in op.get("property_matches", []):
                if m.get("status") == "pending":
                    total_prop_matches += 1
                elif m.get("status") == "confirmed":
                    total_prop_confirmed += 1
            for m in op.get("party_matches", []):
                if m.get("status") == "pending":
                    total_party_matches += 1
                elif m.get("status") == "confirmed":
                    total_party_confirmed += 1
        click.echo(f"Operator registry: {len(operators)} operators")
        click.echo(f"  Property matches pending:   {total_prop_matches}")
        click.echo(f"  Property matches confirmed: {total_prop_confirmed}")
        click.echo(f"  Party matches pending:      {total_party_matches}")
        click.echo(f"  Party matches confirmed:    {total_party_confirmed}")
        return

    ext_active = store.active_dir()
    if ext_active is None:
        click.echo("No active operator extraction. Run 'cleo op-extract --sandbox' then '--promote' first.", err=True)
        raise SystemExit(1)

    click.echo(f"Matching operators from {ext_active.name} against registries...\n")

    match_results = run_matching(ext_active)

    click.echo(f"  Operators:          {match_results['total_operators']}")
    click.echo(f"  Property matches:   {match_results['total_property_matches']}")
    click.echo(f"  Party matches:      {match_results['total_party_matches']}")

    # Show samples
    for slug, result in list(match_results["results"].items())[:5]:
        pending_props = [m for m in result["property_matches"] if m.get("status") == "pending"]
        party_matches = result["party_matches"]
        if pending_props or party_matches:
            click.echo(f"\n  {slug} ({result['name']}):")
            for m in pending_props[:3]:
                click.echo(f"    Property: {m['extracted_address']}, {m['extracted_city']} -> {m.get('prop_id', 'no match')} ({m['confidence']:.2f})")
            for m in party_matches[:2]:
                click.echo(f"    Party: {m['party_display_name']} ({m['match_type']}, {m['confidence']:.2f})")

    if dry_run:
        click.echo("\nDry run — no changes written.")
        return

    # Build and save registry
    registry = build_registry(match_results, ext_active)
    save_registry(registry)
    meta = registry["meta"]
    click.echo(f"\n  Registry: {meta['total_operators']} operators ({meta['created']} new, {meta['updated']} updated)")
    click.echo(f"  Saved to {OPERATORS_REGISTRY_PATH}")


@main.command(name="op-inspect")
@click.argument("slug")
def op_inspect_cmd(slug: str):
    """Inspect extracted data for an operator.

    Shows the structured extraction output (contacts, properties, photos).

    \b
    Examples:
        cleo op-inspect riocan
    """
    from cleo.operators.engine import store
    from cleo.operators.registry import load_registry

    # Try registry first
    reg = load_registry()
    operators = reg.get("operators", {})
    for op_id, op in operators.items():
        if op.get("slug") == slug:
            click.echo(f"Operator: {op_id} ({op.get('name', '')})")
            click.echo(f"URL: {op.get('url', '')}")
            click.echo(f"Description: {op.get('description', '')[:200]}")
            click.echo(f"\nContacts ({len(op.get('contacts', []))}):")
            for c in op.get("contacts", [])[:10]:
                click.echo(f"  {c.get('name', '')} — {c.get('title', '')} {c.get('email', '') or ''}")
            click.echo(f"\nExtracted Properties ({len(op.get('extracted_properties', []))}):")
            for p in op.get("extracted_properties", [])[:10]:
                click.echo(f"  {p.get('address', '')}, {p.get('city', '')} — {p.get('plaza_name', '') or ''}")
            click.echo(f"\nProperty Matches ({len(op.get('property_matches', []))}):")
            for m in op.get("property_matches", []):
                if m.get("status") == "no_match":
                    continue
                click.echo(f"  {m.get('extracted_address', '')} -> {m.get('prop_id', '')} ({m['confidence']:.2f}) [{m['status']}]")
            click.echo(f"\nParty Matches ({len(op.get('party_matches', []))}):")
            for m in op.get("party_matches", []):
                click.echo(f"  {m.get('party_display_name', '')} ({m.get('match_type', '')}) [{m['status']}]")
            return

    # Fall back to extracted dir
    ext_active = store.active_dir()
    target = ext_active
    if target is None:
        sb = store.sandbox_path()
        if sb.is_dir():
            target = sb

    if target is None:
        click.echo("No extraction data. Run 'cleo op-extract --sandbox' first.", err=True)
        raise SystemExit(1)

    json_path = target / f"{slug}.json"
    if not json_path.exists():
        click.echo(f"No extraction data for '{slug}'.", err=True)
        raise SystemExit(1)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


# Need to import OPERATORS_REGISTRY_PATH for op-match
from cleo.config import OPERATORS_REGISTRY_PATH  # noqa: E402


# ─── Google Places & Street View ──────────────────────────────────


@main.command(name="google")
@click.option("--test", is_flag=True, help="Test API key connectivity (1 free metadata call)")
@click.option("--status", is_flag=True, help="Show budget usage and enrichment progress")
def google_cmd(test, status):
    """Google Places & Street View utilities."""
    from cleo.config import GOOGLE_API_KEY

    if test:
        if not GOOGLE_API_KEY:
            click.echo("GOOGLE_API_KEY not set in .env", err=True)
            raise SystemExit(1)

        from cleo.google.budget import BudgetGuardian
        from cleo.google.client import GooglePlacesClient

        budget = BudgetGuardian()
        client = GooglePlacesClient(GOOGLE_API_KEY, budget)
        try:
            result = client.test_connection()
            if result["ok"]:
                click.echo(f"Connection OK — pano_id: {result['pano_id']}")
                click.echo(f"Budget file: {budget.path}")
            else:
                click.echo(f"Connection test returned status: {result['status']}", err=True)
                raise SystemExit(1)
        except Exception as e:
            click.echo(f"Connection test failed: {e}", err=True)
            raise SystemExit(1)
        finally:
            client.close()
        return

    if status:
        from cleo.google.enrichment import enrichment_status

        st = enrichment_status()

        # Budget table
        click.echo("\n=== Budget Usage ===")
        budget = st["budget"]
        meta = budget.pop("_meta", {})
        click.echo(f"Month: {meta.get('month', '?')}")
        if meta.get("tampered"):
            click.echo("WARNING: TAMPER DETECTED — all calls blocked!")
        click.echo(f"{'SKU':<25} {'Used':>6} {'Limit':>6} {'Remaining':>9} {'%':>6} {'Today':>6} {'Daily Cap':>9}")
        click.echo("-" * 80)
        for sku, info in budget.items():
            limit_str = str(info["limit"]) if info["limit"] is not None else "unlim"
            rem_str = str(info["remaining"]) if info["remaining"] is not None else "unlim"
            daily_lim = str(info["daily_limit"]) if info["daily_limit"] is not None else "unlim"
            click.echo(
                f"{sku:<25} {info['used']:>6} {limit_str:>6} {rem_str:>9} "
                f"{info['pct']:>5.1f}% {info['daily_used']:>6} {daily_lim:>9}"
            )

        # Enrichment progress
        click.echo("\n=== Places Enrichment ===")
        places = st["places"]
        click.echo(f"Properties tracked:  {places['total_properties']}")
        click.echo(f"With place_id:       {places['with_place_id']}")
        click.echo(f"With essentials:     {places['with_essentials']}")
        click.echo(f"With pro:            {places['with_pro']}")
        click.echo(f"With enterprise:     {places['with_enterprise']}")

        click.echo("\n=== Street View ===")
        sv = st["streetview"]
        click.echo(f"Metadata checked:    {sv['total_checked']}")
        click.echo(f"With coverage:       {sv['with_coverage']}")
        click.echo(f"No coverage:         {sv['no_coverage']}")
        click.echo(f"Images fetched:      {sv['images_fetched']}")
        click.echo()
        return

    click.echo("Use --test or --status. See: cleo google --help")


@main.command(name="google-enrich")
@click.option(
    "--phase",
    type=click.Choice(["text-search", "details", "streetview"]),
    required=True,
    help="Enrichment phase to run",
)
@click.option(
    "--tier",
    type=click.Choice(["essentials", "pro", "enterprise"]),
    default=None,
    help="Details tier (required when --phase=details)",
)
@click.option("--limit", type=int, default=None, help="Max properties to process")
@click.option("--dry-run", is_flag=True, help="Report what would be done without making API calls")
def google_enrich_cmd(phase, tier, limit, dry_run):
    """Run Google Places / Street View enrichment pipeline."""
    from cleo.config import GOOGLE_API_KEY
    from cleo.google.enrichment import run_text_search, run_details, run_streetview

    if not GOOGLE_API_KEY and not dry_run:
        click.echo("GOOGLE_API_KEY not set in .env", err=True)
        raise SystemExit(1)

    if phase == "details" and tier is None:
        click.echo("--tier is required when --phase=details", err=True)
        raise SystemExit(1)

    if phase == "text-search":
        result = run_text_search(limit=limit, dry_run=dry_run)
    elif phase == "details":
        result = run_details(tier=tier, limit=limit, dry_run=dry_run)
    elif phase == "streetview":
        result = run_streetview(limit=limit, dry_run=dry_run)
    else:
        click.echo(f"Unknown phase: {phase}", err=True)
        raise SystemExit(1)

    # Print results
    click.echo(json.dumps(result, indent=2))


# ─── OSM Tenant Discovery ─────────────────────────────────────────


@main.command(name="osm-tenants")
@click.option("--limit", type=int, default=None, help="Max properties to process")
@click.option("--radius", type=int, default=150, help="Search radius in meters (default 150)")
@click.option("--dry-run", is_flag=True, help="Report what would be done without making calls")
@click.option("--status", is_flag=True, help="Show tenant discovery progress")
def osm_tenants_cmd(limit, radius, dry_run, status):
    """Discover tenants at properties via OpenStreetMap (free, no API key)."""
    from cleo.osm.enrichment import run_tenant_discovery, tenant_status

    if status:
        st = tenant_status()
        click.echo("\n=== OSM Tenant Discovery ===")
        click.echo(f"Properties with coords:  {st['total_with_coords']}")
        click.echo(f"Already checked:         {st['properties_checked']}")
        click.echo(f"  With tenants:          {st['with_tenants']}")
        click.echo(f"  Empty:                 {st['empty']}")
        click.echo(f"Total tenants found:     {st['total_tenants']}")
        click.echo(f"Pending:                 {st['pending']}")
        click.echo()
        return

    result = run_tenant_discovery(limit=limit, radius=radius, dry_run=dry_run)
    click.echo(json.dumps(result, indent=2))


@main.command(name="osm-brands")
@click.option("--dry-run", is_flag=True, help="Report what would be done")
@click.option("--status", is_flag=True, help="Show brand search results")
def osm_brands_cmd(dry_run, status):
    """Search all of Ontario for master brands via OSM (free, one query)."""
    from cleo.osm.brand_search import run_brand_search, OSM_BRANDS_PATH

    if status:
        if not OSM_BRANDS_PATH.exists():
            click.echo("No brand search data yet. Run: cleo osm-brands")
            return
        data = json.loads(OSM_BRANDS_PATH.read_text(encoding="utf-8"))
        meta = data.get("meta", {})
        click.echo("\n=== OSM Brand Search ===")
        click.echo(f"Total POIs fetched:       {meta.get('total_pois_fetched', 0)}")
        click.echo(f"Master brands:            {meta.get('master_brands', 0)}")
        click.echo(f"Brands found in OSM:      {meta.get('brands_matched_in_osm', 0)}")
        click.echo(f"Filtered POIs:            {meta.get('filtered_pois', 0)}")
        click.echo(f"Properties with matches:  {meta.get('properties_with_matches', 0)}")
        click.echo(f"Total tenant matches:     {meta.get('total_matches', 0)}")
        click.echo()
        brand_counts = meta.get("brand_counts", {})
        if brand_counts:
            click.echo("Top brands found:")
            for brand, count in list(brand_counts.items())[:30]:
                click.echo(f"  {count:>5}  {brand}")
        click.echo()
        return

    result = run_brand_search(dry_run=dry_run)
    click.echo(json.dumps(result, indent=2))


@main.command(name="osm-match")
def osm_match_cmd():
    """Cross-reference tenant addresses with property addresses."""
    from cleo.osm.matcher import run_address_match

    result = run_address_match()
    click.echo(f"Confirmed (address match): {result['confirmed']}")
    click.echo(f"Nearby (proximity only):   {result['nearby']}")
    click.echo(f"Properties without addr:   {result['properties_without_address']}")


@main.command(name="osm-refine-coords")
@click.option("--dry-run", is_flag=True, help="Report what would change without saving")
def osm_refine_coords_cmd(dry_run):
    """Refine property coordinates using confirmed tenant OSM locations."""
    from cleo.osm.brand_search import refine_property_coords

    result = refine_property_coords(dry_run=dry_run)
    if "error" in result:
        click.echo(result["error"])
        return
    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}Properties refined: {result['properties_refined']}")
    click.echo(f"{prefix}Skipped (not in registry): {result['skipped']}")


@main.command(name="footprints")
@click.option("--status", "show_status", is_flag=True, help="Show footprint data status.")
@click.option("--enrich-osm", is_flag=True, help="Enrich footprints with OSM metadata.")
@click.option("--osm-limit", type=int, default=None, help="Max OSM area clusters to query (for testing).")
@click.option("--force", is_flag=True, help="Re-download even if zip exists.")
def footprints_cmd(show_status, enrich_osm, osm_limit, force):
    """Download, filter, and enrich Microsoft Building Footprints.

    Downloads the Ontario bulk GeoJSON (~250MB), filters to buildings
    within 200m of our properties, and optionally enriches with OSM
    building metadata.

    \b
    Examples:
        cleo footprints               # Download + filter
        cleo footprints --status      # Show footprint stats
        cleo footprints --enrich-osm  # Add OSM metadata
    """
    from cleo.footprints.ingest import (
        download_footprints,
        filter_footprints,
        footprint_status,
    )

    if show_status:
        st = footprint_status()
        click.echo("\n=== Building Footprints ===")
        click.echo(f"Ontario.zip:       {'present' if st['zip_exists'] else 'not downloaded'}")
        if st["zip_exists"]:
            click.echo(f"  Size:            {st['zip_size_mb']:.1f} MB")
        click.echo(f"Buildings file:    {'present' if st['buildings_file_exists'] else 'not built'}")
        if st["buildings_file_exists"]:
            click.echo(f"  Buildings:       {st['building_count']:,}")
            meta = st.get("meta", {})
            if meta.get("total_scanned"):
                click.echo(f"  Total scanned:   {meta['total_scanned']:,}")
            if meta.get("property_count"):
                click.echo(f"  Properties used: {meta['property_count']:,}")
            if meta.get("osm_enriched"):
                click.echo(f"  OSM enriched:    {meta['osm_enriched']:,}")
        click.echo()
        return

    if enrich_osm:
        from cleo.footprints.osm_enrich import enrich_with_osm

        click.echo("Enriching footprints with OSM building metadata...\n")
        result = enrich_with_osm(limit=osm_limit)
        click.echo(f"\nEnriched:           {result['enriched']:,}")
        click.echo(f"Clusters queried:   {result['clusters_queried']:,}")
        click.echo(f"OSM buildings:      {result['osm_buildings_fetched']:,}")
        click.echo(f"Elapsed:            {result['elapsed_s']:.1f}s")
        return

    # Default: download + filter
    click.echo("Step 1: Downloading Microsoft Building Footprints for Ontario...\n")
    zip_path = download_footprints(force=force)
    click.echo(f"\nStep 2: Filtering to buildings near properties...\n")
    result = filter_footprints(zip_path)
    click.echo(f"\nDone!")
    click.echo(f"  Total scanned:   {result['total_scanned']:,}")
    click.echo(f"  Kept:            {result['kept']:,}")
    click.echo(f"  Properties used: {result['property_count']:,}")
    click.echo(f"  Elapsed:         {result['elapsed_s']:.1f}s")


@main.command(name="footprint-match")
@click.option("--status", "show_status", is_flag=True, help="Show match stats.")
@click.option("--dry-run", is_flag=True, help="Preview matches without saving.")
def footprint_match_cmd(show_status, dry_run):
    """Match properties and brands to building footprints spatially.

    Uses point-in-polygon containment with a 30m proximity fallback
    for coordinate drift.

    \b
    Examples:
        cleo footprint-match             # Run matching
        cleo footprint-match --status    # Show current stats
        cleo footprint-match --dry-run   # Preview without saving
    """
    from cleo.footprints.matcher import match_status, run_matching

    if show_status:
        st = match_status()
        if not st.get("matched"):
            click.echo("No matches yet. Run: cleo footprint-match")
            return
        click.echo("\n=== Footprint Matching ===")
        click.echo(f"Properties matched:    {st['property_footprints']:,}")
        click.echo(f"Brand spatial matches: {st['brand_spatial_matches']:,}")
        stats = st.get("stats", {})
        for key, val in stats.items():
            click.echo(f"  {key}: {val}")
        click.echo()
        return

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}Running spatial matching...\n")
    result = run_matching(dry_run=dry_run)

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        raise SystemExit(1)

    stats = result.get("stats", {})
    click.echo(f"\n{prefix}Results:")
    click.echo(f"  Properties matched (containment): {stats.get('contained', 0):,}")
    click.echo(f"  Properties matched (proximity):   {stats.get('proximate', 0):,}")
    click.echo(f"  Properties unmatched:              {stats.get('unmatched', 0):,}")
    click.echo(f"  Properties no coords:              {stats.get('no_coords', 0):,}")
    click.echo(f"  Match rate:                        {stats.get('match_rate_pct', 0):.1f}%")
    click.echo(f"  Brands spatially matched:          {stats.get('brands_spatially_matched', 0):,}")
    click.echo(f"  Brands no footprint:               {stats.get('brands_no_footprint', 0):,}")


@main.command(name="footprint-enrich")
@click.option("--dry-run", is_flag=True, help="Preview without saving.")
@click.option("--no-snap", is_flag=True, help="Don't snap property coords to building centroids.")
def footprint_enrich_cmd(dry_run, no_snap):
    """Add building footprint fields to properties.json.

    Adds footprint_id, footprint_area_sqm, footprint_building_type, and
    footprint_match_method to matched properties. Also snaps property
    coordinates to building footprint centroids so map pins land on
    the actual building (preserves original coords as pre_snap_lat/lng).
    """
    from cleo.footprints.enrichment import enrich_properties

    prefix = "[DRY RUN] " if dry_run else ""
    result = enrich_properties(dry_run=dry_run, snap_coords=not no_snap)

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        raise SystemExit(1)

    click.echo(f"{prefix}Enriched:          {result['enriched']:,}")
    click.echo(f"{prefix}Coords snapped:    {result['coords_snapped']:,}")
    if result['coords_snapped']:
        click.echo(f"{prefix}  Avg snap dist:   {result['avg_snap_distance_m']:.1f}m")
        click.echo(f"{prefix}  Max snap dist:   {result['max_snap_distance_m']:.1f}m")
    click.echo(f"{prefix}Cleared stale:     {result['cleared_stale']:,}")
    click.echo(f"{prefix}Total props:       {result['total_properties']:,}")


@main.command(name="parcels")
@click.option("--status", "show_status", is_flag=True, help="Show parcel harvest status.")
@click.option("--harvest", is_flag=True, help="Harvest parcels from ArcGIS services.")
@click.option("--municipality", type=str, default=None, help="Only harvest for this municipality (e.g. london, grey).")
@click.option("--dry-run", is_flag=True, help="Preview eligible properties without querying.")
@click.option("--limit", type=int, default=None, help="Max properties to query (for testing).")
def parcels_cmd(show_status, harvest, municipality, dry_run, limit):
    """Harvest municipal parcel boundaries from ArcGIS REST services.

    Downloads parcel polygons and attributes for properties in covered
    municipalities. For services with an address layer configured (e.g. London),
    harvests by address lookup first -- no coordinates required. Falls back to
    coordinate bbox for services without an address layer.

    \b
    Examples:
        cleo parcels --status                          # Show harvest stats
        cleo parcels --harvest --dry-run               # Preview eligible properties
        cleo parcels --harvest --municipality london    # Harvest London via address lookup
        cleo parcels --harvest                          # Harvest all municipalities
        cleo parcels --harvest --limit 5               # Test with 5 properties
    """
    from cleo.parcels.harvester import harvest_parcels, harvest_status

    if show_status:
        st = harvest_status()
        click.echo("\n=== Parcel Harvest ===")
        click.echo(f"Parcels cached:     {st['total_parcels']:,}")
        click.echo(f"Properties mapped:  {st['properties_mapped']:,}")
        click.echo(f"No coverage:        {st['no_coverage']:,}")
        by_muni = st.get("by_municipality", {})
        if by_muni:
            click.echo("\nBy municipality:")
            for m, cnt in sorted(by_muni.items()):
                click.echo(f"  {m}: {cnt:,}")
        services = st.get("services", {})
        if services:
            click.echo(f"\nRegistered services: {len(services)}")
            for key, svc in services.items():
                cities_str = ", ".join(svc["cities"][:5])
                if len(svc["cities"]) > 5:
                    cities_str += f" (+{len(svc['cities']) - 5} more)"
                click.echo(f"  {key}: {svc['name']} ({cities_str})")
        click.echo()
        return

    if not harvest:
        click.echo("Use --harvest to start harvesting, or --status to check progress.")
        click.echo("Run 'cleo parcels --help' for all options.")
        return

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}Harvesting parcel boundaries...\n")

    result = harvest_parcels(
        municipality=municipality,
        dry_run=dry_run,
        limit=limit,
    )

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        if result.get("no_coords"):
            click.echo(f"  Properties without coords: {result['no_coords']:,}")
        if result.get("no_coverage"):
            click.echo(f"  Properties outside coverage: {result['no_coverage']:,}")
        raise SystemExit(1)

    if dry_run:
        click.echo(f"{prefix}Eligible properties: {result['eligible_properties']:,}")
        by_muni = result.get("by_municipality", {})
        for m, cnt in sorted(by_muni.items()):
            click.echo(f"  {m}: {cnt:,}")
        click.echo(f"\nNo coords:    {result['no_coords']:,}")
        click.echo(f"No coverage:  {result['no_coverage']:,}")
        return

    click.echo(f"Queried:       {result['queried']:,}")
    click.echo(f"Found:         {result['found']:,}")
    click.echo(f"No result:     {result['no_result']:,}")
    click.echo(f"Elapsed:       {result['elapsed_s']:.1f}s")


@main.command(name="parcel-enrich")
@click.option("--dry-run", is_flag=True, help="Preview without saving.")
@click.option("--report", is_flag=True, help="Print detailed report of multi-property parcels.")
def parcel_enrich_cmd(dry_run, report):
    """Consolidate properties by parcel and enrich with spatial data.

    Adds parcel attributes (ID, PIN, area, zoning) to properties, groups
    properties that share the same parcel, and assigns brand POIs via
    spatial containment. Also subsumes the old parcel-match functionality.

    \b
    Examples:
        cleo parcel-enrich              # Run consolidation
        cleo parcel-enrich --dry-run    # Preview without saving
        cleo parcel-enrich --report     # Show multi-property parcel details
    """
    from cleo.parcels.consolidate import consolidate

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(f"{prefix}Running parcel consolidation...\n")
    result = consolidate(dry_run=dry_run)

    if "error" in result:
        click.echo(f"Error: {result['error']}", err=True)
        raise SystemExit(1)

    click.echo(f"{prefix}Properties enriched:         {result['enriched']:,}")
    click.echo(f"{prefix}Cleared stale:               {result['cleared_stale']:,}")
    click.echo(f"{prefix}Spatially matched (new):     {result['spatially_matched']:,}")
    click.echo(f"{prefix}Multi-property parcels:      {result['multi_property_parcels']:,}")
    click.echo(f"{prefix}Brand POIs matched:          {result['brands_matched']:,}")
    click.echo(f"{prefix}Parcels with brands:         {result['parcels_with_brands']:,}")
    click.echo(f"{prefix}Total properties:            {result['total_properties']:,}")

    if report:
        multi = result.get("multi_details", [])
        if not multi:
            click.echo("\nNo multi-property parcels found.")
        else:
            click.echo(f"\n=== Multi-Property Parcels ({len(multi)}) ===\n")
            for detail in multi[:50]:  # cap output
                click.echo(f"  {detail['pcl_id']} ({detail['municipality']}) -- {detail['property_count']} properties")
                for i, pid in enumerate(detail["property_ids"]):
                    addr = detail["addresses"][i] if i < len(detail["addresses"]) else ""
                    click.echo(f"    {pid}  {addr}")
                if detail.get("brands"):
                    click.echo(f"    Brands: {', '.join(detail['brands'])}")
                click.echo()


@main.command(name="discover-types")
def discover_types_cmd():
    """Discover available property types from the Realtrack search form."""
    try:
        username, password = get_credentials()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    try:
        session = RealtrackSession(username, password)
    except AuthenticationError as e:
        click.echo(f"Login failed: {e}", err=True)
        raise SystemExit(1)

    try:
        options = discover_property_types(session)
        if not options:
            click.echo("Could not find property type options on search page.")
            raise SystemExit(1)

        click.echo(f"Found {len(options)} property types:\n")
        click.echo(f"  {'Value':<20} Label")
        click.echo(f"  {'─' * 20} {'─' * 40}")
        for opt in options:
            click.echo(f"  {opt['value']:<20} {opt['label']}")

        click.echo(f"\nCurrently configured in PROPERTY_TYPES:")
        for slug, sf3 in sorted(PROPERTY_TYPES.items()):
            click.echo(f"  {slug:<20} → {sf3}")
    finally:
        session.close()


@main.command(name="migrate-html")
@click.option("--dry-run", is_flag=True, help="Show what would be moved without moving.")
def migrate_html_cmd(dry_run: bool):
    """Move flat data/html/RT*.html files into data/html/retail/ subdirectory.

    Builds the HTML index after migration. Idempotent — skips files
    already in subdirectories.
    """
    import shutil

    flat_files = sorted(HTML_DIR.glob("RT*.html"))
    if not flat_files:
        click.echo("No flat HTML files found in data/html/. Already migrated or empty.")
        # Rebuild index anyway
        if not dry_run:
            idx = HtmlIndex()
            count = idx.rebuild()
            idx.save()
            click.echo(f"Rebuilt HTML index: {count:,} entries.")
        return

    retail_dir = HTML_DIR / "retail"
    prefix = "[DRY RUN] " if dry_run else ""

    if not dry_run:
        retail_dir.mkdir(exist_ok=True)

    moved = 0
    skipped = 0
    for path in flat_files:
        dest = retail_dir / path.name
        if dest.exists():
            skipped += 1
            continue
        if dry_run:
            click.echo(f"  {prefix}{path.name} → retail/{path.name}")
        else:
            shutil.move(str(path), str(dest))
        moved += 1

    click.echo(f"\n{prefix}Moved: {moved:,} files → data/html/retail/")
    if skipped:
        click.echo(f"{prefix}Skipped (already exists): {skipped:,}")

    if not dry_run:
        idx = HtmlIndex()
        count = idx.rebuild()
        idx.save()
        click.echo(f"Rebuilt HTML index: {count:,} entries.")


@main.command(name="rebuild-html-index")
def rebuild_html_index_cmd():
    """Rebuild html_index.json by scanning all data/html/ subdirectories."""
    idx = HtmlIndex()
    count = idx.rebuild()
    idx.save()
    click.echo(f"Rebuilt HTML index: {count:,} entries.")

    # Show breakdown by type
    type_counts: dict[str, int] = {}
    for subdir in sorted(HTML_DIR.iterdir()):
        if subdir.is_dir():
            n = len(list(subdir.glob("*.html")))
            if n > 0:
                type_counts[subdir.name] = n
    if type_counts:
        click.echo("\nBreakdown by type:")
        for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
            click.echo(f"  {t:<20} {n:,}")


if __name__ == "__main__":
    main()
