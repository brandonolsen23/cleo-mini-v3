"""HTML index: maps RT IDs to their subpath within data/html/."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from cleo.config import HTML_DIR, HTML_INDEX_PATH

logger = logging.getLogger(__name__)


class HtmlIndex:
    """Manages html_index.json — lookup from RT ID to subpath.

    File format:
    {
        "RT196880": "retail/RT196880.html",
        "RT12345": "industrial/RT12345.html",
        ...
    }

    All subpaths are relative to HTML_DIR.
    """

    def __init__(self, path: Path = HTML_INDEX_PATH, html_dir: Path = HTML_DIR):
        self.path = path
        self.html_dir = html_dir
        self._data: Dict[str, str] = self._load()

    def _load(self) -> Dict[str, str]:
        if not self.path.exists():
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.debug("Loaded HTML index with %d entries.", len(data))
        return data

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, sort_keys=True)
        logger.info("Saved HTML index (%d entries) to %s", len(self._data), self.path)

    def resolve(self, rt_id: str) -> Path:
        """Return the full path to an RT ID's HTML file.

        Checks the index first, falls back to scanning subdirs,
        and finally falls back to the flat legacy path.
        """
        if rt_id in self._data:
            return self.html_dir / self._data[rt_id]

        # Fallback: scan subdirs
        found = self._scan_for(rt_id)
        if found:
            return found

        # Final fallback: flat legacy path (pre-migration)
        return self.html_dir / f"{rt_id}.html"

    def _scan_for(self, rt_id: str) -> Optional[Path]:
        """Search all type subdirs for an RT ID's HTML file."""
        filename = f"{rt_id}.html"
        for subdir in sorted(self.html_dir.iterdir()):
            if subdir.is_dir():
                candidate = subdir / filename
                if candidate.exists():
                    # Cache it for next time
                    subpath = f"{subdir.name}/{filename}"
                    self._data[rt_id] = subpath
                    return candidate
        return None

    def register(self, rt_id: str, prop_type: str) -> None:
        """Register an RT ID with its property type."""
        self._data[rt_id] = f"{prop_type}/{rt_id}.html"

    def get_type(self, rt_id: str) -> Optional[str]:
        """Return the property type for an RT ID, or None if unknown."""
        subpath = self._data.get(rt_id)
        if subpath and "/" in subpath:
            return subpath.split("/")[0]
        return None

    def all_html_files(self, prop_type: Optional[str] = None) -> List[Path]:
        """Return all indexed HTML file paths, optionally filtered by type."""
        paths = []
        for rt_id, subpath in self._data.items():
            if prop_type is not None:
                if not subpath.startswith(f"{prop_type}/"):
                    continue
            paths.append(self.html_dir / subpath)
        return sorted(paths)

    def rebuild(self) -> int:
        """Rebuild the index by scanning all type subdirs on disk.

        Returns the number of entries found.
        """
        self._data.clear()
        count = 0
        for subdir in sorted(self.html_dir.iterdir()):
            if not subdir.is_dir():
                continue
            prop_type = subdir.name
            for html_file in sorted(subdir.glob("*.html")):
                rt_id = html_file.stem
                self._data[rt_id] = f"{prop_type}/{html_file.name}"
                count += 1
        logger.info("Rebuilt HTML index: %d files across %s",
                     count, [d.name for d in sorted(self.html_dir.iterdir()) if d.is_dir()])
        return count

    @property
    def count(self) -> int:
        return len(self._data)

    def __contains__(self, rt_id: str) -> bool:
        return rt_id in self._data
