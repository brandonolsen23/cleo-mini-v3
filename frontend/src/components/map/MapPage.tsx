import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import MapGL, { Source, Layer, Popup } from "react-map-gl/mapbox";
import type { MapRef, MapMouseEvent } from "react-map-gl/mapbox";
import type { LayerProps } from "react-map-gl/mapbox";
import type { FeatureCollection, Point, Polygon, MultiPolygon } from "geojson";
import type { GeoJSONSource } from "mapbox-gl";
import { MagnifyingGlass, SlidersHorizontal, CaretDown, CaretUp, X } from "@phosphor-icons/react";
import { useProperties } from "../../api/properties";
import type { PropertySummary } from "../../types/property";
import PropertyPopup from "./PropertyPopup";
import MultiSelect from "../shared/MultiSelect";
import type { MultiSelectOption } from "../shared/MultiSelect";
import { BRAND_CATEGORY, CATEGORY_COLORS, CATEGORY_LABELS, type Category } from "../shared/BrandBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN as string;

const clusterLayer: LayerProps = {
  id: "clusters",
  type: "circle",
  source: "properties",
  filter: ["has", "point_count"],
  paint: {
    "circle-color": [
      "step",
      ["get", "point_count"],
      "#a8a29e", // stone-400: < 10
      10,
      "#78716c", // stone-500: 10-50
      50,
      "#57534e", // stone-600: 50-200
      200,
      "#44403c", // stone-700: 200+
    ],
    "circle-radius": [
      "step",
      ["get", "point_count"],
      18, // < 10
      10,
      24, // 10-50
      50,
      30, // 50-200
      200,
      36, // 200+
    ],
  },
};

const clusterCountLayer: LayerProps = {
  id: "cluster-count",
  type: "symbol",
  source: "properties",
  filter: ["has", "point_count"],
  layout: {
    "text-field": "{point_count_abbreviated}",
    "text-size": 13,
  },
  paint: {
    "text-color": "#ffffff",
  },
};

// Radix step 8 hex values for pin coloring
const PIN_STATUS_COLORS: [string, string][] = [
  ["not_started", "#bcbbb5"],
  ["attempted_contact", "#5eb1ef"],
  ["interested", "#3db9cf"],
  ["listed", "#53b9ab"],
  ["active_deal", "#53b9ab"],
  ["in_negotiation", "#56ba9f"],
  ["under_contract", "#65ba74"],
  ["closed_won", "#8db654"],
  ["lost_cancelled", "#9b9ef0"],
  ["do_not_contact", "#ec8e7b"],
];

const unclusteredPointLayer: LayerProps = {
  id: "unclustered-point",
  type: "circle",
  source: "properties",
  filter: ["!", ["has", "point_count"]],
  paint: {
    "circle-color": [
      "match",
      ["get", "pin_status"],
      ...PIN_STATUS_COLORS.flat(),
      "#bcbbb5", // fallback
    ] as any,
    "circle-radius": 7,
    "circle-stroke-width": 2,
    "circle-stroke-color": "#ffffff",
  },
};

const footprintFillLayer: LayerProps = {
  id: "footprint-fill",
  type: "fill",
  source: "footprints",
  paint: {
    "fill-color": [
      "case",
      ["has", "matched_prop"],
      "#3b82f6", // blue for matched
      "#9ca3af", // gray for unmatched
    ],
    "fill-opacity": 0.25,
  },
};

const footprintLineLayer: LayerProps = {
  id: "footprint-line",
  type: "line",
  source: "footprints",
  paint: {
    "line-color": "#1e40af",
    "line-width": 1.5,
    "line-opacity": 0.7,
  },
};

const parcelFillLayer: LayerProps = {
  id: "parcel-fill",
  type: "fill",
  source: "parcels",
  paint: {
    "fill-color": "#f59e0b", // amber
    "fill-opacity": 0.15,
  },
};

const parcelLineLayer: LayerProps = {
  id: "parcel-line",
  type: "line",
  source: "parcels",
  paint: {
    "line-color": "#d97706", // amber-600
    "line-width": 1.5,
    "line-opacity": 0.7,
  },
};

const EMPTY_FC: FeatureCollection<Polygon | MultiPolygon> = {
  type: "FeatureCollection",
  features: [],
};

const FOOTPRINT_ZOOM_THRESHOLD = 15;

function parsePriceNumeric(price: string): number {
  const cleaned = price.replace(/[^0-9.]/g, "");
  return cleaned ? parseFloat(cleaned) : 0;
}

const MAP_VIEW_KEY = "cleo-map-view";

function getSavedView() {
  try {
    const raw = sessionStorage.getItem(MAP_VIEW_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return null;
}

export default function MapPage() {
  const { data: properties, loading, error } = useProperties();
  const mapRef = useRef<MapRef>(null);
  const [selected, setSelected] = useState<PropertySummary | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const savedView = useRef(getSavedView());

  // --- URL param state ---
  const searchText = searchParams.get("q") || "";
  const yearFrom = searchParams.get("yf") || "";
  const yearTo = searchParams.get("yt") || "";
  const priceMin = searchParams.get("pmin") || "";
  const priceMax = searchParams.get("pmax") || "";
  const popMin = searchParams.get("popmin") || "";
  const popMax = searchParams.get("popmax") || "";
  const bsMin = searchParams.get("bsmin") || "";
  const bsMax = searchParams.get("bsmax") || "";
  const acMin = searchParams.get("acmin") || "";
  const acMax = searchParams.get("acmax") || "";
  const txnsOnly = searchParams.get("txns") === "1";
  const noTxns = searchParams.get("notxns") === "1";
  const contactOnly = searchParams.get("contact") === "1";
  const phoneOnly = searchParams.get("phone") === "1";
  const selectedCategories = useMemo(() => {
    const raw = searchParams.get("cat");
    return raw ? raw.split(",").filter(Boolean) : [];
  }, [searchParams]);
  const selectedBrands = useMemo(() => {
    const raw = searchParams.get("brands");
    return raw ? raw.split(",").filter(Boolean) : [];
  }, [searchParams]);

  // --- Footprint state ---
  const showFootprints = searchParams.get("fp") === "1";
  const [footprintData, setFootprintData] = useState<FeatureCollection<Polygon | MultiPolygon>>(EMPTY_FC);
  const [currentZoom, setCurrentZoom] = useState(6);
  const footprintFetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchFootprints = useCallback((map: MapRef) => {
    if (!showFootprints) return;
    const zoom = map.getZoom();
    if (zoom < FOOTPRINT_ZOOM_THRESHOLD) {
      setFootprintData(EMPTY_FC);
      return;
    }
    const bounds = map.getBounds();
    if (!bounds) return;
    const { _sw, _ne } = bounds as any;
    const south = _sw.lat;
    const west = _sw.lng;
    const north = _ne.lat;
    const east = _ne.lng;
    fetch(`/api/footprints/geojson?south=${south}&west=${west}&north=${north}&east=${east}`)
      .then((r) => r.json())
      .then((data) => setFootprintData(data))
      .catch(() => {});
  }, [showFootprints]);

  // --- Parcel state ---
  const showParcels = searchParams.get("pcl") === "1";
  const [parcelData, setParcelData] = useState<FeatureCollection<Polygon | MultiPolygon>>(EMPTY_FC);
  const parcelFetchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchParcels = useCallback((map: MapRef) => {
    if (!showParcels) return;
    const zoom = map.getZoom();
    if (zoom < FOOTPRINT_ZOOM_THRESHOLD) {
      setParcelData(EMPTY_FC);
      return;
    }
    const bounds = map.getBounds();
    if (!bounds) return;
    const { _sw, _ne } = bounds as any;
    const south = _sw.lat;
    const west = _sw.lng;
    const north = _ne.lat;
    const east = _ne.lng;
    fetch(`/api/parcels/geojson?south=${south}&west=${west}&north=${north}&east=${east}`)
      .then((r) => r.json())
      .then((data) => setParcelData(data))
      .catch(() => {});
  }, [showParcels]);

  const hasFilters = !!(yearFrom || yearTo || priceMin || priceMax || popMin || popMax || bsMin || bsMax || acMin || acMax || txnsOnly || noTxns || contactOnly || phoneOnly || selectedCategories.length || selectedBrands.length);
  const [filtersOpen, setFiltersOpen] = useState(hasFilters);

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

  // --- Filter options ---
  const categoryOptions: MultiSelectOption[] = useMemo(
    () =>
      (Object.keys(CATEGORY_LABELS) as Category[]).map((key) => ({
        value: key,
        label: CATEGORY_LABELS[key],
        color: CATEGORY_COLORS[key].split(" ")[0],
      })),
    []
  );

  const brandOptions: MultiSelectOption[] = useMemo(() => {
    const brandsInData = new Set(properties.flatMap((p) => p.brands));
    let entries = Object.entries(BRAND_CATEGORY).filter(([b]) => brandsInData.has(b));
    if (selectedCategories.length > 0) {
      entries = entries.filter(([, cat]) => selectedCategories.includes(cat));
    }
    return entries
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([brand, cat]) => ({
        value: brand,
        label: brand,
        color: CATEGORY_COLORS[cat].split(" ")[0],
      }));
  }, [properties, selectedCategories]);

  // --- Geocoded + filtered ---
  const geocoded = useMemo(
    () => properties.filter((p) => p.lat !== null && p.lng !== null),
    [properties]
  );

  const filtered = useMemo(() => {
    const q = searchText.toLowerCase();
    const hasCat = selectedCategories.length > 0;
    const hasBrand = selectedBrands.length > 0;
    const yf = yearFrom ? parseInt(yearFrom, 10) : NaN;
    const yt = yearTo ? parseInt(yearTo, 10) : NaN;
    const pmin = priceMin ? parseFloat(priceMin) : NaN;
    const pmax = priceMax ? parseFloat(priceMax) : NaN;
    const popmin = popMin ? parseInt(popMin, 10) : NaN;
    const popmax = popMax ? parseInt(popMax, 10) : NaN;
    const bsmin = bsMin ? parseFloat(bsMin) : NaN;
    const bsmax = bsMax ? parseFloat(bsMax) : NaN;
    const acmin = acMin ? parseFloat(acMin) : NaN;
    const acmax = acMax ? parseFloat(acMax) : NaN;

    return geocoded.filter((p) => {
      if (q && !(p._search_text ?? "").includes(q)) return false;

      if (!isNaN(yf) || !isNaN(yt)) {
        const year = parseInt(p.latest_sale_year, 10);
        if (isNaN(year)) return false;
        if (!isNaN(yf) && year < yf) return false;
        if (!isNaN(yt) && year > yt) return false;
      }

      if (!isNaN(pmin) || !isNaN(pmax)) {
        const price = parsePriceNumeric(p.latest_sale_price);
        if (!price) return false;
        if (!isNaN(pmin) && price < pmin) return false;
        if (!isNaN(pmax) && price > pmax) return false;
      }

      if (!isNaN(popmin) || !isNaN(popmax)) {
        const pop = p.population;
        if (pop == null) return false;
        if (!isNaN(popmin) && pop < popmin) return false;
        if (!isNaN(popmax) && pop > popmax) return false;
      }

      if (!isNaN(bsmin) || !isNaN(bsmax)) {
        const raw = p.building_sf?.replace(/[^0-9.]/g, "");
        if (!raw) return false;
        const val = parseFloat(raw);
        if (isNaN(val)) return false;
        if (!isNaN(bsmin) && val < bsmin) return false;
        if (!isNaN(bsmax) && val > bsmax) return false;
      }

      if (!isNaN(acmin) || !isNaN(acmax)) {
        const raw = p.site_area?.replace(/[^0-9.]/g, "");
        if (!raw) return false;
        const val = parseFloat(raw);
        if (isNaN(val)) return false;
        if (!isNaN(acmin) && val < acmin) return false;
        if (!isNaN(acmax) && val > acmax) return false;
      }

      if ((hasCat || hasBrand) && !p.brands.some(
        (b) =>
          (hasCat && selectedCategories.includes(BRAND_CATEGORY[b])) ||
          (hasBrand && selectedBrands.includes(b))
      )) return false;

      if (txnsOnly && p.transaction_count === 0) return false;
      if (noTxns && p.transaction_count > 0) return false;
      if (contactOnly && !p.has_contact) return false;
      if (phoneOnly && !p.has_phone) return false;

      return true;
    });
  }, [geocoded, searchText, yearFrom, yearTo, priceMin, priceMax, popMin, popMax, bsMin, bsMax, acMin, acMax, selectedCategories, selectedBrands, txnsOnly, noTxns, contactOnly, phoneOnly]);

  // Clear popup when the selected property gets filtered out
  useEffect(() => {
    if (selected && !filtered.some((p) => p.prop_id === selected.prop_id)) {
      setSelected(null);
    }
  }, [filtered, selected]);

  // Fetch footprints when toggle is enabled
  useEffect(() => {
    if (showFootprints && mapRef.current) {
      fetchFootprints(mapRef.current);
    } else if (!showFootprints) {
      setFootprintData(EMPTY_FC);
    }
  }, [showFootprints, fetchFootprints]);

  // Fetch parcels when toggle is enabled
  useEffect(() => {
    if (showParcels && mapRef.current) {
      fetchParcels(mapRef.current);
    } else if (!showParcels) {
      setParcelData(EMPTY_FC);
    }
  }, [showParcels, fetchParcels]);

  const geojson = useMemo<FeatureCollection>(
    () => ({
      type: "FeatureCollection",
      features: filtered.map((p) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [p.lng!, p.lat!] },
        properties: { prop_id: p.prop_id, pin_status: p.pin_status || "not_started" },
      })),
    }),
    [filtered]
  );

  const propById = useMemo(() => {
    const m: Record<string, PropertySummary> = {};
    for (const p of filtered) m[p.prop_id] = p;
    return m;
  }, [filtered]);

  const activeFilterCount = [
    yearFrom || yearTo ? 1 : 0,
    priceMin || priceMax ? 1 : 0,
    popMin || popMax ? 1 : 0,
    bsMin || bsMax ? 1 : 0,
    acMin || acMax ? 1 : 0,
    txnsOnly || noTxns ? 1 : 0,
    contactOnly ? 1 : 0,
    phoneOnly ? 1 : 0,
    selectedCategories.length ? 1 : 0,
    selectedBrands.length ? 1 : 0,
  ].reduce((a, b) => a + b, 0);

  const onClick = useCallback(
    (e: MapMouseEvent) => {
      const map = mapRef.current;
      if (!map) return;

      // Check clusters first
      const clusterFeatures = map.queryRenderedFeatures(e.point, {
        layers: ["clusters"],
      });
      if (clusterFeatures.length > 0) {
        const feature = clusterFeatures[0];
        const clusterId = feature.properties?.cluster_id;
        const source = map.getSource("properties") as GeoJSONSource;
        source.getClusterExpansionZoom(clusterId, (err: Error | null | undefined, zoom: number | null | undefined) => {
          if (err || zoom == null) return;
          const geom = feature.geometry as Point;
          map.easeTo({
            center: [geom.coordinates[0], geom.coordinates[1]],
            zoom,
          });
        });
        return;
      }

      // Check unclustered points
      const pointFeatures = map.queryRenderedFeatures(e.point, {
        layers: ["unclustered-point"],
      });
      if (pointFeatures.length > 0) {
        const propId = pointFeatures[0].properties?.prop_id;
        const prop = propById[propId];
        if (prop) setSelected(prop);
      }
    },
    [propById]
  );

  if (!MAPBOX_TOKEN) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center max-w-md">
          <h2 className="text-lg font-semibold text-foreground mb-2">
            Mapbox token not configured
          </h2>
          <p className="text-sm text-muted-foreground">
            Add <code className="bg-muted px-1 rounded">VITE_MAPBOX_TOKEN</code> to{" "}
            <code className="bg-muted px-1 rounded">frontend/.env</code> and restart the dev
            server.
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading properties...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-destructive">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="relative" style={{ height: "100vh" }}>
      {/* Filter panel */}
      <div className="absolute top-3 left-3 z-10 bg-background/95 backdrop-blur rounded-lg shadow-lg" style={{ maxWidth: 380 }}>
        <div className="px-3 py-2 flex items-center gap-2">
          <div className="relative flex-1">
            <MagnifyingGlass size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search..."
              value={searchText}
              onChange={(e) => updateParams({ q: e.target.value || null })}
              className="pl-7 pr-3 py-1.5 w-full h-8 text-sm"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setFiltersOpen(!filtersOpen)}
            className="inline-flex items-center gap-1 px-2 py-1.5 text-xs font-medium h-8"
          >
            <SlidersHorizontal size={13} />
            Filters
            {activeFilterCount > 0 && (
              <Badge variant="secondary" className="px-1.5 py-0.5 rounded-full text-[10px] font-semibold leading-none">
                {activeFilterCount}
              </Badge>
            )}
            {filtersOpen ? <CaretUp size={12} /> : <CaretDown size={12} />}
          </Button>
          <span className="text-xs text-muted-foreground whitespace-nowrap">
            {filtered.length.toLocaleString()}{(searchText || hasFilters) && ` / ${geocoded.length.toLocaleString()}`}
          </span>
        </div>

        {filtersOpen && (
          <div className="px-3 pb-3 pt-1 border-t border-border space-y-2">
            {/* Year range */}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">Year</span>
              <Input
                type="number"
                placeholder="From"
                value={yearFrom}
                onChange={(e) => updateParams({ yf: e.target.value || null })}
                className="px-2 py-1 w-20 h-7 text-sm"
              />
              <span className="text-muted-foreground text-xs">to</span>
              <Input
                type="number"
                placeholder="To"
                value={yearTo}
                onChange={(e) => updateParams({ yt: e.target.value || null })}
                className="px-2 py-1 w-20 h-7 text-sm"
              />
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

            {/* Population range */}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">Pop.</span>
              <Input
                type="number"
                placeholder="Min"
                value={popMin}
                onChange={(e) => updateParams({ popmin: e.target.value || null })}
                className="px-2 py-1 w-24 h-7 text-sm"
              />
              <span className="text-muted-foreground text-xs">to</span>
              <Input
                type="number"
                placeholder="Max"
                value={popMax}
                onChange={(e) => updateParams({ popmax: e.target.value || null })}
                className="px-2 py-1 w-24 h-7 text-sm"
              />
            </div>

            {/* Building SF range */}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">Bldg SF</span>
              <Input
                type="number"
                placeholder="Min"
                value={bsMin}
                onChange={(e) => updateParams({ bsmin: e.target.value || null })}
                className="px-2 py-1 w-24 h-7 text-sm"
              />
              <span className="text-muted-foreground text-xs">to</span>
              <Input
                type="number"
                placeholder="Max"
                value={bsMax}
                onChange={(e) => updateParams({ bsmax: e.target.value || null })}
                className="px-2 py-1 w-24 h-7 text-sm"
              />
            </div>

            {/* Acreage range */}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">Acres</span>
              <Input
                type="number"
                step="0.01"
                placeholder="Min"
                value={acMin}
                onChange={(e) => updateParams({ acmin: e.target.value || null })}
                className="px-2 py-1 w-20 h-7 text-sm"
              />
              <span className="text-muted-foreground text-xs">to</span>
              <Input
                type="number"
                step="0.01"
                placeholder="Max"
                value={acMax}
                onChange={(e) => updateParams({ acmax: e.target.value || null })}
                className="px-2 py-1 w-20 h-7 text-sm"
              />
            </div>

            {/* Brand selects */}
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider w-12 shrink-0">Brand</span>
              <MultiSelect
                options={categoryOptions}
                selected={selectedCategories}
                onChange={(vals) => updateParams({ cat: vals.length ? vals.join(",") : null })}
                placeholder="Category"
              />
              <MultiSelect
                options={brandOptions}
                selected={selectedBrands}
                onChange={(vals) => updateParams({ brands: vals.length ? vals.join(",") : null })}
                placeholder="Name"
              />
            </div>

            {/* Checkboxes + clear */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 pt-1">
              <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer select-none">
                <Checkbox
                  checked={txnsOnly}
                  onCheckedChange={(checked) => updateParams({ txns: checked ? "1" : null, notxns: null })}
                />
                Has txns
              </label>
              <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer select-none">
                <Checkbox
                  checked={noTxns}
                  onCheckedChange={(checked) => updateParams({ notxns: checked ? "1" : null, txns: null })}
                />
                No txns
              </label>
              <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer select-none">
                <Checkbox
                  checked={contactOnly}
                  onCheckedChange={(checked) => updateParams({ contact: checked ? "1" : null })}
                />
                Has contact
              </label>
              <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer select-none">
                <Checkbox
                  checked={phoneOnly}
                  onCheckedChange={(checked) => updateParams({ phone: checked ? "1" : null })}
                />
                Has phone
              </label>
              <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer select-none">
                <Checkbox
                  checked={showFootprints}
                  onCheckedChange={(checked) => updateParams({ fp: checked ? "1" : null })}
                />
                Building footprints
                {showFootprints && currentZoom < FOOTPRINT_ZOOM_THRESHOLD && (
                  <span className="text-[10px] text-muted-foreground">(zoom in)</span>
                )}
              </label>
              <label className="flex items-center gap-1.5 text-xs text-foreground cursor-pointer select-none">
                <Checkbox
                  checked={showParcels}
                  onCheckedChange={(checked) => updateParams({ pcl: checked ? "1" : null })}
                />
                Parcel boundaries
                {showParcels && currentZoom < FOOTPRINT_ZOOM_THRESHOLD && (
                  <span className="text-[10px] text-muted-foreground">(zoom in)</span>
                )}
              </label>
              {hasFilters && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => updateParams({ yf: null, yt: null, pmin: null, pmax: null, popmin: null, popmax: null, bsmin: null, bsmax: null, acmin: null, acmax: null, txns: null, notxns: null, contact: null, phone: null, cat: null, brands: null })}
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
          // Debounced footprint + parcel fetch
          if (footprintFetchTimer.current) clearTimeout(footprintFetchTimer.current);
          footprintFetchTimer.current = setTimeout(() => {
            if (mapRef.current) fetchFootprints(mapRef.current);
          }, 300);
          if (parcelFetchTimer.current) clearTimeout(parcelFetchTimer.current);
          parcelFetchTimer.current = setTimeout(() => {
            if (mapRef.current) fetchParcels(mapRef.current);
          }, 300);
        }}
        interactiveLayerIds={["clusters", "unclustered-point"]}
        cursor="pointer"
      >
        <Source
          id="properties"
          type="geojson"
          data={geojson}
          cluster={true}
          clusterMaxZoom={11}
          clusterRadius={35}
        >
          <Layer {...clusterLayer} />
          <Layer {...clusterCountLayer} />
          <Layer {...unclusteredPointLayer} />
        </Source>

        {showFootprints && (
          <Source id="footprints" type="geojson" data={footprintData}>
            <Layer {...footprintFillLayer} />
            <Layer {...footprintLineLayer} />
          </Source>
        )}

        {showParcels && (
          <Source id="parcels" type="geojson" data={parcelData}>
            <Layer {...parcelFillLayer} />
            <Layer {...parcelLineLayer} />
          </Source>
        )}

        {selected && (
          <Popup
            latitude={selected.lat!}
            longitude={selected.lng!}
            onClose={() => setSelected(null)}
            closeButton={false}
            closeOnClick={false}
            maxWidth="300px"
            offset={12}
          >
            <PropertyPopup
              property={selected}
              onClose={() => setSelected(null)}
            />
          </Popup>
        )}
      </MapGL>

      {/* Legend */}
      <div className="absolute bottom-4 right-4 z-10 bg-background/95 backdrop-blur rounded-lg shadow-lg px-3 py-2">
        <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">Pipeline</p>
        <div className="space-y-1">
          {([
            ["#bcbbb5", "Not Started"],
            ["#5eb1ef", "Attempted Contact"],
            ["#3db9cf", "Interested"],
            ["#53b9ab", "Listed / Active Deal"],
            ["#56ba9f", "In Negotiation"],
            ["#65ba74", "Under Contract"],
            ["#8db654", "Closed / Won"],
            ["#9b9ef0", "Lost / Cancelled"],
            ["#ec8e7b", "Do Not Contact"],
          ] as const).map(([color, label]) => (
            <div key={label} className="flex items-center gap-1.5">
              <span
                className="inline-block w-3 h-3 rounded-full border border-white shadow-sm flex-none"
                style={{ backgroundColor: color }}
              />
              <span className="text-[10px] text-foreground leading-none">{label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
