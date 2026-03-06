# Anchor Layer Architecture Plan

> How Properties, Groups, Contacts, and CRM survive Data Engine rebuilds.
>
> Depends on: `docs/definitions.md` (canonical terminology)
>
> Created: 2026-03-05

---

## The Problem

The Data Engine produces better data over time — that's the whole point. But when we
promote compiled v003, rebuild properties, and re-derive groups:

1. **Property IDs shift.** `PRO_00001` was "123 Main St" in v002 but is now "456 Oak Ave"
   in v003 because a new ARN sorted earlier. Any Deal referencing `PRO_00001` now points
   to the wrong property.

2. **Group IDs are ephemeral.** The OwnerIndex is rebuilt in-memory on every request. Hash
   IDs (`a1b2c3d4e5f6`) are deterministic but change if a parser fix alters name spelling.
   LNK_ IDs are stable but only cover manually linked groups.

3. **CRM records become orphaned.** Deals, Lists, and Connections reference PRO_ and
   hash IDs that may no longer exist or point to different records.

**Current state of fragility:**

| Identifier | How Generated | Survives Rebuild? |
|---|---|---|
| ARN (20-digit) | Provincial data | Always — external, immutable |
| RT ID (RT196880) | Realtrack HTML | Always — external, immutable |
| LNK_NNNNN | Manual curation | Always — in owner_links.json |
| PRO_NNNNN (P00001 today) | Sequential counter on sorted ARNs | No — shifts on any change |
| Owner hash (md5[:12]) | MD5 of normalized name | Fragile — parser fixes break it |
| CRM Deal (D00001) | Sequential in deals.json | ID itself stable, but refs are not |

---

## The Solution: Three Persistent Registries + Reconciliation

### Overview

```
DATA ENGINE                      ANCHOR LAYER                    CRM
(versioned, rebuilds)            (persistent, append-only)       (persistent, user-curated)

Compiled Records ──→ Properties ──→ property_id_map.json        Deals (DEAL_)
                     (read-only)    ARN → PRO_NNNNN             Lists (LST_)
                         │                                       Connections (CXN_)
                         ├────────→ group_registry.json              │
                         │          GRP_NNNNN → known names          │
                         │              │                            │
                         └────────→ contact_registry.json            │
                                    CON_NNNNN → individuals          │
                                        │                            │
                                        └─── Reconciliation ────────→│
                                             (validate refs,
                                              refresh IDs,
                                              flag orphans)
```

**The key principle:** CRM records anchor to **stable identifiers** (ARN, normalized
name sets), not to derived IDs (PRO_, GRP_). Derived IDs are convenience handles that
get refreshed during reconciliation. If a PRO_ ID changes, the Deal's ARN reference
still points to the right property — we just update the convenience PRO_ field.

---

## A. Property ID Map (`data/property_id_map.json`)

### Purpose
Persistent, append-only mapping from 20-digit ARN to PRO_NNNNN. Ensures the same
physical property always gets the same PRO_ ID, regardless of how many times the
Data Engine rebuilds.

### Structure
```json
{
  "meta": {
    "created": "2026-03-05T10:00:00",
    "last_updated": "2026-03-05T10:00:00",
    "next_id": 19154
  },
  "map": {
    "00260010120100000000": "PRO_00001",
    "00260010120200000000": "PRO_00002"
  }
}
```

### Rules
1. **Append-only.** Once an ARN gets a PRO_ ID, that mapping never changes.
2. **Never reassign.** If an ARN disappears from compiled records (e.g., bad data
   removed), its PRO_ ID is retired — never given to another ARN.
3. **Monotonic counter.** `next_id` always increments. No gaps are filled.
4. **Seed from current.** On first run, seed from existing properties.json so that
   current PRO_ IDs (once we migrate from P00001 to PRO_00001 format) stay the same.

### Changes to Properties Builder
```
Current:  for arn in sorted(arns): pid_counter += 1; pid = f"P{pid_counter:05d}"
Proposed: for arn in arns:
            if arn in id_map: pid = id_map[arn]
            else: pid = next_available_id(); id_map[arn] = pid
```

The builder reads `property_id_map.json` at start, assigns stable IDs, writes any
new mappings back at end. Properties.json is still rebuilt wholesale, but IDs are
stable.

### Config
```python
PROPERTY_ID_MAP_PATH = DATA_DIR / "property_id_map.json"
```

---

## B. Group Registry (`data/group_registry.json`)

### Purpose
Persistent registry of every company/individual that appears as a buyer or seller
in any transaction. Replaces the in-memory OwnerIndex with a persistent store.
Absorbs the current `owner_links.json` functionality.

### What's a Group?
A Group is one or more normalized company/individual names that represent the same
real-world actor. The Group registry tracks:

- All known name variants (from transaction data)
- Which names have been manually linked together
- Display name (user-chosen or auto-derived)
- First/last seen dates
- Source transactions (RT IDs where this name appeared)

### Structure
```json
{
  "meta": {
    "created": "2026-03-05T10:00:00",
    "last_updated": "2026-03-05T10:00:00",
    "next_id": 10049,
    "total_groups": 10048
  },
  "groups": {
    "GRP_00001": {
      "id": "GRP_00001",
      "display_name": "RioCan REIT",
      "known_names": [
        "RIOCAN HOLDINGS INC",
        "RIOCAN REAL ESTATE INVESTMENT TRUST"
      ],
      "created_at": "2026-03-05T10:00:00",
      "updated_at": "2026-03-05T10:00:00",
      "migrated_from": "LNK_00004"
    },
    "GRP_00002": {
      "id": "GRP_00002",
      "display_name": "Goldmanco",
      "known_names": [
        "GOLDMANCO INC",
        "2099151 ONTARIO INC"
      ],
      "created_at": "2026-03-05T10:00:00",
      "updated_at": "2026-03-05T10:00:00",
      "migrated_from": "LNK_00001"
    },
    "GRP_05432": {
      "id": "GRP_05432",
      "display_name": "John Smith",
      "known_names": [
        "JOHN SMITH"
      ],
      "created_at": "2026-03-05T10:00:00",
      "updated_at": null,
      "migrated_from": null
    }
  },
  "name_index": {
    "RIOCAN HOLDINGS INC": "GRP_00001",
    "RIOCAN REAL ESTATE INVESTMENT TRUST": "GRP_00001",
    "GOLDMANCO INC": "GRP_00002",
    "2099151 ONTARIO INC": "GRP_00002",
    "JOHN SMITH": "GRP_05432"
  }
}
```

### Rules
1. **Every unique normalized buyer/seller name gets a GRP_ ID** — either its own
   or shared with linked names.
2. **Append-only IDs.** GRP_ IDs are never reassigned. If a Group dissolves
   (all names unlinked), the GRP_ ID is retired.
3. **Manual linking merges groups.** When you link "RIOCAN HOLDINGS INC" with
   "RIOCAN REAL ESTATE INVESTMENT TRUST", both names point to the same GRP_ ID.
   The lower-numbered GRP_ ID wins. The other becomes an alias in the registry.
4. **name_index is the fast-lookup layer.** Normalized name → GRP_ ID.
   Rebuilt on every reconciliation but persisted for query performance.
5. **Scope: ALL buyers and sellers.** Not just current owners. Every name that
   has ever appeared on a transaction gets a GRP_ entry. This supports seller
   tracking, historical analysis, and CRM prospecting across both sides.

### Migration from Current System
1. Every existing LNK_ group becomes a GRP_ (preserving the LNK_ ID in
   `migrated_from` for audit trail).
2. Every unlinked owner hash gets a new GRP_ ID.
3. `owner_links.json` is archived but no longer the source of truth.
4. `owner_link_log.jsonl` continues as the audit log (renamed to
   `group_link_log.jsonl`).

### Reconciliation Behavior
When the Data Engine promotes new compiled records:
1. Scan all buyer/seller names from the new properties build.
2. For each normalized name:
   - If it exists in `name_index` → keep existing GRP_ ID
   - If it's new → assign next GRP_ ID, add to registry
3. If a parser fix changed a name (e.g., "RIOCAN HOLDNGS" → "RIOCAN HOLDINGS"):
   - The old misspelled name stays in the registry (mapped to same GRP_)
   - The new correct name is added as another known_name
   - No GRP_ ID changes — the Group just gains a new name variant
4. Report: new groups, merged names, name corrections

### Config
```python
GROUP_REGISTRY_PATH = DATA_DIR / "group_registry.json"
GROUP_LINK_LOG_PATH = DATA_DIR / "group_link_log.jsonl"
```

---

## C. Contact Registry (`data/contact_registry.json`)

### Purpose
Persistent registry of every individual person who appears in transaction data.
One person = one CON_ ID, regardless of how many transactions or Groups they appear
with. Tracks association history with Groups over time.

### Where Contacts Come From
In compiled records, individuals appear as:
- `buyer.contact` — the named person at a buying company
- `seller.contact` — the named person at a selling company
- Individuals who ARE the buyer/seller (not a company — these are also Groups)

### Structure
```json
{
  "meta": {
    "created": "2026-03-05T10:00:00",
    "last_updated": "2026-03-05T10:00:00",
    "next_id": 1
  },
  "contacts": {
    "CON_00001": {
      "id": "CON_00001",
      "first_name": "Derek",
      "last_name": "Hull",
      "display_name": "Derek Hull",
      "phones": ["416-555-0123"],
      "emails": [],
      "type": "buyer",
      "source": "transaction",
      "group_associations": [
        {
          "group_id": "GRP_00002",
          "group_name": "Goldmanco",
          "status": "active",
          "first_seen": "RT45678",
          "first_seen_date": "2024-06-15",
          "last_seen": "RT98765",
          "last_seen_date": "2025-11-20"
        },
        {
          "group_id": "GRP_00789",
          "group_name": "H&R REIT",
          "status": "former",
          "first_seen": "RT12345",
          "first_seen_date": "2018-03-01",
          "last_seen": "RT34567",
          "last_seen_date": "2023-08-15"
        }
      ],
      "created_at": "2026-03-05T10:00:00",
      "updated_at": "2026-03-05T10:00:00"
    }
  },
  "name_index": {
    "DEREK HULL": "CON_00001"
  }
}
```

### Group Association Status
- **active** — Contact appears on recent transactions with this Group
- **former** — Contact no longer appears with this Group (newer transactions
  show them with a different Group). UI shows "formerly with [Group]" badge,
  greyed out.

Status is derived automatically: if a Contact's most recent transaction is with
Group A but they have older transactions with Group B, then A = active, B = former.
Can also be manually overridden.

### Deduplication Challenge
Contact names from Realtrack are not always consistent:
- "Andrew Duncan" vs "ANDREW DUNCAN" vs "A. Duncan"
- Same person at different companies over time

**Phase 1 (build):** Exact normalized name match only. One CON_ per unique
`normalize_contact_name(name)`. Conservative — may create duplicates.

**Phase 2 (manual merge):** Same linking mechanism as Groups. Merge two CON_ IDs
when you identify they're the same person.

### Reconciliation Behavior
1. Scan all `buyer.contact` and `seller.contact` names from new properties build.
2. Match against `name_index`. Existing names keep their CON_ ID.
3. New names get new CON_ IDs.
4. Update `group_associations` — add new associations, update last_seen dates.
5. Recalculate active/former status based on transaction dates.

### Config
```python
CONTACT_REGISTRY_PATH = DATA_DIR / "contact_registry.json"
CONTACT_LINK_LOG_PATH = DATA_DIR / "contact_link_log.jsonl"
```

---

## D. CRM Records (Deals, Lists, Connections)

### Anchoring Strategy

Every CRM record stores **both** the stable anchor AND the convenience ID:

```json
{
  "deal_id": "DEAL_00001",
  "name": "123 Main St London — Goldmanco Sale",
  "arn": "00260010120100000000",
  "property_id": "PRO_00001",
  "group_id": "GRP_00002",
  "contact_ids": ["CON_00001", "CON_00045"],
  "stage": "nurturing",
  "deal_owner": "brandon",
  "amount": 2500000,
  "close_date": null,
  "notes": "Owner interested in selling, follow up Q2",
  "created_at": "2026-03-05T10:00:00",
  "updated_at": "2026-03-05T10:00:00"
}
```

**Why both ARN and PRO_?** ARN is the anchor that never breaks. PRO_ is the
convenience ID used in URLs, UI, and human communication. After reconciliation,
PRO_ is refreshed from the ARN→PRO_ map. If the map is consistent (it always
is, because it's append-only), PRO_ never changes either.

### List Structure
```json
{
  "list_id": "LST_00001",
  "name": "London Retail Owners - Q1 2026",
  "items": [
    {"type": "property", "arn": "00260010120100000000", "property_id": "PRO_00001"},
    {"type": "group", "group_id": "GRP_00002"},
    {"type": "contact", "contact_id": "CON_00001"}
  ],
  "created_at": "2026-03-05T10:00:00",
  "updated_at": "2026-03-05T10:00:00"
}
```

### Connection Structure
```json
{
  "connection_id": "CXN_00001",
  "contact_id": "CON_00001",
  "group_id": "GRP_00002",
  "type": "phone_call",
  "direction": "outbound",
  "outcome": "spoke_with",
  "notes": "Interested in listing 123 Main St",
  "deal_id": "DEAL_00001",
  "logged_by": "brandon",
  "logged_at": "2026-03-05T14:30:00"
}
```

### Config
```python
CRM_DEALS_PATH = CRM_DIR / "deals.json"         # existing, schema updated
CRM_LISTS_PATH = CRM_DIR / "lists.json"          # replaces outreach/lists.json
CRM_CONNECTIONS_PATH = CRM_DIR / "connections.json"  # new
```

---

## E. Reconciliation Step

### When It Runs
After every `cleo properties` rebuild. Could be a flag (`cleo properties --reconcile`)
or automatic.

### What It Does

```
Step 1: Property ID Map
  - Read property_id_map.json
  - For each ARN in new properties build:
    - If ARN in map → use existing PRO_ ID
    - If ARN not in map → assign next PRO_ ID, add to map
  - Write updated map
  - Report: N existing, N new, N retired (in map but not in build)

Step 2: Group Registry
  - Read group_registry.json
  - Scan all buyer/seller names from new properties
  - For each normalized name:
    - If in name_index → keep GRP_ ID
    - If new → assign next GRP_ ID
  - Write updated registry
  - Report: N existing, N new, N name variants added

Step 3: Contact Registry
  - Read contact_registry.json
  - Scan all buyer.contact / seller.contact names
  - Match against name_index
  - Update group_associations (new associations, date updates)
  - Recalculate active/former status
  - Write updated registry
  - Report: N existing, N new, N association changes

Step 4: CRM Validation
  - For each Deal:
    - Verify ARN still exists in properties
    - Refresh property_id from map
    - Verify group_id still exists in registry
    - Verify contact_ids still exist
    - Flag orphans
  - For each List:
    - Validate all item references
    - Flag missing items
  - Report: N deals valid, N orphaned, N refreshed
```

### Output
```
=== Reconciliation Report ===
Properties: 19,153 → 19,847 (+694 new, 0 retired)
  PRO_ IDs: 19,847 mapped (0 reassigned, 694 new)
Groups:     10,048 → 10,312 (+264 new)
  12 groups gained new name variants (parser improvement)
  3 names moved between groups (manual relink needed?)
Contacts:   0 → 8,234 (+8,234 new)  [first run]
  4,102 have active group associations
  1,847 appear with multiple groups over time
CRM:        0 deals, 0 lists, 0 connections (nothing to validate yet)
```

---

## F. Implementation Order

### Phase 1: Property ID Stability (do first — smallest blast radius)
1. Add `PROPERTY_ID_MAP_PATH` to config.py
2. Create `cleo/properties/id_map.py` — load/save/assign functions
3. Modify `build_properties()` in builder.py to use ID map instead of counter
4. Change format from `P00001` to `PRO_00001`
5. Seed map from current properties.json (P00001 → PRO_00001 for all existing)
6. Run `cleo properties` — verify all existing properties keep equivalent IDs
7. Update frontend to handle PRO_ format (search/replace P-ID references)

### Phase 2: Group Registry (replaces owner module)
1. Add config paths
2. Create `cleo/groups/registry.py` — persistent Group store
3. Create `cleo/groups/linker.py` — manual linking (absorbs owners/links.py)
4. Seed registry from current owner_links.json + OwnerIndex hash entities
5. Create `cleo/groups/index.py` — query layer (replaces OwnerIndex)
6. Create `cleo/web/groups.py` — API routes (replaces owners.py)
7. Rename frontend: Entity* → Group*, /owners → /groups, /api/owners → /api/groups
8. Fix the duplicate Link/Linked button during this rename
9. Archive `cleo/owners/` and `cleo/parties/`

### Phase 3: Contact Registry (new)
1. Create `cleo/contacts/registry.py` — persistent Contact store
2. Create `cleo/contacts/linker.py` — manual merge for duplicate contacts
3. Extract contacts from properties on first build
4. Create `cleo/web/contacts.py` — API routes
5. Create frontend Contacts page under CRM section

### Phase 4: Reconciliation Engine
1. Create `cleo/reconcile/engine.py` — orchestrates all three registries
2. Wire into `cleo properties` (automatic or `--reconcile` flag)
3. Create `cleo reconcile` CLI command for manual runs
4. Build reconciliation report output

### Phase 5: CRM Schema (new, anchored from start)
1. Redesign deals.json with ARN + GRP_ + CON_ anchors
2. Redesign lists.json (replaces outreach/lists.json)
3. Create connections.json (new)
4. Wire CRM validation into reconciliation
5. Frontend CRM section: Deals, Lists, Connections pages

### Phase 6: HubSpot Sync (future)
1. Bidirectional sync: Groups ↔ Companies, Contacts ↔ Contacts, Deals ↔ Deals
2. Cleo is source of truth for transaction-derived data
3. HubSpot is source of truth for manual enrichment (notes, emails, sequences)

---

## G. Migration Path (Zero Downtime)

The migration can be done incrementally with no data loss:

1. **Property ID map** runs alongside current builder. Old `P00001` format still
   works everywhere until frontend is updated. Map seeds from existing data so
   no IDs change for current properties.

2. **Group registry** seeds from current `owner_links.json` + OwnerIndex. Existing
   LNK_ groups become GRP_ groups. Hash-based entities get stable GRP_ IDs.
   Old `/api/owners` routes can redirect to `/api/groups` during transition.

3. **Contact registry** is brand new — no migration needed. First build populates
   from transaction data.

4. **CRM** is mostly unbuilt. Current deals.json and outreach/ have minimal data.
   Migrate what exists, then build new schema.

Each phase is independently deployable and testable. No big-bang migration required.
