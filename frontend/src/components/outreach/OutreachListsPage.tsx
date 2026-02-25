import { useCallback } from "react";
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
import { MagnifyingGlass, ArrowsDownUp, ArrowUp, ArrowDown, Plus } from "@phosphor-icons/react";
import { useOutreachLists } from "../../api/outreach";
import type { OutreachList } from "../../types/outreach";
import Pagination from "../shared/Pagination";
import { useTableParams } from "../../hooks/useTableParams";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const columnHelper = createColumnHelper<OutreachList>();

function globalFilterFn(
  row: { original: OutreachList },
  _columnId: string,
  filterValue: string,
): boolean {
  const q = filterValue.toLowerCase();
  const d = row.original;
  return (
    d.name.toLowerCase().includes(q) ||
    d.list_id.toLowerCase().includes(q) ||
    (d.description || "").toLowerCase().includes(q)
  );
}

const columns = [
  columnHelper.accessor("name", {
    header: "Name",
    meta: { grow: true },
    cell: (info) => (
      <div>
        <div className="text-sm font-medium truncate">{info.getValue()}</div>
        {info.row.original.description && (
          <div className="text-xs text-muted-foreground mt-0.5 truncate">
            {info.row.original.description}
          </div>
        )}
      </div>
    ),
  }),
  columnHelper.accessor("item_count", {
    header: "Properties",
    size: 100,
    cell: (info) => (
      <div className="text-sm font-medium">{info.getValue().toLocaleString()}</div>
    ),
  }),
  columnHelper.accessor("contacted_count", {
    header: "Contacted",
    size: 100,
    cell: (info) => {
      const contacted = info.getValue() ?? 0;
      const total = info.row.original.item_count;
      return (
        <div className="text-sm">
          {contacted} / {total}
        </div>
      );
    },
  }),
  columnHelper.accessor("created", {
    header: "Created",
    size: 100,
    cell: (info) => (
      <div className="text-sm">{info.getValue()?.slice(0, 10) || "\u2014"}</div>
    ),
  }),
  columnHelper.accessor("updated", {
    header: "Updated",
    size: 100,
    cell: (info) => (
      <div className="text-sm">{info.getValue()?.slice(0, 10) || "\u2014"}</div>
    ),
  }),
];

export default function OutreachListsPage() {
  const { data, loading, error } = useOutreachLists();
  const {
    globalFilter, sorting, pagination,
    setGlobalFilter, setSorting, setPagination,
  } = useTableParams([{ id: "updated", desc: true }]);
  const navigate = useNavigate();

  const table = useReactTable({
    data,
    columns,
    state: { sorting, globalFilter, pagination },
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
    (listId: string) => {
      navigate(`/outreach/${listId}`);
    },
    [navigate],
  );

  const filteredCount = table.getFilteredRowModel().rows.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading outreach lists...</div>
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
      {/* Header */}
      <div className="flex-none px-6 py-4 bg-background border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-foreground">Outreach Lists</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {filteredCount.toLocaleString()} lists
              {globalFilter && ` (filtered from ${data.length.toLocaleString()})`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="relative">
              <MagnifyingGlass
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                type="text"
                placeholder="Search lists..."
                value={globalFilter}
                onChange={(e) => setGlobalFilter(e.target.value)}
                className="pl-9 pr-4 py-2 w-56 h-9 text-sm"
              />
            </div>
            <Button size="sm" onClick={() => navigate("/outreach/new")}>
              <Plus size={14} />
              New List
            </Button>
          </div>
        </div>
      </div>

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
                onClick={() => handleRowClick(row.original.list_id)}
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
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-sm text-muted-foreground"
                >
                  No outreach lists yet. Create one to get started.
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
