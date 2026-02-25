import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import type { ColumnFiltersState } from "@tanstack/react-table";
import { MagnifyingGlass, ArrowsDownUp, ArrowUp, ArrowDown, X, SlidersHorizontal, CaretDown, CaretUp } from "@phosphor-icons/react";
import { useProperties } from "../../api/properties";
import type { PropertySummary } from "../../types/property";
import Pagination from "../shared/Pagination";
import BrandBadge, { BRAND_CATEGORY, CATEGORY_COLORS, CATEGORY_LABELS, type Category } from "../shared/BrandBadge";
import MultiSelect from "../shared/MultiSelect";
import type { MultiSelectOption } from "../shared/MultiSelect";
import { useTableParams } from "../../hooks/useTableParams";
import MapLink from "../shared/MapLink";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

const columnHelper = createColumnHelper<PropertySummary>();

function globalFilterFn(
  row: { original: PropertySummary },
  _columnId: string,
  filterValue: string,
): boolean {
  const q = filterValue.toLowerCase();
  return (row.original._search_text ?? "").includes(q);
}

function parsePriceNumeric(price: string): number {
  const cleaned = price.replace(/[^0-9.]/g, "");
  return cleaned ? parseFloat(cleaned) : 0;
}

function formatPopulation(pop: number | null): string {
  if (pop == null) return "";
  if (pop >= 1_000_000) return `${(pop / 1_000_000).toFixed(1)}M`;
  if (pop >= 10_000) return `${Math.round(pop / 1_000)}K`;
  if (pop >= 1_000) return `${(pop / 1_000).toFixed(1)}K`;
  return String(pop);
}

const columns = [
  columnHelper.accessor("address", {
    header: "Property",
    size: 260,
    cell: (info) => (
      <div>
        <div className="text-sm font-medium flex items-center gap-1.5 min-w-0">
          <span className="truncate" title={info.getValue()}>
            {info.getValue()}
          </span>
          <MapLink
            address={`${info.getValue()}, ${info.row.original.city}`}
            lat={info.row.original.lat}
            lng={info.row.original.lng}
          />
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {info.row.original.city}
        </div>
        {info.row.original.population != null && (
          <div className="text-xs text-muted-foreground mt-0.5 tabular-nums">
            Pop: {formatPopulation(info.row.original.population)}
          </div>
        )}
      </div>
    ),
  }),
  columnHelper.accessor("latest_sale_date", {
    header: "Last Sale",
    size: 120,
    enableGlobalFilter: false,
    sortingFn: (a, b) =>
      (a.original.latest_sale_date_iso || "").localeCompare(
        b.original.latest_sale_date_iso || ""
      ),
    cell: (info) => (
      <div>
        <div className="text-sm font-medium">{info.getValue() || info.row.original.latest_sale_year}</div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {info.row.original.transaction_count} txn{info.row.original.transaction_count !== 1 ? "s" : ""}
        </div>
      </div>
    ),
  }),
  columnHelper.accessor("latest_sale_price", {
    header: "Sale Price",
    size: 140,
    enableGlobalFilter: false,
    sortingFn: (a, b) =>
      parsePriceNumeric(a.original.latest_sale_price) -
      parsePriceNumeric(b.original.latest_sale_price),
    filterFn: (row, _columnId, filterValue: { min: string; max: string }) => {
      const price = parsePriceNumeric(row.original.latest_sale_price);
      if (!price) return false;
      if (filterValue.min && price < parseFloat(filterValue.min)) return false;
      if (filterValue.max && price > parseFloat(filterValue.max)) return false;
      return true;
    },
    cell: (info) => (
      <div className="text-sm font-medium">{info.getValue()}</div>
    ),
  }),
  columnHelper.accessor("brands", {
    header: "Brand",
    size: 190,
    filterFn: (row, _columnId, filterValue: { categories: string[]; brands: string[] }) => {
      const rowBrands = row.original.brands;
      const hasCat = filterValue.categories.length > 0;
      const hasBrand = filterValue.brands.length > 0;
      if (!hasCat && !hasBrand) return true;
      return rowBrands.some(
        (b) =>
          (hasCat && filterValue.categories.includes(BRAND_CATEGORY[b])) ||
          (hasBrand && filterValue.brands.includes(b))
      );
    },
    cell: (info) => {
      const brands = info.getValue();
      if (!brands?.length) return null;
      return (
        <div className="flex flex-col items-start gap-1">
          {brands.map((b) => <BrandBadge key={b} brand={b} />)}
        </div>
      );
    },
  }),
  columnHelper.accessor("owner", {
    header: "Owner",
    meta: { grow: true },
    cell: (info) => (
      <div>
        <div className="text-sm font-medium truncate" title={info.getValue()}>
          {info.getValue()}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1.5">
          <span className="font-mono">{info.row.original.prop_id}</span>
          {info.row.original.has_photos && <span>📷</span>}
        </div>
      </div>
    ),
  }),
  // Hidden filter-only columns
  columnHelper.accessor("population", {
    header: "Market",
    enableSorting: false,
    enableGlobalFilter: false,
    filterFn: (row, _columnId, filterValue: { min: string; max: string }) => {
      const pop = row.original.population;
      if (pop == null) return false;
      if (filterValue.min && pop < parseInt(filterValue.min)) return false;
      if (filterValue.max && pop > parseInt(filterValue.max)) return false;
      return true;
    },
  }),
  columnHelper.accessor("latest_sale_year", {
    header: "Sale Year",
    enableSorting: false,
    enableGlobalFilter: false,
    filterFn: (row, _columnId, filterValue: { from: string; to: string }) => {
      const latest = parseInt(row.original.latest_sale_year, 10);
      if (isNaN(latest)) return false;
      const from = filterValue.from ? parseInt(filterValue.from, 10) : NaN;
      const to = filterValue.to ? parseInt(filterValue.to, 10) : NaN;
      if (!isNaN(from) && latest < from) return false;
      if (!isNaN(to) && latest > to) return false;
      return true;
    },
  }),
  columnHelper.accessor("has_contact", {
    header: "Contact",
    enableSorting: false,
    enableGlobalFilter: false,
    filterFn: (row) => row.original.has_contact,
  }),
  columnHelper.accessor("has_phone", {
    header: "Phone",
    enableSorting: false,
    enableGlobalFilter: false,
    filterFn: (row) => row.original.has_phone,
  }),
  columnHelper.accessor("building_sf", {
    header: "Bldg SF",
    enableSorting: false,
    enableGlobalFilter: false,
    filterFn: (row, _columnId, filterValue: { min: string; max: string }) => {
      const raw = row.original.building_sf?.replace(/[^0-9.]/g, "");
      if (!raw) return false;
      const val = parseFloat(raw);
      if (isNaN(val)) return false;
      if (filterValue.min && val < parseFloat(filterValue.min)) return false;
      if (filterValue.max && val > parseFloat(filterValue.max)) return false;
      return true;
    },
  }),
  columnHelper.accessor("site_area", {
    header: "Acres",
    enableSorting: false,
    enableGlobalFilter: false,
    filterFn: (row, _columnId, filterValue: { min: string; max: string }) => {
      const raw = row.original.site_area?.replace(/[^0-9.]/g, "");
      if (!raw) return false;
      const val = parseFloat(raw);
      if (isNaN(val)) return false;
      if (filterValue.min && val < parseFloat(filterValue.min)) return false;
      if (filterValue.max && val > parseFloat(filterValue.max)) return false;
      return true;
    },
  }),
];

export default function PropertiesPage() {
  const { data, loading, error } = useProperties();
  const {
    globalFilter, sorting, pagination,
    setGlobalFilter, setSorting, setPagination,
    searchParams, updateParams,
  } = useTableParams([{ id: "latest_sale_date", desc: true }]);
  const navigate = useNavigate();

  // Read filter params from URL
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
  const hasFilters = !!(yearFrom || yearTo || priceMin || priceMax || popMin || popMax || bsMin || bsMax || acMin || acMax || contactOnly || phoneOnly || selectedCategories.length || selectedBrands.length);
  const [filtersOpen, setFiltersOpen] = useState(hasFilters);

  // Category dropdown options
  const categoryOptions: MultiSelectOption[] = useMemo(
    () =>
      (Object.keys(CATEGORY_LABELS) as Category[]).map((key) => ({
        value: key,
        label: CATEGORY_LABELS[key],
        color: CATEGORY_COLORS[key].split(" ")[0],
      })),
    []
  );

  // Brand dropdown options — derived from dataset, filtered by selected categories
  const brandOptions: MultiSelectOption[] = useMemo(() => {
    const brandsInData = new Set(data.flatMap((p) => p.brands));
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
  }, [data, selectedCategories]);

  // Build column filters from URL params
  const columnFilters: ColumnFiltersState = useMemo(() => {
    const filters: ColumnFiltersState = [];
    if (yearFrom || yearTo) {
      filters.push({ id: "latest_sale_year", value: { from: yearFrom, to: yearTo } });
    }
    if (priceMin || priceMax) {
      filters.push({ id: "latest_sale_price", value: { min: priceMin, max: priceMax } });
    }
    if (popMin || popMax) {
      filters.push({ id: "population", value: { min: popMin, max: popMax } });
    }
    if (contactOnly) {
      filters.push({ id: "has_contact", value: true });
    }
    if (phoneOnly) {
      filters.push({ id: "has_phone", value: true });
    }
    if (bsMin || bsMax) {
      filters.push({ id: "building_sf", value: { min: bsMin, max: bsMax } });
    }
    if (acMin || acMax) {
      filters.push({ id: "site_area", value: { min: acMin, max: acMax } });
    }
    if (selectedCategories.length || selectedBrands.length) {
      filters.push({ id: "brands", value: { categories: selectedCategories, brands: selectedBrands } });
    }
    return filters;
  }, [yearFrom, yearTo, priceMin, priceMax, popMin, popMax, bsMin, bsMax, acMin, acMax, contactOnly, phoneOnly, selectedCategories, selectedBrands]);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting, globalFilter, pagination, columnFilters,
      columnVisibility: { has_contact: false, has_phone: false, population: false, latest_sale_year: false, building_sf: false, site_area: false },
    },
    globalFilterFn,
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    autoResetPageIndex: false,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const handleRowClick = useCallback(
    (propId: string) => {
      navigate(`/properties/${propId}`);
    },
    [navigate]
  );

  const isFiltered = !!(globalFilter || hasFilters);
  const filteredCount = table.getFilteredRowModel().rows.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading properties...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-destructive">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Page header */}
      <div className="flex-none px-6 py-4 bg-background border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold">Properties</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {filteredCount.toLocaleString()} properties
              {isFiltered && ` (filtered from ${data.length.toLocaleString()})`}
            </p>
          </div>
          <div className="relative">
            <MagnifyingGlass
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              type="text"
              placeholder="Search all columns..."
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="pl-9 pr-4 w-72 h-9"
            />
          </div>
        </div>
      </div>

      {/* Filter toggle */}
      <div className="flex-none px-6 py-2 bg-muted border-b border-border">
        <button
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
        >
          <SlidersHorizontal size={14} />
          Filters
          {hasFilters && (
            <span className="ml-1 px-1.5 py-0.5 bg-secondary text-secondary-foreground rounded-full text-[10px] font-semibold">
              {[yearFrom || yearTo ? 1 : 0, priceMin || priceMax ? 1 : 0, popMin || popMax ? 1 : 0, bsMin || bsMax ? 1 : 0, acMin || acMax ? 1 : 0, contactOnly ? 1 : 0, phoneOnly ? 1 : 0, selectedCategories.length ? 1 : 0, selectedBrands.length ? 1 : 0].reduce((a, b) => a + b, 0)}
            </span>
          )}
          {filtersOpen ? <CaretUp size={12} /> : <CaretDown size={12} />}
        </button>

        {filtersOpen && (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-2.5 pb-0.5 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Year</span>
              <input
                type="number"
                placeholder="From"
                value={yearFrom}
                onChange={(e) => updateParams({ yf: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span className="text-muted-foreground">to</span>
              <input
                type="number"
                placeholder="To"
                value={yearTo}
                onChange={(e) => updateParams({ yt: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              {(yearFrom || yearTo) && (
                <Button variant="ghost" size="icon-sm" className="rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => updateParams({ yf: null, yt: null, page: null })}><X size={12} /></Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Price</span>
              <span className="text-muted-foreground">$</span>
              <input
                type="number"
                placeholder="Min"
                value={priceMin}
                onChange={(e) => updateParams({ pmin: e.target.value || null, page: null })}
                className="px-2 py-1 w-24 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span className="text-muted-foreground">to $</span>
              <input
                type="number"
                placeholder="Max"
                value={priceMax}
                onChange={(e) => updateParams({ pmax: e.target.value || null, page: null })}
                className="px-2 py-1 w-24 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              {(priceMin || priceMax) && (
                <Button variant="ghost" size="icon-sm" className="rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => updateParams({ pmin: null, pmax: null, page: null })}><X size={12} /></Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Pop.</span>
              <input
                type="number"
                placeholder="Min"
                value={popMin}
                onChange={(e) => updateParams({ popmin: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span className="text-muted-foreground">to</span>
              <input
                type="number"
                placeholder="Max"
                value={popMax}
                onChange={(e) => updateParams({ popmax: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              {(popMin || popMax) && (
                <Button variant="ghost" size="icon-sm" className="rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => updateParams({ popmin: null, popmax: null, page: null })}><X size={12} /></Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Bldg SF</span>
              <input
                type="number"
                placeholder="Min"
                value={bsMin}
                onChange={(e) => updateParams({ bsmin: e.target.value || null, page: null })}
                className="px-2 py-1 w-24 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span className="text-muted-foreground">to</span>
              <input
                type="number"
                placeholder="Max"
                value={bsMax}
                onChange={(e) => updateParams({ bsmax: e.target.value || null, page: null })}
                className="px-2 py-1 w-24 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              {(bsMin || bsMax) && (
                <Button variant="ghost" size="icon-sm" className="rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => updateParams({ bsmin: null, bsmax: null, page: null })}><X size={12} /></Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Acres</span>
              <input
                type="number"
                step="0.01"
                placeholder="Min"
                value={acMin}
                onChange={(e) => updateParams({ acmin: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span className="text-muted-foreground">to</span>
              <input
                type="number"
                step="0.01"
                placeholder="Max"
                value={acMax}
                onChange={(e) => updateParams({ acmax: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-input bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              {(acMin || acMax) && (
                <Button variant="ghost" size="icon-sm" className="rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => updateParams({ acmin: null, acmax: null, page: null })}><X size={12} /></Button>
              )}
            </div>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                <Checkbox
                  checked={contactOnly}
                  onCheckedChange={(checked) => updateParams({ contact: checked ? "1" : null, page: null })}
                />
                Has contact
              </label>
              <label className="flex items-center gap-1.5 text-sm cursor-pointer select-none">
                <Checkbox
                  checked={phoneOnly}
                  onCheckedChange={(checked) => updateParams({ phone: checked ? "1" : null, page: null })}
                />
                Has phone
              </label>
            </div>
            <div className="flex items-center gap-3">
              <MultiSelect
                label="Category"
                options={categoryOptions}
                selected={selectedCategories}
                onChange={(vals) => updateParams({ cat: vals.length ? vals.join(",") : null, page: null })}
                placeholder="All categories"
              />
              {selectedCategories.length > 0 && (
                <Button variant="ghost" size="icon-sm" className="rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => updateParams({ cat: null, page: null })}><X size={12} /></Button>
              )}
              <MultiSelect
                label="Brand"
                options={brandOptions}
                selected={selectedBrands}
                onChange={(vals) => updateParams({ brands: vals.length ? vals.join(",") : null, page: null })}
                placeholder="All brands"
              />
              {selectedBrands.length > 0 && (
                <Button variant="ghost" size="icon-sm" className="rounded-full text-destructive hover:bg-destructive/10 hover:text-destructive" onClick={() => updateParams({ brands: null, page: null })}><X size={12} /></Button>
              )}
            </div>
            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => updateParams({ yf: null, yt: null, pmin: null, pmax: null, popmin: null, popmax: null, bsmin: null, bsmax: null, acmin: null, acmax: null, contact: null, phone: null, cat: null, brands: null, page: null })}
              >
                <X size={12} />
                Clear all
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Column headers */}
      <div className="flex-none bg-background border-b border-border">
        {table.getHeaderGroups().map((headerGroup) => (
          <div key={headerGroup.id} className="flex">
            {headerGroup.headers.map((header) => {
              const grow = (header.column.columnDef.meta as { grow?: boolean })?.grow;
              return (
              <div
                key={header.id}
                className={`px-4 py-2 text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider cursor-pointer select-none hover:bg-accent overflow-hidden ${grow ? "flex-1 min-w-0" : "flex-none"}`}
                style={grow ? undefined : { width: header.getSize() }}
                onClick={header.column.getToggleSortingHandler()}
              >
                <div className="flex items-center gap-1">
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext()
                  )}
                  {header.column.getCanSort() &&
                    (({
                      asc: <ArrowUp size={12} />,
                      desc: <ArrowDown size={12} />,
                    }[header.column.getIsSorted() as string] ?? (
                      <ArrowsDownUp size={12} className="text-muted-foreground/50" />
                    )))}
                </div>
              </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-auto">
        {table.getRowModel().rows.map((row) => (
          <div
            key={row.id}
            className="flex hover:bg-muted/50 cursor-pointer border-b border-border transition-colors"
            onClick={() => handleRowClick(row.original.prop_id)}
          >
            {row.getVisibleCells().map((cell) => {
              const grow = (cell.column.columnDef.meta as { grow?: boolean })?.grow;
              return (
              <div
                key={cell.id}
                className={`px-4 py-4 text-xs overflow-hidden ${grow ? "flex-1 min-w-0" : "flex-none"}`}
                style={grow ? undefined : { width: cell.column.getSize() }}
              >
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </div>
              );
            })}
          </div>
        ))}
      </div>

      {/* Pagination */}
      <Pagination table={table} />
    </div>
  );
}
