# Cleo Mini V3 — Project Context

## What This Project Is

Cleo Mini V3 is a Python CLI tool and web application for commercial real estate transaction data from Realtrack.com (Ontario retail building sales). It scrapes HTML detail pages, parses them into structured JSON, validates the data, geocodes addresses, builds property and party registries, and provides both a review UI and a front-facing React SPA for exploring the data.

## System Documentation

Read `docs/system-guide.md` first — it is the authoritative reference for the entire system. It covers architecture, all CLI commands, data flow, parsing pipeline, validation checks, versioning, extraction, geocoding, property/party registries, GeoWarehouse integration, the front-facing app, and the full API reference.

## Key Files to Read (in order of importance)

### Core orchestration
- `cleo/cli.py` — All CLI commands (~21 commands). Start here to understand what the system does.
- `cleo/config.py` — All paths (~19 constants including CRM), env vars, credentials.
- `cleo/versioning.py` — Generic `VersionedStore` class (sandbox/promote/rollback/diff). Used by parse, extract, and GeoWarehouse pipelines.

### Ingestion
- `cleo/ingest/session.py` — Authenticated httpx session with Realtrack.com
- `cleo/ingest/scraper.py` — Search submission, result link extraction, search params
- `cleo/ingest/fetcher.py` — Detail page fetch, RT ID extraction from HTML
- `cleo/ingest/tracker.py` — `IngestTracker` class managing `data/seen_rt_ids.json`
- `scripts/full_scan.py` — Bulk download script for closing the ingestion gap

### Parsing
- `cleo/parse/parsers/build_transaction_context.py` — **The most important file.** Main orchestrator that calls 27 individual parsers and produces a `TransactionContext` dataclass. Contains all dataclass definitions, address range expansion, c/o routing logic, and company vs person detection.
- `cleo/parse/engine.py` — Core parse loop (HTML dir -> JSON dir)
- `cleo/parse/versioning.py` — Parse-specific versioning (wraps VersionedStore)
- `cleo/parse/diff_report.py` — CLI diff formatting

### Validation
- `cleo/validate/html_checks.py` — 14 HTML-level checks (H001-H014) with `FLAG_DEFS` dict
- `cleo/validate/runner.py` — HTML check runner, flag I/O, determinations I/O
- `cleo/validate/parse_checks.py` — 10 parse-level checks (P001-P010) with `PARSE_FLAG_DEFS`
- `cleo/validate/parse_runner.py` — Parse check runner, cross-reference with HTML flags

### Address extraction & geocoding
- `cleo/extract/engine.py` — Extraction loop: parsed JSON -> geocodable address expansions
- `cleo/extract/address_expander.py` — Compound address expansion, PO Box/legal description detection
- `cleo/extract/versioning.py` — Extract-specific versioning (wraps VersionedStore)
- `cleo/geocode/cache.py` — `GeocodeCache` class (address -> lat/lng)
- `cleo/geocode/client.py` — Mapbox batch geocoding client
- `cleo/geocode/collector.py` — Collects geocodable addresses from extracted data, applies overrides
- `cleo/geocode/here_client.py` — HERE geocoding client (alternative provider)
- `cleo/geocode/runner.py` — Geocoding orchestrator
- `cleo/geocode/index.py` — Address index builder

### Property & party registries
- `cleo/properties/registry.py` — Build/update property registry, dedup by (address, city), stable P-IDs, geocode backfill
- `cleo/properties/normalize.py` — Address/city normalization for deduplication
- `cleo/parties/registry.py` — Union-find clustering of companies, stable G-IDs, manual override support
- `cleo/parties/normalize.py` — Name/phone/address normalization
- `cleo/parties/auto_confirm.py` — Auto-confirmation of party names
- `cleo/parties/suggestions.py` — Suggested affiliations and grouping reasons

### GeoWarehouse integration
- `cleo/geowarehouse/ingest.py` — Copy GW HTML files from browser extension
- `cleo/geowarehouse/parser.py` — Parse GW property detail pages (BeautifulSoup, stable HTML `id` attrs)
- `cleo/geowarehouse/engine.py` — GW parse loop, dedup by PIN, GW-ID assignment
- `cleo/geowarehouse/address.py` — MPAC address parser: splits GW property addresses into street/city/province/postal components
- `cleo/geowarehouse/match.py` — Match GW records to property registry

### CRM integration
- `cleo/web/crm.py` — FastAPI router at `/api/crm/*` for contacts enrichment and deal tracking (stages: lead, contacted, negotiating, under_contract, closed_won, closed_lost)

### Web app & frontend
- `cleo/web/app.py` — FastAPI app with ~55 API endpoints (review UI + front-facing app + CRM)
- `cleo/web/static/index.html` — Three-column review interface (HTML | Active | Sandbox)
- `cleo/web/static/pipeline.html` — Four-column pipeline inspector (HTML | Parsed | Extracted | Geocoded)
- `frontend/src/App.tsx` — React SPA router: Dashboard, Transactions, Properties, Parties, Contacts, Brands, Map, CRM (Contacts + Deals), Admin

## Data Layout

```
data/
  html/{RT_ID}.html          — ~15,806 raw HTML files from Realtrack
  seen_rt_ids.json           — Master tracker: {rt_id: timestamp}
  html_flags.json            — HTML validation results (flagged records only)
  parse_flags.json           — Parse validation results (flagged records only)
  reviews.json               — Human review determinations + field overrides
  determinations.json        — CLI-based HTML review determinations
  extract_reviews.json       — Extraction review determinations
  parsed/
    sandbox/                 — Temporary staging for new parse output
    v001/ through v014/      — Immutable version snapshots
    active -> v014           — Symlink to current active version
  extracted/
    v001/ through v007/      — Versioned address extractions
    active -> v007
  gw_html/                   — GeoWarehouse HTML files (~798 files)
  gw_parsed/
    v001/                    — GeoWarehouse parsed JSON
  geocode_cache.json         — Address -> {lat, lng} cache (~36K entries)
  address_index.json         — Location index linking geocoded addresses to RT IDs
  coordinates.json           — Brand store coordinate data from scrapers
  properties.json            — Canonical property registry (P-IDs, ~19,741 properties)
  parties.json               — Party group registry (G-IDs, ~16,839 groups)
  party_edits.jsonl          — Party edit audit log
  brand_keywords.json        — Brand keyword configuration
  brand_matches.json         — Brand to property linkage (~7,881 matched properties)
  brand_unmatched.json       — Brand locations that didn't match properties (~4,257)
  markets.json               — City population reference
  feedback.json              — User feedback
  geocode_cron.log           — Geocoding audit log with provider disagreement analysis
  crm/
    contacts.json            — CRM contact records
    deals.json               — CRM deal records
    edits.jsonl              — CRM edit audit log
```

## Architecture at a Glance

```
Realtrack.com → [cleo scrape] → data/html/*.html
                                      ↓
                               [cleo validate] → data/html_flags.json
                                      ↓
                            [cleo parse --sandbox] → data/parsed/sandbox/
                                      ↓
                             [cleo parse --diff] → regression check
                                      ↓
                           [cleo parse --promote] → data/parsed/v00N/
                                      ↓
                             [cleo parse-check] → data/parse_flags.json
                                      ↓
                                [cleo web] → data/reviews.json
                                      ↓
                          [cleo extract --sandbox] → data/extracted/sandbox/
                                      ↓
                          [cleo extract --promote] → data/extracted/v00N/
                                      ↓
                              [cleo geocode] → data/geocode_cache.json
                                      ↓
                        [cleo geocode --build-index] → data/address_index.json
                                      ↓
                            [cleo properties] → data/properties.json
                                      ↓
                              [cleo parties] → data/parties.json
                                      ↓
                          [cleo web] → Front-facing React SPA at /app/*

GeoWarehouse (parallel):
  [cleo gw-ingest] → [cleo gw-parse] → [cleo gw-match] → properties.json
```

## Conventions

- **RT IDs:** Strings like "RT196880" (variable length digits after "RT")
- **Property IDs:** P-prefixed, 5-digit (`P00001`, `P00002`, ...)
- **Party IDs:** G-prefixed, 5-digit (`G00001`, `G00002`, ...)
- **GeoWarehouse IDs:** GW-prefixed (`GW00001`, ...)
- All data is JSON on disk — no database
- Versioning uses v001, v002, etc. with an `active` symlink, managed by `VersionedStore`
- Flag IDs: H001-H014 for HTML checks, P001-P010 for parse checks
- Review determinations: `clean`, `bad_source`, `parser_issue`
- Records reviewed as `clean` that change between versions are treated as regressions and block promotion
- Volatile fields are excluded from diffs: `ingest_timestamp`, `html_path`, `skip_index` (parse); `source_version` (extract); `gw_source_file` (GW)

## Dev Server Ports

- **5173** — Vite dev server (`cd frontend && npm run dev`). This is the URL to use for everything in development. It serves the React frontend with hot reload and proxies all `/api/*` requests to the backend.
- **8099** — FastAPI backend (`cleo web`). Runs the API and serves static files in production. Do not use this port directly during frontend development — always go through 5173.
- **In dev, always use `http://localhost:5173`** for both viewing the app and testing API calls.

## Common Tasks

- **Improving a parser:** Edit the relevant file in `cleo/parse/parsers/`, then run `cleo parse --sandbox`, `cleo parse --diff`, review changes, then `cleo parse --promote`
- **Adding a new HTML check:** Add to `FLAG_DEFS` and `check_html()` in `cleo/validate/html_checks.py`
- **Adding a new parse check:** Add to `PARSE_FLAG_DEFS` and `_CHECKS` in `cleo/validate/parse_checks.py`
- **Debugging a parse issue:** Use `cleo inspect RT_ID` to see parsed output alongside raw HTML
- **Updating address extraction:** Edit `cleo/extract/address_expander.py`, then `cleo extract --sandbox`, `--diff`, `--promote`
- **Rebuilding registries:** Run `cleo properties` then `cleo parties` (properties must be built first for party-property cross-referencing)
- **Running the front-facing app (dev):** `cd frontend && npm run dev` (port 5173, proxies to 8099). Backend: `cleo web` in another terminal.
- **Building the front-facing app:** `cd frontend && npm run build` (outputs to `cleo/web/static/app/`)
- **Adding a GeoWarehouse data source:** `cleo gw-ingest`, `cleo gw-parse --sandbox`, `--diff`, `--promote`, `cleo gw-match`
