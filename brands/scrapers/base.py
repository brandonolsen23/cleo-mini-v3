"""Shared output schema, utilities, and write-to-JSON helper for brand scrapers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class StoreRecord:
    brand: str
    store_name: str
    address: str
    city: str
    province: str
    postal_code: str | None
    phone: str | None
    lat: float | None
    lng: float | None
    source_url: str
    scraped_at: str


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def make_client(**kwargs) -> httpx.Client:
    return httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, **kwargs)


def write_brand_json(brand_slug: str, records: list[StoreRecord]) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = DATA_DIR / f"{brand_slug}.json"
    out.write_text(
        json.dumps([asdict(r) for r in records], indent=2, ensure_ascii=False) + "\n"
    )
    return out
