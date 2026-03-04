"""Parcel resolution engine: resolves every source record to a parcel via ARN/PIN/coords.

Reads from:
  - expanded/active/{ID}.json     (source, property addresses with canonicals)
  - parsed/active/{RT_ID}.json    (RT transaction.arn, transaction.pins)
  - gw_parsed/active/{GW_ID}.json (GW site_structure.arn, registry.pin / pin)
  - coordinates.json              (geocode results per canonical address)
  - parcels/parcel_cache.json     (permanent parcel geometry cache)

Writes one parcelled JSON per source record to output_dir/{ID}.json.

Resolution priority per record:
  1. arn_direct  — record has ARN (RT parsed or GW), pad to 20, lookup/query
  2. pin_bridge  — record has PIN, reverse-lookup or query provincial API
  3. spatial     — geocoded coords, point-in-polygon provincial API query
  4. none        — all methods exhausted
"""

import json
import logging
import os
import signal
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cleo.parcels.arn import normalize_arn
from cleo.parcels.resolver import ParcelResolver, pad_arn_15_to_20, normalize_pin
from cleo.parcels.provincial import TokenExpiredError

logger = logging.getLogger(__name__)

# Sentinel set when SIGINT/SIGTERM received — triggers graceful shutdown
_shutdown_requested = False

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TokenRefreshFailed(Exception):
    """Raised when all attempts to get a valid AgMaps token have failed."""
    pass


def _fetch_fresh_token(max_attempts: int = 3) -> str:
    """Fetch a fresh AgMaps token using headless browser automation.

    Retries up to max_attempts times with exponential backoff.
    Raises TokenRefreshFailed if all attempts fail.
    """
    import sys
    scripts_dir = str(_PROJECT_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    from fetch_agmaps_token import fetch_token, save_token_to_env, test_token

    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info("Fetching AgMaps token (attempt %d/%d)...", attempt, max_attempts)
            token = fetch_token(headed=False, timeout_ms=60_000)

            logger.info("Validating token...")
            if test_token(token):
                save_token_to_env(token)
                os.environ["AGMAPS_TOKEN"] = token
                logger.info("Token refreshed and saved to .env")
                return token
            else:
                logger.warning("Token validation failed on attempt %d", attempt)
                last_err = RuntimeError("Token fetched but failed validation")
        except Exception as e:
            last_err = e
            logger.warning("Token fetch attempt %d failed: %s", attempt, e)

        if attempt < max_attempts:
            wait = 10 * attempt
            logger.info("Waiting %ds before retry...", wait)
            time.sleep(wait)

    raise TokenRefreshFailed(
        f"All {max_attempts} token fetch attempts failed. Last error: {last_err}"
    )


def _ensure_valid_token(skip_api: bool) -> Optional[str]:
    """Ensure we have a valid AgMaps token. Returns the token or raises TokenRefreshFailed."""
    if skip_api:
        return None

    from cleo.config import AGMAPS_TOKEN

    # If we have a token, test it
    if AGMAPS_TOKEN:
        try:
            from cleo.parcels.provincial import ProvincialParcelClient
            client = ProvincialParcelClient(token=AGMAPS_TOKEN)
            client.test_connection()
            client.close()
            logger.info("Existing AgMaps token is valid")
            return AGMAPS_TOKEN
        except (TokenExpiredError, Exception) as e:
            logger.info("Existing token expired or invalid: %s", e)

    # Need a fresh token — retries internally, raises TokenRefreshFailed on total failure
    return _fetch_fresh_token()


def _get_best_coords(
    canonical: str,
    coord_store: Dict[str, Dict],
) -> Optional[Dict[str, float]]:
    """Look up geocoded coordinates for a canonical address string."""
    if not canonical or canonical not in coord_store:
        return None
    providers = coord_store[canonical]
    for provider in ("mapbox", "geocodio", "here", "scraper"):
        if provider in providers:
            pdata = providers[provider]
            lat = pdata.get("lat")
            lng = pdata.get("lng")
            if lat and lng:
                return {"lat": float(lat), "lng": float(lng), "provider": provider}
    return None


def _collect_identifiers(
    record_id: str,
    source: str,
    expanded: Dict,
    parsed_dir: Path,
    gw_parsed_dir: Path,
    coord_store: Dict[str, Dict],
) -> Dict[str, Any]:
    """Collect all available identifiers for parcel resolution."""
    ident: Dict[str, Any] = {
        "arn_raw": "",
        "arn_20": "",
        "pins": [],
        "coords": None,
    }

    if source == "realtrack":
        # Read parsed record for ARN and PINs
        parsed_path = parsed_dir / f"{record_id}.json"
        if parsed_path.exists():
            parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
            txn = parsed.get("transaction", {})
            site = parsed.get("site", {})

            arn_raw = txn.get("arn", "")
            if arn_raw:
                ident["arn_raw"] = arn_raw
                ident["arn_20"] = normalize_arn(arn_raw)

            # PINs from transaction and site
            pins = []
            for p in txn.get("pins", []):
                if p:
                    pins.append(normalize_pin(str(p)))
            site_pins = site.get("pins", "")
            if site_pins:
                for sp in str(site_pins).split(","):
                    np = normalize_pin(sp)
                    if np and len(np) >= 9 and np not in pins:
                        pins.append(np)
            ident["pins"] = pins

    elif source == "geowarehouse":
        # Read GW parsed record for ARN and PIN
        # GW records are in gw_parsed/active/ (not the main parsed dir)
        gw_path = gw_parsed_dir / f"{record_id}.json"
        if gw_path.exists():
            gw_data = json.loads(gw_path.read_text(encoding="utf-8"))
            site_struct = gw_data.get("site_structure", {})
            registry = gw_data.get("registry", {})

            arn_raw = site_struct.get("arn", "")
            if arn_raw:
                ident["arn_raw"] = arn_raw
                ident["arn_20"] = normalize_arn(arn_raw)

            pin = registry.get("pin", "") or gw_data.get("pin", "")
            if pin:
                ident["pins"] = [normalize_pin(str(pin))]

    # For all sources: get coords from the first property canonical address
    prop = expanded.get("property")
    if prop:
        addresses = prop.get("addresses", []) if isinstance(prop, dict) else []
        for addr in addresses:
            canonical = addr.get("canonical", "")
            if canonical:
                coords = _get_best_coords(canonical, coord_store)
                if coords:
                    ident["coords"] = coords
                    break

    # Brand source: also check property_alt
    if ident["coords"] is None and source == "brand":
        prop_alt = expanded.get("property_alt", [])
        if isinstance(prop_alt, list):
            for item in prop_alt:
                for addr in item.get("addresses", []):
                    canonical = addr.get("canonical", "")
                    if canonical:
                        coords = _get_best_coords(canonical, coord_store)
                        if coords:
                            ident["coords"] = coords
                            break
                if ident["coords"]:
                    break

    return ident


def _resolve_record(
    ident: Dict[str, Any],
    resolver: ParcelResolver,
) -> Dict[str, Any]:
    """Attempt parcel resolution using the priority chain.

    Returns {method, method_chain, confidence, parcel_data}.
    """
    method_chain: List[str] = []
    arn_20 = ident.get("arn_20", "")
    pins = ident.get("pins", [])
    coords = ident.get("coords")

    # 1. ARN direct
    if arn_20 and len(arn_20) >= 15:
        parcel = resolver.resolve_by_arn(arn_20)
        if parcel:
            method_chain.append("arn_direct")
            return {
                "method": "arn_direct",
                "method_chain": method_chain,
                "confidence": "high",
                "parcel_data": parcel,
            }
        method_chain.append("arn_direct_miss")

    # 2. PIN bridge
    for pin in pins:
        if len(pin) >= 9:
            parcel = resolver.resolve_by_pin(pin)
            if parcel:
                method_chain.append("pin_bridge")
                return {
                    "method": "pin_bridge",
                    "method_chain": method_chain,
                    "confidence": "medium",
                    "parcel_data": parcel,
                }
    if pins:
        method_chain.append("pin_bridge_miss")

    # 3. Spatial
    if coords:
        parcel = resolver.resolve_by_coords(coords["lat"], coords["lng"])
        if parcel:
            method_chain.append("spatial")
            return {
                "method": "spatial",
                "method_chain": method_chain,
                "confidence": "low",
                "parcel_data": parcel,
            }
        method_chain.append("spatial_miss")

    # 4. None
    method_chain.append("none")
    return {
        "method": "none",
        "method_chain": method_chain,
        "confidence": None,
        "parcel_data": None,
    }


def _build_output(
    record_id: str,
    source: str,
    source_version: str,
    ident: Dict[str, Any],
    resolution: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the output JSON for a parcelled record."""
    parcel_data = resolution["parcel_data"]

    result: Dict[str, Any] = {
        "id": record_id,
        "source": source,
        "source_version": source_version,

        "resolution": {
            "resolved_arn": parcel_data["arn"] if parcel_data else "",
            "method": resolution["method"],
            "method_chain": resolution["method_chain"],
            "pin": parcel_data.get("pin", "") if parcel_data else "",
            "confidence": resolution["confidence"],
        },

        "input_identifiers": {
            "arn_raw": ident.get("arn_raw", ""),
            "arn_20": ident.get("arn_20", ""),
            "pins": ident.get("pins", []),
            "coords": ident.get("coords"),
        },
    }

    if parcel_data:
        result["parcel"] = {
            "arn": parcel_data.get("arn", ""),
            "pin": parcel_data.get("pin", ""),
            "geometry": parcel_data.get("geometry"),
            "centroid": parcel_data.get("centroid"),
            "attributes": parcel_data.get("attributes", {}),
            "source": parcel_data.get("source", ""),
            "cached_at": parcel_data.get("cached_at", ""),
        }
    else:
        result["parcel"] = None

    return result


def _make_resolver(skip_api: bool, token: Optional[str] = None) -> ParcelResolver:
    """Create a ParcelResolver, optionally with a specific token."""
    from cleo.parcels.cache import ParcelCache

    cache = ParcelCache()

    if skip_api or not token:
        return ParcelResolver(cache=cache, skip_api=True)

    # Create a resolver with a fresh provincial client using the given token
    resolver = ParcelResolver(cache=cache, skip_api=False)
    # Force-init the client with our token
    from cleo.parcels.provincial import ProvincialParcelClient
    resolver._client = ProvincialParcelClient(token=token)
    return resolver


def resolve_all(
    expanded_dir: Path,
    parsed_dir: Path,
    gw_parsed_dir: Path,
    coordinates_path: Path,
    output_dir: Path,
    source_version: str = "",
    skip_api: bool = False,
    resume: bool = False,
    osm_pois_dir: Optional[Path] = None,
) -> Dict:
    """Resolve parcels for all records from all sources.

    Processes expanded records (RT, GW, Brand) and optionally OSM POI records.
    OSM records come from osm_pois/active/ and have native coords — they skip
    the address pipeline entirely and go straight to spatial resolution.

    If skip_api is False, automatically fetches/refreshes the AgMaps token
    and handles mid-run token expiry by re-fetching.

    If resume is True, skips records that already have output files in
    output_dir, allowing interrupted runs to continue.

    Returns summary: {total, resolved, unresolved, by_method, by_source, errors, elapsed}
    """
    global _shutdown_requested
    _shutdown_requested = False

    start = time.time()
    total = 0
    processed = 0
    skipped = 0
    resolved = 0
    unresolved = 0
    errors = 0
    error_ids: List[str] = []
    by_method: Dict[str, int] = {}
    by_source: Dict[str, int] = {}
    token_refreshes = 0

    # --- Install signal handlers for graceful shutdown ---
    prev_sigint = signal.getsignal(signal.SIGINT)
    prev_sigterm = signal.getsignal(signal.SIGTERM)

    def _handle_shutdown(signum, frame):
        global _shutdown_requested
        if _shutdown_requested:
            # Second signal — force exit
            logger.warning("Second interrupt — forcing exit")
            raise SystemExit(1)
        _shutdown_requested = True
        sig_name = signal.Signals(signum).name
        logger.warning("Received %s — finishing current record then saving cache and exiting cleanly...", sig_name)

    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    # --- Build set of already-completed records for resume ---
    existing_ids: set[str] = set()
    if resume:
        existing_ids = {
            f.stem for f in output_dir.glob("*.json") if f.stem != "_meta"
        }
        if existing_ids:
            logger.info("Resume mode: %d records already in sandbox, skipping them", len(existing_ids))

    try:
        # --- Load coordinate store ---
        logger.info("Loading coordinate store...")
        coord_store: Dict[str, Dict] = {}
        if coordinates_path.exists():
            data = json.loads(coordinates_path.read_text(encoding="utf-8"))
            coord_store = data.get("addresses", {})
        logger.info("  %d addresses loaded", len(coord_store))

        # --- Ensure valid token (auto-fetch if needed) ---
        # Raises TokenRefreshFailed if all attempts fail — let it propagate
        # so the CLI retry loop can handle it.
        token = _ensure_valid_token(skip_api)

        # --- Initialize resolver ---
        logger.info("Initializing parcel resolver (skip_api=%s)...", skip_api)
        resolver = _make_resolver(skip_api, token)
        cache_stats = resolver._cache.stats()
        logger.info("  Cache: %d parcels (%s)", cache_stats["total"],
                    ", ".join(f"{k}: {v}" for k, v in cache_stats.get("by_source", {}).items()))

        # --- Process all expanded records ---
        expanded_files = sorted(expanded_dir.glob("*.json"))
        for exp_path in expanded_files:
            if exp_path.stem == "_meta":
                continue
            total += 1
            record_id = exp_path.stem

            # Resume: skip records already processed
            if record_id in existing_ids:
                skipped += 1
                continue

            # Graceful shutdown: stop processing new records
            if _shutdown_requested:
                logger.info("Shutdown requested — stopping after %d processed records", processed)
                break

            try:
                expanded = json.loads(exp_path.read_text(encoding="utf-8"))
                source = expanded.get("source", "unknown")

                # Collect all available identifiers
                ident = _collect_identifiers(
                    record_id, source, expanded,
                    parsed_dir, gw_parsed_dir, coord_store,
                )

                # Resolve parcel (with token expiry handling)
                try:
                    resolution = _resolve_record(ident, resolver)
                except TokenExpiredError:
                    # Token expired mid-run — save cache, fetch new token, rebuild resolver
                    logger.warning("Token expired at record %d/%d. Refreshing...", processed, total - skipped)
                    resolver.save_cache()
                    # Retries internally (3 attempts). Raises TokenRefreshFailed
                    # if all fail — let it propagate so the CLI retry loop handles it.
                    token = _fetch_fresh_token()
                    token_refreshes += 1
                    resolver = _make_resolver(False, token)
                    # Retry this record with the new token
                    resolution = _resolve_record(ident, resolver)

                # Build and write output
                output = _build_output(
                    record_id, source, source_version, ident, resolution,
                )
                out_path = output_dir / f"{record_id}.json"
                out_path.write_text(
                    json.dumps(output, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

                processed += 1
                method = resolution["method"]
                by_method[method] = by_method.get(method, 0) + 1
                by_source[source] = by_source.get(source, 0) + 1

                if method != "none":
                    resolved += 1
                else:
                    unresolved += 1

            except Exception as e:
                errors += 1
                error_ids.append(record_id)
                logger.error("Error resolving %s: %s", record_id, e)

            # Progress + periodic cache save (every 500 records for safer recovery)
            if processed % 500 == 0 and processed > 0:
                elapsed_so_far = time.time() - start
                rate = processed / elapsed_so_far if elapsed_so_far > 0 else 0
                remaining = total - skipped - processed - errors
                eta_s = remaining / rate if rate > 0 else 0
                eta_min = eta_s / 60
                logger.info(
                    "Progress: %d/%d processed (%d skipped, %d resolved, %d unresolved, %d errors) "
                    "%.1f rec/s, ~%.0f min remaining",
                    processed, total - skipped, skipped, resolved, unresolved, errors,
                    rate, eta_min,
                )
                resolver.save_cache()

        # --- Process OSM POI records (if available) ---
        if osm_pois_dir and osm_pois_dir.exists() and not _shutdown_requested:
            osm_files = sorted(osm_pois_dir.glob("*.json"))
            osm_count = sum(1 for f in osm_files if f.stem != "_meta")
            if osm_count:
                logger.info("Processing %d OSM POI records...", osm_count)
            for osm_path in osm_files:
                if osm_path.stem == "_meta":
                    continue
                total += 1
                record_id = osm_path.stem

                if record_id in existing_ids:
                    skipped += 1
                    continue

                if _shutdown_requested:
                    logger.info("Shutdown requested — stopping after %d processed records", processed)
                    break

                try:
                    osm_rec = json.loads(osm_path.read_text(encoding="utf-8"))

                    # OSM records have native coords, no ARN/PIN
                    coords = osm_rec.get("coords")
                    ident: Dict[str, Any] = {
                        "arn_raw": "",
                        "arn_20": "",
                        "pins": [],
                        "coords": coords,
                    }

                    try:
                        resolution = _resolve_record(ident, resolver)
                    except TokenExpiredError:
                        logger.warning("Token expired at OSM record %s. Refreshing...", record_id)
                        resolver.save_cache()
                        token = _fetch_fresh_token()
                        token_refreshes += 1
                        resolver = _make_resolver(False, token)
                        resolution = _resolve_record(ident, resolver)

                    output = _build_output(
                        record_id, "osm", source_version, ident, resolution,
                    )
                    out_path = output_dir / f"{record_id}.json"
                    out_path.write_text(
                        json.dumps(output, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )

                    processed += 1
                    method = resolution["method"]
                    by_method[method] = by_method.get(method, 0) + 1
                    by_source["osm"] = by_source.get("osm", 0) + 1

                    if method != "none":
                        resolved += 1
                    else:
                        unresolved += 1

                except Exception as e:
                    errors += 1
                    error_ids.append(record_id)
                    logger.error("Error resolving OSM %s: %s", record_id, e)

                if processed % 500 == 0 and processed > 0:
                    elapsed_so_far = time.time() - start
                    rate = processed / elapsed_so_far if elapsed_so_far > 0 else 0
                    remaining = total - skipped - processed - errors
                    eta_s = remaining / rate if rate > 0 else 0
                    logger.info(
                        "Progress: %d/%d processed (%d skipped, %d resolved, %d unresolved, %d errors) "
                        "%.1f rec/s, ~%.0f min remaining",
                        processed, total - skipped, skipped, resolved, unresolved, errors,
                        rate, eta_s / 60,
                    )
                    resolver.save_cache()

        # Final cache save
        resolver.save_cache()

    except Exception:
        # On any unhandled error, save cache before re-raising
        try:
            resolver.save_cache()
        except Exception:
            pass
        raise

    finally:
        # Restore original signal handlers
        signal.signal(signal.SIGINT, prev_sigint)
        signal.signal(signal.SIGTERM, prev_sigterm)

    elapsed = time.time() - start
    resolver_stats = resolver.get_stats()

    status = "interrupted" if _shutdown_requested else "complete"
    logger.info(
        "Run %s: %d processed, %d skipped, %d resolved, %d unresolved, %d errors in %.1fs",
        status, processed, skipped, resolved, unresolved, errors, elapsed,
    )

    return {
        "total": total,
        "processed": processed,
        "skipped": skipped,
        "resolved": resolved,
        "unresolved": unresolved,
        "errors": errors,
        "error_ids": error_ids,
        "by_method": by_method,
        "by_source": by_source,
        "elapsed": elapsed,
        "token_refreshes": token_refreshes,
        "resolver_stats": resolver_stats,
        "interrupted": _shutdown_requested,
    }
