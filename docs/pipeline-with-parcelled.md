# Pipeline Architecture — All Sources Through Parcelled + Compiled

## Full Pipeline Flow

```mermaid
flowchart LR
    subgraph Sources
        RT["Realtrack.com<br/>~92K HTML files"]
        GW["GeoWarehouse<br/>798 HTML files"]
        BR["Brand APIs<br/>94 brands"]
        OSM["OSM Overpass<br/>(planned)"]
    end

    subgraph "Stage 1 — Parse"
        RT -->|"cleo scrape"| HTML["data/html/{type}/*.html"]
        HTML -->|"cleo parse"| PARSED["parsed/active/<br/>15,813 RT records"]
        GW -->|"cleo gw-ingest"| GWHTML["data/gw_html/*.html"]
        GWHTML -->|"cleo gw-parse"| GWPARSED["gw_parsed/active/<br/>448 GW records"]
        BR -->|"brands/run.py"| BRDATA["brands/data/*.json<br/>~14,340 locations"]
    end

    subgraph "Stage 2 — Normalize"
        PARSED -->|address fields| NORM
        GWPARSED -->|address fields| NORM
        BRDATA -->|address fields| NORM
        NORM["cleo normalize<br/>normalized/active/<br/>29,247 records"]
    end

    subgraph "Stage 3 — Expand"
        NORM -->|"cleo expand"| EXP["expanded/active/<br/>29,247 records<br/>~64K address entries"]
    end

    subgraph "Stage 4 — Geocode"
        EXP -->|canonical addresses| GEO["cleo geocode<br/>coordinates.json<br/>47,371 unique addresses"]
    end

    subgraph "Stage 5 — Parcelled"
        direction TB
        EXP -->|"record IDs + source"| PARCEL_ENGINE
        GEO -->|"coords per canonical"| PARCEL_ENGINE
        PARSED -.->|"RT: ARN, PINs"| PARCEL_ENGINE
        GWPARSED -.->|"GW: ARN, PIN"| PARCEL_ENGINE
        OSM -.->|"OSM: coords only<br/>(planned)"| PARCEL_ENGINE

        PARCEL_ENGINE["cleo parcelled<br/>Resolution Engine"]

        PARCEL_ENGINE -->|"ARN direct"| PROV["Provincial GIS API<br/>(AgMaps MapServer)"]
        PARCEL_ENGINE -->|"PIN bridge"| PROV
        PARCEL_ENGINE -->|"Spatial query"| PROV
        PROV -->|"parcel boundary + ARN"| CACHE["parcel_cache.json<br/>(permanent, grows)"]
        CACHE --> PARCELLED["parcelled/active/<br/>29,247+ records<br/>Each has: resolved ARN,<br/>method, geometry, centroid"]
    end

    subgraph "Stage 6 — Compile"
        PARSED -.->|"bypass: transaction,<br/>parties, site, broker,<br/>description, photos"| COMPILER
        EXP -->|"addresses"| COMPILER
        GEO -->|"lat/lng per address"| COMPILER
        PARCELLED -->|"parcel data"| COMPILER

        COMPILER["cleo compile<br/>compiled/active/<br/>29,247+ records"]
    end

    subgraph "Read Layer"
        COMPILER --> PROPS["Properties<br/>(grouped by ARN)"]
    end

    style Sources fill:#f0f0f0,stroke:#999
    style PARCEL_ENGINE fill:#fff3cd,stroke:#ffc107
    style PROV fill:#d1ecf1,stroke:#0c5460
    style CACHE fill:#d4edda,stroke:#155724
    style PARCELLED fill:#d4edda,stroke:#155724
    style COMPILER fill:#cce5ff,stroke:#004085
    style PROPS fill:#e2d5f1,stroke:#6f42c1
```

## Resolution Priority Chain (per record)

```mermaid
flowchart LR
    START["Record from<br/>expanded/active"] --> HAS_ARN{Has ARN?}

    HAS_ARN -->|"RT: 73% have ARN<br/>GW: 98% have ARN<br/>Brand: never<br/>OSM: never"| ARN_LOOKUP["1. ARN Direct<br/>Pad 15→20 digits<br/>Cache lookup → API query"]
    HAS_ARN -->|No| HAS_PIN{Has PIN?}

    ARN_LOOKUP -->|Hit| DONE_HIGH["RESOLVED<br/>confidence: high"]
    ARN_LOOKUP -->|Miss| HAS_PIN

    HAS_PIN -->|"RT: many have PINs<br/>GW: has PIN"| PIN_LOOKUP["2. PIN Bridge<br/>PIN→ARN reverse index<br/>Cache lookup → API query"]
    HAS_PIN -->|No| HAS_COORDS{Has coords?}

    PIN_LOOKUP -->|Hit| DONE_MED["RESOLVED<br/>confidence: medium"]
    PIN_LOOKUP -->|Miss| HAS_COORDS

    HAS_COORDS -->|"All sources have<br/>geocoded coords<br/>(OSM has native coords)"| SPATIAL["3. Spatial<br/>Point-in-polygon query<br/>Provincial API"]
    HAS_COORDS -->|No| NONE

    SPATIAL -->|Hit| DONE_LOW["RESOLVED<br/>confidence: low"]
    SPATIAL -->|Miss| NONE["UNRESOLVED<br/>method: none"]

    style DONE_HIGH fill:#d4edda,stroke:#155724
    style DONE_MED fill:#fff3cd,stroke:#856404
    style DONE_LOW fill:#f8d7da,stroke:#721c24
    style NONE fill:#e2e3e5,stroke:#383d41
```

## What Each Source Carries Into the Parcelled Stage

```mermaid
flowchart TB
    subgraph "Realtrack (15,813 records)"
        RT_IDS["Identifiers from parsed/active:<br/>• ARN (73% of records, 15-digit)<br/>• PINs (from transaction + site)<br/>• Coords (from geocoded canonical)"]
    end

    subgraph "GeoWarehouse (448 records)"
        GW_IDS["Identifiers from gw_parsed/active:<br/>• ARN (98% of records, 15-digit)<br/>• PIN (from registry block)<br/>• Coords (from geocoded canonical)"]
    end

    subgraph "Brand (12,986 records)"
        BR_IDS["Identifiers:<br/>• No ARN (never has one)<br/>• No PIN (never has one)<br/>• Coords (from geocoded canonical)"]
    end

    subgraph "OSM POI (planned)"
        OSM_IDS["Identifiers:<br/>• No ARN<br/>• No PIN<br/>• Coords (native from Overpass,<br/>  no geocoding needed)"]
    end

    RT_IDS --> PARCELLED_ENGINE["Parcelled Engine<br/>Resolution Chain"]
    GW_IDS --> PARCELLED_ENGINE
    BR_IDS --> PARCELLED_ENGINE
    OSM_IDS --> PARCELLED_ENGINE

    PARCELLED_ENGINE --> OUT["parcelled/active/{ID}.json<br/><br/>Every record gets one output:<br/>• resolved_arn (20-digit or empty)<br/>• method (arn_direct/pin_bridge/spatial/none)<br/>• confidence (high/medium/low/null)<br/>• parcel geometry + centroid<br/>• parcel attributes"]
```

## Compiled Record Assembly

```mermaid
flowchart LR
    subgraph "Bypass (RT only)"
        BYPASS["parsed/active/{RT_ID}.json<br/>─────────────────────<br/>transaction: sale_date, price, ARN<br/>consideration: cash, debt, chattels<br/>site: legal desc, area, zoning, sf<br/>seller: name, contact, phones<br/>buyer: name, contact, phones<br/>broker: brokerage, phone<br/>description, photos"]
    end

    subgraph "Address Pipeline (all sources)"
        ADDRS["expanded/active/{ID}.json<br/>─────────────────────<br/>property addresses (canonical)<br/>property_alt addresses<br/>seller/buyer/owner addresses"]
        COORDS["coordinates.json<br/>─────────────────────<br/>lat, lng per canonical<br/>accuracy, provider<br/>formatted_address"]
    end

    subgraph "Parcel Pipeline (all sources)"
        PARCELS["parcelled/active/{ID}.json<br/>─────────────────────<br/>resolved_arn (20-digit)<br/>method, confidence<br/>geometry, centroid<br/>PIN, attributes"]
    end

    BYPASS --> COMPILED
    ADDRS --> COMPILED
    COORDS --> COMPILED
    PARCELS --> COMPILED

    COMPILED["compiled/active/{ID}.json<br/>═══════════════════════<br/>RT: transaction + site + parties +<br/>    addresses + geocode + parcel<br/><br/>GW: addresses + geocode + parcel<br/><br/>Brand: addresses + geocode + parcel<br/><br/>OSM: coords + parcel (planned)"]

    COMPILED --> PROPERTIES["Properties Layer<br/>(read-only grouping by ARN)"]

    style BYPASS fill:#fff3cd
    style ADDRS fill:#d1ecf1
    style COORDS fill:#d1ecf1
    style PARCELS fill:#d4edda
    style COMPILED fill:#cce5ff
    style PROPERTIES fill:#e2d5f1
```

## OSM POI Entry Point (Planned)

OSM POIs skip Parse → Normalize → Expand → Geocode because they already have
coordinates from OpenStreetMap. They enter directly at the Parcelled stage.

```mermaid
flowchart LR
    OVERPASS["Overpass API<br/>All branded/named POIs<br/>in Ontario"] -->|"cleo osm-snapshot"| SNAPSHOT["osm_pois/active/<br/>OSM_00001.json<br/>OSM_00002.json<br/>..."]

    SNAPSHOT -->|"coords only<br/>(no ARN, no PIN)"| PARCELLED["Parcelled Engine<br/>(spatial resolution only)"]

    PARCELLED -->|"Provincial API<br/>point query"| RESULT["parcelled/active/OSM_00001.json<br/>resolved_arn, geometry, centroid"]

    RESULT --> COMPILE["Compiled<br/>compiled/active/OSM_00001.json<br/>source: osm<br/>parcel + brand + coords"]

    COMPILE --> PROPS["Properties<br/>(linked via ARN)"]

    style SNAPSHOT fill:#e8f5e9
    style PARCELLED fill:#fff3cd
    style COMPILE fill:#cce5ff
    style PROPS fill:#e2d5f1
```

## Source ID Schemes

| Source | ID Format | Example | Count |
|--------|-----------|---------|-------|
| Realtrack | RT{digits} | RT100008 | 15,813 |
| GeoWarehouse | GW{5-digit} | GW00001 | 448 |
| Brand | BR_{5-digit} | BR_00001 | 12,986 |
| OSM POI | OSM_{5-digit} | OSM_00001 | (planned) |

All sources converge at the parcelled stage. All get compiled.
All link to properties via the 20-digit ARN.
