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

# Properties
PROPERTIES_PATH = DATA_DIR / "properties.json"
PROPERTY_EDITS_PATH = DATA_DIR / "property_edits.jsonl"

# Markets (static population reference)
MARKETS_PATH = DATA_DIR / "markets.json"

# Parties
PARTIES_PATH = DATA_DIR / "parties.json"
PARTY_EDITS_PATH = DATA_DIR / "party_edits.jsonl"
KEYWORDS_PATH = DATA_DIR / "brand_keywords.json"

# Brands
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
PARCELS_MATCHES_PATH = PARCELS_DIR / "matches.json"
PARCELS_SERVICES_PATH = PARCELS_DIR / "services.json"
PARCELS_CONSOLIDATION_PATH = PARCELS_DIR / "consolidation.json"

# Geocoding
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "").strip()
HERE_API_KEY = os.getenv("HERE_API_KEY", "").strip()
GEOCODIO_KEY = os.getenv("GEOCODIO_KEY", "").strip()
GEOCODE_CACHE_PATH = DATA_DIR / "geocode_cache.json"
COORDINATES_PATH = DATA_DIR / "coordinates.json"
ADDRESS_INDEX_PATH = DATA_DIR / "address_index.json"

# Google Places & Street View
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GOOGLE_PLACES_PATH = DATA_DIR / "google_places.json"
GOOGLE_BUDGET_PATH = DATA_DIR / "google_budget.json"
STREETVIEW_DIR = DATA_DIR / "streetview"
STREETVIEW_META_PATH = DATA_DIR / "streetview_meta.json"

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
