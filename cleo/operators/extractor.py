"""AI extraction using Claude API.

Classifies crawled pages and extracts structured data (contacts, properties,
photos, tenant lists) from relevant pages.
"""

import json
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Page categories
CATEGORIES = [
    "PORTFOLIO",
    "ABOUT",
    "TEAM",
    "CONTACT",
    "PROPERTY_DETAIL",
    "IRRELEVANT",
]

CLASSIFY_PROMPT = """Classify this webpage into exactly ONE category:
- PORTFOLIO: lists multiple properties or locations
- ABOUT: company overview, history, mission
- TEAM: leadership, management, staff bios
- CONTACT: contact information, office locations
- PROPERTY_DETAIL: detailed info about a single property/plaza
- IRRELEVANT: news, blog, legal, careers, investor relations, login, etc.

Respond with ONLY the category name, nothing else."""

EXTRACT_PROMPT = """Extract structured data from this commercial real estate company webpage.
Return a JSON object with these fields (use null for missing data):

{
  "company_info": {
    "name": "Full company name if visible",
    "legal_names": ["Any legal/registered names mentioned"],
    "description": "Brief company description if found"
  },
  "contacts": [
    {
      "name": "Full name",
      "title": "Job title",
      "email": "email@example.com",
      "phone": "phone number"
    }
  ],
  "properties": [
    {
      "address": "Street address",
      "city": "City name",
      "province": "Province code (e.g. ON)",
      "plaza_name": "Name of plaza/centre if mentioned",
      "size_sqft": "Size in sqft if mentioned",
      "year_built": "Year built if mentioned",
      "tenants": ["List of tenant names"],
      "description": "Brief property description"
    }
  ],
  "photos": [
    {
      "url": "Full image URL",
      "caption": "Image caption or alt text",
      "property_context": "Which property this photo relates to"
    }
  ]
}

IMPORTANT:
- Only extract Ontario (ON) properties unless province is clearly stated
- Only include real property addresses, not PO boxes or mailing addresses
- For photos, only include property/building photos, not headshots or logos
- Return valid JSON only, no markdown formatting"""


def preprocess_html(html: str) -> str:
    """Strip non-content elements to reduce token count."""
    soup = BeautifulSoup(html, "lxml")

    # Remove non-content tags
    for tag in soup.find_all(["script", "style", "nav", "footer", "svg", "noscript", "iframe"]):
        tag.decompose()

    # Get text-heavy content
    body = soup.find("body")
    if body is None:
        return soup.get_text(separator="\n", strip=True)[:15000]

    text = body.get_text(separator="\n", strip=True)

    # Also preserve img tags for photo extraction
    images = []
    for img in soup.find_all("img"):
        src = img.get("src", "")
        alt = img.get("alt", "")
        if src and not any(skip in src.lower() for skip in ["logo", "icon", "avatar", "pixel", "tracking"]):
            images.append(f"[IMG src={src} alt={alt}]")

    if images:
        text += "\n\nIMAGES ON PAGE:\n" + "\n".join(images[:30])

    # Truncate to roughly fit in context
    return text[:15000]


def classify_page(html: str, client, model: str = "claude-haiku-4-5-20251001") -> str:
    """Classify a page using Claude API. Returns category string."""
    text = preprocess_html(html)
    if len(text.strip()) < 50:
        return "IRRELEVANT"

    try:
        response = client.messages.create(
            model=model,
            max_tokens=20,
            messages=[
                {"role": "user", "content": f"{CLASSIFY_PROMPT}\n\n---\n\n{text[:3000]}"}
            ],
        )
        category = response.content[0].text.strip().upper()
        if category in CATEGORIES:
            return category
        return "IRRELEVANT"
    except Exception as e:
        logger.warning("Classification failed: %s", e)
        return "IRRELEVANT"


def extract_page(
    html: str,
    base_url: str,
    client,
    model: str = "claude-haiku-4-5-20251001",
) -> dict | None:
    """Extract structured data from a page using Claude API."""
    text = preprocess_html(html)
    if len(text.strip()) < 50:
        return None

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Website: {base_url}\n\n"
                        f"{EXTRACT_PROMPT}\n\n---\n\n{text}"
                    ),
                }
            ],
        )
        raw = response.content[0].text.strip()

        # Try to parse JSON from the response
        # Handle markdown code blocks
        if "```" in raw:
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", raw, re.DOTALL)
            if match:
                raw = match.group(1)

        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("JSON parse failed for %s: %s", base_url, e)
        return None
    except Exception as e:
        logger.warning("Extraction failed for %s: %s", base_url, e)
        return None


def merge_extractions(extractions: list[dict], slug: str, name: str, url: str) -> dict:
    """Merge extraction results from multiple pages into a single operator record."""
    contacts: list[dict] = []
    properties: list[dict] = []
    photos: list[dict] = []
    company_name = name
    legal_names: list[str] = []
    description = ""

    seen_contacts: set[str] = set()
    seen_addresses: set[str] = set()
    seen_photos: set[str] = set()

    for ext in extractions:
        if not ext:
            continue

        # Company info
        info = ext.get("company_info") or {}
        if info.get("name") and len(info["name"]) > len(company_name):
            company_name = info["name"]
        for ln in info.get("legal_names") or []:
            if ln and ln not in legal_names:
                legal_names.append(ln)
        if info.get("description") and len(info.get("description", "")) > len(description):
            description = info["description"]

        # Contacts (dedup by name)
        for c in ext.get("contacts") or []:
            cname = (c.get("name") or "").strip()
            if not cname:
                continue
            key = cname.upper()
            if key in seen_contacts:
                continue
            seen_contacts.add(key)
            contacts.append({
                "name": cname,
                "title": c.get("title") or None,
                "email": c.get("email") or None,
                "phone": c.get("phone") or None,
            })

        # Properties (dedup by address)
        for p in ext.get("properties") or []:
            addr = (p.get("address") or "").strip()
            city = (p.get("city") or "").strip()
            if not addr:
                continue
            key = f"{addr.upper()}|{city.upper()}"
            if key in seen_addresses:
                continue
            seen_addresses.add(key)
            properties.append({
                "address": addr,
                "city": city,
                "province": p.get("province") or "ON",
                "plaza_name": p.get("plaza_name") or None,
                "size_sqft": p.get("size_sqft") or None,
                "year_built": p.get("year_built") or None,
                "tenants": p.get("tenants") or [],
                "description": p.get("description") or None,
            })

        # Photos (dedup by URL)
        for ph in ext.get("photos") or []:
            purl = (ph.get("url") or "").strip()
            if not purl:
                continue
            if purl in seen_photos:
                continue
            seen_photos.add(purl)
            photos.append({
                "url": purl,
                "caption": ph.get("caption") or None,
                "property_context": ph.get("property_context") or None,
            })

    return {
        "slug": slug,
        "name": company_name,
        "legal_names": legal_names,
        "description": description,
        "contacts": contacts,
        "properties": properties,
        "photos": photos,
    }
