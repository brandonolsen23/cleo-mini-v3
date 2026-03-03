import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import MapGL, { Source, Layer, Popup } from "react-map-gl/mapbox";
import type { MapRef, MapMouseEvent } from "react-map-gl/mapbox";
import type { LayerProps } from "react-map-gl/mapbox";
import type { FeatureCollection } from "geojson";
import type { GeoJSONSource } from "mapbox-gl";
import type { Point } from "geojson";
import { SlidersHorizontal, CaretDown, CaretUp, X } from "@phosphor-icons/react";
import { useParcelFilters } from "../../api/parcels";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string;

// ---------------------------------------------------------------------------
// Layer definitions
// ---------------------------------------------------------------------------

// Parcel polygons from the registry — colored by whether they have transactions
const registryParcelFillLayer: LayerProps = {
  id: "registry-parcel-fill",
  type: "fill",
  source: "registry-parcels",
  filter: ["==", ["geometry-type"], "Polygon"],
  paint: {
    "fill-color": [
      "case",
      ["get", "has_transactions"],
      "#0d9488", // teal-600 for parcels with transactions
      "#f59e0b", // amber-500 for branded-only
    ],
    "fill-opacity": 0.2,
  },
};

const registryParcelLineLayer: LayerProps = {
  id: "registry-parcel-line",
  type: "line",
  source: "registry-parcels",
  filter: ["==", ["geometry-type"], "Polygon"],
  paint: {
    "line-color": [
      "case",
      ["get", "has_transactions"],
      "#0f766e", // teal-700
      "#d97706", // amber-600
    ],
    "line-width": 1.5,
    "line-opacity": 0.7,
  },
};

// Point fallback for parcels without polygon geometry
const registryPointLayer: LayerProps = {
  id: "registry-point",
  type: "circle",
  source: "registry-parcels",
  filter: ["==", ["geometry-type"], "Point"],
  paint: {
    "circle-color": [
      "case",
      ["get", "has_transactions"],
      "#0d9488",
      "#f59e0b",
    ],
    "circle-radius": 6,
    "circle-stroke-width": 1.5,
    "circle-stroke-color": "#ffffff",
  },
};

// Cluster layers for centroid points at low zoom
const clusterLayer: LayerProps = {
  id: "clusters",
  type: "circle",
  source: "registry-centroids",
  filter: ["has", "point_count"],
  paint: {
    "circle-color": [
      "step",
      ["get", "point_count"],
      "#a8a29e",
      10,
      "#78716c",
      50,
      "#57534e",
      200,
      "#44403c",
    ],
    "circle-radius": [
      "step",
      ["get", "point_count"],
      18,
      10, 24,
      50, 30,
      200, 36,
    ],
  },
};

const clusterCountLayer: LayerProps = {
  id: "cluster-count",
  type: "symbol",
  source: "registry-centroids",
  filter: ["has", "point_count"],
  layout: {
    "text-field": "{point_count_abbreviated}",
    "text-size": 13,
  },
  paint: {
    "text-color": "#ffffff",
  },
};

const unclusteredCentroidLayer: LayerProps = {
  id: "unclustered-centroid",
  type: "circle",
  source: "registry-centroids",
  filter: ["!", ["has", "point_count"]],
  paint: {
    "circle-color": [
      "case",
      ["get", "has_transactions"],
      "#0d9488",
      "#f59e0b",
    ],
    "circle-radius": 6,
    "circle-stroke-width": 1.5,
    "circle-stroke-color": "#ffffff",
  },
};

// POI layers from Mapbox vector tiles
const POI_ZOOM_THRESHOLD = 14;
const POLYGON_ZOOM_THRESHOLD = 14;

const poiLabelLayer: LayerProps = {
  id: "poi-labels",
  type: "symbol",
  source: "composite",
  "source-layer": "poi_label",
  minzoom: POI_ZOOM_THRESHOLD,
  filter: [
    "match",
    ["get", "class"],
    ["shop", "restaurant", "fast_food", "bank", "fuel", "cafe", "bar", "pharmacy", "convenience", "supermarket", "car", "clothing", "hotel", "fitness_centre"],
    true,
    false,
  ],
  layout: {
    "text-field": ["get", "name"],
    "text-size": 11,
    "text-anchor": "top",
    "text-offset": [0, 0.8],
    "icon-allow-overlap": false,
    "text-allow-overlap": false,
    "text-optional": true,
  },
  paint: {
    "text-color": "#7c3aed",
    "text-halo-color": "#ffffff",
    "text-halo-width": 1.5,
  },
};

const poiCircleLayer: LayerProps = {
  id: "poi-circles",
  type: "circle",
  source: "composite",
  "source-layer": "poi_label",
  minzoom: POI_ZOOM_THRESHOLD,
  filter: [
    "match",
    ["get", "class"],
    ["shop", "restaurant", "fast_food", "bank", "fuel", "cafe", "bar", "pharmacy", "convenience", "supermarket", "car", "clothing", "hotel", "fitness_centre"],
    true,
    false,
  ],
  paint: {
    "circle-radius": 4,
    "circle-color": "#7c3aed",
    "circle-stroke-width": 1.5,
    "circle-stroke-color": "#ffffff",
    "circle-opacity": 0.7,
  },
};

const EMPTY_FC: FeatureCollection = {
  type: "FeatureCollection",
  features: [],
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MAP_VIEW_KEY = "cleo-map-view";

function getSavedView() {
  try {
    const raw = sessionStorage.getItem(MAP_VIEW_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
}

function formatPrice(price: number | null): string {
  if (price == null) return "";
  if (price >= 1_000_000) return `$${(price / 1_000_000).toFixed(1)}M`;
  if (price >= 1_000) return `$${Math.round(price / 1_000)}K`;
  return `$${price}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function MapPage() {
  const navigate = useNavigate();
  const mapRef = useRef<MapRef>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const savedView = useRef(getSavedView());
  const { data: filtersData } = useParcelFilters();

  // Popup state
  const [popupData, setPopupData] = useState<{
    lng: number;
    lat: number;
    arn: string;
    pid: string | null;
    address: string;
    city: string | null;
    brands: string[];
    transaction_count: number;
    latest_price: number | null;
    latest_date: string | null;
    sources: string[];
    zoning: string | null;
  } | null>(null);

  // URL param state
  const cityFilter = searchParams.get("city") || "";
  const brandFilter = searchParams.get("brand") || "";
  const txnsFilter = searchParams.get("txns") || "";
  const priceMin = searchParams.get("pmin") || "";
  const priceMax = searchParams.get("pmax") || "";
  const showPOIs = searchParams.get("poi") === "1";

  const hasFilters = !!(cityFilter || brandFilter || txnsFilter || priceMin || priceMax);
  const [filtersOpen, setFiltersOpen] = useState(hasFilters);
  const [currentZoom, setCurrentZoom] = useState(6);

  // Parcel GeoJSON data (polygons + point fallbacks)
  const [parcelData, setParcelData] = useState<FeatureCollection>(EMPTY_FC);
  const [parcelLoading, setParcelLoading] = useState(false);
  const [parcelCount, setParcelCount] = useState(0);
  const fetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const updateParams = useCallback(
    (updates: Record<string, string | null>) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, val] of Object.entries(updates)) {
          if (val == null || val === "") next.delete(key);
          else next.set(key, val);
        }
        return next;
      }, { replace: true });
    },
    [setSearchParams]
  );

  // Fetch parcel polygons when map moves or filters change
  const fetchParcels = useCallback((map: MapRef) => {
    const bounds = map.getBounds();
    if (!bounds) return;

    const { _sw, _ne } = bounds as any;
    const qs = new URLSearchParams();
    qs.set("south", _sw.lat.toFixed(5));
    qs.set("west", _sw.lng.toFixed(5));
    qs.set("north", _ne.lat.toFixed(5));
    qs.set("east", _ne.lng.toFixed(5));
    if (cityFilter) qs.set("city", cityFilter);
    if (brandFilter) qs.set("brand", brandFilter);
    if (txnsFilter === "yes") qs.set("has_transactions", "true");
    if (txnsFilter === "no") qs.set("has_transactions", "false");
    if (priceMin) qs.set("min_price", priceMin);
    if (priceMax) qs.set("max_price", priceMax);

    setParcelLoading(true);
    fetch(`/api/parcels/registry/geojson?${qs.toString()}`)
      .then((r) => r.json())
      .then((data: FeatureCollection) => {
        setParcelData(data);
        setParcelCount(data.features?.length ?? 0);
        setParcelLoading(false);
      })
      .catch(() => setParcelLoading(false));
  }, [cityFilter, brandFilter, txnsFilter, priceMin, priceMax]);

  // Centroid points for clustering at low zoom
  const centroidGeojson = useMemo<FeatureCollection>(() => ({
    type: "FeatureCollection",
    features: (parcelData.features || [])
      .filter((f) => f.properties)
      .map((f) => {
        const p = f.properties!;
        // Use centroid from properties or compute from geometry
        let lng: number, lat: number;
        if (f.geometry.type === "Point") {
          [lng, lat] = f.geometry.coordinates as [number, number];
        } else if (f.geometry.type === "Polygon") {
          const ring = (f.geometry as GeoJSON.Polygon).coordinates[0];
          lng = ring.reduce((s, c) => s + c[0], 0) / ring.length;
          lat = ring.reduce((s, c) => s + c[1], 0) / ring.length;
        } else {
          return null;
        }
        return {
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [lng, lat] },
          properties: {
            arn: p.arn,
            pid: p.pid,
            address: p.address,
            city: p.city,
            brands: p.brands,
            brand_count: p.brand_count,
            transaction_count: p.transaction_count,
            latest_price: p.latest_price,
            latest_date: p.latest_date,
            has_transactions: p.has_transactions,
            sources: p.sources,
            zoning: p.zoning,
          },
        };
      })
      .filter(Boolean) as FeatureCollection["features"],
  }), [parcelData]);

  // Initial fetch and filter-change fetch
  useEffect(() => {
    if (mapRef.current) {
      fetchParcels(mapRef.current);
    }
  }, [fetchParcels]);

  const showPolygons = currentZoom >= POLYGON_ZOOM_THRESHOLD;

  const onClick = useCallback(
    (e: MapMouseEvent) => {
      const map = mapRef.current;
      if (!map) return;

      // Check clusters
      const clusterFeatures = map.queryRenderedFeatures(e.point, { layers: ["clusters"] });
      if (clusterFeatures.length > 0) {
        const feature = clusterFeatures[0];
        const clusterId = feature.properties?.cluster_id;
        const source = map.getSource("registry-centroids") as GeoJSONSource;
        source.getClusterExpansionZoom(clusterId, (err: Error | null | undefined, zoom: number | null | undefined) => {
          if (err || zoom == null) return;
          const geom = feature.geometry as Point;
          map.easeTo({ center: [geom.coordinates[0], geom.coordinates[1]], zoom });
        });
        return;
      }

      // Check polygon clicks
      const parcelFeatures = map.queryRenderedFeatures(e.point, {
        layers: ["registry-parcel-fill", "registry-point", "unclustered-centroid"],
      });
      if (parcelFeatures.length > 0) {
        const props = parcelFeatures[0].properties ?? {};
        // Parse JSON arrays stored as strings in properties
        let brands: string[] = [];
        let sources: string[] = [];
        try { brands = JSON.parse(props.brands || "[]"); } catch { brands = []; }
        try { sources = JSON.parse(props.sources || "[]"); } catch { sources = []; }

        setPopupData({
          lng: e.lngLat.lng,
          lat: e.lngLat.lat,
          arn: props.arn || "",
          pid: props.pid || null,
          address: props.address || "",
          city: props.city || null,
          brands,
          transaction_count: props.transaction_count ?? 0,
          latest_price: props.latest_price ?? null,
          latest_date: props.latest_date || null,
          sources,
          zoning: props.zoning || null,
        });
        return;
      }

      // Click empty space — close popup
      setPopupData(null);
    },
    []
  );

  if (!MAPBOX_TOKEN) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <h2 className="text-lg font-semibold text-foreground mb-2">Mapbox token not configured</h2>
          <p className="text-sm text-muted-foreground">
            Add <code className="bg-muted px-1 rounded">VITE_MAPBOX_TOKEN</code> to{" "}
            <code className="bg-muted px-1 rounded">frontend/.env</code> and restart the dev server.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="relative" style={{ height: "100vh" }}>
      {/* Filter panel */}
      <div className="absolute top-3 left-3 z-10 bg-background/95 backdrop-blur rounded-lg shadow-lg" style={{ maxWidth: 380 }}>
        <div className="px-3 py-2 flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setFiltersOpen(!filtersOpen)}
            className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium h-8"
          >
            <SlidersHorizontal size={13} />
            Filters
            {hasFilters && (
              <Badge variant="secondary" className="px-1.5 py-0.5 rounded-full text-[10px] font-semibold leading-none">!</Badge>
            )}
            {filtersOpen ? <CaretUp size={12} /> : <CaretDown size={12} />}
          </Button>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {parcelLoading ? "Loading..." : `${parcelCount.toLocaleString()} parcels`}
          </span>
        </div>

        {filtersOpen && (
          <div className="px-3 pb-3 pt-1 border-t border-border space-y-2">
            {/* City */}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">City</span>
              <select
                value={cityFilter}
                onChange={(e) => updateParams({ city: e.target.value || null })}
                className="text-xs border rounded px-2 py-1 bg-background flex-1 h-7"
              >
                <option value="">All cities</option>
                {filtersData?.cities.slice(0, 50).map((c) => (
                  <option key={c.name} value={c.name}>{c.name} ({c.count.toLocaleString()})</option>
                ))}
              </select>
            </div>

            {/* Brand */}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">Brand</span>
              <select
                value={brandFilter}
                onChange={(e) => updateParams({ brand: e.target.value || null })}
                className="text-xs border rounded px-2 py-1 bg-background flex-1 h-7"
              >
                <option value="">All brands</option>
                {filtersData?.brands.slice(0, 100).sort((a, b) => a.name.localeCompare(b.name)).map((b) => (
                  <option key={b.name} value={b.name}>{b.name} ({b.count})</option>
                ))}
              </select>
            </div>

            {/* Price range */}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">Price</span>
              <span className="text-muted-foreground text-xs">$</span>
              <Input
                type="number"
                placeholder="Min"
                value={priceMin}
                onChange={(e) => updateParams({ pmin: e.target.value || null })}
                className="px-2 py-1 w-24 h-7 text-sm"
              />
              <span className="text-muted-foreground text-xs">to $</span>
              <Input
                type="number"
                placeholder="Max"
                value={priceMax}
                onChange={(e) => updateParams({ pmax: e.target.value || null })}
                className="px-2 py-1 w-24 h-7 text-sm"
              />
            </div>

            {/* Toggles */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-1">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">Txns</span>
                <select
                  value={txnsFilter}
                  onChange={(e) => updateParams({ txns: e.target.value || null })}
                  className="text-xs border rounded px-2 py-1 bg-background h-7"
                >
                  <option value="">Any</option>
                  <option value="yes">With transactions</option>
                  <option value="no">No transactions</option>
                </select>
              </div>
              <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer select-none">
                <Checkbox
                  checked={showPOIs}
                  onCheckedChange={(checked) => updateParams({ poi: checked ? "1" : null })}
                />
                Brand POIs
                {showPOIs && currentZoom < POI_ZOOM_THRESHOLD && (
                  <span className="text-[10px] text-muted-foreground">(zoom in)</span>
                )}
              </label>
              {hasFilters && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => updateParams({ city: null, brand: null, txns: null, pmin: null, pmax: null })}
                  className="ml-auto inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground h-auto px-1 py-0.5"
                >
                  <X size={12} />
                  Clear
                </Button>
              )}
            </div>
          </div>
        )}
      </div>

      <MapGL
        ref={mapRef}
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={savedView.current ?? {
          latitude: 44.0,
          longitude: -79.5,
          zoom: 6,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle="mapbox://styles/mapbox/light-v11"
        onClick={onClick}
        onMoveEnd={(e) => {
          const { latitude, longitude, zoom, bearing, pitch } = e.viewState;
          sessionStorage.setItem(MAP_VIEW_KEY, JSON.stringify({ latitude, longitude, zoom, bearing, pitch }));
          setCurrentZoom(zoom);
          // Debounced parcel fetch on pan/zoom
          if (fetchTimer.current) clearTimeout(fetchTimer.current);
          fetchTimer.current = setTimeout(() => {
            if (mapRef.current) fetchParcels(mapRef.current);
          }, 300);
        }}
        onLoad={() => {
          if (mapRef.current) fetchParcels(mapRef.current);
        }}
        interactiveLayerIds={["clusters", "unclustered-centroid", "registry-parcel-fill", "registry-point"]}
        cursor="pointer"
      >
        {/* Polygon source — visible at high zoom */}
        {showPolygons && (
          <Source id="registry-parcels" type="geojson" data={parcelData}>
            <Layer {...registryParcelFillLayer} />
            <Layer {...registryParcelLineLayer} />
            <Layer {...registryPointLayer} />
          </Source>
        )}

        {/* Centroid cluster source — visible at low zoom */}
        {!showPolygons && (
          <Source
            id="registry-centroids"
            type="geojson"
            data={centroidGeojson}
            cluster={true}
            clusterMaxZoom={12}
            clusterRadius={35}
          >
            <Layer {...clusterLayer} />
            <Layer {...clusterCountLayer} />
            <Layer {...unclusteredCentroidLayer} />
          </Source>
        )}

        {/* POI layers from Mapbox vector tiles */}
        {showPOIs && (
          <>
            <Layer {...poiCircleLayer} />
            <Layer {...poiLabelLayer} />
          </>
        )}

        {/* Popup */}
        {popupData && (
          <Popup
            latitude={popupData.lat}
            longitude={popupData.lng}
            onClose={() => setPopupData(null)}
            closeButton={false}
            closeOnClick={false}
            maxWidth="300px"
            offset={12}
          >
            <div className="min-w-[220px] max-w-[280px]">
              <div className="flex items-start justify-between gap-2 mb-1">
                <h3 className="text-sm font-semibold text-foreground leading-tight">
                  {popupData.address || "Unnamed Parcel"}
                </h3>
                <button
                  onClick={() => setPopupData(null)}
                  className="text-muted-foreground hover:text-foreground text-lg leading-none -mt-0.5"
                >
                  &times;
                </button>
              </div>
              <p className="text-xs text-muted-foreground mb-2">
                {popupData.city}
                {popupData.pid && <span className="ml-2 font-mono">{popupData.pid}</span>}
              </p>

              <div className="space-y-1 text-xs text-foreground">
                {popupData.transaction_count > 0 && (
                  <div className="flex justify-between">
                    <span>Transactions</span>
                    <span className="font-medium">{popupData.transaction_count}</span>
                  </div>
                )}
                {popupData.latest_price != null && (
                  <div className="flex justify-between">
                    <span>Latest price</span>
                    <span className="font-medium">{formatPrice(popupData.latest_price)}</span>
                  </div>
                )}
                {popupData.latest_date && (
                  <div className="flex justify-between">
                    <span>Latest sale</span>
                    <span className="font-medium">{popupData.latest_date}</span>
                  </div>
                )}
                {popupData.zoning && (
                  <div className="flex justify-between">
                    <span>Zoning</span>
                    <span className="font-mono">{popupData.zoning}</span>
                  </div>
                )}
                {popupData.brands.length > 0 && (
                  <div className="flex flex-wrap gap-1 pt-1">
                    {popupData.brands.map((b) => (
                      <Badge key={b} variant="secondary" className="text-[10px] px-1.5 py-0">
                        {b}
                      </Badge>
                    ))}
                  </div>
                )}
                {popupData.sources.length > 0 && (
                  <div className="flex gap-1 pt-1">
                    {popupData.sources.map((s) => (
                      <Badge key={s} variant="outline" className="text-[10px] px-1.5 py-0">
                        {s}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex gap-2 mt-3">
                <Button
                  variant="secondary"
                  size="sm"
                  className="flex-1 text-xs"
                  onClick={() => {
                    setPopupData(null);
                    navigate(`/parcels/${popupData.arn}`);
                  }}
                >
                  View parcel
                </Button>
              </div>
            </div>
          </Popup>
        )}
      </MapGL>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 z-10 bg-background/95 backdrop-blur rounded-lg shadow-lg px-3 py-2">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Parcels</p>
        <div className="space-y-1">
          {([
            ["#0d9488", "With transactions"],
            ["#f59e0b", "Branded only"],
          ] as const).map(([color, label]) => (
            <div key={label} className="flex items-center gap-1.5">
              <span
                className="inline-block w-3 h-3 rounded-sm border border-white shadow-sm flex-none"
                style={{ backgroundColor: color }}
              />
              <span className="text-[10px] text-foreground leading-none">{label}</span>
            </div>
          ))}
          {showPOIs && (
            <div className="flex items-center gap-1.5 mt-1.5 pt-1.5 border-t border-border">
              <span className="inline-block w-3 h-3 rounded-full border border-white shadow-sm flex-none" style={{ backgroundColor: "#7c3aed" }} />
              <span className="text-[10px] text-foreground leading-none">Brand POI</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
