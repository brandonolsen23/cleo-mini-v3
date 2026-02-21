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
import { MagnifyingGlass, ArrowsDownUp, ArrowUp, ArrowDown, Plus } from "@phosphor-icons/react";
import { useDeals, createDeal } from "../../api/crm";
import type { DealSummary } from "../../types/crm";
import { DEAL_STAGES, STAGE_LABELS } from "../../types/crm";
import DealStageBadge from "./DealStageBadge";
import Pagination from "../shared/Pagination";
import { useTableParams } from "../../hooks/useTableParams";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import DealForm from "./DealForm";

const columnHelper = createColumnHelper<DealSummary>();

function globalFilterFn(
  row: { original: DealSummary },
  _columnId: string,
  filterValue: string,
): boolean {
  const q = filterValue.toLowerCase();
  const d = row.original;
  return (
    d.title.toLowerCase().includes(q) ||
    d.deal_id.toLowerCase().includes(q) ||
    (d.property?.address ?? "").toLowerCase().includes(q) ||
    (d.property?.city ?? "").toLowerCase().includes(q) ||
    d.contacts.some((c) => c.name.toLowerCase().includes(q))
  );
}

const columns = [
  columnHelper.accessor("title", {
    header: "Title",
    meta: { grow: true },
    cell: (info) => (
      <div className="text-sm font-medium truncate">{info.getValue()}</div>
    ),
  }),
  columnHelper.display({
    id: "property",
    header: "Property",
    size: 220,
    cell: (info) => {
      const p = info.row.original.property;
      if (!p) return <span className="text-sm text-muted-foreground">{"\u2014"}</span>;
      return (
        <div>
          <div className="text-sm truncate">{p.address}</div>
          <div className="text-xs text-muted-foreground">{p.city}</div>
        </div>
      );
    },
  }),
  columnHelper.accessor("stage", {
    header: "Stage",
    size: 130,
    filterFn: (row, _colId, value: string) => {
      if (!value) return true;
      return row.original.stage === value;
    },
    cell: (info) => <DealStageBadge stage={info.getValue()} />,
  }),
  columnHelper.display({
    id: "contacts",
    header: "Contacts",
    size: 180,
    cell: (info) => {
      const contacts = info.row.original.contacts;
      if (!contacts.length) return <span className="text-sm text-muted-foreground">{"\u2014"}</span>;
      return (
        <div className="text-sm truncate">
          {contacts.map((c) => c.name).join(", ")}
        </div>
      );
    },
  }),
  columnHelper.accessor("updated", {
    header: "Updated",
    size: 100,
    cell: (info) => (
      <div className="text-sm">{info.getValue()?.slice(0, 10) || "\u2014"}</div>
    ),
  }),
];

export default function DealsPage() {
  const { data, loading, error, reload } = useDeals();
  const {
    globalFilter, sorting, pagination,
    setGlobalFilter, setSorting, setPagination,
    searchParams, updateParams,
  } = useTableParams([{ id: "updated", desc: true }]);
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);

  const stageFilter = searchParams.get("stage") || "";

  const columnFilters: ColumnFiltersState = useMemo(() => {
    const filters: ColumnFiltersState = [];
    if (stageFilter) {
      filters.push({ id: "stage", value: stageFilter });
    }
    return filters;
  }, [stageFilter]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter, pagination, columnFilters },
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
    (dealId: string) => {
      navigate(`/crm/deals/${dealId}`);
    },
    [navigate],
  );

  const filteredCount = table.getFilteredRowModel().rows.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading deals...</div>
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
            <h1 className="text-lg font-semibold text-foreground">Deals</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {filteredCount.toLocaleString()} deals
              {(globalFilter || stageFilter) && ` (filtered from ${data.length.toLocaleString()})`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={stageFilter}
              onChange={(e) => updateParams({ stage: e.target.value || null, page: null })}
              className="h-9 rounded-md border border-input bg-background px-3 text-sm"
            >
              <option value="">All stages</option>
              {DEAL_STAGES.map((s) => (
                <option key={s} value={s}>{STAGE_LABELS[s]}</option>
              ))}
            </select>
            <div className="relative">
              <MagnifyingGlass
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                type="text"
                placeholder="Search deals..."
                value={globalFilter}
                onChange={(e) => setGlobalFilter(e.target.value)}
                className="pl-9 pr-4 py-2 w-56 h-9 text-sm"
              />
            </div>
            <Button size="sm" onClick={() => setShowForm(true)}>
              <Plus size={14} />
              New Deal
            </Button>
          </div>
        </div>
      </div>

      {/* New deal form */}
      {showForm && (
        <div className="flex-none px-6 py-4 border-b border-border bg-muted/50">
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle>New Deal</CardTitle>
            </CardHeader>
            <CardContent>
              <DealForm
                onSubmit={async (formData) => {
                  const result = await createDeal(formData);
                  setShowForm(false);
                  reload();
                  navigate(`/crm/deals/${result.deal_id}`);
                }}
                onCancel={() => setShowForm(false)}
                submitLabel="Create Deal"
              />
            </CardContent>
          </Card>
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-muted z-10">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => {
                  const sort = header.column.getIsSorted();
                  const canSort = header.column.getCanSort();
                  const meta = header.column.columnDef.meta as
                    | { grow?: boolean }
                    | undefined;
                  return (
                    <th
                      key={header.id}
                      className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-4 py-2.5 select-none"
                      style={{
                        width: meta?.grow ? undefined : header.getSize(),
                      }}
                      onClick={
                        canSort
                          ? header.column.getToggleSortingHandler()
                          : undefined
                      }
                    >
                      <span
                        className={
                          canSort
                            ? "inline-flex items-center gap-1 cursor-pointer"
                            : ""
                        }
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        {canSort &&
                          (sort === "asc" ? (
                            <ArrowUp size={12} />
                          ) : sort === "desc" ? (
                            <ArrowDown size={12} />
                          ) : (
                            <ArrowsDownUp size={12} className="opacity-30" />
                          ))}
                      </span>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr
                key={row.id}
                className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                onClick={() => handleRowClick(row.original.deal_id)}
              >
                {row.getVisibleCells().map((cell) => {
                  const meta = cell.column.columnDef.meta as
                    | { grow?: boolean }
                    | undefined;
                  return (
                    <td
                      key={cell.id}
                      className="px-4 py-3"
                      style={{
                        width: meta?.grow ? undefined : cell.column.getSize(),
                      }}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
            {table.getRowModel().rows.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-12 text-center text-sm text-muted-foreground">
                  No deals found. Create one to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {table.getPageCount() > 1 && (
        <div className="flex-none border-t border-border">
          <Pagination table={table} />
        </div>
      )}
    </div>
  );
}
