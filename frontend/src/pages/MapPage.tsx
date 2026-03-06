import {
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
} from "react";
import { useSearchParams } from "react-router-dom";
import Map, {
  Source,
  Layer,
  Popup,
  NavigationControl,
  type MapRef,
  type MapMouseEvent,
  type ViewStateChangeEvent,
} from "react-map-gl/mapbox";
import { Text, Badge, Spinner } from "@radix-ui/themes";
import { Funnel, X } from "@phosphor-icons/react";
import { fetchApi } from "@/api/client";
import type { FiltersResponse } from "@/types";
import {
  ParcelPopupContent,
  type ParcelPopupProps,
} from "@/components/map/ParcelPopup";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

const DEFAULT_CENTER = { latitude: 44.3, longitude: -79.5 };
const DEFAULT_ZOOM = 6;
const PARCEL_ZOOM_THRESHOLD = 14;

// Radix jade palette (Mapbox GL paint can't use CSS vars)
const JADE_9 = "#26997b";
const JADE_11 = "#208368";

// Selection highlight (Radix amber)
const AMBER_9 = "#ffb224";
const AMBER_11 = "#ab6400";

// Category filter highlight (Radix blue)
const BLUE_9 = "#3e63dd";
const BLUE_11 = "#3a5bc7";

// ---------------------------------------------------------------------------
// Layer definitions
// ---------------------------------------------------------------------------

/* eslint-disable @typescript-eslint/no-explicit-any */
// clusterLayer is computed inside the component so its color
// responds to the active category filter.

const clusterCountLayer: any = {
  id: "cluster-count",
  type: "symbol",
  source: "properties",
  filter: ["has", "point_count"],
  layout: {
    "text-field": ["get", "point_count_abbreviated"],
    "text-size": 13,
    "text-font": ["DIN Pro Medium", "Arial Unicode MS Bold"],
  },
  paint: {
    "text-color": "#ffffff",
  },
};

// parcelFillLayer and parcelOutlineLayer are computed inside the component
// so they can respond to the active category filter.

const selectedParcelFillLayer: any = {
  id: "selected-parcel-fill",
  type: "fill",
  source: "selected-parcel",
  paint: {
    "fill-color": AMBER_9,
    "fill-opacity": 0.3,
  },
};

const selectedParcelOutlineLayer: any = {
  id: "selected-parcel-outline",
  type: "line",
  source: "selected-parcel",
  paint: {
    "line-color": AMBER_11,
    "line-width": 2.5,
    "line-opacity": 1,
  },
};
/* eslint-enable @typescript-eslint/no-explicit-any */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GeoProperties {
  id: string;
  address: string;
  city: string;
  owner: string;
  latest_price: number | null;
  latest_date: string;
  tenants: string[];
  tenant_categories: string[];
  categories: string[];
  sources: string[];
  transaction_count: number;
  parcel_method: string;
}

interface GeoResponse {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: { type: "Point"; coordinates: [number, number] };
    properties: GeoProperties;
  }>;
  total: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MapPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const mapRef = useRef<MapRef>(null);

  const [geoData, setGeoData] = useState<GeoResponse | null>(null);
  const [parcelData, setParcelData] = useState<GeoJSON.FeatureCollection | null>(null);
  const [selectedParcel, setSelectedParcel] = useState<GeoJSON.FeatureCollection | null>(null);
  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [currentZoom, setCurrentZoom] = useState(DEFAULT_ZOOM);
  const [popupInfo, setPopupInfo] = useState<{
    lng: number;
    lat: number;
    props: ParcelPopupProps;
  } | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Brand autocomplete state
  const [brandQuery, setBrandQuery] = useState("");
  const [brandDropdownOpen, setBrandDropdownOpen] = useState(false);

  // Filters + viewport from URL (survives navigation)
  const cityFilter = searchParams.get("city") || "";
  const categoryFilter = searchParams.get("category") || "";
  const brandFilters = useMemo(() => {
    const raw = searchParams.get("brands") || "";
    return raw ? raw.split("|") : [];
  }, [searchParams]);

  const initialLat = Number(searchParams.get("lat")) || DEFAULT_CENTER.latitude;
  const initialLng = Number(searchParams.get("lng")) || DEFAULT_CENTER.longitude;
  const initialZoom = Number(searchParams.get("z")) || DEFAULT_ZOOM;

  // ── Load data on mount ──────────────────────────────────────

  useEffect(() => {
    Promise.all([
      fetchApi<GeoResponse>("/properties/geo"),
      fetchApi<FiltersResponse>("/properties/filters"),
    ])
      .then(([geo, flt]) => {
        setGeoData(geo);
        setFilters(flt);
      })
      .finally(() => setLoading(false));
  }, []);

  // ── Client-side filtered GeoJSON ────────────────────────────

  const filteredGeo = useMemo(() => {
    if (!geoData) return null;

    const cLow = cityFilter.toLowerCase();
    const catLow = categoryFilter.toLowerCase();
    const brandSet = new Set(brandFilters.map((b) => b.toLowerCase()));

    if (!cLow && !catLow && brandSet.size === 0) return geoData;

    const filtered = geoData.features.filter((f) => {
      if (cLow && f.properties.city.toLowerCase() !== cLow) return false;
      if (
        catLow &&
        !f.properties.categories.some((c) => c.toLowerCase() === catLow)
      )
        return false;
      // Brand filter: OR logic — property must have at least one matching tenant
      if (
        brandSet.size > 0 &&
        !f.properties.tenants.some((t) => brandSet.has(t.toLowerCase()))
      )
        return false;
      return true;
    });

    return {
      type: "FeatureCollection" as const,
      features: filtered,
      total: filtered.length,
    };
  }, [geoData, cityFilter, categoryFilter, brandFilters]);

  // ── Dynamic parcel layers (highlight when category filter active) ──

  // Build a Mapbox expression that matches parcels with any active filter
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const filterMatchExpr: any[] | null = useMemo(() => {
    const parts: any[] = [];
    if (categoryFilter) {
      parts.push(["in", categoryFilter, ["get", "categories"]]);
    }
    // Brand filter: OR — match if ANY selected brand is in tenants
    for (const b of brandFilters) {
      parts.push(["in", b, ["get", "tenants"]]);
    }
    if (parts.length === 0) return null;
    if (parts.length === 1) return parts[0];
    return ["any", ...parts];
  }, [categoryFilter, brandFilters]);

  const hasActiveFilter = categoryFilter || brandFilters.length > 0;

  const parcelFillLayer: any = useMemo(() => ({
    id: "parcel-fill",
    type: "fill",
    source: "parcels",
    paint: filterMatchExpr
      ? {
          "fill-color": ["case", filterMatchExpr, BLUE_9, JADE_9],
          "fill-opacity": ["case", filterMatchExpr, 0.25, 0.04],
        }
      : { "fill-color": JADE_9, "fill-opacity": 0.1 },
  }), [filterMatchExpr]);

  const parcelOutlineLayer: any = useMemo(() => ({
    id: "parcel-outline",
    type: "line",
    source: "parcels",
    paint: filterMatchExpr
      ? {
          "line-color": ["case", filterMatchExpr, BLUE_11, JADE_11],
          "line-width": ["case", filterMatchExpr, 2.5, 1],
          "line-opacity": ["case", filterMatchExpr, 1, 0.3],
        }
      : { "line-color": JADE_11, "line-width": 1.5, "line-opacity": 0.7 },
  }), [filterMatchExpr]);

  const clusterLayer: any = useMemo(() => ({
    id: "clusters",
    type: "circle",
    source: "properties",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": hasActiveFilter ? BLUE_9 : JADE_9,
      "circle-radius": [
        "step",
        ["get", "point_count"],
        18,
        50, 24,
        200, 30,
        1000, 36,
      ],
      "circle-opacity": 0.85,
      "circle-stroke-width": 2,
      "circle-stroke-color": "#ffffff",
    },
  }), [hasActiveFilter]);
  /* eslint-enable @typescript-eslint/no-explicit-any */

  // ── Fetch parcel polys on viewport change ───────────────────

  const fetchParcels = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (!map) return;

    if (map.getZoom() < PARCEL_ZOOM_THRESHOLD) {
      setParcelData(null);
      setSelectedParcel(null);
      setPopupInfo(null);
      return;
    }

    const bounds = map.getBounds();
    if (!bounds) return;

    fetchApi<GeoJSON.FeatureCollection>("/parcels/cache/bbox", {
      south: String(bounds.getSouth()),
      west: String(bounds.getWest()),
      north: String(bounds.getNorth()),
      east: String(bounds.getEast()),
    })
      .then(setParcelData)
      .catch(() => setParcelData(null));
  }, []);

  // Debounced moveend — fetch parcels + persist viewport to URL
  const moveEndTimer = useRef<ReturnType<typeof setTimeout>>();
  const onMoveEnd = useCallback(() => {
    clearTimeout(moveEndTimer.current);
    moveEndTimer.current = setTimeout(() => {
      fetchParcels();

      // Persist viewport to URL so back-navigation restores position
      const map = mapRef.current?.getMap();
      if (!map) return;
      const center = map.getCenter();
      const zoom = map.getZoom();
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("lat", center.lat.toFixed(5));
        next.set("lng", center.lng.toFixed(5));
        next.set("z", zoom.toFixed(2));
        return next;
      }, { replace: true });
    }, 300);
  }, [fetchParcels, setSearchParams]);

  // Fetch parcels on initial load (restores boundaries after back-navigation)
  const onLoad = useCallback(() => {
    fetchParcels();
  }, [fetchParcels]);

  // Track zoom for UI
  const onMove = useCallback((e: ViewStateChangeEvent) => {
    setCurrentZoom(e.viewState.zoom);
  }, []);

  // ── Click handler ───────────────────────────────────────────

  const onClick = useCallback(
    (e: MapMouseEvent) => {
      const feature = e.features?.[0];
      if (!feature) {
        setSelectedParcel(null);
        setPopupInfo(null);
        return;
      }

      // Click cluster → zoom in
      if (feature.layer?.id === "clusters") {
        const map = mapRef.current?.getMap();
        if (!map) return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const source = map.getSource("properties") as any;
        const clusterId = feature.properties?.cluster_id;
        if (clusterId == null || !source?.getClusterExpansionZoom) return;
        source.getClusterExpansionZoom(
          clusterId,
          (err: Error | null, zoom: number) => {
            if (err) return;
            map.easeTo({
              center: (feature.geometry as GeoJSON.Point).coordinates as [
                number,
                number,
              ],
              zoom,
            });
          },
        );
        return;
      }

      // Click parcel → select and show popup
      if (feature.layer?.id === "parcel-fill") {
        const arn = feature.properties?.arn;
        if (!arn || !parcelData) return;

        // Find full feature from parcelData (event geometry may be simplified)
        const fullFeature = parcelData.features.find(
          (f) => f.properties?.arn === arn,
        );
        if (!fullFeature) return;

        // Highlight selected parcel
        setSelectedParcel({
          type: "FeatureCollection",
          features: [fullFeature],
        });

        // Build popup props from parcel feature properties
        const p = feature.properties || {};
        setPopupInfo({
          lng: e.lngLat.lng,
          lat: e.lngLat.lat,
          props: {
            arn: p.arn || "",
            pin: p.pin || "",
            property_id: p.property_id || "",
            address: p.address || "",
            city: p.city || "",
            owner: p.owner || "",
            group_id: p.group_id || "",
            group_name: p.group_name || "",
            latest_price: p.latest_price ?? null,
            latest_date: p.latest_date || "",
            tenants:
              typeof p.tenants === "string"
                ? JSON.parse(p.tenants)
                : p.tenants || [],
            tenant_categories:
              typeof p.tenant_categories === "string"
                ? JSON.parse(p.tenant_categories)
                : p.tenant_categories || [],
            categories:
              typeof p.categories === "string"
                ? JSON.parse(p.categories)
                : p.categories || [],
            sources:
              typeof p.sources === "string"
                ? JSON.parse(p.sources)
                : p.sources || [],
            transaction_count: p.transaction_count || 0,
            parcel_method: p.parcel_method || "",
            photo: p.photo || "",
          },
        });
      }
    },
    [parcelData],
  );

  // ── Cursor ──────────────────────────────────────────────────

  const onMouseEnter = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (map) map.getCanvas().style.cursor = "pointer";
  }, []);

  const onMouseLeave = useCallback(() => {
    const map = mapRef.current?.getMap();
    if (map) map.getCanvas().style.cursor = "";
  }, []);

  // ── Filter helpers ──────────────────────────────────────────

  const setFilter = useCallback(
    (key: string, value: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      });
    },
    [setSearchParams],
  );

  const addBrand = useCallback(
    (brand: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        const existing = (next.get("brands") || "").split("|").filter(Boolean);
        if (!existing.includes(brand)) {
          existing.push(brand);
          next.set("brands", existing.join("|"));
        }
        return next;
      });
      setBrandQuery("");
      setBrandDropdownOpen(false);
    },
    [setSearchParams],
  );

  const removeBrand = useCallback(
    (brand: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        const remaining = (next.get("brands") || "")
          .split("|")
          .filter((b) => b && b !== brand);
        if (remaining.length > 0) next.set("brands", remaining.join("|"));
        else next.delete("brands");
        return next;
      });
    },
    [setSearchParams],
  );

  const clearFilters = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams();
      // Preserve viewport params
      const lat = prev.get("lat");
      const lng = prev.get("lng");
      const z = prev.get("z");
      if (lat) next.set("lat", lat);
      if (lng) next.set("lng", lng);
      if (z) next.set("z", z);
      return next;
    });
    setBrandQuery("");
    setBrandDropdownOpen(false);
  }, [setSearchParams]);

  const activeFilterCount =
    [cityFilter, categoryFilter].filter(Boolean).length + brandFilters.length;

  // ── Loading state ───────────────────────────────────────────

  if (loading) {
    return (
      <div
        className="flex items-center justify-center"
        style={{ height: "calc(100dvh - var(--header-height))" }}
      >
        <Spinner size="3" />
      </div>
    );
  }

  // ── Render ──────────────────────────────────────────────────

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <Map
        ref={mapRef}
        initialViewState={{
          longitude: initialLng,
          latitude: initialLat,
          zoom: initialZoom,
        }}
        mapboxAccessToken={MAPBOX_TOKEN}
        mapStyle="mapbox://styles/mapbox/light-v11"
        style={{ width: "100%", height: "100%" }}
        interactiveLayerIds={["clusters", "parcel-fill"]}
        onClick={onClick}
        onMouseEnter={onMouseEnter}
        onMouseLeave={onMouseLeave}
        onLoad={onLoad}
        onMoveEnd={onMoveEnd}
        onMove={onMove}
      >
        <NavigationControl position="bottom-right" />

        {/* Parcel polygons — visible at zoom >= 14 */}
        {parcelData && (
          <Source id="parcels" type="geojson" data={parcelData}>
            <Layer {...parcelFillLayer} />
            <Layer {...parcelOutlineLayer} />
          </Source>
        )}

        {/* Selected parcel highlight */}
        {selectedParcel && (
          <Source id="selected-parcel" type="geojson" data={selectedParcel}>
            <Layer {...selectedParcelFillLayer} />
            <Layer {...selectedParcelOutlineLayer} />
          </Source>
        )}

        {/* Property clusters for low-zoom navigation */}
        {filteredGeo && (
          <Source
            id="properties"
            type="geojson"
            data={filteredGeo as GeoJSON.FeatureCollection}
            cluster
            clusterMaxZoom={14}
            clusterRadius={50}
          >
            <Layer {...clusterLayer} />
            <Layer {...clusterCountLayer} />
          </Source>
        )}

        {/* Popup on parcel click */}
        {popupInfo && (
          <Popup
            longitude={popupInfo.lng}
            latitude={popupInfo.lat}
            anchor="bottom"
            onClose={() => {
              setPopupInfo(null);
              setSelectedParcel(null);
            }}
            closeOnClick={false}
            maxWidth="320px"
            offset={12}
          >
            <ParcelPopupContent props={popupInfo.props} />
          </Popup>
        )}
      </Map>

      {/* ── Floating filter panel ──────────────────────────────── */}
      <div
        className="absolute left-4 top-4 flex flex-col gap-2"
        style={{ zIndex: 10 }}
      >
        {/* Stats + filter toggle */}
        <div className="flex items-center gap-2 rounded-[var(--radius-3)] border border-[var(--gray-6)] bg-white px-3 py-2 shadow-sm">
          <Text size="1" weight="medium" className="text-[var(--gray-12)]">
            {(filteredGeo?.total ?? 0).toLocaleString()} properties
          </Text>
          <button
            className={`flex items-center gap-1 rounded-[var(--radius-2)] px-2 py-1 text-xs ${
              showFilters || activeFilterCount > 0
                ? "bg-[var(--accent-3)] text-[var(--accent-11)]"
                : "text-[var(--gray-11)] hover:bg-[var(--gray-a3)]"
            }`}
            onClick={() => setShowFilters(!showFilters)}
          >
            <Funnel size={14} />
            Filters
            {activeFilterCount > 0 && (
              <Badge size="1" variant="solid" color="jade" radius="full">
                {activeFilterCount}
              </Badge>
            )}
          </button>
          {activeFilterCount > 0 && (
            <button
              className="flex items-center gap-1 text-xs text-[var(--gray-9)] hover:text-[var(--gray-12)]"
              onClick={clearFilters}
            >
              <X size={12} />
              Clear
            </button>
          )}
        </div>

        {/* Filter dropdowns */}
        {showFilters && filters && (
          <div className="flex flex-col gap-2 rounded-[var(--radius-3)] border border-[var(--gray-6)] bg-white p-3 shadow-sm" style={{ overflow: "visible" }}>
            <div className="flex flex-col gap-1">
              <Text
                size="1"
                weight="medium"
                className="text-[var(--gray-11)]"
              >
                City
              </Text>
              <select
                value={cityFilter}
                onChange={(e) => setFilter("city", e.target.value)}
                className="rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-2 py-1.5 text-xs text-[var(--gray-12)] outline-none focus:border-[var(--accent-8)]"
              >
                <option value="">All cities</option>
                {filters.cities.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Text
                size="1"
                weight="medium"
                className="text-[var(--gray-11)]"
              >
                Brand Category
              </Text>
              <select
                value={categoryFilter}
                onChange={(e) => setFilter("category", e.target.value)}
                className="rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-2 py-1.5 text-xs text-[var(--gray-12)] outline-none focus:border-[var(--accent-8)]"
              >
                <option value="">All categories</option>
                {filters.categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            {/* Brand autocomplete */}
            <div className="flex flex-col gap-1">
              <Text
                size="1"
                weight="medium"
                className="text-[var(--gray-11)]"
              >
                Brands
              </Text>
              <div className="relative">
                <input
                  type="text"
                  value={brandQuery}
                  onChange={(e) => {
                    setBrandQuery(e.target.value);
                    setBrandDropdownOpen(true);
                  }}
                  onFocus={() => setBrandDropdownOpen(true)}
                  placeholder="Type to search brands..."
                  className="w-full rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-2 py-1.5 text-xs text-[var(--gray-12)] outline-none focus:border-[var(--accent-8)]"
                />
                {brandDropdownOpen && brandQuery.length >= 1 && (
                  <div className="absolute left-0 right-0 top-full mt-1 max-h-[200px] overflow-y-auto rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white shadow-md" style={{ zIndex: 50 }}>
                    {(filters.brands ?? [])
                      .filter(
                        (b) =>
                          b.toLowerCase().includes(brandQuery.toLowerCase()) &&
                          !brandFilters.includes(b),
                      )
                      .slice(0, 12)
                      .map((b) => (
                        <button
                          key={b}
                          className="block w-full px-2 py-1.5 text-left text-xs text-[var(--gray-12)] hover:bg-[var(--gray-a3)]"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => addBrand(b)}
                        >
                          {b}
                        </button>
                      ))}
                  </div>
                )}
              </div>
              {/* Selected brand chips */}
              {brandFilters.length > 0 && (
                <div className="flex flex-wrap gap-1 pt-0.5">
                  {brandFilters.map((b) => (
                    <Badge
                      key={b}
                      size="1"
                      variant="soft"
                      color="blue"
                      className="cursor-pointer"
                      onClick={() => removeBrand(b)}
                    >
                      {b}
                      <X size={10} className="ml-0.5" />
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Zoom hint for parcels */}
      {currentZoom < PARCEL_ZOOM_THRESHOLD && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 rounded-[var(--radius-3)] border border-[var(--gray-6)] bg-white px-3 py-1.5 shadow-sm">
          <Text size="1" className="text-[var(--gray-9)]">
            Zoom in to see parcel boundaries
          </Text>
        </div>
      )}
    </div>
  );
}
