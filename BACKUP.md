# Data Backup Guide

The `data/` directory (~2.3 GB) is excluded from git and protected by iCloud sync. This document clarifies what's irreplaceable vs regenerable.

## Irreplaceable Data (protected by iCloud sync)

These files contain human work or costly API results that can't be trivially recreated:

| File | Why it matters |
|------|---------------|
| `data/html/` | 15,806 scraped Realtrack pages — re-scraping requires authenticated sessions and time |
| `data/gw_html/` | 798 GeoWarehouse HTML files — captured via browser extension |
| `data/reviews.json` | Human review determinations for parsed records |
| `data/determinations.json` | CLI-based HTML review determinations |
| `data/extract_reviews.json` | Extraction review determinations |
| `data/geocode_cache.json` | ~36K geocoded addresses — costs API credits to rebuild |
| `data/properties.json` | Curated property registry with manual edits (19,741 properties) |
| `data/parties.json` | Party group registry with manual edits (16,839 groups) |
| `data/party_edits.jsonl` | Party edit audit log |
| `data/seen_rt_ids.json` | Master ingest tracker |
| `data/crm/` | CRM contacts, deals, and edit audit log |
| `data/brand_keywords.json` | Brand keyword configuration |
| `data/markets.json` | City population reference |

## Regenerable Data (can be rebuilt from source)

These files can be recreated by running CLI commands:

| File | Rebuild command |
|------|----------------|
| `data/parsed/` | `cleo parse --sandbox` then `--promote` (from HTML files) |
| `data/extracted/` | `cleo extract --sandbox` then `--promote` (from parsed data) |
| `data/gw_parsed/` | `cleo gw-parse --sandbox` then `--promote` (from GW HTML) |
| `data/html_flags.json` | `cleo validate` |
| `data/parse_flags.json` | `cleo parse-check` |
| `data/address_index.json` | `cleo geocode --build-index` |
| `data/brand_matches.json` | `cd brands && python run.py match` |
| `data/brand_unmatched.json` | `cd brands && python run.py match` |
| `data/coordinates.json` | `cd brands && python run.py all` |
| `cleo/web/static/app/` | `cd frontend && npm run build` |

## Source Code (protected by git + GitHub)

All source code is version-controlled and pushed to GitHub at `https://github.com/brandonolsen23/cleo-mini-v3`. This includes `cleo/`, `brands/`, `frontend/`, `scripts/`, `tests/`, and `docs/`.
