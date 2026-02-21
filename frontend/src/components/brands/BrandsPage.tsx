import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
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
import { useBrands } from "../../api/brands";
import type { BrandStore } from "../../types/brand";
import Pagination from "../shared/Pagination";
import BrandBadge from "../shared/BrandBadge";
import { useTableParams } from "../../hooks/useTableParams";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";

const columnHelper = createColumnHelper<BrandStore>();

const columns = [
  columnHelper.accessor("store_name", {
    header: "Store",
    meta: { grow: true },
    cell: (info) => (
      <div>
        <div className="text-sm font-medium flex items-center gap-1.5 min-w-0">
          <span className="truncate" title={info.getValue()}>
            {info.getValue()}
          </span>
          <BrandBadge brand={info.row.original.brand} />
        </div>
        <div className="text-xs text-muted-foreground mt-0.5 truncate">
          {[info.row.original.address, info.row.original.city, info.row.original.province, info.row.original.postal_code].filter(Boolean).join(", ")}
        </div>
      </div>
    ),
  }),
  columnHelper.accessor("prop_id", {
    header: "Property",
    size: 120,
    cell: (info) => {
      const pid = info.getValue();
      return (
        <div>
          <div className="text-sm font-medium">
            {pid ? (
              <Link
                to={`/properties/${pid}`}
                className="text-primary hover:text-primary/80 font-mono text-xs"
                onClick={(e) => e.stopPropagation()}
              >
                {pid}
              </Link>
            ) : (
              <span className="text-muted-foreground/40">--</span>
            )}
          </div>
          {info.row.original.transaction_count > 0 && (
            <div className="text-xs text-muted-foreground mt-0.5">
              {info.row.original.transaction_count} txn{info.row.original.transaction_count !== 1 ? "s" : ""}
            </div>
          )}
        </div>
      );
    },
  }),
  // Hidden filter-only columns
  columnHelper.accessor("brand", {
    header: "Brand",
    enableSorting: false,
    filterFn: (row, _columnId, filterValue: string[]) => {
      if (!filterValue.length) return true;
      return filterValue.includes(row.original.brand);
    },
  }),
  columnHelper.accessor("transaction_count", {
    header: "Txns",
    size: 70,
    enableSorting: false,
    enableGlobalFilter: false,
    filterFn: (row, _columnId, filterValue: boolean) => {
      if (filterValue) return row.original.has_transactions;
      return true;
    },
  }),
];

export default function BrandsPage() {
  const { data, loading, error } = useBrands();
  const {
    globalFilter, sorting, pagination,
    setGlobalFilter, setSorting, setPagination,
    searchParams, updateParams,
  } = useTableParams();

  // Read filter params from URL
  const brandFilter = searchParams.get("brands")?.split(",").filter(Boolean) || [];
  const txOnly = searchParams.get("tx") === "1";
  const hasFilters = !!(brandFilter.length || txOnly);
  const [filtersOpen, setFiltersOpen] = useState(hasFilters);

  // Get unique brand names
  const brandNames = useMemo(() => {
    const names = new Set(data.map((s) => s.brand));
    return Array.from(names).sort();
  }, [data]);

  // Build column filters
  const columnFilters: ColumnFiltersState = useMemo(() => {
    const filters: ColumnFiltersState = [];
    if (brandFilter.length) {
      filters.push({ id: "brand", value: brandFilter });
    }
    if (txOnly) {
      filters.push({ id: "transaction_count", value: true });
    }
    return filters;
  }, [brandFilter, txOnly]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter, pagination, columnFilters, columnVisibility: { brand: false, transaction_count: false } },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onPaginationChange: setPagination,
    autoResetPageIndex: false,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const toggleBrand = useCallback(
    (brand: string) => {
      const current = searchParams.get("brands")?.split(",").filter(Boolean) || [];
      const next = current.includes(brand)
        ? current.filter((b) => b !== brand)
        : [...current, brand];
      updateParams({ brands: next.length ? next.join(",") : null, page: null });
    },
    [searchParams, updateParams]
  );

  const isFiltered = !!(globalFilter || hasFilters);
  const filteredCount = table.getFilteredRowModel().rows.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading brands...</div>
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
            <h1 className="text-lg font-semibold text-foreground">Brands</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {filteredCount.toLocaleString()} stores
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
              className="pl-9 pr-4 py-2 w-72 h-9 text-sm"
            />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex-none px-6 py-2 bg-muted border-b border-border">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground h-auto px-1 py-0.5"
        >
          <SlidersHorizontal size={14} />
          Filters
          {hasFilters && (
            <Badge variant="secondary" className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] font-semibold">
              {(brandFilter.length ? 1 : 0) + (txOnly ? 1 : 0)}
            </Badge>
          )}
          {filtersOpen ? <CaretUp size={12} /> : <CaretDown size={12} />}
        </Button>

        {filtersOpen && (
          <div className="flex items-center gap-6 mt-2.5 pb-0.5 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Brand</span>
              {brandNames.map((name) => (
                <label key={name} className="flex items-center gap-1.5 text-sm text-foreground cursor-pointer select-none">
                  <Checkbox
                    checked={brandFilter.includes(name)}
                    onCheckedChange={() => toggleBrand(name)}
                  />
                  {name}
                </label>
              ))}
            </div>
            <div className="flex items-center gap-4 border-l border-border pl-6">
              <label className="flex items-center gap-1.5 text-sm text-foreground cursor-pointer select-none">
                <Checkbox
                  checked={txOnly}
                  onCheckedChange={(checked) => updateParams({ tx: checked ? "1" : null, page: null })}
                />
                Has transactions
              </label>
            </div>
            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => updateParams({ brands: null, tx: null, page: null })}
                className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground h-auto px-1 py-0.5"
              >
                <X size={12} />
                Clear
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
                      <ArrowsDownUp size={12} className="text-muted-foreground/40" />
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
            className="flex hover:bg-muted/50 border-b border-border transition-colors"
          >
            {row.getVisibleCells().map((cell) => {
              const grow = (cell.column.columnDef.meta as { grow?: boolean })?.grow;
              return (
              <div
                key={cell.id}
                className={`px-4 py-4 text-xs text-foreground overflow-hidden ${grow ? "flex-1 min-w-0" : "flex-none"}`}
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
