"""Cleo Mini V3 CLI."""

import json
import logging
import time
from datetime import datetime

import click

from cleo.config import DATA_DIR, HTML_DIR, get_credentials
from cleo.ingest.fetcher import fetch_detail_page
from cleo.ingest.scraper import get_total_results, submit_search_and_get_links
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
def scrape(delay: float):
    """Scrape new transactions from Realtrack.com.

    Logs in, searches for Retail Buildings, visits up to 50 detail pages,
    and saves HTML for any new RT IDs not already in the local store.
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
        skip_indices = submit_search_and_get_links(session)
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

        # Step 6: Save HTML for new RT IDs only
        new_rt_set = set(new_rt_ids)
        saved = 0
        for rt_id, html in results:
            if rt_id in new_rt_set:
                path = HTML_DIR / f"{rt_id}.html"
                path.write_text(html, encoding="utf-8")
                saved += 1
                logger.info("Saved %s", path.name)

        # Step 7: Update tracker
        tracker.mark_seen(new_rt_ids)

        click.echo(
            f"Done! Saved {saved} new transactions. "
            f"Total known: {tracker.count}."
        )

    finally:
        session.close()


@main.command()
def check():
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
        total = get_total_results(session)
        if total is None:
            click.echo("Could not extract total from Realtrack.", err=True)
            raise SystemExit(1)

        tracker = IngestTracker()
        local = tracker.count
        gap = total - local

        click.echo(f"Realtrack total:  {total:,}")
        click.echo(f"Local RT IDs:     {local:,}")
        click.echo(f"Gap:              {gap:,}")

        if gap == 0:
            click.echo("Perfect — fully synced.")
        elif gap > 0:
            click.echo(f"Missing {gap:,} transactions.")
        else:
            click.echo(f"Local has {abs(gap):,} more than Realtrack (possible dupes or type overlap).")
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
@click.option("--retry-failures", is_flag=True, help="Re-try previously failed addresses.")
@click.option("--status", "show_status", is_flag=True, help="Show geocode cache stats.")
@click.option("--build-index", is_flag=True, help="Build address index from cache + extracted data.")
@click.option("--batch-size", type=int, default=50, help="Addresses per batch API call.")
@click.option("--delay", type=float, default=0.15, help="Seconds between batch API calls.")
@click.option("--provider", type=click.Choice(["mapbox", "here"]), default="mapbox", help="Geocoding provider.")
def geocode_cmd(dry_run, limit, retry_failures, show_status, build_index, batch_size, delay, provider):
    """Geocode extracted addresses using Mapbox or HERE API.

    Scans extracted/active for all geocodable addresses, checks the
    cache, and geocodes any missing addresses.

    \b
    Examples:
        cleo geocode --status                  # Show cache stats
        cleo geocode --dry-run                 # Preview what would be geocoded
        cleo geocode --limit 5000              # Geocode up to 5000 new addresses
        cleo geocode                           # Geocode all remaining (Mapbox)
        cleo geocode --provider here           # Geocode using HERE
        cleo geocode --retry-failures          # Re-try previously failed addresses
        cleo geocode --build-index             # Build address index from cache
    """
    from cleo.config import MAPBOX_TOKEN, HERE_API_KEY, GEOCODE_CACHE_PATH, ADDRESS_INDEX_PATH, EXTRACTED_DIR, EXTRACT_REVIEWS_PATH
    from cleo.geocode.cache import GeocodeCache

    cache = GeocodeCache(GEOCODE_CACHE_PATH)

    if show_status:
        stats = cache.stats()
        click.echo(f"Geocode cache: {GEOCODE_CACHE_PATH}")
        click.echo(f"  Total entries:  {stats['total']:,}")
        click.echo(f"  Successes:      {stats['successes']:,}")
        click.echo(f"  Failures:       {stats['failures']:,}")
        return

    if build_index:
        from cleo.geocode.index import build_address_index
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

    # Geocoding mode
    ext_store = extract_ver.store
    ext_active = ext_store.active_dir()
    if ext_active is None:
        click.echo("No active extraction version. Run 'cleo extract --sandbox' then '--promote' first.", err=True)
        raise SystemExit(1)

    from cleo.geocode.runner import run_geocode

    client = None
    if not dry_run:
        if provider == "here":
            from cleo.geocode.here_client import HereClient
            if not HERE_API_KEY:
                click.echo("HERE_API_KEY not set. Add it to your .env file.", err=True)
                raise SystemExit(1)
            client = HereClient(HERE_API_KEY)
            if delay == 0.15:  # default wasn't overridden
                delay = 0.22  # 4.5 req/sec, safe under HERE's 5/sec limit
            click.echo(f"Using HERE geocoding provider ({delay:.2f}s delay)")
        else:
            from cleo.geocode.client import MapboxClient
            if not MAPBOX_TOKEN:
                click.echo("MAPBOX_TOKEN not set. Add it to your .env file.", err=True)
                raise SystemExit(1)
            client = MapboxClient(MAPBOX_TOKEN)

    try:
        summary = run_geocode(
            extracted_dir=ext_active,
            reviews_path=EXTRACT_REVIEWS_PATH,
            cache=cache,
            client=client,
            dry_run=dry_run,
            limit=limit,
            retry_failures=retry_failures,
            batch_size=batch_size,
            delay=delay,
        )
    finally:
        if client:
            client.close()

    click.echo(f"\nGeocode summary:")
    click.echo(f"  Total unique addresses:  {summary['total_unique']:,}")
    click.echo(f"  Total references:        {summary['total_references']:,}")
    click.echo(f"  Already cached:          {summary['already_cached']:,}")
    if summary['cleared_failures']:
        click.echo(f"  Cleared failures:        {summary['cleared_failures']:,}")
    click.echo(f"  To geocode:              {summary['to_geocode']:,}")
    if not dry_run and summary['to_geocode'] > 0:
        click.echo(f"  Geocoded:                {summary['geocoded']:,}")
        click.echo(f"    Successes:             {summary['successes']:,}")
        click.echo(f"    Failures:              {summary['failures']:,}")
        click.echo(f"  Batch API requests:      {summary['batch_requests']:,}")
        click.echo(f"  Elapsed:                 {summary['elapsed']:.1f}s")


@main.command()
@click.option("--status", "show_status", is_flag=True, help="Show property registry stats.")
@click.option("--dry-run", is_flag=True, help="Preview what would change without writing.")
@click.option("--apply-geocodes", is_flag=True, help="Backfill lat/lng from geocode cache into properties.")
def properties(show_status: bool, dry_run: bool, apply_geocodes: bool):
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
        from cleo.config import GEOCODE_CACHE_PATH, EXTRACTED_DIR
        from cleo.properties.registry import load_registry, save_registry, backfill_geocodes

        if not PROPERTIES_PATH.exists():
            click.echo("No property registry found. Run 'cleo properties' first.", err=True)
            raise SystemExit(1)
        if not GEOCODE_CACHE_PATH.exists():
            click.echo("No geocode cache found. Run 'cleo geocode' first.", err=True)
            raise SystemExit(1)

        registry = load_registry(PROPERTIES_PATH)

        ext_active = None
        ext_store = extract_ver.store
        ext_active = ext_store.active_dir()

        click.echo("Backfilling geocode coordinates into properties...")
        result = backfill_geocodes(
            registry=registry,
            cache_path=GEOCODE_CACHE_PATH,
            extracted_dir=ext_active,
        )

        click.echo(f"  Already had coords:  {result['already_had']:,}")
        click.echo(f"  Updated from cache:  {result['updated']:,}")
        click.echo(f"  No match in cache:   {result['no_match']:,}")

        if result["updated"] > 0 and not dry_run:
            save_registry(registry, PROPERTIES_PATH)
            click.echo(f"\nSaved to {PROPERTIES_PATH}")
        elif dry_run:
            click.echo(f"\nDry run — no changes written.")
        else:
            click.echo(f"\nNo new coordinates to apply.")
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
        html_path = HTML_DIR / f"{rt_id}.html"
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
    html_path = HTML_DIR / f"{rt_id}.html"
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


if __name__ == "__main__":
    main()
