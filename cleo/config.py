import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# Paths
DATA_DIR = _PROJECT_ROOT / "data"
HTML_DIR = DATA_DIR / "html"
PARSED_DIR = DATA_DIR / "parsed"
EXTRACTED_DIR = DATA_DIR / "extracted"
TRACKER_PATH = DATA_DIR / "seen_rt_ids.json"
HTML_INDEX_PATH = DATA_DIR / "html_index.json"
EXTRACT_REVIEWS_PATH = DATA_DIR / "extract_reviews.json"

# Normalization
NORMALIZED_DIR = DATA_DIR / "normalized"
NORM_REVIEWS_PATH = DATA_DIR / "norm_reviews.json"

# Expansion
EXPANDED_DIR = DATA_DIR / "expanded"
EXPAND_REVIEWS_PATH = DATA_DIR / "expand_reviews.json"

# Parcelled (versioned parcel resolution per source record)
PARCELLED_DIR = DATA_DIR / "parcelled"
PARCELLED_REVIEWS_PATH = DATA_DIR / "parcelled_reviews.json"

# OSM POIs (snapshot source records for parcelled stage)
OSM_POIS_DIR = DATA_DIR / "osm_pois"

# Compiled (all sources reassembled per record)
COMPILED_DIR = DATA_DIR / "compiled"
COMPILED_REVIEWS_PATH = DATA_DIR / "compiled_reviews.json"

# Geocoded (versioned stage — expanded + coordinates assembled)
GEOCODED_DIR = DATA_DIR / "geocoded"
GEO_REVIEWS_PATH = DATA_DIR / "geo_reviews.json"

# Properties
PROPERTIES_PATH = DATA_DIR / "properties.json"
PROPERTIES_UNRESOLVED_PATH = DATA_DIR / "properties_unresolved.json"
SEARCH_INDEX_PATH = DATA_DIR / "search_index.json"
PROPERTY_EDITS_PATH = DATA_DIR / "property_edits.jsonl"

# Markets (static population reference)
MARKETS_PATH = DATA_DIR / "markets.json"

# Parties
PARTIES_PATH = DATA_DIR / "parties.json"
PARTY_EDITS_PATH = DATA_DIR / "party_edits.jsonl"
KEYWORDS_PATH = DATA_DIR / "brand_keywords.json"

# Owners
OWNER_LINKS_PATH = DATA_DIR / "owner_links.json"
OWNER_LINK_LOG_PATH = DATA_DIR / "owner_link_log.jsonl"

# Data issues (user-flagged from UI)
DATA_ISSUES_PATH = DATA_DIR / "data_issues.json"

# Brands
NORMALIZE_SKIP_BRANDS = {
    "esso.json", "mobil.json", "pioneer.json", "ultramar.json",
}
BRAND_MATCHES_PATH = DATA_DIR / "brand_matches.json"
BRANDS_DATA_DIR = _PROJECT_ROOT / "brands" / "data"
MASTER_BRANDS_CSV = Path(os.getenv(
    "MASTER_BRANDS_CSV",
    os.path.expanduser("~/Library/CloudStorage/OneDrive-CanadianCommercial/00_Prospecting/Master Retail Sheet - All Brands.csv"),
))

# Feedback
FEEDBACK_PATH = DATA_DIR / "feedback.json"

# CRM
CRM_DIR = DATA_DIR / "crm"
CRM_CONTACTS_PATH = CRM_DIR / "contacts.json"
CRM_DEALS_PATH = CRM_DIR / "deals.json"
CRM_EDITS_PATH = CRM_DIR / "edits.jsonl"

# Outreach
OUTREACH_DIR = DATA_DIR / "outreach"
OUTREACH_LISTS_PATH = OUTREACH_DIR / "lists.json"
OUTREACH_LOG_PATH = OUTREACH_DIR / "outreach_log.json"
OUTREACH_EDITS_PATH = OUTREACH_DIR / "edits.jsonl"

# GeoWarehouse
GW_SOURCE_DIR = Path(os.getenv("GW_SOURCE_DIR", str(Path.home() / "Downloads/GeoWarehouse/gw-ingest-data")))
GW_HTML_DIR = DATA_DIR / "gw_html"
GW_PARSED_DIR = DATA_DIR / "gw_parsed"

# Operators
OPERATORS_DIR = DATA_DIR / "operators"
OPERATORS_CONFIG_PATH = OPERATORS_DIR / "config.json"
OPERATORS_CRAWL_DIR = OPERATORS_DIR / "crawl"
OPERATORS_EXTRACTED_DIR = OPERATORS_DIR / "extracted"
OPERATORS_REGISTRY_PATH = OPERATORS_DIR / "operators.json"
OPERATORS_EDITS_PATH = OPERATORS_DIR / "edits.jsonl"
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# Footprints
FOOTPRINTS_DIR = DATA_DIR / "footprints"
FOOTPRINTS_PATH = FOOTPRINTS_DIR / "buildings.json"
FOOTPRINTS_MATCHES_PATH = FOOTPRINTS_DIR / "matches.json"
FOOTPRINTS_RAW_DIR = FOOTPRINTS_DIR / "raw"

# Parcels
PARCELS_DIR = DATA_DIR / "parcels"
PARCELS_PATH = PARCELS_DIR / "parcels.json"
PROVINCIAL_RAW_PATH = PARCELS_DIR / "provincial_raw.json"
PARCELS_MATCHES_PATH = PARCELS_DIR / "matches.json"
PARCELS_SERVICES_PATH = PARCELS_DIR / "services.json"
PARCELS_CONSOLIDATION_PATH = PARCELS_DIR / "consolidation.json"
BRANDED_PARCELS_DIR = DATA_DIR / "branded_parcels"
PROPERTY_PARCEL_INDEX_PATH = PARCELS_DIR / "property_parcel_index.json"

# Parcel-centric registry
PARCEL_CACHE_PATH = PARCELS_DIR / "parcel_cache.json"
PARCEL_REGISTRY_PATH = DATA_DIR / "parcel_registry.json"

# Geocoding
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "").strip()
HERE_API_KEY = os.getenv("HERE_API_KEY", "").strip()
GEOCODIO_KEY = os.getenv("GEOCODIO_KEY", "").strip()
GEOCODE_CACHE_PATH = DATA_DIR / "geocode_cache.json"
COORDINATES_PATH = DATA_DIR / "coordinates.json"
ADDRESS_INDEX_PATH = DATA_DIR / "address_index.json"

# Google Places & Street View
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()

# Ontario Assessment Parcel MapServer (AgMaps)
AGMAPS_TOKEN = os.getenv("AGMAPS_TOKEN", "").strip()
AGMAPS_PARCEL_URL = "https://ws.lioservices.lrc.gov.on.ca/arcgis4/rest/services/AIA/Assessment_Parcel_Map/MapServer/0"
GOOGLE_PLACES_PATH = DATA_DIR / "google_places.json"
GOOGLE_BUDGET_PATH = DATA_DIR / "google_budget.json"
STREETVIEW_DIR = DATA_DIR / "streetview"
STREETVIEW_META_PATH = DATA_DIR / "streetview_meta.json"

# Monitor / metrics
METRICS_DIR = DATA_DIR / "metrics"

# Ensure directories exist
HTML_DIR.mkdir(parents=True, exist_ok=True)
PARSED_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
CRM_DIR.mkdir(parents=True, exist_ok=True)
OUTREACH_DIR.mkdir(parents=True, exist_ok=True)
OPERATORS_DIR.mkdir(parents=True, exist_ok=True)
STREETVIEW_DIR.mkdir(parents=True, exist_ok=True)
FOOTPRINTS_DIR.mkdir(parents=True, exist_ok=True)
FOOTPRINTS_RAW_DIR.mkdir(parents=True, exist_ok=True)
PARCELS_DIR.mkdir(parents=True, exist_ok=True)
BRANDED_PARCELS_DIR.mkdir(parents=True, exist_ok=True)
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
EXPANDED_DIR.mkdir(parents=True, exist_ok=True)
GEOCODED_DIR.mkdir(parents=True, exist_ok=True)
PARCELLED_DIR.mkdir(parents=True, exist_ok=True)
OSM_POIS_DIR.mkdir(parents=True, exist_ok=True)
COMPILED_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)

# Realtrack base URL
REALTRACK_BASE = "https://realtrack.com"


def get_credentials() -> tuple[str, str]:
    """Return (username, password) from .env or interactive prompt."""
    username = os.getenv("REALTRACK_USER", "").strip()
    password = os.getenv("REALTRACK_PASS", "").strip()

    if not username:
        username = input("Realtrack username: ").strip()
    if not password:
        import getpass
        password = getpass.getpass("Realtrack password: ").strip()

    if not username or not password:
        raise ValueError("Username and password are required.")

    return username, password
