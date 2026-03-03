import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { MagnifyingGlass, ArrowsDownUp, ArrowUp, ArrowDown, SlidersHorizontal } from "@phosphor-icons/react";
import { useParcels, useParcelFilters } from "../../api/parcels";
import type { ParcelSummary } from "../../types/parcel";
import Pagination from "../shared/Pagination";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const columnHelper = createColumnHelper<ParcelSummary>();

function formatPrice(price: number | null): string {
  if (price == null) return "";
  if (price >= 1_000_000) return `$${(price / 1_000_000).toFixed(1)}M`;
  if (price >= 1_000) return `$${Math.round(price / 1_000)}K`;
  return `$${price}`;
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
    size: 280,
    cell: (info) => (
      <div>
        <div className="text-sm font-medium truncate" title={info.getValue()}>
          {info.getValue() || "(no address)"}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {info.row.original.city}
          {info.row.original.population != null && (
            <span className="ml-2 tabular-nums">Pop: {formatPopulation(info.row.original.population)}</span>
          )}
        </div>
      </div>
    ),
  }),
  columnHelper.accessor("brand_count", {
    header: "Brands",
    size: 180,
    cell: (info) => {
      const brands = info.row.original.brands;
      if (!brands.length) return <span className="text-xs text-muted-foreground">--</span>;
      return (
        <div className="flex flex-wrap gap-1">
          {brands.slice(0, 3).map((b) => (
            <Badge key={b} variant="secondary" className="text-[10px] px-1.5 py-0">
              {b}
            </Badge>
          ))}
          {brands.length > 3 && (
            <span className="text-[10px] text-muted-foreground">+{brands.length - 3}</span>
          )}
        </div>
      );
    },
  }),
  columnHelper.accessor("transaction_count", {
    header: "Txns",
    size: 60,
    cell: (info) => (
      <span className="text-sm tabular-nums">{info.getValue() || "--"}</span>
    ),
  }),
  columnHelper.accessor("latest_price", {
    header: "Latest Price",
    size: 110,
    sortingFn: (a, b) =>
      (a.original.latest_price ?? 0) - (b.original.latest_price ?? 0),
    cell: (info) => (
      <div>
        <div className="text-sm font-medium tabular-nums">{formatPrice(info.getValue())}</div>
        {info.row.original.latest_date && (
          <div className="text-xs text-muted-foreground mt-0.5">{info.row.original.latest_date}</div>
        )}
      </div>
    ),
  }),
  columnHelper.accessor("zoning", {
    header: "Zoning",
    size: 80,
    cell: (info) => (
      <span className="text-xs font-mono">{info.getValue() || ""}</span>
    ),
  }),
  columnHelper.accessor("sources", {
    header: "Sources",
    size: 120,
    enableSorting: false,
    cell: (info) => {
      const srcs = info.getValue();
      return (
        <div className="flex gap-1">
          {srcs.map((s) => (
            <Badge
              key={s}
              variant="outline"
              className="text-[10px] px-1.5 py-0"
            >
              {s}
            </Badge>
          ))}
        </div>
      );
    },
  }),
];

export default function ParcelsPage() {
  const navigate = useNavigate();
  const [globalFilter, setGlobalFilter] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [cityFilter, setCityFilter] = useState("");
  const [brandFilter, setBrandFilter] = useState("");
  const [txnFilter, setTxnFilter] = useState<"" | "yes" | "no">("");

  // Build query params
  const params = useMemo(() => {
    const p: Record<string, string> = { limit: "1000" };
    if (cityFilter) p.city = cityFilter;
    if (brandFilter) p.brand = brandFilter;
    if (txnFilter === "yes") p.has_transactions = "true";
    if (txnFilter === "no") p.has_transactions = "false";
    return p;
  }, [cityFilter, brandFilter, txnFilter]);

  const { data, loading, error } = useParcels(params);
  const { data: filtersData } = useParcelFilters();

  const rows = data?.results ?? [];

  // Local search filter
  const filteredRows = useMemo(() => {
    if (!globalFilter) return rows;
    const q = globalFilter.toLowerCase();
    return rows.filter(
      (r) =>
        (r.address || "").toLowerCase().includes(q) ||
        (r.city || "").toLowerCase().includes(q) ||
        r.brands.some((b) => b.toLowerCase().includes(q)) ||
        (r.arn || "").includes(q) ||
        (r.pid || "").toLowerCase().includes(q)
    );
  }, [rows, globalFilter]);

  const table = useReactTable({
    data: filteredRows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: 50 },
      sorting: [{ id: "latest_price", desc: true }],
    },
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border">
        <div>
          <h1 className="text-lg font-semibold">Parcels</h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            {data ? `${data.total.toLocaleString()} parcels` : "Loading..."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowFilters(!showFilters)}
            className={showFilters ? "bg-muted" : ""}
          >
            <SlidersHorizontal size={16} className="mr-1" />
            Filters
          </Button>
          <div className="relative">
            <MagnifyingGlass size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search parcels..."
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="pl-9 w-64 h-9"
            />
          </div>
        </div>
      </div>

      {/* Filters */}
      {showFilters && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-6 py-2 border-b border-border bg-muted/30">
          <div className="flex items-center gap-1.5">
            <label className="text-xs text-muted-foreground">City</label>
            <select
              value={cityFilter}
              onChange={(e) => setCityFilter(e.target.value)}
              className="text-xs border rounded px-2 py-1 bg-background"
            >
              <option value="">All cities</option>
              {filtersData?.cities.slice(0, 50).map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({c.count.toLocaleString()})
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <label className="text-xs text-muted-foreground">Brand</label>
            <select
              value={brandFilter}
              onChange={(e) => setBrandFilter(e.target.value)}
              className="text-xs border rounded px-2 py-1 bg-background"
            >
              <option value="">All brands</option>
              {filtersData?.brands.slice(0, 100).map((b) => (
                <option key={b.name} value={b.name}>
                  {b.name} ({b.count})
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1.5">
            <label className="text-xs text-muted-foreground">Transactions</label>
            <select
              value={txnFilter}
              onChange={(e) => setTxnFilter(e.target.value as "" | "yes" | "no")}
              className="text-xs border rounded px-2 py-1 bg-background"
            >
              <option value="">Any</option>
              <option value="yes">With transactions</option>
              <option value="no">No transactions</option>
            </select>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="px-6 py-3 text-sm text-red-600 bg-red-50">
          Error: {error}
        </div>
      )}

      {/* Column headers */}
      <div className="flex items-center px-6 py-2 border-b border-border bg-muted/20">
        {table.getHeaderGroups().map((hg) =>
          hg.headers.map((header) => (
            <div
              key={header.id}
              className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground cursor-pointer select-none flex items-center gap-1"
              style={{
                width: header.getSize(),
                minWidth: header.getSize(),
                flex: (header.column.columnDef.meta as any)?.grow ? "1" : undefined,
              }}
              onClick={header.column.getToggleSortingHandler()}
            >
              {flexRender(header.column.columnDef.header, header.getContext())}
              {header.column.getIsSorted() === "asc" && <ArrowUp size={12} />}
              {header.column.getIsSorted() === "desc" && <ArrowDown size={12} />}
              {!header.column.getIsSorted() && header.column.getCanSort() && (
                <ArrowsDownUp size={12} className="opacity-30" />
              )}
            </div>
          ))
        )}
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-auto">
        {loading && !rows.length ? (
          <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
            Loading parcels...
          </div>
        ) : (
          table.getRowModel().rows.map((row) => (
            <div
              key={row.original.arn}
              className="flex items-center px-6 py-2.5 border-b border-border/50 cursor-pointer hover:bg-muted/50 transition-colors"
              onClick={() => navigate(`/parcels/${row.original.arn}`)}
            >
              {row.getVisibleCells().map((cell) => (
                <div
                  key={cell.id}
                  style={{
                    width: cell.column.getSize(),
                    minWidth: cell.column.getSize(),
                    flex: (cell.column.columnDef.meta as any)?.grow ? "1" : undefined,
                  }}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </div>
              ))}
            </div>
          ))
        )}
      </div>

      {/* Pagination */}
      {table.getPageCount() > 1 && <Pagination table={table} />}
    </div>
  );
}
