"""Generic versioned data store: sandbox / promote / rollback / diff."""

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"^v(\d{3})$")


class VersionedStore:
    """Manages versioned JSON output with sandbox staging, promotion, and diff.

    Each instance operates on a base directory (e.g. data/parsed/ or
    data/extracted/) with the layout::

        base_dir/
            sandbox/          # Temporary staging
            v001/, v002/      # Immutable version snapshots
            active -> v00N    # Symlink to current version
    """

    def __init__(
        self,
        base_dir: Path,
        volatile_fields: Set[str] = frozenset(),
        reviews_path: Optional[Path] = None,
    ):
        self.base_dir = base_dir
        self.volatile_fields = set(volatile_fields)
        self.reviews_path = reviews_path

    # -- Paths ---------------------------------------------------------------

    def sandbox_path(self) -> Path:
        return self.base_dir / "sandbox"

    def active_symlink(self) -> Path:
        return self.base_dir / "active"

    # -- Sandbox lifecycle ---------------------------------------------------

    def sandbox_exists(self) -> bool:
        return self.sandbox_path().is_dir()

    def ensure_sandbox(self) -> Path:
        """Create sandbox directory. Raises if it already exists."""
        sb = self.sandbox_path()
        if sb.exists():
            raise FileExistsError(
                f"Sandbox already exists at {sb}. "
                "Use --discard to remove it first."
            )
        sb.mkdir(parents=True)
        return sb

    def discard_sandbox(self) -> bool:
        """Delete the sandbox directory. Returns True if it existed."""
        sb = self.sandbox_path()
        if sb.exists():
            shutil.rmtree(sb)
            logger.info("Discarded sandbox at %s", sb)
            return True
        return False

    # -- Versions ------------------------------------------------------------

    def list_versions(self) -> List[str]:
        """Return sorted list of version names (e.g. ['v001', 'v002'])."""
        versions = []
        if self.base_dir.exists():
            for d in self.base_dir.iterdir():
                if d.is_dir() and _VERSION_RE.match(d.name):
                    versions.append(d.name)
        return sorted(versions)

    def _next_version(self) -> str:
        versions = self.list_versions()
        if not versions:
            return "v001"
        last = versions[-1]
        num = int(last[1:])
        return f"v{num + 1:03d}"

    def active_version(self) -> Optional[str]:
        """Return the name of the active version, or None."""
        link = self.active_symlink()
        if link.is_symlink():
            return link.resolve().name
        return None

    def active_dir(self) -> Optional[Path]:
        """Return the path of the active version directory, or None."""
        link = self.active_symlink()
        if link.is_symlink():
            target = link.resolve()
            if target.is_dir():
                return target
        return None

    def _update_active_symlink(self, version_dir: Path) -> None:
        link = self.active_symlink()
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(version_dir.name)
        logger.info("Active → %s", version_dir.name)

    # -- Promote -------------------------------------------------------------

    def promote(self) -> str:
        """Promote sandbox to the next version.

        Renames sandbox → v00N, writes _meta.json, updates active symlink.
        Returns the new version name.
        """
        sb = self.sandbox_path()
        if not sb.is_dir():
            raise FileNotFoundError("No sandbox to promote. Run --sandbox first.")

        version = self._next_version()
        target = self.base_dir / version

        sb.rename(target)
        logger.info("Promoted sandbox → %s", version)

        json_count = len(list(target.glob("*.json")))
        meta = {
            "version": version,
            "promoted_at": datetime.now().isoformat(),
            "file_count": json_count,
        }
        with open(target / "_meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        self._update_active_symlink(target)
        return version

    # -- Rollback ------------------------------------------------------------

    def rollback(self, version: str) -> None:
        """Point active symlink to a specific version."""
        target = self.base_dir / version
        if not target.is_dir():
            raise FileNotFoundError(f"Version {version} does not exist.")
        self._update_active_symlink(target)
        logger.info("Rolled back to %s", version)

    # -- Diff ----------------------------------------------------------------

    def _strip_volatile(self, data: Dict) -> Dict:
        return {k: v for k, v in data.items() if k not in self.volatile_fields}

    @staticmethod
    def _flatten(data: Any, prefix: str = "") -> Dict[str, Any]:
        items = {}
        if isinstance(data, dict):
            for k, v in data.items():
                new_key = f"{prefix}.{k}" if prefix else k
                items.update(VersionedStore._flatten(v, new_key))
        elif isinstance(data, list):
            items[prefix] = data
        else:
            items[prefix] = data
        return items

    def diff_sandbox_vs_active(self) -> Dict:
        """Compare every JSON in sandbox against active version."""
        sb = self.sandbox_path()
        act = self.active_dir()

        if not sb.is_dir():
            raise FileNotFoundError("No sandbox found.")
        if act is None:
            raise FileNotFoundError("No active version to diff against.")

        # Load reviews for regression detection
        reviews: Dict = {}
        if self.reviews_path and self.reviews_path.exists():
            reviews = json.loads(self.reviews_path.read_text(encoding="utf-8"))
        clean_rt_ids = {
            rt_id for rt_id, r in reviews.items()
            if r.get("determination") == "clean" and not r.get("sandbox_accepted")
        }

        sandbox_files = {p.stem: p for p in sb.glob("*.json") if p.stem != "_meta"}
        active_files = {p.stem: p for p in act.glob("*.json") if p.stem != "_meta"}

        unchanged = 0
        changed = 0
        new_count = len(sandbox_files.keys() - active_files.keys())
        removed_count = len(active_files.keys() - sandbox_files.keys())

        field_changes: Dict[str, int] = {}
        samples: List[Dict] = []
        regressions: List[Dict] = []

        for rt_id in sorted(sandbox_files.keys() & active_files.keys()):
            with open(sandbox_files[rt_id], "r") as f:
                sb_data = self._strip_volatile(json.load(f))
            with open(active_files[rt_id], "r") as f:
                act_data = self._strip_volatile(json.load(f))

            if sb_data == act_data:
                unchanged += 1
                continue

            changed += 1

            sb_flat = self._flatten(sb_data)
            act_flat = self._flatten(act_data)
            all_keys = set(sb_flat.keys()) | set(act_flat.keys())

            changed_fields = []
            for key in all_keys:
                sb_val = sb_flat.get(key)
                act_val = act_flat.get(key)
                if sb_val != act_val:
                    field_changes[key] = field_changes.get(key, 0) + 1
                    changed_fields.append(key)
                    if len(samples) < 3:
                        samples.append({
                            "rt_id": rt_id,
                            "field": key,
                            "before": act_val,
                            "after": sb_val,
                        })

            if rt_id in clean_rt_ids and changed_fields:
                regressions.append({
                    "rt_id": rt_id,
                    "changed_fields": changed_fields,
                })

        return {
            "unchanged": unchanged,
            "changed": changed,
            "new": new_count,
            "removed": removed_count,
            "field_changes": dict(
                sorted(field_changes.items(), key=lambda x: -x[1])
            ),
            "samples": samples,
            "regressions": regressions,
        }
