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
EXTRACT_REVIEWS_PATH = DATA_DIR / "extract_reviews.json"

# Properties
PROPERTIES_PATH = DATA_DIR / "properties.json"

# Markets (static population reference)
MARKETS_PATH = DATA_DIR / "markets.json"

# Parties
PARTIES_PATH = DATA_DIR / "parties.json"
PARTY_EDITS_PATH = DATA_DIR / "party_edits.jsonl"
KEYWORDS_PATH = DATA_DIR / "brand_keywords.json"

# Brands
BRAND_MATCHES_PATH = DATA_DIR / "brand_matches.json"
BRANDS_DATA_DIR = _PROJECT_ROOT / "brands" / "data"

# Feedback
FEEDBACK_PATH = DATA_DIR / "feedback.json"

# CRM
CRM_DIR = DATA_DIR / "crm"
CRM_CONTACTS_PATH = CRM_DIR / "contacts.json"
CRM_DEALS_PATH = CRM_DIR / "deals.json"
CRM_EDITS_PATH = CRM_DIR / "edits.jsonl"

# GeoWarehouse
GW_SOURCE_DIR = Path(os.getenv("GW_SOURCE_DIR", str(Path.home() / "Downloads/GeoWarehouse/gw-ingest-data")))
GW_HTML_DIR = DATA_DIR / "gw_html"
GW_PARSED_DIR = DATA_DIR / "gw_parsed"

# Geocoding
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "").strip()
HERE_API_KEY = os.getenv("HERE_API_KEY", "").strip()
GEOCODE_CACHE_PATH = DATA_DIR / "geocode_cache.json"
ADDRESS_INDEX_PATH = DATA_DIR / "address_index.json"

# Ensure directories exist
HTML_DIR.mkdir(parents=True, exist_ok=True)
PARSED_DIR.mkdir(parents=True, exist_ok=True)
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
CRM_DIR.mkdir(parents=True, exist_ok=True)

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
