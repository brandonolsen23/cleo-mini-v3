# Cleanup Checklist — Pre-Geocode Gate

**Created:** 2026-03-01
**Status:** COMPLETED (all items done March 1, 2026)
**Purpose:** Fix all documentation drift, dead code, and technical debt before building the geocode stage on top of the expand engine (v004). Nothing new gets built until this list is done.
**Gate:** When every item below is checked off, we proceed to wiring geocode collection to read from `data/expanded/active/`.

> This gate is passed. Work has continued to the Parcelled and Compiled stages (March 2). See `docs/pipeline-with-parcelled.md` for the current pipeline.

---

## 1. Update CLAUDE.md

CLAUDE.md is the primary onboarding doc and the first thing read on every session. It has drifted significantly from the actual system state.

- [x] **Fix HTML file count and layout.** Change `data/html/{RT_ID}.html` with "~15,806 raw HTML files" to `data/html/{type}/*.html` across 9 property types (~92,547 files). Reference `HtmlIndex` for lookups.
- [x] **Update architecture diagram.** Replace the legacy linear flow (`parse → extract → geocode → properties`) with the current pipeline: `parse → normalize → expand → geocode`. Keep GeoWarehouse parallel flow. Add the "Other Data" bypass from pipeline-flowchart.md.
- [x] **Add missing modules to Key Files section.** Add entries for:
  - `cleo/normalize/` (engine.py, address.py, municipalities.py, versioning.py)
  - `cleo/expand/` (engine.py, expander.py, versioning.py)
  - `cleo/parcels/` (client.py, harvester.py, provincial.py, registry_builder.py, spatial.py)
  - `cleo/geocode/store.py` (unified CoordinateStore)
  - `cleo/geocode/unified_collector.py`
  - `cleo/ingest/html_index.py` (HtmlIndex for multi-type lookups)
- [x] **Update CLI command count and list.** Replace "~21 commands" with actual count. Add `normalize`, `expand`, `parcels`, `parcel-match`, `parcel-enrich`, `migrate-html`, `rebuild-html-index`, `discover-types`, `google`, `google-enrich`, `osm-brands`.
- [x] **Update Data Layout section.** Add:
  - `data/normalized/` (v001 through v019, active -> v019)
  - `data/expanded/` (v001 through v004, active -> v004)
  - `data/coordinates.json` (~50K unified multi-provider entries)
  - `data/municipalities.json` (414 AMO municipalities)
  - `data/parcels/` directory structure
  - `data/branded_parcels/` per-city files
  - `data/streetview/` cached images
  - `data/html_index.json`
  - `data/norm_reviews.json`, `data/expand_reviews.json`
- [x] **Update property/party counts.** Verify current counts from actual data files and update.
- [x] **Update Common Tasks section.** Add normalize and expand workflows. Add parcel harvesting workflow.
- [x] **Mark extract as legacy.** Add a note under the extract entry: "Legacy stage — superseded by normalize + expand pipeline. Kept for backward compatibility."

---

## 2. Deprecate the Extract Stage

The normalize + expand pipeline replaces extract. Both coexist with no markers, which is confusing.

- [x] **Add deprecation warning to CLI.** In `cleo/cli.py`, add a `click.echo("WARNING: extract is deprecated — use 'cleo normalize' + 'cleo expand' instead.")` at the top of `extract_cmd()`.
- [x] **Add deprecation comment to engine.** Put a comment block at the top of `cleo/extract/engine.py` explaining it's superseded by `cleo/normalize/engine.py` + `cleo/expand/engine.py`.
- [x] **Update all docs that reference extract.** In each doc, add "(legacy)" after extract references and note the replacement.
- [x] **Do NOT delete extract yet.** It still has active endpoints and review UI. Removal is a separate task after geocode is wired to expanded/.

---

## 3. Fix cli.py Code Duplication

Three+ variants of the same cleanup function with inconsistent signatures.

- [x] **Consolidate `_clear_sandbox_accepted()` variants.** Replace all of these:
  - `_clear_sandbox_accepted()` (line ~1365, no args, hardcoded path)
  - `_clear_sandbox_accepted(reviews_path)` (line ~1397, takes arg)
  - `_clear_extract_sandbox_accepted()` (line ~1381)
  - `_clear_norm_sandbox_accepted()` (line ~1412)

  With one generic function:
  ```python
  def _clear_sandbox_accepted(reviews_path: Path) -> int:
      """Remove sandbox-accepted entries from a reviews file. Returns count removed."""
  ```
  Update all callers (parse --promote, normalize --promote, expand --promote, extract --promote) to pass their respective reviews path.

---

## 4. Update pipeline-stages-strategy.md

This doc describes stages 4-6 as if they're working. They aren't.

- [x] **Change status line** from "Status: Draft" to "Status: Stages 1-3 implemented, Stages 4-6 planned."
- [x] **Add status badges to each stage heading:**
  - Stage 1 PARSED: `[ACTIVE — v014]`
  - Stage 2 NORMALIZED: `[ACTIVE — v019]`
  - Stage 3 EXPANDED: `[ACTIVE — v004]`
  - Stage 4 GEOCODED: `[PLANNED — no review cycle yet]`
  - Stage 5 PARCELS: `[IN PROGRESS — harvesting works, no review cycle]`
  - Stage 6 PROPERTIES: `[ACTIVE — no sandbox/promote cycle, rebuilt wholesale]`
- [x] **Update version references.** Replace stale v007/v002 normalize/expand references with v019/v004.
- [x] **Mark aspirational sections.** Add "Not yet implemented" callouts to:
  - Geocode three-panel review description
  - `data/geo_reviews.json` reference
  - `data/parcel_reviews.json` reference
  - `data/prop_reviews.json` reference
  - Properties sandbox/promote cycle description

---

## 5. Update expand-stage-plan.md

- [x] **Change status line** from "Approved design — ready to implement" to "Implemented — v004 active."
- [x] **Add current stats.** 29,247 input records, 64,244 expanded address entries.
- [x] **Update Future Work section** to reflect current state. Note which items are next (wire geocode collector) vs deferred (retire extract).

---

## 6. Update address-normalization-strategy.md

- [x] **Change status line** to "Implemented — v019 active."
- [x] **Reconcile terminology.** The doc proposes `AddressCategory` with 6 values but the actual implementation uses `address_scope` with 4 values (ontario, canadian, international, unknown) and a separate `category` field (street_address, no_street_number, legal_description, po_box, empty, corporate_seller, corporate_buyer, brand). Document what was actually built vs what was proposed.
- [x] **Add implementation notes.** Mark each of the 10 implementation steps as done/not-done.

---

## 7. Update strategy-2026-02-25.md

- [x] **Add March 1 status update section** at the top showing:
  - Phase 0 (Normalize): DONE (v019)
  - Phase 0 (Expand): DONE (v004)
  - Phase 0 (Audit metrics): NOT DONE
  - Phase 1 (Parcels): IN PROGRESS (Tier 1 municipalities harvesting)
  - Phases 2-4: NOT STARTED
- [x] **Update data counts.** HTML files: 92,547. Geocode: 50K unified. Properties: verify.
- [x] **Update "What's NOT Working Well"** to reflect what's been fixed (address normalization is no longer cracking).

---

## 8. Clean Up Dead/Unused API Endpoints

- [x] **Remove or comment out `/api/properties/{prop_id}/places`** — Google Places endpoint with no UI.
- [x] **Remove or comment out `/api/properties/{prop_id}/tenants`** — OSM tenant endpoint, UI removed.
- [x] **Add TODO comments** to disabled review pages (`/review/geocode`, `/review/parcels`, `/review/properties`) noting they're planned for future stages.

---

## 9. Move Hardcoded Values to Config

- [x] **Fuel brand exclusion list.** Move the hardcoded `["esso", "mobil", "pioneer", "ultramar"]` from normalize engine (line ~352) to `config.py` as `NORMALIZE_SKIP_BRANDS`.
- [x] **Verify no other hardcoded lists** exist in engine files that should be configurable.

---

## 10. Fix Stale Scripts

- [x] **Fix `scripts/queue_all_scan.sh`.** Remove hardcoded PID reference (73347). Either make it accept a PID argument or remove the wait-for-process logic entirely.
- [x] **Review `scripts/run_overnight_scan.sh`.** Verify the hardcoded venv path is correct. Consider making it portable.

---

## 11. Update MEMORY.md

MEMORY.md is over the 200-line limit (229 lines). Only the first 200 lines load.

- [x] **Move detailed content to topic files.** Candidates:
  - Brand scraper details → `memory/brands.md`
  - Parcel module details → `memory/parcels.md`
  - Multi-property-type scraping details → `memory/ingestion.md`
  - Google/OSM/footprints details → `memory/integrations.md`
- [x] **Keep MEMORY.md as a concise index** under 200 lines with links to topic files.
- [x] **Update version numbers** to current values.

---

## 12. Quick Wins (do alongside other items)

- [x] **Add React Error Boundary** at AppLayout level in `frontend/src/App.tsx`.
- [x] **Update `pipeline-flowchart.md` brand count** if 94 brands / 14,340 stores differs from the current "90 brands / 12,986 stores" in the doc.
- [x] **Update `shadcn-migration-plan.md` status.** If shadcn is already in use, mark as "in progress" or "complete" rather than leaving it as a proposal.

---

## Not In Scope (defer to after geocode wiring)

These were flagged in the audit but are separate work streams. Do NOT do them now.

| Item | Why defer |
|---|---|
| Pydantic request validation on POST endpoints | Important but not blocking geocode work |
| API authentication/authorization | Not blocking; app is network-isolated |
| Unit test suite | Start after cleanup, alongside geocode work |
| Frontend server-side pagination | Current dataset size is fine |
| Request deduplication / SWR / React Query | Optimization, not correctness |
| CI/CD pipeline | Build after tests exist |
| Dependency lockfile | Nice to have, not blocking |
| Credential rotation for scraper API keys | Scrapers aren't changing right now |
| Frontend accessibility improvements | Separate initiative |
| CRM cascade delete / validation | CRM isn't the focus right now |

---

## Definition of Done

All items above are checked off. Then:

1. CLAUDE.md accurately reflects the system as of March 2026
2. Every strategy doc has a correct status marker
3. There is one canonical pipeline path (normalize + expand), with extract clearly marked legacy
4. cli.py has no duplicate functions
5. No dead API endpoints serving removed UI features
6. MEMORY.md is under 200 lines with topic files for details
7. Hardcoded config values are in config.py

At that point, we proceed to: **wire the geocode collector to read from `data/expanded/active/`** and build the formalized geocode stage (Stage 4) with its review cycle.
