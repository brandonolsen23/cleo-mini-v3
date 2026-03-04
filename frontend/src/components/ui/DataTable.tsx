import { useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { Text } from "@radix-ui/themes";
import { CaretUp, CaretDown } from "@phosphor-icons/react";
import { cn } from "@/lib/utils";
import { Pagination } from "./Pagination";

interface DataTableProps<T> {
  data: T[];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<T, any>[];
  pageSize?: number;
  globalFilter?: string;
  onRowClick?: (row: T) => void;
  emptyMessage?: string;
}

export function DataTable<T>({
  data,
  columns,
  pageSize = 20,
  globalFilter,
  onRowClick,
  emptyMessage = "No results found",
}: DataTableProps<T>) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      globalFilter,
    },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    initialState: {
      pagination: { pageSize },
    },
  });

  return (
    <div>
      {/* WorkOS-style table: surface variant, warm borders */}
      <div className="overflow-hidden rounded-[var(--radius-4)] border border-[var(--gray-6)]">
        <table className="w-full border-collapse text-left">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr
                key={headerGroup.id}
                className="border-b border-[var(--gray-6)] bg-[var(--gray-2)]"
              >
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  const sorted = header.column.getIsSorted();

                  return (
                    <th
                      key={header.id}
                      className="px-4 py-2.5 text-left"
                      style={{
                        width:
                          header.getSize() !== 150
                            ? header.getSize()
                            : undefined,
                        cursor: canSort ? "pointer" : "default",
                        userSelect: canSort ? "none" : undefined,
                      }}
                      onClick={header.column.getToggleSortingHandler()}
                    >
                      <div className="flex items-center gap-1">
                        <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">
                          {header.isPlaceholder
                            ? null
                            : flexRender(
                                header.column.columnDef.header,
                                header.getContext()
                              )}
                        </span>
                        {canSort && (
                          <span className="inline-flex flex-col">
                            <CaretUp
                              size={9}
                              weight="fill"
                              className={cn(
                                "-mb-px",
                                sorted === "asc"
                                  ? "text-[var(--gray-12)]"
                                  : "text-[var(--gray-8)]"
                              )}
                            />
                            <CaretDown
                              size={9}
                              weight="fill"
                              className={cn(
                                "-mt-px",
                                sorted === "desc"
                                  ? "text-[var(--gray-12)]"
                                  : "text-[var(--gray-8)]"
                              )}
                            />
                          </span>
                        )}
                      </div>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>

          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="py-10 text-center"
                >
                  <Text size="2" color="gray">
                    {emptyMessage}
                  </Text>
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className={cn(
                    "border-b border-[var(--gray-4)] last:border-b-0",
                    onRowClick &&
                      "cursor-pointer hover:bg-[var(--gray-2)]"
                  )}
                  onClick={() => onRowClick?.(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {table.getPageCount() > 1 && (
        <div className="mt-4">
          <Pagination
            currentPage={table.getState().pagination.pageIndex + 1}
            totalPages={table.getPageCount()}
            onPageChange={(page) => table.setPageIndex(page - 1)}
          />
        </div>
      )}
    </div>
  );
}
