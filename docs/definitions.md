# Cleo — Definitions Dictionary

> Canonical reference for all terminology used in Cleo. Every module, UI label, API route,
> variable name, and conversation between team members should use these terms consistently.
> When in doubt, defer to this document.
>
> Last updated: 2026-03-05

---

## System Architecture

### Data Engine

The backend processing system that ingests, normalizes, and enriches real estate data. Replaces the former use of "pipeline" for data processing. The Data Engine runs data through a series of **stages**, each with versioned stores (sandbox/promote/rollback).

**Stages** (in order):
1. **Parse** — Raw HTML to structured JSON
2. **Normalize** — Source-agnostic address decomposition
3. **Expand** — Compound address splitting
4. **Geocode** — Multi-provider coordinate resolution
5. **Parcelled** — Provincial parcel resolution (ARN/PIN/spatial)
6. **Compile** — Merge all stage outputs into unified records

The Data Engine produces **Compiled Records** — the single source of truth for all downstream layers.

### Compiled Record

A single unified JSON record that merges all Data Engine stage outputs for one source record. Contains transaction details, addresses, geocode coordinates, and parcel data. Identified by a **source_id** (RT196880, BR_00001, GW00001, OSM_00001). Compiled Records are versioned (v001, v002, etc.) and are the foundation that all Views and CRM data derive from.

### Source

The origin system that a record came from. Four active sources:
- **Realtrack** — Transaction data from Realtrack.com
- **Brand** — Store locator data from commercial brand websites
- **GeoWarehouse** — MPAC property assessment records
- **OSM** — OpenStreetMap branded POI data

### Source ID

The unique identifier for a record within its source. Format varies by source:
- Realtrack: `RT` + digits (e.g. `RT196880`)
- Brand: `BR_` + 5 digits (e.g. `BR_00001`)
- GeoWarehouse: `GW` + 5 digits (e.g. `GW00001`)
- OSM: `OSM_` + 5 digits (e.g. `OSM_00001`)

Use `source_id` as the generic variable name everywhere. Never use `rt_id` as a generic term.

### Version / Versioned Store

An immutable snapshot of stage output (v001, v002, etc.) with an `active` symlink pointing to the current promoted version. The sandbox/promote/rollback cycle is the core mechanism of the Data Engine. Promoting a new version may change the data that downstream layers (Properties, Groups, CRM) rely on — see **Reconciliation**.

---

## Views (Read-Only Data Displays)

Views are pages that display data derived from Compiled Records. They do not create or modify business data — they are windows into the data. Users can navigate from a View into CRM to take action.

### Dashboard

Overview of the entire dataset — summary statistics, recent activity, market insights.

### Properties (View)

Browse and search the property registry. Filterable by city, brand category, price range. Each row links to a Property Detail page showing full transaction history, tenants, parcel info, and current owner.

### Transactions (View)

Browse historical real estate transactions. Every exchange of real estate recorded in the system, regardless of whether you or Jamie are involved.

### Map (View)

Geographic visualization of properties, with layers for parcels, tenants, and transaction activity.

---

## CRM (Business Layer)

CRM is the category of all user-curated business activities. It sits on top of the data produced by the Data Engine and is where prospecting, relationship management, and deal tracking happen. CRM data is **persistent** — it must survive Data Engine rebuilds (see Reconciliation).

### Group

A company, partnership, trust, or individual that participates in real estate transactions — buying, selling, leasing, or owning property. Replaces the former terms "entity", "party", and "owner" (as a noun for the concept).

Examples: RioCan REIT, Goldmanco, an individual person who buys/sells property.

**ID format:** `GRP_NNNNN` (e.g. `GRP_00001`)

A Group is identified by one or more **known names** — the various legal names, trade names, and registration names that appear across transactions. These names are linked together manually to form a single Group.

A Group can be an **Owner** of one or more properties (see Owner below). But "Group" is the entity; "Owner" is the role.

Maps to HubSpot: **Companies**

### Contact

An individual person. Period. There is one unified Contact list in the system. Whether someone appears as a buyer contact on a Realtrack transaction, a seller representative, or someone you cold-called — they are one Contact.

**ID format:** `CON_NNNNN` (e.g. `CON_00001`)

Contacts are associated with Groups. A Contact can move between Groups over time (e.g. Derek Hull moved from H&R REIT to Goldmanco). The system tracks the **association history** — which Group a Contact was associated with on which transaction, and whether they are currently active with that Group. Former associations are visually de-emphasized ("formerly with") but never deleted from the underlying data.

Contact types:
| Type | Description |
|---|---|
| Buyer | Acquired property in a transaction |
| Seller | Disposed of property in a transaction |
| Lessee | Leased property |
| Lessor | Leased property to a tenant |
| Agent | Individual real estate sales representative (see Agent definition) |
| Professional | Non-agent professionals — appraisers, lawyers, accountants, etc. |
| Personal | Someone from your personal circle, not from transaction data |

Contact fields (maps to HubSpot):
| Cleo Field | HubSpot Field | Description |
|---|---|---|
| first_name | firstname | First name |
| last_name | lastname | Last name |
| email | email | Email address |
| phone | phone | Primary phone |
| mobile | mobilephone | Mobile phone |
| job_title | jobtitle | Job title |
| company_name | company | Current company (Group display name) |
| address | address | Street address |
| city | city | City |
| province | state | Province/state |
| postal_code | zip | Postal code |
| type | type_of_contact | buyer, seller, lessee, lessor, agent, professional, personal |
| source | — | How this contact entered the system (transaction, manual, import) |

HubSpot is the external CRM. Cleo fields **map to** HubSpot fields — the systems stay in sync, but Cleo uses its own terminology and field names. Cleo is the source of truth for transaction-derived data; HubSpot is the source of truth for manually entered CRM enrichment (notes, email threads, sequences). Sync is bidirectional where fields overlap.

### Deal

A transaction that you or Jamie are actively working on. A Deal associates a Property, one or more Groups, one or more Contacts, and tracks progress through deal stages. Distinct from a **Transaction** (which is a historical fact in the data).

**ID format:** `DEAL_NNNNN` (e.g. `DEAL_00001`)

Deal lifecycle phases:
| Phase | What's happening | HubSpot Stage |
|---|---|---|
| **Prospecting** | Outbound — identifying targets, making connections, stirring things up | Long Shot |
| **Nurturing** | Uncovering deals from what you've stirred up prospecting | Priority Deal / Mandate |
| **Negotiating** | Pushing the most promising opportunities forward — offers, counter-offers | Viable Deal → In Negotiation |
| **Under Contract** | Conditional agreement signed, not yet firm | Under Contract |
| **Firm** | Conditions waived, deal is going to close | Firm |
| **Closed** | Money in the bank, paperwork wrap-up, post-close process | Closed |
| **Lost** | Deal fell through at any stage | Lost |

The phases after Negotiating (Under Contract → Firm → Closed) are **transaction management** — making sure what's been agreed to contractually gets fulfilled. Not a separate category, just the later stages of the same Deal.

Deal fields (maps to HubSpot):
| Cleo Field | HubSpot Field | Description |
|---|---|---|
| name | dealname | Deal name (typically the property address) |
| stage | dealstage | Current stage in the pipeline |
| amount | amount | Expected deal value |
| close_date | closedate | Expected or actual close date |
| deal_owner | hubspot_owner_id | Jamie or Brandon |
| description | description | Deal notes and context |
| next_step | hs_next_step | Next action required |
| priority | hs_priority | Priority level |
| lost_reason | closed_lost_reason | Why the deal was lost |

### Pipeline

The progression of Deals through lifecycle phases. "Fill the pipeline", "load the boat", "pipeline is drying up" — this always refers to the **sales pipeline** of active Deals, never the Data Engine.

The pipeline has a natural flow: **Prospecting → Nurturing → Negotiating → Under Contract → Firm → Closed**. Deals move forward (or fall out as Lost) through these phases.

### List

A saved, named collection of Properties, Groups, and/or Contacts for a specific purpose — typically prospecting campaigns. Used to organize outreach targets.

**ID format:** `LST_NNNNN` (e.g. `LST_00001`)

### Prospecting

The activity of identifying and reaching out to potential deal opportunities. Replaces the former term "outreach." Prospecting turns discoveries from Views into potential Deals in the Pipeline.

### Connection

A logged interaction with a Contact or Group. "How many connections did you make today?" Replaces the former overloaded use of "contact" as a verb. Each Connection is a record of a phone call, email, meeting, or other touchpoint.

**ID format:** `CXN_NNNNN` (e.g. `CXN_00001`)

---

## Property & Parcel Terms

### Property

A unique real estate parcel in Ontario, identified by a 20-digit ARN. One ARN = one Property. Properties are a read-only derived layer rebuilt from Compiled Records — they are NOT manually created.

**ID format:** `PRO_NNNNN` (e.g. `PRO_00001`)

**Stable anchor:** The 20-digit ARN. Property IDs must be persistent across Data Engine rebuilds (see Reconciliation).

### Owner

The Group that currently owns a Property. "Owner" is a **role**, not an entity type. It refers to the buyer from the most recent transaction on a Property. A Group "is an Owner" of properties — it is not "an Owner" as a category of thing.

Usage:
- "RioCan REIT owns 67 properties" (correct)
- "Show me all Owners with 10+ properties" (correct — filtering Groups by the Owner role)
- "Open the Owner page" (incorrect — it's the Groups page)

### Parcel

The provincial assessment parcel polygon from MPAC, identified by a 20-digit ARN. The physical land boundary. Every Property corresponds to exactly one Parcel.

### ARN (Assessment Roll Number)

The 20-digit provincial identifier for a parcel of land in Ontario. Assigned by MPAC. This is the single most stable identifier in the system — it never changes for a given piece of land. All property-level references in CRM should anchor to ARN.

### PIN (Property Identification Number)

An alternative parcel identifier used by GeoWarehouse and Ontario land registry. Can be used to look up the corresponding ARN.

### Site

The physical characteristics of a property — legal description, site area, frontage, depth, zoning code, building square footage. Not a standalone entity, just a group of fields on a Transaction or Property.

### Tenant

A commercial brand or business occupying a Property. Derived from brand store locators and OSM data, not from lease records. A Property can have multiple Tenants.

---

## Transaction Terms

### Transaction

Any exchange of real estate recorded in the system. A historical fact parsed from Realtrack data. Contains seller, buyer, sale date, sale price, consideration breakdown, site details, and broker information.

A Transaction is **not** something you or Jamie are working on — that's a Deal.

### Consideration

The financial breakdown of a Transaction — cash, assumed debt, chattels, chargees, and the verbatim description from the land registry.

### Transferor / Transferee

Ontario Land Registry terminology for seller and buyer, respectively. Used only at the Parse stage internally. Renamed to **Seller** and **Buyer** at the Compile stage. You will never see these terms in the UI or in conversation.

---

## People Associated with Transactions

### Buyer

The party acquiring a property in a Transaction. At the compile stage, this is a structured object with `name` (the company or individual), `contact` (the named individual, if the buyer is a company), `phone`, and `address`.

### Seller

The party disposing of a property in a Transaction. Same structure as Buyer.

### Brokerage

The real estate firm that facilitated a Transaction (e.g. Re/Max, CBRE, Colliers). A company, not an individual. May become a first-class registry in the future.

### Agent

The individual real estate sales representative or broker who facilitated a Transaction, working at a Brokerage. Replaces the ambiguous term "broker" when referring to a person (as opposed to the firm).

---

## ID Format Reference

| Entity | Format | Example | Persistent? | Anchor |
|---|---|---|---|---|
| Property | `PRO_NNNNN` | PRO_00001 | Yes (via ARN map) | 20-digit ARN |
| Group | `GRP_NNNNN` | GRP_00001 | Yes (registry) | Normalized name set |
| Contact | `CON_NNNNN` | CON_00001 | Yes (registry) | Name + context |
| Deal | `DEAL_NNNNN` | DEAL_00001 | Yes | — |
| List | `LST_NNNNN` | LST_00001 | Yes | — |
| Connection | `CXN_NNNNN` | CXN_00001 | Yes | — |
| Parcel Cache | 20-digit ARN | 00260010120100000000 | Yes (provincial) | — |
| RT Source | `RT` + digits | RT196880 | Yes (external) | — |
| Brand Source | `BR_NNNNN` | BR_00001 | Version-scoped | — |
| GW Source | `GW` + 5 digits | GW00001 | Version-scoped | — |
| OSM Source | `OSM_NNNNN` | OSM_00001 | Version-scoped | — |

---

## Reconciliation

When the Data Engine promotes a new version of Compiled Records, the downstream persistent layers (Properties, Groups, Contacts, Deals) must be reconciled — not rebuilt from scratch.

**The principle:** Data Engine versions improve data quality. CRM data accumulates business value. The two must coexist. A new compiled version should never destroy CRM work.

**Stable anchors for reconciliation:**
- Properties anchor to **ARN** (never changes)
- Groups anchor to **normalized name sets** (deterministic, with manual linking)
- Contacts anchor to **name + associated Group + transaction context**
- Deals anchor to **ARN + Group** (the property and the counterparty)

**After every Data Engine promotion, a reconciliation step:**
1. Properties: Match new compiled records to existing PRO_IDs via ARN. New ARNs get new IDs. No ID is ever reassigned.
2. Groups: Match new buyer/seller names against known_names in the Group registry. New names get new GRP_IDs. Merged names keep existing GRP_IDs.
3. Contacts: Match new contact names against existing Contact records. Surface new contacts for review.
4. Deals: Validate ARN and Group references. Flag any orphaned references.
5. Report: Show what changed, what's new, what needs attention.

---

## Deprecated Terms

These terms should no longer be used. If you encounter them in code, they should be migrated.

| Deprecated Term | Replacement | Notes |
|---|---|---|
| Entity | **Group** | Frontend UI labels, TypeScript types |
| Party | **Group** | Legacy `cleo/parties/` module |
| Owner (as entity type) | **Group** | "Owner" is now a role, not a category |
| Pipeline (for data processing) | **Data Engine** | "Pipeline" is reserved for CRM deal stages |
| Outreach | **Prospecting** | The activity of finding and contacting targets |
| Contact (as verb) | **Connection** | "Made a connection" not "made contact" |
| Broker (person) | **Agent** | The individual. "Brokerage" for the firm. |
| rt_id (as generic) | **source_id** | Use `rt_id` only for actual Realtrack IDs |
| P00001 (format) | **PRO_00001** | Property IDs use PRO_ prefix |
| G00001 (format) | **GRP_00001** | Group IDs use GRP_ prefix |
| LNK_00001 (format) | **GRP_00001** | Link groups become Group IDs |
| C00001 (CRM contact) | **CON_00001** | Contact IDs use CON_ prefix |
| D00001 (CRM deal) | **DEAL_00001** | Deal IDs use DEAL_ prefix |
| OL00001 (outreach list) | **LST_00001** | List IDs use LST_ prefix |

---

## Conceptual Model

```
DATA ENGINE (versioned, improves over time)
  Realtrack HTML ──→ Parse → Normalize → Expand → Geocode → Parcelled → Compile
  Brand APIs ──────→ Normalize → Expand → Geocode → Parcelled → Compile
  GeoWarehouse ────→ Normalize → Expand → Geocode → Parcelled → Compile
  OSM POIs ────────→ Parcelled → Compile
                                                                    │
                                                         Compiled Records
                                                                    │
                          ┌─────────────────────────────────────────┤
                          │                                         │
                    VIEWS (read-only)                     CRM (persistent, user-curated)
                    ├─ Dashboard                          ├─ Groups (GRP_)
                    ├─ Properties                         ├─ Contacts (CON_)
                    ├─ Transactions                       ├─ Deals (DEAL_)
                    └─ Map                                ├─ Lists (LST_)
                          │                               ├─ Prospecting
                          │                               └─ Connections (CXN_)
                          │                                         │
                          └──── Navigate into CRM ─────────────────→│
                          │←─── CRM enriches Views ────────────────│
```

The arrows between Views and CRM are bidirectional:
- From a Property View, you can create a Deal or add to a List
- CRM data (deal stage, connection history) enriches what you see in Views
