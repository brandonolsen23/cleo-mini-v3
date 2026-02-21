from typing import List
from bs4 import BeautifulSoup, Tag


def parse_photos(soup: BeautifulSoup) -> List[str]:
    """
    Collect all image URLs referenced in the RealTrack detail carousel.

    The photo carousel lives inside <div id="mygallery">; each panel
    contains an <img> pointing to the CacheFly `/photos/` CDN. We only
    collect images that reside in that gallery to avoid picking up
    unrelated icons.
    """
    photo_urls: List[str] = []
    gallery = soup.find("div", id="mygallery")
    if not gallery:
        # Older listings sometimes include a single photo outside the carousel.
        fallback_img = soup.find("img", src=True)
        if fallback_img:
            src = fallback_img["src"].strip()
            if "/photos/" in src or "/assets/files/" in src:
                photo_urls.append(src)
        return photo_urls

    for img in gallery.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src:
            continue
        # RealTrack stores photos on cachefly.net/photos or on /photos/.
        if "/photos/" not in src:
            continue
        if src not in photo_urls:
            photo_urls.append(src)
    return photo_urls
