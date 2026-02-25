"""BudgetGuardian — usage tracking and hard limits for Google API calls.

This is the single chokepoint for ALL Google API requests. Every call must
pass through can_use() before making a request, and record_use() after.

Safety mechanisms:
- Hard monthly limits per SKU (set to 90% of free tier)
- Daily limits to prevent burning the whole month in one run
- Auto month-reset with history archival
- Tamper detection: if used > limit, ALL calls are blocked
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, date
from pathlib import Path

from cleo.config import GOOGLE_BUDGET_PATH

logger = logging.getLogger(__name__)


class BudgetExhausted(Exception):
    """Raised when a budget limit would be exceeded."""


# Hard-coded limits — 90% of free tier to account for counting discrepancies.
# These are NOT configurable at runtime.
MONTHLY_LIMITS: dict[str, int | None] = {
    "text_search_ids": None,          # unlimited (IDs Only is free)
    "details_essentials": 9_000,       # 90% of 10,000
    "details_pro": 4_500,              # 90% of 5,000
    "details_enterprise": 900,         # 90% of 1,000
    "streetview_metadata": None,       # unlimited (free)
    "streetview_image": 9_000,         # 90% of 10,000
}

# Daily limits: monthly / 28 days (rounded down)
DAILY_LIMITS: dict[str, int | None] = {
    sku: (limit // 28 if limit is not None else None)
    for sku, limit in MONTHLY_LIMITS.items()
}

WARNING_THRESHOLD = 0.80  # warn at 80% usage


class BudgetGuardian:
    """Persistent usage tracker gating all Google API calls."""

    def __init__(self, path: Path = GOOGLE_BUDGET_PATH):
        self.path = path
        self._data: dict = self._load()
        self._check_month_reset()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return self._empty_month()

    def _empty_month(self) -> dict:
        today = date.today()
        return {
            "month": today.strftime("%Y-%m"),
            "skus": {
                sku: {"used": 0, "limit": limit}
                for sku, limit in MONTHLY_LIMITS.items()
            },
            "daily": {},
            "history": {},
        }

    def _check_month_reset(self) -> None:
        """If the current month differs from stored month, archive and reset."""
        current_month = date.today().strftime("%Y-%m")
        if self._data.get("month") != current_month:
            old_month = self._data.get("month", "unknown")
            # Archive previous month
            if old_month != "unknown":
                history = self._data.get("history", {})
                history[old_month] = {
                    sku: info.get("used", 0)
                    for sku, info in self._data.get("skus", {}).items()
                }
                self._data = self._empty_month()
                self._data["history"] = history
            else:
                self._data = self._empty_month()
            logger.info("Budget reset for new month: %s (archived: %s)", current_month, old_month)
            self.save()

    def _today_key(self) -> str:
        return date.today().isoformat()

    def _is_tampered(self) -> bool:
        """Check if any SKU has used > limit (indicates manual tampering or bug)."""
        for sku, info in self._data.get("skus", {}).items():
            limit = MONTHLY_LIMITS.get(sku)
            if limit is not None and info.get("used", 0) > limit:
                return True
        return False

    def can_use(self, sku: str, count: int = 1) -> bool:
        """Check if count requests for sku are within budget.

        Returns False if:
        - Tamper detection triggered (any SKU over limit)
        - Monthly limit would be exceeded
        - Daily limit would be exceeded
        """
        if sku not in MONTHLY_LIMITS:
            logger.error("Unknown SKU: %s", sku)
            return False

        # Tamper detection: if ANY sku is over limit, block everything
        if self._is_tampered():
            logger.error(
                "TAMPER DETECTED: a SKU has used > limit. "
                "ALL calls blocked until manually reviewed."
            )
            return False

        # Check monthly limit
        monthly_limit = MONTHLY_LIMITS[sku]
        if monthly_limit is not None:
            current = self._data["skus"][sku]["used"]
            if current + count > monthly_limit:
                logger.warning(
                    "Monthly budget exhausted for %s: %d + %d > %d",
                    sku, current, count, monthly_limit,
                )
                return False

        # Check daily limit
        daily_limit = DAILY_LIMITS[sku]
        if daily_limit is not None:
            today = self._today_key()
            daily_data = self._data.get("daily", {}).get(today, {})
            daily_used = daily_data.get(sku, 0)
            if daily_used + count > daily_limit:
                logger.warning(
                    "Daily budget exhausted for %s: %d + %d > %d",
                    sku, daily_used, count, daily_limit,
                )
                return False

        return True

    def record_use(self, sku: str, count: int = 1) -> None:
        """Record count successful API calls for sku."""
        if sku not in MONTHLY_LIMITS:
            raise ValueError(f"Unknown SKU: {sku}")

        # Update monthly
        self._data["skus"][sku]["used"] += count

        # Update daily
        today = self._today_key()
        if "daily" not in self._data:
            self._data["daily"] = {}
        if today not in self._data["daily"]:
            self._data["daily"][today] = {}
        self._data["daily"][today][sku] = (
            self._data["daily"][today].get(sku, 0) + count
        )

        # Warn at 80%
        monthly_limit = MONTHLY_LIMITS[sku]
        if monthly_limit is not None:
            used = self._data["skus"][sku]["used"]
            pct = used / monthly_limit
            if pct >= WARNING_THRESHOLD:
                logger.warning(
                    "Budget warning: %s at %.0f%% (%d / %d)",
                    sku, pct * 100, used, monthly_limit,
                )

        self.save()

    def status(self) -> dict:
        """Return current usage, remaining, percentage for all SKUs."""
        result = {}
        for sku, limit in MONTHLY_LIMITS.items():
            used = self._data["skus"].get(sku, {}).get("used", 0)
            today = self._today_key()
            daily_used = self._data.get("daily", {}).get(today, {}).get(sku, 0)
            daily_limit = DAILY_LIMITS[sku]

            entry = {
                "used": used,
                "limit": limit,
                "remaining": (limit - used) if limit is not None else None,
                "pct": round(used / limit * 100, 1) if limit else 0.0,
                "daily_used": daily_used,
                "daily_limit": daily_limit,
            }
            result[sku] = entry

        result["_meta"] = {
            "month": self._data.get("month"),
            "tampered": self._is_tampered(),
        }
        return result

    def save(self) -> None:
        """Write budget to disk atomically."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(self._data, indent=2, ensure_ascii=False)
        fd, tmp_path = tempfile.mkstemp(
            dir=self.path.parent, suffix=".tmp", prefix=".budget_"
        )
        try:
            os.write(fd, content.encode("utf-8"))
            os.close(fd)
            os.replace(tmp_path, self.path)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def remaining(self, sku: str) -> int | None:
        """Return remaining monthly budget for a SKU, or None if unlimited."""
        limit = MONTHLY_LIMITS.get(sku)
        if limit is None:
            return None
        used = self._data["skus"].get(sku, {}).get("used", 0)
        return max(0, limit - used)

    def daily_remaining(self, sku: str) -> int | None:
        """Return remaining daily budget for a SKU, or None if unlimited."""
        daily_limit = DAILY_LIMITS.get(sku)
        if daily_limit is None:
            return None
        today = self._today_key()
        daily_used = self._data.get("daily", {}).get(today, {}).get(sku, 0)
        return max(0, daily_limit - daily_used)

    def effective_remaining(self, sku: str) -> int | None:
        """Return the minimum of monthly and daily remaining, or None if unlimited."""
        monthly = self.remaining(sku)
        daily = self.daily_remaining(sku)
        if monthly is None and daily is None:
            return None
        if monthly is None:
            return daily
        if daily is None:
            return monthly
        return min(monthly, daily)
