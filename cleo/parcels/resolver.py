"""Universal parcel resolver — resolves any identifier to a cached parcel.

Resolution priority:
  1. ARN lookup in cache (instant, O(1))
  2. ARN query against provincial API (if miss)
  3. PIN lookup via pin_to_arn index in cache
  4. PIN query against provincial API (if miss)
  5. Spatial point query against provincial API (if coords provided)

All resolved parcels are permanently cached.
"""

from __future__ import annotations

import logging
from typing import Optional

from cleo.parcels.cache import ParcelCache, polygon_centroid
from cleo.parcels.provincial import TokenExpiredError

logger = logging.getLogger(__name__)


def pad_arn_15_to_20(arn_15: str) -> str:
    """Pad a 15-digit RT/GW ARN to 20-digit provincial format."""
    arn_clean = arn_15.strip()
    if len(arn_clean) == 20:
        return arn_clean
    if len(arn_clean) == 15:
        return arn_clean + "00000"
    if 10 <= len(arn_clean) < 20:
        return arn_clean + "0" * (20 - len(arn_clean))
    return arn_clean


def normalize_pin(pin: str) -> str:
    """Strip dashes from PIN, return bare digits."""
    return pin.replace("-", "").strip()


class ParcelResolver:
    """Resolve any identifier (ARN, PIN, coords) to a cached parcel record.

    Uses the ParcelCache for instant lookups. On cache miss, optionally
    queries the provincial MapServer API and caches the result permanently.

    Set skip_api=True to disable API queries (offline/cache-only mode).
    """

    def __init__(
        self,
        cache: ParcelCache | None = None,
        skip_api: bool = False,
    ):
        self._cache = cache or ParcelCache()
        self._skip_api = skip_api
        self._client = None  # lazy init
        self._pin_to_arn: dict[str, str] | None = None  # lazy built

        # Stats
        self.stats_cache_hit = 0
        self.stats_api_hit = 0
        self.stats_api_miss = 0
        self.stats_api_error = 0

    def _get_client(self):
        """Lazy-init the provincial client."""
        if self._client is None:
            try:
                from cleo.parcels.provincial import ProvincialParcelClient
                self._client = ProvincialParcelClient()
            except ValueError:
                self._client = False  # Sentinel: no client available
        return self._client if self._client is not False else None

    def _build_pin_index(self) -> dict[str, str]:
        """Build a PIN -> ARN reverse index from the cache."""
        if self._pin_to_arn is not None:
            return self._pin_to_arn
        self._pin_to_arn = {}
        for arn, parcel in self._cache.parcels.items():
            pin = parcel.get("pin")
            if pin:
                self._pin_to_arn[normalize_pin(pin)] = arn
        return self._pin_to_arn

    def _cache_feature(self, feature: dict, source: str = "api") -> Optional[str]:
        """Extract parcel data from a provincial API feature and cache it.
        Returns the 20-digit ARN or None."""
        attrs = feature.get("attributes", {})
        arn = str(attrs.get("ASSESSMENT_ROLL_NUMBER", ""))
        if not arn:
            return None

        geometry = _arcgis_to_geojson(feature.get("geometry", {}))
        centroid = polygon_centroid(geometry) if geometry else None
        pin = str(attrs.get("PIN", "")) if attrs.get("PIN") else None

        self._cache.put(
            arn_20=arn,
            pin=pin,
            geometry=geometry,
            centroid=centroid,
            attributes={
                k: v for k, v in attrs.items()
                if k not in ("ASSESSMENT_ROLL_NUMBER", "PIN", "Shape", "Shape.STArea()", "Shape.STLength()")
            },
            source=source,
        )

        # Update PIN index if we have one
        if pin and self._pin_to_arn is not None:
            self._pin_to_arn[normalize_pin(pin)] = arn

        return arn

    def resolve_by_arn(self, arn: str) -> Optional[dict]:
        """Resolve a parcel by ARN (15 or 20 digit). Returns cached parcel dict or None."""
        arn_20 = pad_arn_15_to_20(arn)

        # Check cache first
        cached = self._cache.get(arn_20)
        if cached:
            self.stats_cache_hit += 1
            return cached

        if self._skip_api:
            return None

        # Query API
        client = self._get_client()
        if not client:
            return None

        try:
            features = client.query_by_arn(arn_20)
        except TokenExpiredError:
            raise  # Let caller handle token refresh
        except Exception as exc:
            logger.warning("API error resolving ARN %s: %s", arn_20, exc)
            self.stats_api_error += 1
            return None

        if features:
            cached_arn = self._cache_feature(features[0], source="api_arn")
            if cached_arn:
                self.stats_api_hit += 1
                return self._cache.get(cached_arn)

        self.stats_api_miss += 1
        return None

    def resolve_by_pin(self, pin: str) -> Optional[dict]:
        """Resolve a parcel by PIN. Checks cache index first, then API."""
        pin_clean = normalize_pin(pin)

        # Check cache PIN index
        pin_index = self._build_pin_index()
        if pin_clean in pin_index:
            arn = pin_index[pin_clean]
            cached = self._cache.get(arn)
            if cached:
                self.stats_cache_hit += 1
                return cached

        if self._skip_api:
            return None

        # Query API by PIN
        client = self._get_client()
        if not client:
            return None

        try:
            features = client.query_by_pin(pin_clean)
        except TokenExpiredError:
            raise  # Let caller handle token refresh
        except Exception as exc:
            logger.warning("API error resolving PIN %s: %s", pin_clean, exc)
            self.stats_api_error += 1
            return None

        if features:
            cached_arn = self._cache_feature(features[0], source="api_pin")
            if cached_arn:
                self.stats_api_hit += 1
                return self._cache.get(cached_arn)

        self.stats_api_miss += 1
        return None

    def resolve_by_coords(self, lat: float, lng: float) -> Optional[dict]:
        """Resolve a parcel by spatial point query. Always hits API."""
        if self._skip_api:
            return None

        client = self._get_client()
        if not client:
            return None

        try:
            features = client.query_at_point(lat, lng)
        except TokenExpiredError:
            raise  # Let caller handle token refresh
        except Exception as exc:
            logger.warning("API error resolving coords (%s, %s): %s", lat, lng, exc)
            self.stats_api_error += 1
            return None

        if features:
            best = client.pick_containing_parcel(features, lat, lng)
            if best:
                cached_arn = self._cache_feature(best, source="api_spatial")
                if cached_arn:
                    self.stats_api_hit += 1
                    return self._cache.get(cached_arn)

        self.stats_api_miss += 1
        return None

    def resolve(
        self,
        arn: str | None = None,
        pin: str | None = None,
        lat: float | None = None,
        lng: float | None = None,
    ) -> Optional[dict]:
        """Resolve using the best available identifier. Priority: ARN > PIN > coords."""
        if arn:
            result = self.resolve_by_arn(arn)
            if result:
                return result

        if pin:
            result = self.resolve_by_pin(pin)
            if result:
                return result

        if lat is not None and lng is not None:
            result = self.resolve_by_coords(lat, lng)
            if result:
                return result

        return None

    def save_cache(self) -> None:
        """Persist the cache to disk."""
        self._cache.save()

    def get_stats(self) -> dict:
        """Return resolution statistics."""
        return {
            "cache_total": self._cache.total,
            "cache_hits": self.stats_cache_hit,
            "api_hits": self.stats_api_hit,
            "api_misses": self.stats_api_miss,
            "api_errors": self.stats_api_error,
        }


def _arcgis_to_geojson(arcgis_geom: dict) -> Optional[dict]:
    """Convert ArcGIS geometry (rings format) to GeoJSON Polygon."""
    rings = arcgis_geom.get("rings")
    if not rings:
        return None
    return {
        "type": "Polygon",
        "coordinates": rings,
    }
