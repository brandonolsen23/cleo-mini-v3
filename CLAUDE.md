# Cleo Mini V3 — Project Context

## What This Project Is

Cleo Mini V3 is a Python CLI tool and web application for commercial real estate transaction data in Ontario. It ingests data from three sources (Realtrack.com transaction pages, brand store locators, and GeoWarehouse property records), normalizes and expands addresses, geocodes them, harvests parcel boundaries, and builds canonical property and party registries. It provides both a multi-stage review UI for data quality and a front-facing React SPA for exploring the data.

## System Documentation

- `docs/system-guide.md` — Detailed reference for parsing, validation checks, versioning, geocoding, property/party registries, GeoWarehouse integration, and the full API. Note: some sections describe the legacy extract pipeline; the canonical address path is now normalize → expand (see below).
- `docs/cleanup-checklist.md` — Completed pre-geocode gate checklist (March 1, 2026). All items done. Kept for reference.

## Frontend Styling

- `frontend/STYLING.md` — **Read this before writing any frontend component.** Defines the complete design system: typography weights (400/500 only, never 700), color tokens (Radix --gray-N, never hardcoded hex), card patterns, spacing scale, and how to change the accent color. All rules are mandatory — no ad-hoc styles.

## Strategy Documents

- `docs/pipeline-with-parcelled.md` — **The authoritative pipeline reference.** Mermaid flowcharts showing all four data sources (Realtrack, Brands, GeoWarehouse, OSM POIs), the full 8-stage pipeline (Parse → Normalize → Expand → Geocode → Parcelled → Compile), resolution priority chain, source ID schemes, and compiled record assembly. Read this first to understand the system architecture.
- `docs/pipeline-flowchart.md` — Older pipeline flowchart (pre-parcelled/compiled stages). Superseded by `pipeline-with-parcelled.md` but kept for reference.
- `docs/pipeline-stages-strategy.md` — **Read this before making changes to any pipeline stage.** Defines the sandbox/confirm/promote improvement cycle. Stages 1-5 (Parsed, Normalized, Expanded, Geocoded, Parcelled) use versioned stores. Compiled (Stage 6) also versioned. Properties are a read-only grouping layer by ARN.
- `docs/expand-stage-plan.md` — Expand stage design (implemented, v007 active): terminology (alternate vs alias), identity isolation rules, dedup rules per source, multi-parcel transaction handling, matching flow, output structure.
- `docs/strategy-2026-02-25.md` — Overall project strategy and phased plan (Phase 0: normalization → Phase 1: parcels → Phase 2: party grouping → Phase 3: app reorg → Phase 4: integrations). Phase 0 complete. Phase 1 (parcels/parcelled) is in progress.
- `docs/address-normalization-strategy.md` — Phase 0 detailed plan (implemented, v024 active): NormalizedAddress dataclass, three normalization layers (Clean → Standardize → Contextualize), municipality lookup, success criteria.
- `docs/parcel-centric-rebuild-plan.md` — Early architecture plan for parcel-centric rebuild. Partially superseded by the parcelled stage implementation. Kept for reference.

## Key Files to Read (in order of importance)

### Core orchestration
- `cleo/cli.py` — All 41 CLI commands. Start here to understand what the system does.
- `cleo/config.py` — All paths (~80 constants), env vars, credentials.
- `cleo/versioning.py` — Generic `VersionedStore` class (sandbox/promote/rollback/diff). Used by parse, normalize, expand, parcelled, compiled, geocoded, extract, and GeoWarehouse pipelines.

### Ingestion
- `cleo/ingest/session.py` — Authenticated httpx session with Realtrack.com
- `cleo/ingest/scraper.py` — Multi-property-type search (9 types: retail, industrial, multifamily, office, hotel-motel, restaurant-bar, other-bldg, comm-ind-land, res-land, farm, other-land)
- `cleo/ingest/fetcher.py` — Detail page fetch, RT ID extraction from HTML
- `cleo/ingest/tracker.py` — `IngestTracker` managing `data/seen_rt_ids.json` (v2 format: `{RT_ID: {ts, type}}`)
- `cleo/ingest/html_index.py` — `HtmlIndex` class managing `data/html_index.json` (RT ID → subpath lookup for type subdirectories)
- `scripts/full_scan.py` — Bulk download script for closing the ingestion gap

### Parsing
- `cleo/parse/parsers/build_transaction_context.py` — **The most important file.** Main orchestrator that calls 27 individual parsers and produces a `TransactionContext` dataclass. Contains all dataclass definitions, address range expansion, c/o routing logic, and company vs person detection.
- `cleo/parse/engine.py` — Core parse loop (HTML dir -> JSON dir), uses `rglob("*.html")` for type subdirectories
- `cleo/parse/versioning.py` — Parse-specific versioning (wraps VersionedStore)
- `cleo/parse/diff_report.py` — CLI diff formatting

### Validation
- `cleo/validate/html_checks.py` — 14 HTML-level checks (H001-H014) with `FLAG_DEFS` dict
- `cleo/validate/runner.py` — HTML check runner, flag I/O, determinations I/O
- `cleo/validate/parse_checks.py` — 10 parse-level checks (P001-P010) with `PARSE_FLAG_DEFS`
- `cleo/validate/parse_runner.py` — Parse check runner, cross-reference with HTML flags

### Address normalization (canonical path — replaces extract)
- `cleo/normalize/address.py` — **The single normalization path for all addresses.** Source-agnostic. Three entry points: `normalize_from_fields()` (RT property, brands), `normalize_from_string()` (RT party addresses), `normalize_from_mpac()` (GeoWarehouse). Outputs decomposed fields (street_number, street_name, street_suffix, street_direction, unit, unit_type, po_box, city, province, postal_code, category, address_scope).
- `cleo/normalize/engine.py` — Normalize adapter: reads RT parsed + brands + GW, feeds core normalizer, writes versioned output
- `cleo/normalize/municipalities.py` — Official municipality lookup (414 AMO municipalities from `data/municipalities.json`): `is_official()`, `get_canonical()`, `get_info()`
- `cleo/normalize/versioning.py` — VersionedStore at `data/normalized/`

### Address expansion
- `cleo/expand/engine.py` — Reads normalized, splits compound addresses (ranges, ampersands, commas), writes versioned output
- `cleo/expand/expander.py` — Compound splitting logic, canonical string building, skip rules (PO box, legal description, international)
- `cleo/expand/versioning.py` — VersionedStore at `data/expanded/`

### Address extraction (legacy — superseded by normalize + expand)
- `cleo/extract/engine.py` — Legacy extraction loop: parsed JSON -> geocodable address expansions. Use normalize + expand instead.
- `cleo/extract/address_expander.py` — Legacy compound expansion. Superseded by `cleo/expand/expander.py`.
- `cleo/extract/versioning.py` — Legacy versioning (wraps VersionedStore)

### Geocoding
- `cleo/geocode/store.py` — `CoordinateStore`: unified multi-provider coordinate store at `data/coordinates.json` (~50K entries). `best_coords()` returns median of providers. Supports Mapbox, Geocodio, HERE, and scraper results.
- `cleo/geocode/unified_collector.py` — Collects geocodable addresses from RT + GW + brands + buyer/seller with priority tagging
- `cleo/geocode/client.py` — Mapbox batch geocoding client (v6 API, batch limit 50)
- `cleo/geocode/geocodio_client.py` — Geocodio batch client (2,300/day free tier)
- `cleo/geocode/here_client.py` — HERE geocoding client
- `cleo/geocode/cache.py` — Legacy `GeocodeCache` (Mapbox-only, kept for backward compat)
- `cleo/geocode/runner.py` — Geocoding orchestrator
- `cleo/geocode/index.py` — Address index builder

### Parcelled (versioned parcel resolution per source record)
- `cleo/parcelled/engine.py` — Core parcel resolution engine. Reads expanded records, collects ARN/PIN/coords from parsed data, resolves each record through the priority chain (ARN direct → PIN bridge → spatial → none), writes versioned output. Auto-fetches AgMaps token via Playwright headless browser, handles mid-run token expiry with auto-refresh.
- `cleo/parcelled/versioning.py` — VersionedStore at `data/parcelled/`
- `cleo/parcels/resolver.py` — `ParcelResolver`: resolution priority chain (ARN → PIN → coords), lazy-init provincial client, propagates `TokenExpiredError` for auto-refresh
- `cleo/parcels/cache.py` — `ParcelCache`: permanent parcel cache at `data/parcels/parcel_cache.json`, keyed by 20-digit ARN, grows as new parcels are discovered from provincial API
- `cleo/parcels/provincial.py` — Provincial Assessment Parcel client (MPAC via AgMaps token): `query_at_point()`, `query_by_arn()`, `query_by_pin()`, `TokenExpiredError`
- `cleo/parcels/arn.py` — ARN normalization: pad 15-digit to 20-digit provincial format
- `scripts/fetch_agmaps_token.py` — Playwright headless browser automation: opens AgMaps viewer, accepts disclaimer, captures ArcGIS token from network traffic, validates, saves to `.env`

### Compiled (versioned merged records from all pipeline stages)
- `cleo/compiled/engine.py` — Merges data from parsed (bypass: transaction, parties, site, broker), expanded (addresses), coordinates (geocode), and parcelled (parcel resolution) into unified compiled records per source ID. Reads from `parcelled/active/` for parcel data.
- `cleo/compiled/versioning.py` — VersionedStore at `data/compiled/`

### Property & party registries
- `cleo/properties/registry.py` — Build/update property registry, dedup by (address, city), stable P-IDs, geocode backfill, multi-source merge (RT + GW + expanded addresses)
- `cleo/properties/normalize.py` — Address/city normalization for deduplication
- `cleo/parties/registry.py` — Union-find clustering of companies, stable G-IDs, manual override support
- `cleo/parties/normalize.py` — Name/phone/address normalization
- `cleo/parties/auto_confirm.py` — Auto-confirmation of party names
- `cleo/parties/suggestions.py` — Suggested affiliations and grouping reasons

### Parcels (utilities — core resolution is in Parcelled section above)
- `cleo/parcels/client.py` — ArcGIS REST client: bbox spatial queries, UTM/WebMercator math (no pyproj), throttling
- `cleo/parcels/harvester.py` — Property-by-property parcel + zoning queries (municipal ArcGIS)
- `cleo/parcels/store.py` — `ParcelStore`: parcels.json cache, PCL_NNNNN IDs, dedup by (municipality, PIN/ARN)
- `cleo/parcels/spatial.py` — `ParcelIndex`: STRtree for point-in-parcel queries
- `cleo/parcels/registry.py` — Service registry: loads `data/parcels/services.json`, resolves city → ArcGIS endpoint
- `cleo/parcels/registry_builder.py` — Builds parcel registry with dedup and stable IDs
- `cleo/parcels/matcher.py` — Brand POI → parcel → property matching via spatial containment
- `cleo/parcels/enrichment.py` — Writes parcel_id, parcel_pin, zoning_code to properties.json

### GeoWarehouse integration
- `cleo/geowarehouse/ingest.py` — Copy GW HTML files from browser extension
- `cleo/geowarehouse/parser.py` — Parse GW property detail pages (BeautifulSoup, stable HTML `id` attrs)
- `cleo/geowarehouse/engine.py` — GW parse loop, dedup by PIN, GW-ID assignment
- `cleo/geowarehouse/address.py` — MPAC address parser: splits GW property addresses into street/city/province/postal components
- `cleo/geowarehouse/match.py` — Match GW records to property registry

### Google Street View
- `cleo/google/budget.py` — BudgetGuardian: hard limits at 90% of free tier, daily budgets, tamper detection, monthly reset
- `cleo/google/streetview.py` — On-demand fetch: frontend requests image → backend checks cache → fetches from Google if miss → caches to `data/streetview/{prop_id}.jpg`
- `cleo/google/client.py` — Google API client
- `cleo/google/store.py` — Street View metadata store
- `cleo/google/enrichment.py` — Batch enrichment for property registry

### OSM integration
- `cleo/osm/brand_search.py` — Overpass query for all branded POIs in Ontario
- `cleo/osm/client.py` — Overpass API client
- `cleo/osm/matcher.py` — Address-based matching (limited without parcel boundaries)
- `cleo/osm/store.py` — OSM data store

### Operators
- `cleo/operators/crawler.py` — Web crawler for commercial property operator websites
- `cleo/operators/extractor.py` — Claude-powered entity extraction from crawled pages
- `cleo/operators/match.py` — Match operators to property/party registries
- `cleo/operators/registry.py` — Operator registry management

### CRM & outreach
- `cleo/web/crm.py` — FastAPI router at `/api/crm/*` for contacts enrichment and deal tracking
- `cleo/web/outreach.py` — FastAPI router at `/api/outreach/*` for contact lists, CSV export, outcome logging
- `cleo/web/operators.py` — FastAPI router at `/api/operators/*` for operator management

### Web app & frontend
- `cleo/web/app.py` — FastAPI app with ~95 API endpoints (review UI + front-facing app + CRM + operators + outreach + parcels)
- `cleo/web/static/review_shared.css` — Shared CSS for all stage review pages
- `cleo/web/static/review_shared.js` — Shared JS framework (navigation, review panel, regression bar, field rendering)
- `cleo/web/static/review_landing.html` — Review landing page linking to all stage reviewers
- `cleo/web/static/review_parse.html` — Parse review: HTML Source | Active Parsed | Sandbox Parsed
- `cleo/web/static/review_normalize.html` — Normalize review: Parsed Addresses | Active Normalized | Sandbox Normalized
- `cleo/web/static/review_expand.html` — Expand review: Normalized | Active Expanded | Sandbox Expanded
- `cleo/web/static/review_extract.html` — Extract review (legacy): Parsed Source | Active Extracted | Sandbox Extracted
- `cleo/web/static/index.html` — Legacy combined parse+extract review (kept for backward compat)
- `cleo/web/static/pipeline.html` — Four-column pipeline inspector (HTML | Parsed | Extracted | Geocoded)
- `cleo/web/static/party_review.html` — Party clustering review UI

### Front-facing React SPA (`frontend/`)
- `frontend/src/App.tsx` — React SPA router: Dashboard, Properties, PropertyDetail, Transactions, TransactionDetail, Map (lazy-loaded), Trace, Monitor, Admin, Showcase
- `frontend/src/pages/PropertiesPage.tsx` — **Primary property browser.** Wired to `/api/properties/browse`. Debounced text search, City filter, Brand Category filter (10 categories from master CSV), server-side pagination (25/page), 8-column DataTable (Address, City, Owner, Sources, Txns, Tenants, Latest Price, Date). All state in URL params (deep-linkable).
- `frontend/src/pages/PropertyDetailPage.tsx` — **Full property detail.** Wired to `/api/properties/{id}`. Current Owner card (name, contact, phones with copy), Transaction History (expandable cards with seller/buyer/consideration/site), Tenants card (brand name + category badges), Parcel card (ARN, PIN, method, confidence), Site card (SF, area, zoning), All Addresses, Source Records.
- `frontend/src/types/index.ts` — All shared TypeScript types: PropertyBrowseItem, BrowseResponse, FiltersResponse, PropertyDetail, PropertyTransaction, PropertyTenant, PropertyContact, PropertyOwner
- `frontend/src/api/client.ts` — `fetchApi<T>(path, params)`, `mutateApi<T>(path, method, body)`
- `frontend/src/components/ui/` — Reusable components: DataTable (TanStack), SearchToolbar, PageHeader, Pagination, EmptyState, StatCard, SimpleLineChart, StackedBarChart, Sidebar, Header, AppLayout, MiniList
- `frontend/src/lib/theme.ts` — Radix Theme config (accent: jade, gray: slate)
- `frontend/src/lib/utils.ts` — cn(), formatCompact(), formatCurrency(), formatPercent()
- `frontend/STYLING.md` — **Read before writing any component.** WorkOS design system rules.

### Properties browse API (front-facing)
- `GET /api/properties/browse` — Paginated property browsing with filtering. Params: `q` (text search via inverted index), `city`, `category` (brand category), `min_price`, `max_price`, `sort` (latest_sale_date|latest_sale_price|city|transaction_count|relevance), `order` (asc|desc), `page`, `per_page`. Returns `{results, total, page, per_page}`.
- `GET /api/properties/filters` — Available filter values: 625 cities, 10 brand categories (Grocery, QSR, Big-Box Retail, Specialty Retail, Discount Retail, Full-Service, Take-out, Automotive, Financial Services, Fuel). Cached by properties.json mtime.
- `GET /api/properties/{property_id}` — Full property record enriched with brand tenant names and categories. Brand metadata resolved via `_BrandInfoCache` (12,986 BR records from normalized/active, matched to master CSV categories with 13-entry alias table for name variants).
- `GET /api/properties/search` — Text search via inverted index (310K tokens). Returns scored results.
- `GET /api/properties/stats` — Master list metadata (total properties, sources, etc.)

### Brand category system
- Master brand CSV at `~/Library/CloudStorage/OneDrive-CanadianCommercial/00_Prospecting/Master Retail Sheet - All Brands.csv` (137 brands, 10 categories). Referenced via `MASTER_BRANDS_CSV` in config.py.
- Brand metadata is lost at the expand stage (expand only carries address data). The web app resolves it at query time by scanning normalized/active/BR_*.json on first API call (~1.5s, cached in `_BrandInfoCache`).
- 13 brand name aliases handle mismatches between scraped names and CSV names (e.g. "McDonald's" → "mcdonalds", "No Frills" → "nofrills").
- 88/88 scraped brand names matched to categories. All 10 categories appear in the filters dropdown.

## Data Layout

```
data/
  html/{type}/*.html         — ~92,547 raw HTML files across 9 property types
                               (retail/, industrial/, multifamily/, office/, etc.)
  html_index.json            — RT ID → subpath lookup for type subdirectories
  seen_rt_ids.json           — Master tracker: {rt_id: {ts, type}}
  html_flags.json            — HTML validation results (flagged records only)
  parse_flags.json           — Parse validation results (flagged records only)
  reviews.json               — Parse review determinations + field overrides
  determinations.json        — CLI-based HTML review determinations
  municipalities.json        — 414 official Ontario municipalities (AMO source)
  parsed/
    sandbox/                 — Temporary staging for new parse output
    v001/ through v014/      — Immutable version snapshots
    active -> v014           — Symlink to current active version
  normalized/
    sandbox/                 — Staging for normalize output
    v001/ through v024/      — All 3 sources (RT + brands + GW) normalized together
    active -> v024           — ~29,247 records
  expanded/
    sandbox/                 — Staging for expand output
    v001/ through v007/      — Compound-split addresses
    active -> v007           — 29,247 records → ~64,244 address entries
  parcelled/
    sandbox/                 — Staging for parcel resolution output
    v001/                    — Resolved parcels per source record (when promoted)
    active -> v001           — Each record gets: resolved_arn, method, confidence,
                               geometry, centroid, parcel attributes
  compiled/
    v001/ through v002/      — Merged records from all pipeline stages
    active -> v002           — RT: transaction + site + parties + addresses +
                               geocode + parcel. GW/Brand: addresses + geocode + parcel
  extracted/                 — (Legacy — superseded by normalized/ + expanded/)
    v001/ through v007/
    active -> v007
  norm_reviews.json          — Normalize stage review determinations
  expand_reviews.json        — Expand stage review determinations
  extract_reviews.json       — Extract stage review determinations (legacy)
  gw_html/                   — GeoWarehouse HTML files (~798 files)
  gw_parsed/
    v001/                    — GeoWarehouse parsed JSON (448 unique PINs)
  coordinates.json           — Unified multi-provider geocode store (~50K entries)
                               Providers: Mapbox, Geocodio, HERE, scraper
  geocode_cache.json         — Legacy Mapbox-only cache (~36K entries, kept for compat)
  address_index.json         — Location index linking geocoded addresses to RT IDs
  properties.json            — Canonical property registry (P-IDs, ~19,741 properties)
  parties.json               — Party group registry (G-IDs, ~16,839 groups)
  party_edits.jsonl          — Party edit audit log
  brand_keywords.json        — Brand keyword configuration
  brand_matches.json         — Brand to property linkage (~7,881 matched properties)
  markets.json               — City population reference (Wikipedia census data)
  parcels/
    parcel_cache.json        — Permanent provincial parcel cache (keyed by 20-digit ARN,
                               grows as parcels are discovered from provincial API)
    parcels.json             — Municipal parcel boundary cache (PCL_NNNNN IDs)
    services.json            — Municipality → ArcGIS endpoint registry
    matches.json             — Brand POI → parcel matches
    consolidation.json       — Multi-provider parcel consolidation
    property_parcel_index.json — Property → parcel linkage
  parcelled_reviews.json     — Parcelled stage review determinations
  branded_parcels/           — Per-city branded parcel data ({city}.json)
  streetview/                — Cached Street View images ({prop_id}.jpg)
  google_budget.json         — Google API budget tracking (BudgetGuardian)
  footprints/                — Building footprint data and matches
  operators/                 — Operator crawl data, extractions, registry
  crm/
    contacts.json            — CRM contact records
    deals.json               — CRM deal records
    edits.jsonl              — CRM edit audit log
  outreach/
    lists.json               — Outreach contact lists
    outreach_log.json        — Contact outcome tracking
    edits.jsonl              — Outreach edit audit log
  feedback.json              — User feedback
```

## Architecture at a Glance

```
Four sources converge at normalize (three active, OSM planned):

  Realtrack.com ─→ [cleo scrape] ─→ data/html/{type}/*.html
                                           ↓
                                    [cleo parse] ─→ data/parsed/active/
                                           ↓
  Brand APIs ────→ [brands/run.py] ─→ brands/data/*.json ──────────────┐
                                                                       ↓
  GeoWarehouse ──→ [cleo gw-parse] ─→ data/gw_parsed/active/ ─────────┤
                                                                       ↓
                              ┌────────────────────────────────────────┘
                              ↓
                    [cleo normalize] ─→ data/normalized/active/
                              ↓           (all 3 sources, ~29,247 records)
                     [cleo expand] ──→ data/expanded/active/
                              ↓           (compound splitting, ~64,244 addresses)
                     [cleo geocode] ──→ data/coordinates.json
                              ↓           (multi-provider, ~50K entries)
                   [cleo parcelled] ──→ data/parcelled/active/
                              ↓           (ARN/PIN/coords → provincial GIS → parcel)
                    [cleo compile] ───→ data/compiled/active/
                              ↓           (merge: parsed bypass + addresses +
                              ↓            geocode + parcel into one record)
                    [cleo properties] → data/properties.json
                              ↓           (read-only grouping by 20-digit ARN)
                      [cleo web] ────→ Front-facing React SPA at /app/*

Non-address data (price, date, parties, ARN, zoning) from parsed/
bypasses normalize/expand and enters directly at the compile stage.

OSM POIs (planned): enter at parcelled stage with native coords,
skip parse/normalize/expand/geocode. Get OSM_XXXXX IDs.

Parcel resolution priority: ARN direct (high) → PIN bridge (medium)
→ spatial/coords (low) → none. Provincial API is free, token auto-fetched.
```

## Conventions

- **RT IDs:** Strings like "RT196880" (variable length digits after "RT")
- **Property IDs:** P-prefixed, 5-digit (`P00001`, `P00002`, ...)
- **Party IDs:** G-prefixed, 5-digit (`G00001`, `G00002`, ...)
- **GeoWarehouse IDs:** GW-prefixed (`GW00001`, ...)
- **OSM POI IDs:** OSM-prefixed, 5-digit (`OSM_00001`, `OSM_00002`, ...) — planned
- All data is JSON on disk — no database
- Versioning uses v001, v002, etc. with an `active` symlink, managed by `VersionedStore`
- Flag IDs: H001-H014 for HTML checks, P001-P010 for parse checks
- Review determinations: `clean`, `bad_source`, `parser_issue`
- Records reviewed as `clean` that change between versions are treated as regressions and block promotion
- **Parcel IDs:** PCL-prefixed (`PCL_00001`, `PCL_00002`, ...)
- **Brand IDs:** BR-prefixed, 5-digit, version-scoped (`BR_00001`, `BR_00002`, ...)
- Volatile fields are excluded from diffs: `ingest_timestamp`, `html_path`, `skip_index` (parse); `source_version`, `city_status`, `unit_type`, `po_box` (normalize); `source_version` (expand/extract); `gw_source_file` (GW)

## Dev Server Ports

- **5173** — Vite dev server (`cd frontend && npm run dev`). This is the URL to use for everything in development. It serves the React frontend with hot reload and proxies all `/api/*` requests to the backend.
- **8099** — FastAPI backend (`cleo web`). Runs the API and serves static files in production. Do not use this port directly during frontend development — always go through 5173.
- **In dev, always use `http://localhost:5173`** for both viewing the app and testing API calls.

## Common Tasks

- **Improving a parser:** Edit the relevant file in `cleo/parse/parsers/`, then run `cleo parse --sandbox`, `cleo parse --diff`, review changes, then `cleo parse --promote`
- **Improving normalization:** Edit `cleo/normalize/address.py`, then `cleo normalize --sandbox`, `--diff`, review at `/review/normalize`, then `--promote`
- **Improving address expansion:** Edit `cleo/expand/expander.py`, then `cleo expand --sandbox`, `--diff`, review at `/review/expand`, then `--promote`
- **Adding a new HTML check:** Add to `FLAG_DEFS` and `check_html()` in `cleo/validate/html_checks.py`
- **Adding a new parse check:** Add to `PARSE_FLAG_DEFS` and `_CHECKS` in `cleo/validate/parse_checks.py`
- **Debugging a parse issue:** Use `cleo inspect RT_ID` to see parsed output alongside raw HTML
- **Rebuilding registries:** Run `cleo properties` then `cleo parties` (properties must be built first for party-property cross-referencing)
- **Running parcel resolution:** `cleo parcelled --sandbox` resolves all records, `--diff`, `--promote`. Use `--skip-api` for cache-only mode. Auto-fetches AgMaps token via headless browser.
- **Running the compiler:** `cleo compile --sandbox` merges all pipeline outputs, `--diff`, `--promote`
- **Full pipeline re-run:** `cleo normalize --sandbox && cleo normalize --promote` → same for expand → geocode → parcelled → compile → properties
- **Harvesting parcels:** `cleo parcels --build [--limit N]` for municipal ArcGIS, or use `scripts/harvest_city_parcels.py --provincial` for province-wide via AgMaps token
- **Running the front-facing app (dev):** `cd frontend && npm run dev` (port 5173, proxies to 8099). Backend: `cleo web` in another terminal.
- **Building the front-facing app:** `cd frontend && npm run build` (outputs to `cleo/web/static/app/`)
- **Adding a GeoWarehouse data source:** `cleo gw-ingest`, `cleo gw-parse --sandbox`, `--diff`, `--promote`, `cleo gw-match`
- **Scraping new property types:** `cleo scrape --type industrial` (or multifamily, office, etc.). Run `cleo discover-types` to see available types.
