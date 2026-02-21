#!/usr/bin/env python3
"""
Download logos for all completed brands using logo.dev API.

Usage:
    cd /Users/brandonolsen23/cleo-mini-v3
    .venv/bin/python scripts/download_logos.py

Primary source: https://img.logo.dev/{domain}
Saves PNGs to frontend/public/brands/{slug}.png
"""

import re
import sys
import time
from pathlib import Path

import httpx

# ---------------------------------------------------------------------------
# Slug logic -- mirrors the frontend:
#   name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "")
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s


# ---------------------------------------------------------------------------
# Brand list: (display_name, domain)
# 94 completed brands from the Cleo brand scraper checklist.
# ---------------------------------------------------------------------------

BRANDS: list[tuple[str, str]] = [
    # Grocery (17)
    ("Loblaws", "loblaws.ca"),
    ("No Frills", "nofrills.ca"),
    ("Real Canadian Superstore", "realcanadiansuperstore.ca"),
    ("Shoppers Drug Mart", "shoppersdrugmart.ca"),
    ("Zehrs", "zehrs.ca"),
    ("Fortinos", "fortinos.ca"),
    ("Valu-Mart", "valumart.ca"),
    ("Independent Grocer", "yourindependentgrocer.ca"),
    ("Wholesale Club", "wholesaleclub.ca"),
    ("Sobeys", "sobeys.com"),
    ("FreshCo", "freshco.com"),
    ("Foodland", "foodland.ca"),
    ("Longos", "longos.com"),
    ("Farm Boy", "farmboy.ca"),
    ("Safeway", "safeway.ca"),
    ("Metro", "metro.ca"),
    ("Food Basics", "foodbasics.ca"),

    # Big-Box Retail (4)
    ("Walmart", "walmart.ca"),
    ("Canadian Tire", "canadiantire.ca"),
    ("Home Depot", "homedepot.ca"),
    ("Costco", "costco.ca"),

    # Discount Retail (4)
    ("Giant Tiger", "gianttiger.com"),
    ("Dollarama", "dollarama.com"),
    ("Dollar Tree", "dollartree.ca"),
    ("Goodwill", "goodwill.org"),

    # Specialty Retail (12)
    ("Best Buy", "bestbuy.ca"),
    ("Staples", "staples.ca"),
    ("JYSK", "jysk.ca"),
    ("HomeSense", "homesense.ca"),
    ("Indigo", "indigo.ca"),
    ("PetSmart", "petsmart.ca"),
    ("Sport Chek", "sportchek.ca"),
    ("The Brick", "thebrick.com"),
    ("Tepperman's", "teppermans.com"),
    ("LCBO", "lcbo.com"),
    ("Toys R Us", "toysrus.ca"),
    ("Rens Pets", "renspets.com"),

    # QSR (12)
    ("McDonald's", "mcdonalds.com"),
    ("A&W", "aw.ca"),
    ("Wendy's", "wendys.com"),
    ("Burger King", "burgerking.ca"),
    ("Harvey's", "harveys.ca"),
    ("Taco Bell", "tacobell.ca"),
    ("Tim Hortons", "timhortons.com"),
    ("Mary Brown's", "marybrowns.com"),
    ("Popeyes", "popeyes.com"),
    ("Starbucks", "starbucks.ca"),
    ("Dairy Queen", "dairyqueen.com"),
    ("Swiss Chalet", "swisschalet.com"),

    # Full-Service Restaurants (9)
    ("Kelsey's", "kelseys.ca"),
    ("Montana's", "montanas.ca"),
    ("East Side Mario's", "eastsidemarios.com"),
    ("Boston Pizza", "bostonpizza.com"),
    ("Chipotle", "chipotle.com"),
    ("Five Guys", "fiveguys.ca"),
    ("St. Louis Bar & Grill", "stlouiswings.com"),
    ("Sunset Grill", "sunsetgrill.ca"),
    ("Wild Wing", "wildwingrestaurants.com"),

    # Take-out / Fast Casual (9)
    ("Domino's", "dominos.ca"),
    ("Pizza Hut", "pizzahut.ca"),
    ("Pizza Pizza", "pizzapizza.ca"),
    ("Pita Pit", "pitapit.ca"),
    ("Firehouse Subs", "firehousesubs.ca"),
    ("Mr. Sub", "mrsub.ca"),
    ("Mucho Burrito", "muchoburrito.com"),
    ("Papa John's", "papajohns.ca"),
    ("Subway", "subway.com"),

    # Fuel (4)
    ("Esso", "esso.ca"),
    ("Ultramar", "ultramar.ca"),
    ("Pioneer", "pioneerpetroleum.ca"),
    ("Mobil", "mobil.ca"),

    # Automotive (21)
    ("Toyota", "toyota.ca"),
    ("Lexus", "lexus.ca"),
    ("Honda", "honda.ca"),
    ("Acura", "acura.ca"),
    ("Nissan", "nissan.ca"),
    ("Infiniti", "infiniti.ca"),
    ("Kia", "kia.ca"),
    ("Hyundai", "hyundai.ca"),
    ("Volvo", "volvocars.com"),
    ("Chrysler", "chrysler.ca"),
    ("Ford", "ford.ca"),
    ("GMC", "gmc.ca"),
    ("Mercedes-Benz", "mercedes-benz.ca"),
    ("Porsche", "porsche.com"),
    ("Land Rover", "landrover.ca"),
    ("Volkswagen", "volkswagen.ca"),
    ("Audi", "audi.ca"),
    ("BMW", "bmw.ca"),
    ("Jaguar", "jaguar.ca"),
    ("Mazda", "mazda.ca"),
    ("Mitsubishi", "mitsubishi.ca"),
]


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "frontend" / "public" / "brands"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading logos for {len(BRANDS)} brands")
    print(f"Output directory: {out_dir}\n")

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []  # (name, reason)

    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        for i, (name, domain) in enumerate(BRANDS, 1):
            slug = slugify(name)
            url = f"https://img.logo.dev/{domain}?token=pk_X-1ZO13GSgeOoUrIuJ6GMQ&size=128&format=png"
            dest = out_dir / f"{slug}.png"

            try:
                resp = client.get(url)

                if resp.status_code != 200:
                    reason = f"HTTP {resp.status_code}"
                    print(f"  [{i:3d}/{len(BRANDS)}] FAIL  {name} ({slug}) -- {reason}")
                    failed.append((name, reason))
                    continue

                content_type = resp.headers.get("content-type", "")
                if "image" not in content_type:
                    reason = f"unexpected content-type: {content_type}"
                    print(f"  [{i:3d}/{len(BRANDS)}] FAIL  {name} ({slug}) -- {reason}")
                    failed.append((name, reason))
                    continue

                dest.write_bytes(resp.content)
                size_kb = len(resp.content) / 1024
                print(f"  [{i:3d}/{len(BRANDS)}] OK    {name} ({slug}) -- {size_kb:.1f} KB")
                succeeded.append(name)

            except httpx.TimeoutException:
                reason = "timeout"
                print(f"  [{i:3d}/{len(BRANDS)}] FAIL  {name} ({slug}) -- {reason}")
                failed.append((name, reason))

            except httpx.HTTPError as exc:
                reason = str(exc)
                print(f"  [{i:3d}/{len(BRANDS)}] FAIL  {name} ({slug}) -- {reason}")
                failed.append((name, reason))

            # Small delay to be polite to the API
            time.sleep(0.1)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"SUMMARY: {len(succeeded)} succeeded, {len(failed)} failed out of {len(BRANDS)} brands")

    if failed:
        print(f"\nFailed brands ({len(failed)}):")
        for name, reason in failed:
            print(f"  - {name}: {reason}")

    if succeeded:
        print(f"\nLogos saved to: {out_dir}")


if __name__ == "__main__":
    main()
