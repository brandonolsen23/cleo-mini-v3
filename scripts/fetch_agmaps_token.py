"""Fetch a fresh AgMaps token by automating the browser.

Opens the AgMaps viewer, accepts the disclaimer, and captures the
ArcGIS token from network traffic. Saves it to .env for use by the
provincial parcel client.

Usage:
    # Headless (default):
    .venv/bin/python scripts/fetch_agmaps_token.py

    # With visible browser (for debugging):
    .venv/bin/python scripts/fetch_agmaps_token.py --headed

    # Just print the token (don't write to .env):
    .venv/bin/python scripts/fetch_agmaps_token.py --print-only
"""

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

AGMAPS_URL = "https://www.lioapplications.lrc.gov.on.ca/AgMaps/Index.html?viewer=AgMaps.AgMaps&locale=en-CA"
TOKEN_URL_PATTERN = "ws.lioservices.lrc.gov.on.ca/arcgis4"


def fetch_token(headed: bool = False, timeout_ms: int = 60_000) -> str:
    """Launch browser, accept disclaimer, capture token."""
    token = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=not headed,
            args=["--ignore-certificate-errors"],
        )
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # Capture token from any request to the ArcGIS service
        def handle_request(request):
            nonlocal token
            url = request.url
            if TOKEN_URL_PATTERN in url and "token=" in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if "token" in params:
                    token = params["token"][0]
                    print(f"  Captured token from request: {url[:80]}...")

        def handle_response(response):
            nonlocal token
            url = response.url
            if TOKEN_URL_PATTERN in url and "token=" in url:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if "token" in params and not token:
                    token = params["token"][0]
                    print(f"  Captured token from response: {url[:80]}...")

        page.on("request", handle_request)
        page.on("response", handle_response)

        print(f"Opening AgMaps viewer...")
        page.goto(AGMAPS_URL, wait_until="networkidle", timeout=timeout_ms)

        # Wait for the disclaimer dialog to appear
        print("Waiting for disclaimer dialog...")
        time.sleep(3)

        # Try multiple selectors for the accept button
        accept_selectors = [
            "button:has-text('Accept')",
            "button:has-text('I Accept')",
            "button:has-text('Agree')",
            "button:has-text('OK')",
            ".disclaimer-accept",
            "[data-command='AcceptDisclaimer']",
            "button.accept",
        ]

        clicked = False
        for selector in accept_selectors:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000):
                    print(f"  Clicking: {selector}")
                    btn.click()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            # Try finding any visible button with accept-like text
            print("  Trying to find accept button by scanning all buttons...")
            buttons = page.locator("button").all()
            for btn in buttons:
                try:
                    text = btn.text_content().strip().lower()
                    if text and any(w in text for w in ["accept", "agree", "ok", "continue"]):
                        if btn.is_visible():
                            print(f"  Clicking button: '{btn.text_content().strip()}'")
                            btn.click()
                            clicked = True
                            break
                except Exception:
                    continue

        if not clicked:
            print("  WARNING: Could not find accept button. Waiting for token anyway...")

        # Wait for the map to load and token requests to fire
        print("Waiting for map to load and token to appear...")
        deadline = time.time() + 30
        while time.time() < deadline:
            if token:
                break
            time.sleep(1)

        if not token:
            # Last resort: check page console and network entries
            print("  Token not captured from network. Checking page state...")
            # Try to extract from any visible token reference
            try:
                content = page.content()
                token_match = re.search(r'token[=:]["\']\s*([A-Za-z0-9_-]{20,})', content)
                if token_match:
                    token = token_match.group(1)
                    print(f"  Found token in page content")
            except Exception:
                pass

        browser.close()

    if not token:
        raise RuntimeError(
            "Could not capture AgMaps token. Try:\n"
            "  1. Run with --headed to see what's happening\n"
            "  2. Manually visit AgMaps and grab token from DevTools\n"
            "  3. Set AGMAPS_TOKEN in .env manually"
        )

    return token


def save_token_to_env(token: str) -> None:
    """Update AGMAPS_TOKEN in .env file."""
    if not ENV_PATH.exists():
        ENV_PATH.write_text(f"AGMAPS_TOKEN={token}\n")
        print(f"Created {ENV_PATH} with token")
        return

    content = ENV_PATH.read_text()
    if "AGMAPS_TOKEN=" in content:
        # Replace existing
        content = re.sub(r"AGMAPS_TOKEN=.*", f"AGMAPS_TOKEN={token}", content)
    else:
        # Append
        if not content.endswith("\n"):
            content += "\n"
        content += f"\nAGMAPS_TOKEN={token}\n"

    ENV_PATH.write_text(content)
    print(f"Updated AGMAPS_TOKEN in {ENV_PATH}")


def test_token(token: str) -> bool:
    """Verify the token works by querying the service."""
    import httpx

    url = "https://ws.lioservices.lrc.gov.on.ca/arcgis4/rest/services/AIA/Assessment_Parcel_Map/MapServer/0"
    try:
        resp = httpx.get(
            url,
            params={"f": "json", "token": token},
            timeout=15,
            verify=False,
        )
        data = resp.json()
        if "error" in data:
            print(f"  Token test FAILED: {data['error'].get('message', data['error'])}")
            return False
        name = data.get("name", "")
        fields = [f.get("name") for f in data.get("fields", [])]
        print(f"  Token test PASSED: layer={name}, {len(fields)} fields")
        print(f"  Fields: {', '.join(fields[:15])}")
        return True
    except Exception as e:
        print(f"  Token test error: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Fetch AgMaps token via browser automation")
    parser.add_argument("--headed", action="store_true", help="Show the browser window")
    parser.add_argument("--print-only", action="store_true", help="Print token but don't save to .env")
    parser.add_argument("--timeout", type=int, default=60, help="Page load timeout in seconds")
    args = parser.parse_args()

    print("=" * 60)
    print("AgMaps Token Fetcher")
    print("=" * 60)

    try:
        token = fetch_token(headed=args.headed, timeout_ms=args.timeout * 1000)
    except Exception as e:
        print(f"\nERROR: {e}")
        sys.exit(1)

    print(f"\nToken: {token[:20]}...{token[-10:]}" if len(token) > 30 else f"\nToken: {token}")
    print(f"Length: {len(token)} chars")

    # Test the token
    print("\nTesting token against Assessment Parcel MapServer...")
    if not test_token(token):
        print("\nWARNING: Token did not pass verification. It may be invalid or expired.")
        if not args.print_only:
            print("Saving anyway — you may need to run this script again.")

    if args.print_only:
        print(f"\nFull token:\n{token}")
    else:
        save_token_to_env(token)
        print("\nDone. You can now run:")
        print("  .venv/bin/python scripts/test_provincial_parcels.py")
        print("  .venv/bin/python scripts/harvest_city_parcels.py london --provincial")


if __name__ == "__main__":
    main()
