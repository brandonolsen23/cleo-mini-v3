"""Website crawler for operator sites.

BFS crawl with priority for portfolio/about/team/contact pages.
Saves raw HTML to data/operators/crawl/{slug}/html/.
"""

import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# High-priority URL patterns (crawled first)
PRIORITY_PATTERNS = [
    re.compile(r"/portfol", re.I),
    re.compile(r"/propert", re.I),
    re.compile(r"/about", re.I),
    re.compile(r"/team", re.I),
    re.compile(r"/leadership", re.I),
    re.compile(r"/management", re.I),
    re.compile(r"/contact", re.I),
    re.compile(r"/tenant", re.I),
    re.compile(r"/plaza", re.I),
    re.compile(r"/location", re.I),
]

# Skip patterns (never crawl)
SKIP_PATTERNS = [
    re.compile(r"\.(pdf|jpg|jpeg|png|gif|svg|webp|mp4|mp3|zip|doc|xls|ppt)", re.I),
    re.compile(r"/cdn-cgi/", re.I),
    re.compile(r"#"),
    re.compile(r"^mailto:", re.I),
    re.compile(r"^tel:", re.I),
    re.compile(r"^javascript:", re.I),
    re.compile(r"/wp-admin", re.I),
    re.compile(r"/wp-login", re.I),
    re.compile(r"/feed/?$", re.I),
    re.compile(r"/xmlrpc", re.I),
]

MAX_PAGES = 100
DELAY = 1.0


def _is_priority(url: str) -> bool:
    return any(p.search(url) for p in PRIORITY_PATTERNS)


def _should_skip(url: str) -> bool:
    return any(p.search(url) for p in SKIP_PATTERNS)


def _same_domain(url: str, base_domain: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    return host == base_domain or host.endswith("." + base_domain)


def _sanitize_filename(url: str) -> str:
    """Convert URL to a filesystem-safe filename."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_") or "index"
    if parsed.query:
        path += "_" + parsed.query[:50].replace("&", "_").replace("=", "-")
    # Keep only safe chars
    path = re.sub(r"[^a-zA-Z0-9_\-.]", "_", path)
    if not path.endswith(".html"):
        path += ".html"
    # Truncate long names
    if len(path) > 200:
        path = path[:200] + ".html"
    return path


def crawl_site(
    base_url: str,
    output_dir: Path,
    max_pages: int = MAX_PAGES,
    delay: float = DELAY,
) -> dict:
    """BFS crawl a website, saving HTML pages to output_dir.

    Returns summary dict with counts.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    parsed_base = urlparse(base_url)
    base_domain = parsed_base.hostname or ""

    visited: set[str] = set()
    priority_queue: list[str] = []
    normal_queue: list[str] = []
    saved = 0
    errors = 0
    skipped = 0

    # Start with base URL
    priority_queue.append(base_url)

    client = httpx.Client(
        headers=HEADERS,
        follow_redirects=True,
        timeout=30,
    )

    try:
        while (priority_queue or normal_queue) and saved < max_pages:
            # Priority queue first
            url = priority_queue.pop(0) if priority_queue else normal_queue.pop(0)

            # Normalize URL
            url = url.split("#")[0]  # strip fragment
            if url in visited:
                continue
            visited.add(url)

            if _should_skip(url):
                skipped += 1
                continue

            if not _same_domain(url, base_domain):
                skipped += 1
                continue

            # Fetch
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except (httpx.HTTPError, httpx.InvalidURL) as e:
                logger.warning("Failed to fetch %s: %s", url, e)
                errors += 1
                continue

            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type:
                skipped += 1
                continue

            html = resp.text

            # Save HTML
            filename = _sanitize_filename(url)
            out_path = output_dir / filename
            # Avoid overwriting (add counter)
            if out_path.exists():
                base_name = out_path.stem
                for i in range(2, 100):
                    candidate = output_dir / f"{base_name}_{i}.html"
                    if not candidate.exists():
                        out_path = candidate
                        break

            out_path.write_text(html, encoding="utf-8")
            saved += 1
            logger.info("[%d/%d] Saved %s", saved, max_pages, filename)

            # Extract links for BFS
            try:
                soup = BeautifulSoup(html, "lxml")
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    abs_url = urljoin(url, href).split("#")[0]
                    if abs_url in visited:
                        continue
                    if _should_skip(abs_url):
                        continue
                    if not _same_domain(abs_url, base_domain):
                        continue
                    if _is_priority(abs_url):
                        if abs_url not in priority_queue:
                            priority_queue.append(abs_url)
                    else:
                        if abs_url not in normal_queue:
                            normal_queue.append(abs_url)
            except Exception as e:
                logger.warning("Error extracting links from %s: %s", url, e)

            if delay > 0 and (priority_queue or normal_queue):
                time.sleep(delay)

    finally:
        client.close()

    return {
        "saved": saved,
        "visited": len(visited),
        "errors": errors,
        "skipped": skipped,
        "queued_remaining": len(priority_queue) + len(normal_queue),
    }
