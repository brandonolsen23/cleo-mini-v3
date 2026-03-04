import { CaretLeft, CaretRight } from "@phosphor-icons/react";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
}: PaginationProps) {
  const pages: (number | "...")[] = [];
  const delta = 1;

  for (let i = 1; i <= totalPages; i++) {
    if (
      i === 1 ||
      i === totalPages ||
      (i >= currentPage - delta && i <= currentPage + delta)
    ) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== "...") {
      pages.push("...");
    }
  }

  return (
    <div className="flex items-center justify-between">
      <span className="text-[12px] leading-[16px] text-[var(--gray-9)]">
        Page {currentPage} of {totalPages}
      </span>
      <div className="flex items-center gap-1">
        <button
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
          className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-2)] text-[var(--gray-11)] transition-colors hover:bg-[var(--gray-3)] disabled:pointer-events-none disabled:text-[var(--gray-8)]"
        >
          <CaretLeft size={14} />
        </button>

        {pages.map((page, i) =>
          page === "..." ? (
            <span
              key={`ellipsis-${i}`}
              className="px-1 text-[12px] text-[var(--gray-9)]"
            >
              ...
            </span>
          ) : (
            <button
              key={page}
              onClick={() => onPageChange(page)}
              className={`flex h-7 min-w-7 items-center justify-center rounded-[var(--radius-2)] px-2 text-[13px] font-medium transition-colors ${
                page === currentPage
                  ? "bg-[var(--gray-12)] text-white"
                  : "text-[var(--gray-11)] hover:bg-[var(--gray-3)]"
              }`}
            >
              {page}
            </button>
          )
        )}

        <button
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-2)] text-[var(--gray-11)] transition-colors hover:bg-[var(--gray-3)] disabled:pointer-events-none disabled:text-[var(--gray-8)]"
        >
          <CaretRight size={14} />
        </button>
      </div>
    </div>
  );
}
