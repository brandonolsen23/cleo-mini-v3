import { CaretLeft, CaretRight, CaretDoubleLeft, CaretDoubleRight } from "@phosphor-icons/react";
import type { Table } from "@tanstack/react-table";
import { Button } from "@/components/ui/button";

export default function Pagination<T>({ table }: { table: Table<T> }) {
  const pageIndex = table.getState().pagination.pageIndex;
  const pageCount = table.getPageCount();
  const totalRows = table.getFilteredRowModel().rows.length;
  const pageSize = table.getState().pagination.pageSize;
  const start = pageIndex * pageSize + 1;
  const end = Math.min((pageIndex + 1) * pageSize, totalRows);

  return (
    <div className="flex-none flex items-center justify-between px-6 py-3 bg-background border-t border-border">
      <span className="text-sm text-muted-foreground">
        {start.toLocaleString()}&ndash;{end.toLocaleString()} of{" "}
        {totalRows.toLocaleString()}
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => table.setPageIndex(0)}
          disabled={!table.getCanPreviousPage()}
        >
          <CaretDoubleLeft size={16} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >
          <CaretLeft size={16} />
        </Button>
        <span className="px-3 text-sm">
          Page {pageIndex + 1} of {pageCount.toLocaleString()}
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >
          <CaretRight size={16} />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8"
          onClick={() => table.setPageIndex(pageCount - 1)}
          disabled={!table.getCanNextPage()}
        >
          <CaretDoubleRight size={16} />
        </Button>
      </div>
    </div>
  );
}
