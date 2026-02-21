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
import { useContacts } from "../../api/contacts";
import type { ContactSummary } from "../../types/contact";
import Pagination from "../shared/Pagination";
import { useTableParams } from "../../hooks/useTableParams";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const columnHelper = createColumnHelper<ContactSummary>();

function globalFilterFn(
  row: { original: ContactSummary },
  _columnId: string,
  filterValue: string,
): boolean {
  const q = filterValue.toLowerCase();
  return (row.original._search_text ?? "").includes(q);
}

const columns = [
  columnHelper.accessor("name", {
    header: "Contact",
    meta: { grow: true },
    cell: (info) => (
      <div>
        <div className="text-sm font-medium truncate" title={info.getValue()}>
          {info.getValue()}
        </div>
        <div className="text-xs text-muted-foreground mt-0.5 truncate" title={info.row.original.phones.join(", ")}>
          {info.row.original.phones.join(", ") || "\u2014"}
        </div>
      </div>
    ),
  }),
  columnHelper.accessor("transaction_count", {
    header: "Activity",
    size: 140,
    enableGlobalFilter: false,
    cell: (info) => (
      <div>
        <div className="text-sm font-medium">{info.getValue()} txns</div>
        <div className="text-xs text-muted-foreground mt-0.5">
          {info.row.original.roles.buyer} buys, {info.row.original.roles.seller} sells
        </div>
      </div>
    ),
  }),
  columnHelper.accessor("sample_entities", {
    header: "Entities",
    size: 240,
    enableSorting: false,
    cell: (info) => {
      const entities = info.getValue();
      const alts = info.row.original.alt_entities ?? [];
      const allNames = [...entities, ...alts];
      const displayEntities = entities.join(", ") || "\u2014";
      const titleText = allNames.join(", ") || "\u2014";
      return (
        <div>
          <div className="text-sm truncate" title={titleText}>
            <span className="text-muted-foreground">{displayEntities}</span>
            {alts.length > 0 && (
              <span className="text-muted-foreground italic">
                {entities.length > 0 ? ", " : ""}
                {alts.join(", ")}
              </span>
            )}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {info.row.original.entity_count} entit{info.row.original.entity_count !== 1 ? "ies" : "y"}
          </div>
        </div>
      );
    },
  }),
  columnHelper.accessor("last_active_iso", {
    header: "Last Active",
    size: 90,
    enableGlobalFilter: false,
    filterFn: (row, _columnId, filterValue: { from: string; to: string }) => {
      const first = row.original.first_active_iso;
      const last = row.original.last_active_iso;
      if (!first || !last) return false;
      const firstYear = first.slice(0, 4);
      const lastYear = last.slice(0, 4);
      if (filterValue.from && lastYear < filterValue.from) return false;
      if (filterValue.to && firstYear > filterValue.to) return false;
      return true;
    },
    cell: (info) => {
      const v = info.getValue();
      return (
        <div className="text-sm font-medium">
          {v ? v.slice(0, 4) : "\u2014"}
        </div>
      );
    },
  }),
  // Hidden column for min txns filter
  columnHelper.accessor("transaction_count", {
    id: "min_txns",
    header: "Min Txns",
    enableSorting: false,
    enableGlobalFilter: false,
    filterFn: (row, _columnId, filterValue: number) => {
      return row.original.transaction_count >= filterValue;
    },
  }),
];

export default function ContactsPage() {
  const { data, loading, error } = useContacts();
  const {
    globalFilter, sorting, pagination,
    setGlobalFilter, setSorting, setPagination,
    searchParams, updateParams,
  } = useTableParams([{ id: "transaction_count", desc: true }]);
  const navigate = useNavigate();

  // Read filter params from URL
  const yearFrom = searchParams.get("yf") || "";
  const yearTo = searchParams.get("yt") || "";
  const minTxns = searchParams.get("mintx") || "";
  const hasFilters = !!(yearFrom || yearTo || minTxns);
  const [filtersOpen, setFiltersOpen] = useState(hasFilters);

  // Build column filters from URL params
  const columnFilters: ColumnFiltersState = useMemo(() => {
    const filters: ColumnFiltersState = [];
    if (yearFrom || yearTo) {
      filters.push({ id: "last_active_iso", value: { from: yearFrom, to: yearTo } });
    }
    if (minTxns) {
      filters.push({ id: "min_txns", value: parseInt(minTxns, 10) });
    }
    return filters;
  }, [yearFrom, yearTo, minTxns]);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting, globalFilter, pagination, columnFilters,
      columnVisibility: { min_txns: false },
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
    (contactId: string) => {
      navigate(`/contacts/${encodeURIComponent(contactId)}`);
    },
    [navigate]
  );

  const isFiltered = !!(globalFilter || hasFilters);
  const filteredCount = table.getFilteredRowModel().rows.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading contacts...</div>
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
            <h1 className="text-lg font-semibold text-foreground">Contacts</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {filteredCount.toLocaleString()} contacts
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
              placeholder="Search names, phones, entities..."
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="pl-9 pr-4 py-2 w-72 h-9 text-sm"
            />
          </div>
        </div>
      </div>

      {/* Filter toggle */}
      <div className="flex-none px-6 py-2 bg-muted border-b border-border">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setFiltersOpen(!filtersOpen)}
          className="h-auto px-0 py-0 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-transparent"
        >
          <SlidersHorizontal size={14} />
          Filters
          {hasFilters && (
            <span className="ml-1 px-1.5 py-0.5 rounded-full text-[10px] bg-secondary text-secondary-foreground">
              {[yearFrom || yearTo ? 1 : 0, minTxns ? 1 : 0].reduce((a, b) => a + b, 0)}
            </span>
          )}
          {filtersOpen ? <CaretUp size={12} /> : <CaretDown size={12} />}
        </Button>

        {filtersOpen && (
          <div className="flex items-center gap-6 mt-2.5 pb-0.5 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Year</span>
              <input
                type="number"
                placeholder="From"
                value={yearFrom}
                onChange={(e) => updateParams({ yf: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
              />
              <span className="text-muted-foreground">to</span>
              <input
                type="number"
                placeholder="To"
                value={yearTo}
                onChange={(e) => updateParams({ yt: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Min Txns</span>
              <input
                type="number"
                placeholder="e.g. 3"
                value={minTxns}
                onChange={(e) => updateParams({ mintx: e.target.value || null, page: null })}
                className="px-2 py-1 w-20 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
              />
            </div>
            {hasFilters && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => updateParams({ yf: null, yt: null, mintx: null, page: null })}
                className="h-auto px-0 py-0 text-xs text-muted-foreground hover:text-foreground hover:bg-transparent"
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
            className="flex hover:bg-accent cursor-pointer border-b border-border transition-colors"
            onClick={() => handleRowClick(row.original.contact_id)}
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
