import { useCallback, useState } from "react";
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
import { useCrmContacts, createCrmContact } from "../../api/crm";
import type { CrmContact } from "../../types/crm";
import Pagination from "../shared/Pagination";
import { useTableParams } from "../../hooks/useTableParams";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import CrmContactForm from "./CrmContactForm";

const columnHelper = createColumnHelper<CrmContact>();

function globalFilterFn(
  row: { original: CrmContact },
  _columnId: string,
  filterValue: string,
): boolean {
  const q = filterValue.toLowerCase();
  const c = row.original;
  return (
    c.name.toLowerCase().includes(q) ||
    c.email.toLowerCase().includes(q) ||
    c.mobile.toLowerCase().includes(q) ||
    c.tags.some((t) => t.toLowerCase().includes(q)) ||
    c.crm_id.toLowerCase().includes(q)
  );
}

const columns = [
  columnHelper.accessor("name", {
    header: "Name",
    meta: { grow: true },
    cell: (info) => (
      <div>
        <div className="text-sm font-medium truncate">{info.getValue()}</div>
        {info.row.original.email && (
          <div className="text-xs text-muted-foreground mt-0.5 truncate">
            {info.row.original.email}
          </div>
        )}
      </div>
    ),
  }),
  columnHelper.accessor("mobile", {
    header: "Mobile",
    size: 130,
    cell: (info) => (
      <div className="text-sm">{info.getValue() || "\u2014"}</div>
    ),
  }),
  columnHelper.accessor("tags", {
    header: "Tags",
    size: 200,
    enableSorting: false,
    cell: (info) => {
      const tags = info.getValue();
      if (!tags.length) return <span className="text-sm text-muted-foreground">{"\u2014"}</span>;
      return (
        <div className="flex flex-wrap gap-1">
          {tags.map((tag) => (
            <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0">
              {tag}
            </Badge>
          ))}
        </div>
      );
    },
  }),
  columnHelper.accessor("deal_count", {
    header: "Deals",
    size: 70,
    cell: (info) => (
      <div className="text-sm font-medium">{info.getValue() ?? 0}</div>
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

export default function CrmContactsPage() {
  const { data, loading, error, reload } = useCrmContacts();
  const {
    globalFilter, sorting, pagination,
    setGlobalFilter, setSorting, setPagination,
  } = useTableParams([{ id: "updated", desc: true }]);
  const navigate = useNavigate();
  const [showForm, setShowForm] = useState(false);

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
    (crmId: string) => {
      navigate(`/crm/contacts/${crmId}`);
    },
    [navigate],
  );

  const filteredCount = table.getFilteredRowModel().rows.length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading CRM contacts...</div>
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
            <h1 className="text-lg font-semibold text-foreground">CRM Contacts</h1>
            <p className="text-sm text-muted-foreground mt-0.5">
              {filteredCount.toLocaleString()} contacts
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
                placeholder="Search name, email, tags..."
                value={globalFilter}
                onChange={(e) => setGlobalFilter(e.target.value)}
                className="pl-9 pr-4 py-2 w-64 h-9 text-sm"
              />
            </div>
            <Button size="sm" onClick={() => setShowForm(true)}>
              <Plus size={14} />
              New Contact
            </Button>
          </div>
        </div>
      </div>

      {/* New contact form */}
      {showForm && (
        <div className="flex-none px-6 py-4 border-b border-border bg-muted/50">
          <Card>
            <CardHeader className="border-b border-border">
              <CardTitle>New CRM Contact</CardTitle>
            </CardHeader>
            <CardContent>
              <CrmContactForm
                onSubmit={async (formData) => {
                  const result = await createCrmContact(formData);
                  setShowForm(false);
                  reload();
                  navigate(`/crm/contacts/${result.crm_id}`);
                }}
                onCancel={() => setShowForm(false)}
                submitLabel="Create Contact"
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
                onClick={() => handleRowClick(row.original.crm_id)}
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
