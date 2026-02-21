# Cleo Mini V3 — System Guide

## 1. Overview

Cleo Mini V3 is a data ingestion, parsing, and review platform for commercial real estate transactions from [Realtrack.com](https://realtrack.com). It scrapes HTML detail pages for Ontario retail building sales, parses the unstructured HTML into structured JSON, validates both the source data and the parsed output, and provides a web-based review interface for human quality assurance.

### High-Level Architecture

```
Realtrack.com
     |
     v
[cleo scrape / full_scan]    Ingestion: login, search, fetch HTML detail pages
     |
     v
data/html/{RT_ID}.html       Raw HTML archive  (~15,759 files)
data/seen_rt_ids.json         Ingestion tracker
     |
     v
[cleo validate]               HTML validation: 14 checks (H001-H014)
     |
     v
data/html_flags.json          Flagged records (only records with flags stored)
     |
     v
[cleo parse --sandbox]        Parsing: HTML -> structured JSON
     |
     v
data/parsed/sandbox/          Sandbox staging area
     |
     v
[cleo parse-check]            Parse validation: 10 checks (P001-P010)
     |
     v
data/parse_flags.json         Parse-level flags
     |
     v
[cleo parse --diff]           Field-level comparison: sandbox vs active
     |
     v
[cleo parse --promote]        Promote sandbox -> versioned snapshot (v001, v002, ...)
     |
     v
data/parsed/v00N/             Immutable version snapshot
data/parsed/active -> v00N    Symlink to current version
     |
     v
[cleo web]                    Three-column review UI + review storage
     |
     v
data/reviews.json             Human determinations and field overrides
     |
     v
[cleo extract --sandbox]      Address extraction: expand compound addresses
     |
     v
data/extracted/v00N/          Versioned extraction snapshots
data/extracted/active -> v00N
     |
     v
[cleo geocode]                Geocode addresses via Mapbox or HERE API
     |
     v
data/geocode_cache.json       Address -> {lat, lng} lookup cache
     |
     v
[cleo geocode --build-index]  Build address index from cache
     |
     v
data/address_index.json       Location index for map/search
     |
     v
[cleo properties]             Build canonical property registry
     |
     v
data/properties.json          Deduplicated property list (P-IDs)
     |
     v
[cleo parties]                Build party group registry (union-find clustering)
     |
     v
data/parties.json             Clustered party groups (G-IDs)
     |
     v
[cleo web]                    Front-facing React SPA at /app/*
                              Transactions | Properties | Parties |
                              Contacts | Brands | Map

GeoWarehouse (parallel pipeline):
     |
     v
[cleo gw-ingest]              Copy GW HTML from browser extension
     |
     v
[cleo gw-parse --sandbox]     Parse GW property detail pages
     |
     v
[cleo gw-match]               Match GW records to property registry
```

### Project Layout

```
cleo-mini-v3/
  .env                        Credentials and API tokens
  pyproject.toml               Package config (cleo-mini 3.0.0)
  CLAUDE.md                    Project instructions for AI assistants
  cleo/
    __init__.py
    cli.py                     CLI entry point (all commands)
    config.py                  Paths, env vars, credentials
    versioning.py              Generic VersionedStore class (sandbox/promote/diff)
    ingest/
      session.py               Authenticated httpx session
      scraper.py               Search submission, result link extraction
      fetcher.py               Detail page fetch, RT ID extraction
      tracker.py               seen_rt_ids.json management
    validate/
      html_checks.py           14 HTML-level flag definitions + check logic
      runner.py                HTML check runner, flag I/O, determinations
      parse_checks.py          10 parse-level flag definitions + check logic
      parse_runner.py          Parse check runner, flag I/O, cross-reference
    parse/
      engine.py                Core parse loop (HTML dir -> JSON dir)
      versioning.py            Parse-specific versioning (wraps VersionedStore)
      diff_report.py           CLI diff formatting
      parsers/
        build_transaction_context.py   Main orchestrator: HTML -> TransactionContext
        parse_address.py               Address extraction
        parse_address_suite.py         Suite/unit extraction
        parse_city.py                  City/municipality extraction
        parse_sale_details.py          Date and price extraction
        parse_rt.py                    RT number extraction
        parse_arn.py                   Assessment Roll Number extraction
        parse_pin.py                   PIN extraction
        parse_seller.py                Seller name/contact
        parse_seller_alternate_names.py
        parse_seller_phone.py
        parse_seller_address.py
        parse_seller_structured.py     Structured company/contact/address lines
        parse_buyer.py                 Buyer name/contact
        parse_buyer_alternate_names.py
        parse_buyer_phone.py
        parse_buyer_address.py
        parse_buyer_structured.py      Structured company/contact/address lines
        parse_party_identity.py        Company vs person detection, officer titles, aliases
        parse_site.py                  Site area
        parse_site_dimensions.py       Frontage, depth
        parse_site_facts.py            Legal description, zoning, ARN, PIN
        parse_consideration.py         Cash, debt, chattels, chargees
        parse_brokerage.py             Brokerage name and phone
        parse_description.py           Property description text
        parse_photos.py                Photo URLs
        parser_utils.py                Shared parser utilities
    extract/
      engine.py                Address extraction loop (parsed -> geocodable)
      address_expander.py      Compound address expansion, PO Box/legal detection
      versioning.py            Extraction versioning (uses VersionedStore)
    geocode/
      cache.py                 GeocodeCache class (address -> lat/lng)
      client.py                Mapbox batch geocoding client
      here_client.py           HERE geocoding client (alternative)
      runner.py                Geocoding orchestrator
      collector.py             Address collection from extracted data
      index.py                 Address index builder
    properties/
      registry.py              Build/update property registry, geocode backfill
      normalize.py             Address/city normalization for deduplication
    parties/
      registry.py              Union-find clustering, party group registry
      normalize.py             Name/phone/address normalization
      auto_confirm.py          Auto-confirmation of party names
      suggestions.py           Suggested affiliations, grouping reasons
    geowarehouse/
      ingest.py                Copy GW HTML from browser extension
      parser.py                Parse GW property detail pages (BeautifulSoup)
      engine.py                GW parse loop
      address.py               GW-specific address parsing
      match.py                 Match GW records to property registry
    web/
      app.py                   FastAPI app (~50 API endpoints)
      static/
        index.html             Three-column review interface
        pipeline.html          Four-column pipeline inspector
        app/                   Built React SPA (from frontend/)
  frontend/                    React TypeScript SPA source
    package.json
    vite.config.ts
    tailwind.config.js
    src/
      App.tsx                  Router: 6 pages + detail views
      components/
        transactions/          TransactionsPage, TransactionDetailPage
        properties/            PropertiesPage, PropertyDetailPage
        parties/               PartiesPage, PartyDetailPage, SuggestedAffiliates
        contacts/              ContactsPage, ContactDetailPage
        brands/                BrandsPage
        map/                   MapPage (Mapbox GL)
        layout/                AppLayout, Sidebar
        shared/                Reusable components
      api/                     API client modules
      types/                   TypeScript interfaces
      hooks/                   Custom React hooks
  scripts/
    full_scan.py               Bulk download of all missing RT IDs
    build_markets.py           Build markets.json (city population reference)
    party_signal_analysis.py   Party clustering analysis
  data/
    html/                      Raw HTML files (~15,759 files)
    parsed/                    Versioned JSON output
      sandbox/                 Current working parse (temporary)
      v001/ through v011/      Immutable version snapshots
      active -> v011           Symlink to current active version
    extracted/                 Versioned address extractions
      v001/ through v006/
      active -> v006
    gw_html/                   GeoWarehouse HTML files (~798 files)
    gw_parsed/                 GeoWarehouse parsed JSON
      v001/
    seen_rt_ids.json           Master tracker of ingested RT IDs
    html_flags.json            HTML validation results (flagged records only)
    parse_flags.json           Parse validation results (flagged records only)
    reviews.json               Human review determinations and overrides
    determinations.json        HTML-level review determinations (from CLI review)
    extract_reviews.json       Extraction review determinations
    geocode_cache.json         Address -> {lat, lng} cache (~35K+ entries)
    address_index.json         Location index linking geocoded addresses to RT IDs
    properties.json            Canonical property registry (P-IDs)
    parties.json               Party group registry (G-IDs)
    party_edits.jsonl          Party edit audit log
    brand_keywords.json        Brand keyword configuration
    brand_matches.json         Brand to property linkage
    brands/data/               Brand store JSON files
    markets.json               City population reference
    feedback.json              User feedback
  docs/
    system-guide.md            This file
  tests/
```

---

## 2. Configuration & Setup

### Prerequisites

- Python 3.10+
- Virtual environment (`venv`)

### Installation

```bash
cd ~/cleo-mini-v3
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**iCloud path workaround:** The project may live under iCloud Drive (`~/Library/Mobile Documents/com~apple~CloudDocs/...`). A symlink at `~/cleo-mini-v3` pointing to the real iCloud path avoids issues with spaces and long paths. The `html_path` field in parsed JSON will reflect the resolved iCloud path.

### Environment Variables

Create `.env` in the project root:

```
REALTRACK_USER=your_username
REALTRACK_PASS=your_password
MAPBOX_TOKEN=your_mapbox_token
HERE_API_KEY=your_here_api_key
GW_SOURCE_DIR=~/Downloads/GeoWarehouse/gw-ingest-data
```

Loaded automatically by `python-dotenv` on import of `cleo.config`. `REALTRACK_USER`/`REALTRACK_PASS` are prompted interactively if not set. `MAPBOX_TOKEN` and `HERE_API_KEY` are required only for geocoding. `GW_SOURCE_DIR` has a default fallback.

### Config Paths (`cleo/config.py`)

| Constant | Value | Purpose |
|---|---|---|
| `DATA_DIR` | `{project_root}/data` | Root data directory |
| `HTML_DIR` | `data/html` | Raw HTML storage |
| `PARSED_DIR` | `data/parsed` | Versioned parse output |
| `EXTRACTED_DIR` | `data/extracted` | Versioned extraction output |
| `TRACKER_PATH` | `data/seen_rt_ids.json` | Ingestion tracker |
| `EXTRACT_REVIEWS_PATH` | `data/extract_reviews.json` | Extraction review determinations |
| `PROPERTIES_PATH` | `data/properties.json` | Property registry |
| `PARTIES_PATH` | `data/parties.json` | Party group registry |
| `PARTY_EDITS_PATH` | `data/party_edits.jsonl` | Party edit audit log |
| `KEYWORDS_PATH` | `data/brand_keywords.json` | Brand keyword configuration |
| `BRAND_MATCHES_PATH` | `data/brand_matches.json` | Brand-to-property linkage |
| `BRANDS_DATA_DIR` | `brands/data` | Brand store JSON files |
| `MARKETS_PATH` | `data/markets.json` | City population reference |
| `FEEDBACK_PATH` | `data/feedback.json` | User feedback |
| `GEOCODE_CACHE_PATH` | `data/geocode_cache.json` | Geocode cache |
| `ADDRESS_INDEX_PATH` | `data/address_index.json` | Address index |
| `GW_SOURCE_DIR` | env `GW_SOURCE_DIR` | GeoWarehouse HTML source |
| `GW_HTML_DIR` | `data/gw_html` | GeoWarehouse HTML storage |
| `GW_PARSED_DIR` | `data/gw_parsed` | GeoWarehouse parsed output |
| `REALTRACK_BASE` | `https://realtrack.com` | API base URL |

Directories (`HTML_DIR`, `PARSED_DIR`, `EXTRACTED_DIR`) are auto-created on import.

### Dependencies

Defined in `pyproject.toml`:

| Package | Purpose |
|---|---|
| `httpx>=0.27` | HTTP client for Realtrack sessions |
| `beautifulsoup4>=4.12` | HTML parsing |
| `lxml>=5.0` | Fast HTML parser backend |
| `click>=8.1` | CLI framework |
| `python-dotenv>=1.0` | `.env` file loading |
| `fastapi>=0.110` | Review web app |
| `uvicorn>=0.27` | ASGI server for web app |

---

## 3. Data Ingestion

### `cleo scrape`

Fetches the newest page of Realtrack search results (50 records) and saves any new HTML files.

**Workflow:**

1. Load credentials from `.env` (or prompt)
2. Create authenticated `RealtrackSession` (POST to `/?page=login`)
3. GET `/?page=search` to establish server-side session state
4. POST `/?page=results` with `SEARCH_PARAMS` (Retail Buildings, 1996-2026, sorted by date descending, 50 per page)
5. Extract detail page links (`<a class="propAddr" href="?page=details&skip=N">`)
6. For each link, GET `/?page=details&skip=N` and extract RT ID from the last `<font color="#848484">` tag
7. Compare against `IngestTracker` to find new RT IDs
8. Save HTML to `data/html/{RT_ID}.html` for new records
9. Update `data/seen_rt_ids.json` with timestamps

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--delay` | `0.75` | Seconds between detail page requests |

**Search parameters** (`cleo/ingest/scraper.py:SEARCH_PARAMS`):
- Type: `retailBldg` (Retail Buildings)
- Date range: 1996-01-01 to 2026-12-31
- Sort: Registration date descending, then amount descending
- Page size: 50 per page

### `cleo check`

Gap analysis between local data and Realtrack's total.

**Workflow:**

1. Login and submit the same search as `cleo scrape`
2. Extract total result count from pagination JavaScript: `.pagination(15750, {`
3. Compare against local `IngestTracker.count`
4. Report: Realtrack total, local count, gap

**Output example:**

```
Realtrack total:  15,759
Local RT IDs:     15,759
Gap:              0
Perfect - fully synced.
```

### `scripts/full_scan.py`

Bulk download script for closing the gap between local and remote. Iterates through all result pages (50 records each), fetching detail pages for any RT IDs not already tracked.

**Key behaviors:**

- Configurable `START_PAGE` to skip already-verified pages
- `DELAY` of 0.4s between requests
- Saves tracker after each page with new finds
- Stops early when the gap is closed
- Progress logging per page with skip ranges and error counts

**Usage:**

```bash
python scripts/full_scan.py
```

### Data Storage

**`data/html/{RT_ID}.html`** — Raw HTML from Realtrack detail pages. One file per transaction. Filename is the RT ID (e.g., `RT196880.html`).

**`data/seen_rt_ids.json`** — Master tracker of all known RT IDs:

```json
{
  "RT197012": "2026-02-08T09:00:00",
  "RT43746": "2026-02-08T09:00:00"
}
```

Keys are RT IDs, values are ISO timestamps of when they were first seen.

---

## 4. HTML Validation

### `cleo validate`

Runs 14 checks against every raw HTML file in `data/html/`. Each check tests one aspect of the HTML source quality.

**Checks (H001-H014):**

| Flag | Name | Description |
|---|---|---|
| H001 | TAG_MISSING | No `<strong id="address">` tag found |
| H002 | TAG_EMPTY | Address tag found but contains no text |
| H003 | ADDRESS_NO_DIGIT | First address line does not start with a digit |
| H004 | NO_TRANSFEROR | No Transferor(s) section found |
| H005 | NO_TRANSFEREE | No Transferee(s) section found |
| H006 | NO_CITY_MUNICIPALITY | No "City : Municipality" line found in header |
| H007 | NO_PRICE | No dollar amount found in header line |
| H008 | NO_DATE | No date pattern (DD Mon YYYY) found in header line |
| H009 | NO_RT_ID | No RT ID found in last gray font tag |
| H010 | NO_SITE | No Site section found |
| H011 | NO_ARN | No Assessment Roll Number section found |
| H012 | NO_DESCRIPTION | No Description section found |
| H013 | NO_BROKER | No Broker/Agent section found |
| H014 | NO_PHOTOS | No street or aerial photos found |

**Check categories:**

- **Mandatory structure** (H001-H009): Core elements that every detail page should have. Flags here likely indicate a broken or unusual page.
- **Optional sections** (H010-H014): Sections that are commonly present but legitimately absent on some records. Informational.

**Output:**

- `data/html_flags.json` — Only flagged records are stored:

```json
{
  "RT43746": ["H003", "H014"],
  "RT10036": ["H010", "H012"]
}
```

- CLI summary table showing counts per flag, clean/flagged ratio, and determination counts if any exist.

### `cleo review`

Interactive CLI-based review of HTML-flagged records. For each unreviewed flagged record, displays the key HTML sections (address tag, header line, transferor, transferee) and prompts for a determination.

**Options:**

| Flag | Description |
|---|---|
| `--flag` | Filter to a specific flag ID (e.g., `H003`) |

**Determinations:**
- `bad_source` — The HTML itself is defective; not a parser issue.
- Skip — Move to next record without recording a determination.

**Storage:** `data/determinations.json`

```json
{
  "RT43746": {
    "determination": "bad_source",
    "flags": ["H003", "H014"],
    "reason": "Page returned login form instead of data",
    "date": "2026-02-10"
  }
}
```

---

## 5. Parsing Pipeline

### `cleo parse --sandbox`

Parses all HTML files into structured JSON in a sandbox staging area.

**Workflow:**

1. Create `data/parsed/sandbox/` directory (fails if already exists)
2. For each `.html` file in `data/html/`:
   a. Read HTML content
   b. Call `build_transaction_context()` to produce a `TransactionContext`
   c. Write `{RT_ID}.json` to the sandbox directory
3. Report: count parsed, count errors, elapsed time

### Parse Order of Operations

The `build_transaction_context()` function in `cleo/parse/parsers/build_transaction_context.py` is the main orchestrator. It takes raw HTML and produces a complete `TransactionContext` dataclass. The parse order is:

**Phase 1 — Transaction Header:**

1. `parse_address(soup)` — Extract primary address from `<strong id="address">`
2. `expand_address_ranges()` — Expand ranges like "123-127 Main St" to individual addresses
3. `deduplicate_addresses()` — Remove duplicate addresses (case-insensitive)
4. `parse_city(soup)` — Extract city and municipality from "City : Municipality" line
5. `parse_address_suite(soup)` — Extract suite/unit numbers
6. `parse_sale_date_and_price(soup)` — Extract date (DD Mon YYYY) and price ($X,XXX)
7. `parse_rt(soup)` — Extract RT number from gray font tag
8. `parse_arn(soup)` — Extract Assessment Roll Number
9. `parse_pin(soup)` — Extract Property Identification Number(s)

**Phase 2 — Seller (Transferor):**

1. `parse_seller(soup)` — Name and contact from Transferor section
2. `parse_seller_alternate_names(soup)` — Up to 6 alternate names
3. `parse_seller_structured(soup)` — Structured company lines, contact lines, address lines
4. `parse_seller_phone(soup)` — Phone number extraction
5. `parse_seller_address(soup)` — Mailing address extraction
6. `_extract_co_from_address()` — c/o routing (see below)
7. `parse_all_party_identities(soup)` — Enhanced: phones, officer titles, aliases, attention lines

**Phase 3 — Buyer (Transferee):**

Same sequence as seller:
1. `parse_buyer_info(soup)` — Name and contact
2. `parse_buyer_alternate_names(soup)` — Up to 6 alternate names
3. `parse_buyer_structured(soup)` — Structured lines
4. `parse_buyer_phone(soup)` — Phone
5. `parse_buyer_address(soup)` — Address
6. `_extract_co_from_address()` — c/o routing
7. Party identity enrichment (from same `parse_all_party_identities` call)

**Phase 4 — Property & Financial:**

1. `parse_site(soup)` — Site area and units
2. `parse_site_dimensions(soup)` — Frontage, depth, and units
3. `extract_site_facts(soup)` — Legal description, zoning, enhanced PIN/ARN
4. `parse_consideration(soup)` — Verbatim consideration text, then regex extraction of cash, assumed debt, chattels, chargee names
5. `parse_brokerage(soup)` — Brokerage name and phone
6. `parse_description(soup)` — Property description text
7. `parse_photos(soup)` — Photo URLs

### Key Algorithms

**Address range expansion:** Addresses like "123-127 Main St" are expanded to `["123 Main St", "124 Main St", ..., "127 Main St"]` using regex pattern matching on `(\d+)[-–](\d+)\s+([A-Za-z]+)`.

**c/o routing (`_extract_co_from_address`):** When an address contains "c/o" entries, they are routed based on content:
1. c/o + starts with digit (e.g., "c/o 231 Main St") → kept in address, "c/o" prefix stripped
2. c/o + company name (detected by `looks_like_company()`) → routed to `alternate_names`
3. c/o + person name → stripped from address (handled by party identity parser)

**Company vs person detection (`looks_like_company`):** Used to determine if a name is a corporate entity or an individual. Checks for patterns like "Inc", "Ltd", "Corp", "LLP", numbered company names, etc.

**Contact resolution via attention:** If a contact field contains what looks like a company name but an attention line (person name) is available, the attention line replaces the contact.

### Output JSON Structure

Each parsed record is saved as `{RT_ID}.json`. Full structure from `TransactionContext.to_dict()`:

```json
{
  "rt_id": "RT100008",
  "skip_index": 0,
  "html_path": "/path/to/data/html/RT100008.html",
  "ingest_timestamp": "2026-02-10T19:42:28.557756",
  "transaction": {
    "address": {
      "address": "1476 QUEEN ST W",
      "address_suite": "",
      "city": "Toronto",
      "municipality": "Metro Toronto",
      "province": "Ontario",
      "postal_code": "",
      "alternate_addresses": ["1476 QUEEN ST W"]
    },
    "sale_date": "07 May 2014",
    "sale_date_iso": "2014-05-07",
    "sale_price": "$2,090,000",
    "sale_price_raw": "$2,090,000",
    "rt_number": "RT100008",
    "arn": "190402310006300",
    "pins": ["213390367"]
  },
  "transferor": {
    "name": "Junaid Brothers Ltd",
    "contact": "Muhammad Rana",
    "phone": "",
    "address": "2457 Strathmore Cres, Mississauga, Ontario, L5M 5K9",
    "alternate_names": [],
    "company_lines": ["Junaid Brothers Ltd"],
    "contact_lines": ["Muhammad Rana"],
    "address_lines": ["2457 Strathmore Cres", "Mississauga, Ontario", "L5M 5K9"],
    "phones": [],
    "officer_titles": [],
    "aliases": ["JUNAID BROTHERS"],
    "attention": "Muhammad Rana"
  },
  "transferee": {
    "name": "8809143 Canada Inc",
    "contact": "Kenneth Ng",
    "phone": "",
    "address": "126 Simcoe St, Suite 2007, Toronto, Ontario, M5H 4E9",
    "alternate_names": [],
    "company_lines": ["8809143 Canada Inc"],
    "contact_lines": ["Kenneth Ng"],
    "address_lines": ["126 Simcoe St", "Suite 2007", "Toronto, Ontario", "M5H 4E9"],
    "phones": [],
    "officer_titles": [],
    "aliases": ["8809143 CANADA"],
    "attention": "Kenneth Ng"
  },
  "site": {
    "legal_description": "Plan 453 Part Lots 23 & 24 As in Inst No WG-78993",
    "site_area": "0.09",
    "site_area_units": "acres",
    "site_frontage": "",
    "site_frontage_units": "",
    "site_depth": "",
    "site_depth_units": "",
    "zoning": "",
    "pins": "",
    "arn": "19"
  },
  "consideration": {
    "cash": "2090000",
    "assumed_debt": "0",
    "chattels": "",
    "verbatim": "cash:\u00a0$2,090,000\u00a0\u00a0\u00a0\u00a0 assumed/vtb\u00a0debt:\u00a0$0",
    "chargees": []
  },
  "broker": {
    "brokerage": "RE/MAX Vision Realty: Raza Haider Naqi, ...",
    "phone": "416-999-7279"
  },
  "export_extras": {
    "postal_code": "",
    "building_sf": "",
    "additional_fields": {}
  },
  "description": "Retail/Residential Bldg: 3 storey; 4-1bdrm over 4,000 sf retail ...",
  "photos": [
    "http://realtrack.cachefly.net/photos/RT10/RT1000/RT100008/0519_072456.jpg"
  ]
}
```

### Dataclass Definitions

| Dataclass | Key Fields |
|---|---|
| `TransactionContext` | `rt_id`, `skip_index`, `html_path`, `ingest_timestamp`, `transaction`, `transferor`, `transferee`, `site`, `consideration`, `broker`, `export_extras`, `description`, `photos` |
| `TransactionHeader` | `address` (TransactionAddress), `sale_date`, `sale_date_iso`, `sale_price`, `sale_price_raw`, `rt_number`, `arn`, `pins` |
| `TransactionAddress` | `address`, `address_suite`, `city`, `municipality`, `province`, `postal_code`, `alternate_addresses` |
| `PartyInfo` | `name`, `contact`, `phone`, `address`, `alternate_names`, `company_lines`, `contact_lines`, `address_lines`, `phones`, `officer_titles`, `aliases`, `attention` |
| `SiteFacts` | `legal_description`, `site_area`, `site_area_units`, `site_frontage`, `site_frontage_units`, `site_depth`, `site_depth_units`, `zoning`, `pins`, `arn` |
| `Consideration` | `cash`, `assumed_debt`, `chattels`, `verbatim`, `chargees` |
| `BrokerInfo` | `brokerage`, `phone` |
| `ExportExtras` | `postal_code`, `building_sf`, `additional_fields` |

---

## 6. Parse Validation

### `cleo parse-check`

Runs 10 checks against every parsed JSON file in the active version (or sandbox with `--use-sandbox`).

**Checks (P001-P010):**

| Flag | Name | Description |
|---|---|---|
| P001 | MISSING_ADDRESS | No address extracted |
| P002 | MISSING_PRICE | No sale price extracted |
| P003 | MISSING_DATE | No sale date extracted |
| P004 | MISSING_SELLER | No seller name extracted |
| P005 | MISSING_BUYER | No buyer name extracted |
| P006 | MISSING_CITY | No city extracted |
| P007 | SELLER_PHONE_TYPE | Seller phone is dict, not string |
| P008 | BUYER_PHONE_TYPE | Buyer phone is dict, not string |
| P009 | SELLER_ADDRESS_TYPE | Seller address is dict, not string |
| P010 | BUYER_ADDRESS_TYPE | Buyer address is dict, not string |

Checks P001-P006 catch missing core fields. Checks P007-P010 catch type errors where a parser returned a dict instead of a flat string.

**Options:**

| Flag | Description |
|---|---|
| `--use-sandbox` | Check sandbox instead of active version |

**Cross-referencing:** After running parse checks, the results are automatically cross-referenced with HTML flags. For each parse-flagged record, the output notes whether the HTML source is also flagged. This helps distinguish parser bugs (HTML clean, parse flagged) from source data issues (both flagged).

**Output:**

- `data/parse_flags.json` — Only flagged records:

```json
{
  "RT43746": ["P007", "P009"]
}
```

- CLI summary table with per-flag counts, clean/flagged ratios, and cross-reference stats.

**Adding a new parse check:**

1. Add an entry to `PARSE_FLAG_DEFS` in `cleo/validate/parse_checks.py`
2. Add a check function to `_CHECKS` dict
3. Re-run: `cleo parse-check`

---

## 7. Review Workflow

### `cleo web`

Launches the FastAPI web app. Serves both the legacy review interface and the front-facing React SPA.

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--port` | `8099` | Port to run on |
| `--pipeline` | `false` | Open the 4-column pipeline inspector instead |

**Usage:**

```bash
cleo web                       # Review UI at http://localhost:8099
cleo web --pipeline            # Pipeline inspector (HTML | Parsed | Extracted | Geocoded)
# Front-facing app always at http://localhost:8099/app/
```

### Three-Column Interface

The review UI shows three columns side-by-side:

| Column | Content | Source |
|---|---|---|
| HTML Source | Raw HTML rendered in iframe | `data/html/{RT_ID}.html` |
| Active (Verified) | Parsed JSON from current active version | `data/parsed/active/{RT_ID}.json` |
| Sandbox (Unverified) | Parsed JSON from sandbox (if exists) | `data/parsed/sandbox/{RT_ID}.json` |

When both active and sandbox data are present, changed fields are highlighted in the sandbox column.

### Navigation & Filtering

- **Filter dropdown:** All records, All flagged, Reviewed, Unreviewed, or by specific flag ID (H001, P004, etc.)
- **Search box:** Filter by RT ID substring
- **RT ID dropdown:** Jump to any record
- **Prev/Next buttons** or left/right arrow keys
- Counter shows current position in filtered set

### Review Panel

A collapsible panel at the bottom with three sections:

**Determination** (required for review):

| Value | Meaning |
|---|---|
| `clean` | Data looks correct as parsed |
| `bad_source` | The HTML source itself is defective |
| `parser_issue` | Parser extracted data incorrectly |

**Notes:** Free-text field for context.

**Override fields** (optional corrections):

Transaction/Property:
- `address`, `address_suite`, `city`, `municipality`, `postal_code`
- `sale_price`, `sale_date`, `arn`
- `description`, `legal_description`, `site_area`, `zoning`

Seller (Transferor):
- `seller_name`, `seller_contact`, `seller_phone`, `seller_address`
- `seller_alt_names` (comma-separated)

Buyer (Transferee):
- `buyer_name`, `buyer_contact`, `buyer_phone`, `buyer_address`
- `buyer_alt_names` (comma-separated)

Broker/Consideration:
- `brokerage`, `broker_phone`
- `consideration_cash`, `consideration_debt`

### Review Storage

`data/reviews.json`:

```json
{
  "RT100008": {
    "determination": "clean",
    "notes": "",
    "overrides": {},
    "date": "2026-02-10"
  },
  "RT100250": {
    "determination": "clean",
    "notes": "",
    "overrides": {
      "seller_address": "333 Sheppard Ave E, Ste 202, Toronto, Ontario, M2N 3B3"
    },
    "date": "2026-02-10"
  },
  "RT10025": {
    "determination": "parser_issue",
    "notes": "Address includes building title...",
    "overrides": {
      "seller_address": "Wing Hang Bank Building 161-167 Queen's Road, 16th Floor Central, Hong Kong"
    },
    "date": "2026-02-10"
  }
}
```

### How Reviews Feed Into Regression Detection

Records with `"determination": "clean"` are treated as verified. During `cleo parse --diff`, if a clean record's parsed output has changed, it is flagged as a **regression** and blocks promotion (see section 8).

### `cleo inspect`

CLI-based inspection tool for viewing parsed data alongside HTML source.

**Usage:**

```bash
cleo inspect RT100008              # View single record
cleo inspect --flagged             # Walk through parse-flagged records
cleo inspect --flag P004           # Only records with specific parse flag
cleo inspect --random              # Spot-check a random clean record
```

Displays parsed data summary (address, city, sale details, parties) and the raw HTML sections for comparison.

### Web API Endpoints (Review UI)

| Method | Path | Description |
|---|---|---|
| GET | `/` | Serve the review UI |
| GET | `/pipeline` | Serve the pipeline inspector |
| GET | `/app/{path}` | Serve the React SPA (all client routes) |
| GET | `/api/status` | Active version, versions list, sandbox exists |
| GET | `/api/rt-ids` | All RT IDs with flags and review status |
| GET | `/api/html/{rt_id}` | Raw HTML file for iframe |
| GET | `/api/active/{rt_id}` | Parsed JSON from active version |
| GET | `/api/sandbox/{rt_id}` | Parsed JSON from sandbox |
| GET | `/api/flags` | Flag definitions and counts |
| GET | `/api/review/{rt_id}` | Get existing review |
| POST | `/api/review/{rt_id}` | Save review (determination, notes, overrides) |
| GET | `/api/reviews/stats` | Review summary (total, by determination, with overrides) |
| GET | `/api/regressions` | RT IDs of reviewed records changed in sandbox |

See Section 17 for the complete API reference covering all ~50 endpoints.

---

## 8. Versioning & Promotion

### Concepts

All versioned data (parsed JSON, extracted addresses, GeoWarehouse records) is managed through the `VersionedStore` class (`cleo/versioning.py`), which provides a uniform sandbox/promote/rollback/diff workflow:

- **Sandbox:** Temporary staging area for new output. Only one sandbox can exist at a time.
- **Version snapshots:** Immutable directories named `v001`, `v002`, etc. Created when a sandbox is promoted.
- **Active symlink:** `active` is a symlink pointing to the current version directory. All reads go through this symlink.

The `VersionedStore` class is used by three pipelines:
- `data/parsed/` — Parse output (volatile fields: `ingest_timestamp`, `html_path`, `skip_index`)
- `data/extracted/` — Address extractions (volatile field: `source_version`)
- `data/gw_parsed/` — GeoWarehouse records (volatile field: `gw_source_file`)

### Version Naming

Versions are named sequentially: `v001`, `v002`, `v003`, etc. The regex pattern is `^v(\d{3})$`. The next version is always one higher than the highest existing version.

### Sandbox Lifecycle

```
[no sandbox]
     |  cleo parse --sandbox
     v
[sandbox exists]  ←─── all HTML parsed into data/parsed/sandbox/
     |
     ├── cleo parse --diff      → compare sandbox vs active
     ├── cleo parse --promote   → sandbox becomes v00N, active points to it
     └── cleo parse --discard   → sandbox deleted
```

### `cleo parse --diff`

Field-level comparison of sandbox against the active version.

**How it works:**

1. Load every `.json` from both sandbox and active (excluding `_meta.json`)
2. For each record present in both:
   a. Strip **volatile fields** (`ingest_timestamp`, `html_path`, `skip_index`) that change between runs but aren't meaningful
   b. Flatten both dicts to dot-notation keys (e.g., `transaction.address.city`)
   c. Compare flattened values
3. Collect changed fields, samples, and regression data

**Output report:**

```
Compared 15,759 records

  Unchanged:  15,700
  Changed:        59
  New:             0
  Removed:         0

Field changes (top 10):
  transferor.address                                      42
  transferor.alternate_names                               17
  ...

Sample diffs:

  RT100378  ->  transferor.address
    before: '231 Main St, Box 862, Erin, Ontario, N0B 1T0'
    after:  'Box 862, Erin, Ontario, N0B 1T0'
```

**Regression detection:** The diff loads `data/reviews.json` and checks if any record with `determination: "clean"` has changed fields. These are flagged as regressions.

### `cleo parse --promote`

Promotes the sandbox to the next version.

**Workflow:**

1. **Regression check** (unless `--force`):
   - Run diff against active
   - If any clean-reviewed records have changed fields, **block promotion**
   - Print the list of regressed RT IDs and their changed fields
   - Exit with error
2. Rename `sandbox/` to `v00N/`
3. Write `_meta.json` into the new version:
   ```json
   {
     "version": "v005",
     "promoted_at": "2026-02-10T19:52:37.945103",
     "file_count": 15759
   }
   ```
4. Update `active` symlink to point to the new version

**Options:**

| Flag | Description |
|---|---|
| `--force` | Skip regression check and promote anyway |

### `cleo parse --rollback-to vXXX`

Points the active symlink to a specific previous version.

```bash
cleo parse --rollback-to v003
# Active -> v003
```

The rolled-back-to version must exist as a directory in `data/parsed/`.

### `cleo parse --discard`

Deletes the sandbox directory entirely (`shutil.rmtree`).

### `cleo parse --status`

Shows current versioning state:

```
Active version:  v005
All versions:    v001, v002, v003, v004, v005
Sandbox:         (none)
```

---

## 9. CLI Command Reference

All commands are registered under the `cleo` entry point (defined in `pyproject.toml` as `cleo = "cleo.cli:main"`).

### `cleo scrape`

Scrape new transactions from Realtrack.com.

```bash
cleo scrape                    # Default 0.75s delay
cleo scrape --delay 1.5        # Slower, gentler on server
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--delay` | float | `0.75` | Seconds between detail page requests |

### `cleo check`

Compare local RT ID count against Realtrack's total.

```bash
cleo check
```

No options. Requires valid credentials.

### `cleo validate`

Run HTML validation checks on all local HTML files.

```bash
cleo validate
```

No options. Scans every file in `data/html/`, runs 14 checks (H001-H014), saves results to `data/html_flags.json`.

### `cleo review`

Interactively review flagged HTML records (CLI-based).

```bash
cleo review                    # All unreviewed flagged records
cleo review --flag H003        # Only records with H003 flag
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--flag` | string | None | Filter to a specific flag ID |

### `cleo parse`

Manage parsed JSON output with versioned snapshots.

```bash
cleo parse --sandbox           # Parse all HTML -> sandbox
cleo parse --diff              # Compare sandbox vs active
cleo parse --promote           # Promote sandbox -> next version
cleo parse --promote --force   # Promote even with regressions
cleo parse --discard           # Delete sandbox
cleo parse --rollback-to v003  # Point active to v003
cleo parse --status            # Show version info
```

| Option | Type | Description |
|---|---|---|
| `--sandbox` | flag | Parse all HTML into sandbox |
| `--diff` | flag | Compare sandbox vs active |
| `--promote` | flag | Promote sandbox to next version |
| `--discard` | flag | Delete sandbox |
| `--rollback-to` | string | Point active to a specific version |
| `--status` | flag | Show current version info |
| `--force` | flag | Force promote even with regressions |

Exactly one action must be specified (except `--force` which combines with `--promote`).

### `cleo parse-check`

Run parse-level validation checks on parsed JSON.

```bash
cleo parse-check               # Check active version
cleo parse-check --use-sandbox # Check sandbox instead
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--use-sandbox` | flag | False | Check sandbox instead of active version |

### `cleo inspect`

Inspect parsed data alongside HTML source.

```bash
cleo inspect RT100008          # Single record
cleo inspect --flagged         # Walk parse-flagged records
cleo inspect --flag P004       # Only records with specific flag
cleo inspect --random          # Spot-check a random clean record
```

| Option | Type | Default | Description |
|---|---|---|---|
| `RT_ID` | argument | None | Specific RT ID to inspect |
| `--flagged` | flag | False | Walk through parse-flagged records |
| `--flag` | string | None | Filter to a specific parse flag |
| `--random` | flag | False | Show a random clean record |

### `cleo web`

Launch the web app (review UI + front-facing React SPA).

```bash
cleo web                       # Default port 8099
cleo web --port 3000           # Custom port
cleo web --pipeline            # Open pipeline inspector
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--port` | int | `8099` | Port to run on |
| `--pipeline` | flag | False | Open the pipeline inspector |

### `cleo extract`

Manage extracted address data with versioned snapshots. Reads parsed JSON from `parsed/active`, expands compound addresses into geocodable variations, and writes to `extracted/sandbox`.

```bash
cleo extract --sandbox         # Extract addresses -> sandbox
cleo extract --diff            # Compare sandbox vs active
cleo extract --promote         # Promote sandbox -> next version
cleo extract --promote --force # Promote even with regressions
cleo extract --discard         # Delete sandbox
cleo extract --rollback-to v003 # Point active to v003
cleo extract --status          # Show version info
```

| Option | Type | Description |
|---|---|---|
| `--sandbox` | flag | Extract all addresses into sandbox |
| `--diff` | flag | Compare sandbox vs active |
| `--promote` | flag | Promote sandbox to next version |
| `--discard` | flag | Delete sandbox |
| `--rollback-to` | string | Point active to a specific version |
| `--status` | flag | Show current version info |
| `--force` | flag | Force promote even with regressions |

### `cleo geocode`

Geocode extracted addresses using Mapbox or HERE API.

```bash
cleo geocode --status                  # Show cache stats
cleo geocode --dry-run                 # Preview what would be geocoded
cleo geocode --limit 5000              # Geocode up to 5000 new addresses
cleo geocode                           # Geocode all remaining (Mapbox)
cleo geocode --provider here           # Geocode using HERE
cleo geocode --retry-failures          # Re-try previously failed addresses
cleo geocode --build-index             # Build address index from cache
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | flag | False | Show what would be geocoded without calling API |
| `--limit` | int | None | Max addresses to geocode in this run |
| `--retry-failures` | flag | False | Re-try previously failed addresses |
| `--status` | flag | False | Show geocode cache stats |
| `--build-index` | flag | False | Build address index from cache + extracted data |
| `--batch-size` | int | `50` | Addresses per batch API call |
| `--delay` | float | `0.15` | Seconds between batch API calls |
| `--provider` | choice | `mapbox` | Geocoding provider (`mapbox` or `here`) |

### `cleo properties`

Build or update the canonical property registry.

```bash
cleo properties --status       # Show registry stats
cleo properties --dry-run      # Preview without writing
cleo properties                # Build/update the registry
cleo properties --apply-geocodes  # Backfill lat/lng from geocode cache
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--status` | flag | False | Show property registry stats |
| `--dry-run` | flag | False | Preview what would change without writing |
| `--apply-geocodes` | flag | False | Backfill lat/lng from geocode cache |

### `cleo parties`

Build or update the party group registry.

```bash
cleo parties --status          # Show registry stats
cleo parties --dry-run         # Preview without writing
cleo parties                   # Build/update the registry
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--status` | flag | False | Show party registry stats |
| `--dry-run` | flag | False | Preview what would change without writing |

### `cleo auto-confirm`

Auto-confirm party names based on high-confidence signals.

```bash
cleo auto-confirm --dry-run    # Preview what would be confirmed
cleo auto-confirm              # Run auto-confirmation
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--dry-run` | flag | False | Preview without writing |

### `cleo gw-ingest`

Copy GeoWarehouse HTML files into `data/gw_html/`.

```bash
cleo gw-ingest --dry-run      # Preview what would be copied
cleo gw-ingest                 # Copy files
cleo gw-ingest --source-dir /path/to/dir  # Custom source directory
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--source-dir` | path | `GW_SOURCE_DIR` | Source directory of GW HTML files |
| `--dry-run` | flag | False | Show what would be copied |

### `cleo gw-parse`

Manage GeoWarehouse parsed JSON with versioned snapshots. Same sandbox/diff/promote workflow as `cleo parse`.

```bash
cleo gw-parse --sandbox        # Parse all GW HTML -> sandbox
cleo gw-parse --diff           # Compare sandbox vs active
cleo gw-parse --promote        # Promote sandbox -> v001
cleo gw-parse --discard        # Delete sandbox
cleo gw-parse --status         # Show version info
```

| Option | Type | Description |
|---|---|---|
| `--sandbox` | flag | Parse all GW HTML into sandbox |
| `--diff` | flag | Compare sandbox vs active |
| `--promote` | flag | Promote sandbox to next version |
| `--discard` | flag | Delete sandbox |
| `--rollback-to` | string | Point active to a specific version |
| `--status` | flag | Show current version info |
| `--force` | flag | Force promote even with regressions |

### `cleo gw-match`

Match GeoWarehouse records to the property registry.

```bash
cleo gw-match --status         # Show current GW match stats
cleo gw-match --dry-run        # Preview matches
cleo gw-match                  # Apply matches to properties.json
```

| Option | Type | Default | Description |
|---|---|---|---|
| `--status` | flag | False | Show current GW match stats |
| `--dry-run` | flag | False | Preview matches without writing |

### `cleo gw-inspect`

Inspect a single GeoWarehouse parsed record.

```bash
cleo gw-inspect GW00001
```

| Option | Type | Description |
|---|---|---|
| `GW_ID` | argument | GW ID to inspect (e.g. GW00001) |

---

## 10. Data Integrity Safeguards

The system implements multiple layers of protection to ensure data quality:

### 1. HTML Validation Before Parsing

`cleo validate` runs 14 checks against every raw HTML file, catching source data issues before they propagate into parsed output. Flagged records are tracked so reviewers can assess whether problems are in the source or the parser.

### 2. Parse Validation After Parsing

`cleo parse-check` runs 10 checks on the parsed JSON output, catching missing fields and type errors. Cross-references with HTML flags to distinguish parser bugs from source issues.

### 3. Manual Review via Web App

`cleo web` provides a three-column comparison interface where a human reviewer can:
- Compare raw HTML against parsed output
- Mark records as `clean`, `bad_source`, or `parser_issue`
- Apply field-level overrides for known parser deficiencies
- Add notes for context

### 4. Regression Blocking on Promotion

When promoting a sandbox to a new version, `cleo parse --promote` automatically checks if any record previously reviewed as `clean` has changed fields. If regressions exist, promotion is **blocked** until:
- Reviews are updated (changing the determination from `clean`)
- Or `--force` is used to override

This prevents parser changes from silently corrupting verified data.

### 5. Immutable Version Snapshots

Each promoted version (`v001`, `v002`, ...) is an immutable directory with a `_meta.json` recording the version name, promotion timestamp, and file count. Previous versions are never modified.

### 6. Rollback Capability

`cleo parse --rollback-to vXXX` instantly points the active symlink to any previous version, enabling immediate recovery if a promotion introduces problems.

### 7. Sandbox Isolation

New parses always go to a sandbox first. The sandbox must be explicitly promoted or discarded — there is no way to accidentally overwrite the active version. Only one sandbox can exist at a time.

### 8. Ingestion Tracking

`data/seen_rt_ids.json` maintains a complete record of every RT ID ever ingested, with timestamps. This prevents duplicate downloads and enables accurate gap analysis via `cleo check`.

### 9. Volatile Field Exclusion

During diff operations, fields that change between parse runs but carry no semantic meaning (`ingest_timestamp`, `html_path`, `skip_index`) are automatically excluded. This prevents false positives in regression detection.

### 10. Atomic File Writes

All registry saves (`properties.json`, `parties.json`, `brand_keywords.json`) use atomic write patterns: write to a `.tmp` file, then rename. This prevents data corruption from interrupted writes.

### 11. Party Edit Audit Log

Every party group modification (disconnect, merge, confirm, keyword review) is appended to `data/party_edits.jsonl` with timestamps. This provides a complete audit trail of manual changes.

---

## 11. Address Extraction

### `cleo extract --sandbox`

Reads every parsed JSON from `parsed/active` and produces geocodable address expansions. Each record yields:

- **Property addresses:** Primary address + alternate addresses, each expanded via compound address logic
- **Seller address:** Normalized mailing address
- **Buyer address:** Normalized mailing address

**Compound address expansion:** Addresses like "1855 - 1911 DUNDAS ST E" are expanded to individual addresses: `["1855 DUNDAS ST E, Toronto, Ontario", "1911 DUNDAS ST E, Toronto, Ontario"]`. Simple addresses with no range produce a single entry.

**Skip detection:** Addresses identified as PO Boxes or legal descriptions (e.g., "Lot 5 Plan 123") are flagged with `skip_geocode: true` so they are excluded from geocoding.

### Extraction Output JSON

Each extracted record (`data/extracted/active/{RT_ID}.json`):

```json
{
  "rt_id": "RT100008",
  "source_version": "v011",
  "property": {
    "addresses": [
      {
        "original": "1476 QUEEN ST W",
        "expanded": ["1476 QUEEN ST W, Toronto, Ontario"],
        "skip_geocode": false
      }
    ]
  },
  "seller": {
    "original": "2457 Strathmore Cres, Mississauga, Ontario, L5M 5K9",
    "normalized": "2457 Strathmore Cres, Mississauga, Ontario, L5M 5K9"
  },
  "buyer": {
    "original": "126 Simcoe St, Suite 2007, Toronto, Ontario, M5H 4E9",
    "normalized": "126 Simcoe St, Suite 2007, Toronto, Ontario, M5H 4E9"
  }
}
```

### Versioning

Uses the same `VersionedStore` as parse output: sandbox, diff, promote, rollback. Volatile field: `source_version`. Reviews stored in `data/extract_reviews.json`.

---

## 12. Geocoding

### `cleo geocode`

Geocodes addresses from extracted data using external APIs.

**Workflow:**

1. Collect all unique geocodable addresses from `extracted/active` (skipping `skip_geocode` entries)
2. Apply any address overrides from `extract_reviews.json`
3. Check which addresses are already in `geocode_cache.json`
4. If `--dry-run`, report stats and exit
5. Send uncached addresses to the API in batches
6. Store results in cache, save periodically

### Providers

**Mapbox (default):**
- API: Mapbox Geocoding v6, batch forward geocode
- Batch limit: 50 addresses per request
- Requires `permanent=true` for storage
- Free tier: 100K requests/month
- Default delay: 0.15s between batches

**HERE (alternative):**
- API: HERE Geocoding & Search
- Rate limit: ~5 requests/sec
- Default delay: 0.22s between batches
- Set `HERE_API_KEY` in `.env`

### Geocode Cache (`data/geocode_cache.json`)

A flat JSON dict keyed by uppercase address string:

```json
{
  "1476 QUEEN ST W, TORONTO, ONTARIO": {
    "lat": 43.6389,
    "lng": -79.4335,
    "formatted_address": "1476 Queen Street West, Toronto, ON M6K 1M1",
    "accuracy": "rooftop",
    "match_code": {"confidence": "exact"},
    "provider": "mapbox"
  },
  "INVALID ADDRESS": {
    "failed": true,
    "fail_reason": "No results"
  }
}
```

### Address Index (`data/address_index.json`)

Built by `cleo geocode --build-index`. Links geocoded locations to RT IDs and their party roles. Used by the map page in the front-facing app.

---

## 13. Property Registry

### `cleo properties`

Builds a canonical, deduplicated property registry from parsed transaction data.

**Deduplication key:** Normalized `(address, city)`. Normalization uppercases, strips punctuation, and collapses whitespace.

**Stable IDs:** Properties are assigned `P`-prefixed IDs (`P00001`, `P00002`, ...) that remain stable across rebuilds. Existing properties keep their IDs; only new properties get new IDs.

**Merge behavior:**
- On rebuild, existing entries are updated with new RT IDs but preserve manual edits
- Compound address matching: If extracted data expands "1855-1911 DUNDAS ST E" into sub-addresses, and "1855 DUNDAS ST E" already exists as a standalone property, the compound transaction's RT ID is merged into that property
- Manually added properties (from GeoWarehouse or other sources) are preserved

### Property Registry (`data/properties.json`)

```json
{
  "meta": {
    "built": "2026-02-15T20:28:00",
    "source_dir": "v011",
    "total_properties": 12413,
    "total_transactions_linked": 15759,
    "multi_transaction_properties": 2476
  },
  "properties": {
    "P00001": {
      "address": "1476 QUEEN ST W",
      "city": "Toronto",
      "municipality": "Metro Toronto",
      "province": "Ontario",
      "postal_code": "M6K 1M1",
      "lat": 43.6389,
      "lng": -79.4335,
      "rt_ids": ["RT100008", "RT150234"],
      "transaction_count": 2,
      "sources": ["rt"],
      "gw_ids": [],
      "created": "2026-02-10",
      "updated": "2026-02-15"
    }
  }
}
```

### Geocode Backfill

`cleo properties --apply-geocodes` backfills `lat`/`lng` coordinates from the geocode cache into properties that don't have them yet. Matching strategies:
1. Direct match on normalized (address, city)
2. RT ID lookup via extracted expanded addresses

---

## 14. Party Registry

### `cleo parties`

Clusters related companies and individuals via union-find, producing a party group registry.

**Clustering rules (all transitive via union-find):**

1. **Same normalized name** (non-numbered companies only). Normalizes by uppercasing, stripping suffixes (Inc, Ltd, Corp), and collapsing whitespace.
2. **Same phone number.** Phones with high fan-out (15+ distinct names) are restricted to same-contact-within-phone matching.
3. **Same filtered alias / alternate name.** Aliases are filtered to exclude law firm names, office building addresses, trivial suffixes, and purely numeric strings.
4. **Same normalized address** (companies only, min 10 chars). Connects entities sharing a mailing address.
5. **Numbered company + same contact.** For entities like "1195117 Ontario Ltd" that can't cluster on name, clusters when they share a contact person.

**Company detection heuristic:** Names containing keywords like "Inc", "Ltd", "Corp", "REIT", "Holdings", etc., or starting with 4+ digits, are classified as companies. Names with 2-3 alpha words are classified as people.

**Stable IDs:** Groups are assigned `G`-prefixed IDs (`G00001`, `G00002`, ...) that persist across rebuilds via normalized name matching.

### Party Registry (`data/parties.json`)

```json
{
  "meta": {
    "built": "2026-02-15T20:28:00",
    "source_dir": "v011",
    "total_groups": 8451,
    "total_company_groups": 6234,
    "total_person_groups": 2217,
    "total_appearances": 15759
  },
  "parties": {
    "G00001": {
      "display_name": "Choice Properties REIT",
      "display_name_override": "",
      "is_company": true,
      "names": ["Choice Properties Limited Partnership", "Choice Properties REIT"],
      "normalized_names": ["choice properties limited partnership", "choice properties reit"],
      "addresses": ["22 St Clair Ave E, Suite 700, Toronto, ON"],
      "contacts": ["Mario Barrafato"],
      "phones": ["(416) 628-7872"],
      "aliases": ["CHOICE PROPERTIES"],
      "alternate_names": [],
      "appearances": [...],
      "transaction_count": 145,
      "buy_count": 87,
      "sell_count": 58,
      "first_active_iso": "2013-05-01",
      "last_active_iso": "2025-12-15",
      "rt_ids": ["RT100880", ...],
      "created": "2026-02-10",
      "updated": "2026-02-15"
    }
  },
  "overrides": {
    "display_name": {"G00001": "Choice Properties REIT"},
    "url": {"G00001": "https://www.choicereit.ca"},
    "confirmed": {"G00001": ["choice properties limited partnership", "choice properties reit"]},
    "merge": [["G00001", "G02654"]],
    "splits": [{"source": "G00500", "normalized_name": "abc realty", "target": "G09001", ...}],
    "dismissed_suggestions": {"G00001": ["G03200"]}
  }
}
```

### Manual Overrides (Preserved on Rebuild)

- **Display name:** Override the auto-selected display name
- **URL:** Associate a website URL with a party group
- **Confirmed:** Mark specific name variants as confirmed members of the group
- **Merges:** Manually merged group pairs (replayed on rebuild)
- **Splits:** Manually disconnected names (replayed on rebuild)
- **Dismissed suggestions:** Suppressed affiliate suggestions

### `cleo auto-confirm`

Auto-confirms party names using high-confidence signals:

1. **Single-name groups:** The only name IS the group — no ambiguity
2. **Alias match:** Transaction-data alias matches the group display name
3. **Shared phone:** Names sharing a phone number within the group (transitive)
4. **Shared contact:** Names sharing a contact person within the group (transitive)

---

## 15. GeoWarehouse Integration

GeoWarehouse (via MPAC) provides property assessment data that enriches the Realtrack transaction registry.

### Pipeline

```
Browser extension saves HTML  →  ~/Downloads/GeoWarehouse/gw-ingest-data/
     |
[cleo gw-ingest]              →  data/gw_html/  (~798 files)
     |
[cleo gw-parse --sandbox]     →  data/gw_parsed/sandbox/
     |                             BeautifulSoup parser using stable HTML id attrs
     |                             Dedup by PIN, GW-ID assignment (GW00001+)
     |
[cleo gw-parse --promote]     →  data/gw_parsed/v001/
     |
[cleo gw-match]               →  data/properties.json (enriched)
                                   Matched: GW records linked to existing properties
                                   Unmatched: New properties created (source: "gw")
                                   Postal codes backfilled from GW data
```

### Key Behaviors

- **Parser:** Uses stable HTML `id` attributes from GeoWarehouse pages (e.g., `id="propertyAddress"`, `id="municipality"`). No fragile CSS/class selectors.
- **Deduplication:** Multiple HTML files for the same property (same PIN) are deduplicated; only the latest version is kept.
- **Non-detail pages:** Pages that aren't property detail pages (search results, collaboration pages) are automatically skipped.
- **Matching:** GW records are matched to the property registry by normalized (address, city) dedup keys. Matched properties receive `gw_ids` links and postal code enrichment.

### Versioning

Uses `VersionedStore` with `volatile_fields={"gw_source_file"}`.

---

## 16. Front-Facing Web App

The front-facing app is a React SPA served at `/app/*` on the same FastAPI server as the review interface.

### Technology Stack

- React 18 + TypeScript 5.7
- Vite 6 (build tooling)
- React Router 7 (client-side routing)
- Tailwind CSS 3.4 (styling)
- TanStack Table 8 + Virtual 3 (data tables with virtualization)
- Mapbox GL 3 + react-map-gl 8 (mapping)
- lucide-react (icons)

### Pages

| Route | Page | Description |
|---|---|---|
| `/app/transactions` | TransactionsPage | Sortable/filterable table of all transactions |
| `/app/transactions/:rtId` | TransactionDetailPage | Full transaction detail |
| `/app/properties` | PropertiesPage | Property registry table |
| `/app/properties/:propId` | PropertyDetailPage | Property detail with transaction history, GW data |
| `/app/parties` | PartiesPage | Party group table |
| `/app/parties/:groupId` | PartyDetailPage | Party detail with names, appearances, suggestions |
| `/app/contacts` | ContactsPage | Individual contacts index |
| `/app/contacts/:contactId` | ContactDetailPage | Contact detail with appearances |
| `/app/brands` | BrandsPage | Brand store locations with property linkage |
| `/app/map` | MapPage | Mapbox visualization of properties (lazy-loaded) |

### Development

```bash
cd frontend && npm run dev    # Dev server on port 5173, proxies /api to 8099
cd frontend && npm run build  # Build to cleo/web/static/app/
```

The dev server (`npm run dev`) proxies API requests to the FastAPI backend at port 8099. For production, the built assets are served directly by FastAPI.

---

## 17. Full API Reference

All endpoints are served by the FastAPI app (`cleo/web/app.py`) on port 8099 (default).

### Status & Metadata

| Method | Path | Description |
|---|---|---|
| GET | `/api/status` | Active versions, sandbox status for parse and extract |
| GET | `/api/rt-ids` | All RT IDs with HTML/parse flags and review status |
| GET | `/api/flags` | Flag definitions (HTML + parse) and counts |

### Transactions (Front-Facing App)

| Method | Path | Description |
|---|---|---|
| GET | `/api/transactions` | Summary list of all transactions (cached per active version) |

Returns: `[{rt_id, address, city, municipality, population, sale_price, sale_date, sale_date_iso, seller, buyer, has_photos, brands}]`

### Properties (Front-Facing App)

| Method | Path | Description |
|---|---|---|
| GET | `/api/properties` | Property registry as summary list (cached by mtime) |
| GET | `/api/properties/{prop_id}` | Full detail: property + linked transactions + GW records + brands |

### Parties (Front-Facing App)

| Method | Path | Description |
|---|---|---|
| GET | `/api/parties` | Party groups as summary list (cached by mtime) |
| GET | `/api/parties/known-attributes` | Phone/contact/address lookup for confirmed groups |
| GET | `/api/parties/{group_id}` | Full party detail: names, appearances, linked properties |
| POST | `/api/parties/{group_id}` | Save display name / URL overrides |
| POST | `/api/parties/{group_id}/disconnect` | Split a name from a party group |
| POST | `/api/parties/{group_id}/confirm` | Mark a name as confirmed in the group |
| GET | `/api/parties/{group_id}/suggestions` | Suggested affiliate groups |
| GET | `/api/parties/{group_id}/grouping-reason` | Explain why a name is in this group |
| POST | `/api/parties/{group_id}/merge` | Merge another group into this one |
| POST | `/api/parties/{group_id}/dismiss-suggestion` | Dismiss a suggested affiliate |

### Contacts (Front-Facing App)

| Method | Path | Description |
|---|---|---|
| GET | `/api/contacts` | All contacts as summary list (cached per active version) |
| GET | `/api/contacts/{contact_id}` | Full contact detail with appearances and linked party groups |

### Brands (Front-Facing App)

| Method | Path | Description |
|---|---|---|
| GET | `/api/brands` | Brand store locations with property linkage |

### Keywords (Brand Matching)

| Method | Path | Description |
|---|---|---|
| GET | `/api/keywords` | All keywords with match counts and review progress |
| POST | `/api/keywords` | Add a new keyword |
| DELETE | `/api/keywords/{keyword}` | Remove a keyword and its reviews |
| GET | `/api/keywords/{keyword}/matches` | Party groups matching the keyword |
| POST | `/api/keywords/{keyword}/review/{group_id}` | Review a keyword match (confirmed/denied) |

### Review Interface (Legacy)

| Method | Path | Description |
|---|---|---|
| GET | `/api/html/{rt_id}` | Raw HTML source for iframe |
| GET | `/api/active/{rt_id}` | Parsed JSON from active version (with brands) |
| GET | `/api/sandbox/{rt_id}` | Parsed JSON from sandbox |
| GET | `/api/review/{rt_id}` | Get existing review determination |
| POST | `/api/review/{rt_id}` | Save review (determination, notes, overrides) |
| GET | `/api/reviews/stats` | Review summary stats |
| GET | `/api/regressions` | RT IDs of reviewed records changed in sandbox |

### Extraction & Geocoding

| Method | Path | Description |
|---|---|---|
| GET | `/api/extracted/{rt_id}` | Extracted addresses from active version |
| GET | `/api/extract-sandbox/{rt_id}` | Extracted addresses from sandbox |
| GET | `/api/extract-changes` | RT IDs where extraction sandbox differs from active |
| GET | `/api/extract-changes/clear-cache` | Clear extraction diff cache |
| GET | `/api/extract-status` | Extraction version info |
| GET | `/api/extract-address-issues` | Address quality issue categories |
| GET | `/api/extract-review/{rt_id}` | Get extraction review |
| POST | `/api/extract-review/{rt_id}` | Save extraction review |
| GET | `/api/extract-regressions` | Extraction-reviewed records changed in sandbox |
| GET | `/api/geocoded/{rt_id}` | Geocode results for an RT ID's addresses |
| GET | `/api/geocode-status` | Geocode cache statistics |

### Feedback

| Method | Path | Description |
|---|---|---|
| GET | `/api/feedback/{entity_id}` | Get feedback for a transaction or property |
| POST | `/api/feedback/{entity_id}` | Save feedback (has_issue, notes) |
