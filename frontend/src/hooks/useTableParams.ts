import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import type { SortingState, PaginationState } from "@tanstack/react-table";

interface TableParams {
  globalFilter: string;
  sorting: SortingState;
  pagination: PaginationState;
  setGlobalFilter: (value: string) => void;
  setSorting: (updater: SortingState | ((prev: SortingState) => SortingState)) => void;
  setPagination: (updater: PaginationState | ((prev: PaginationState) => PaginationState)) => void;
  searchParams: URLSearchParams;
  updateParams: (changes: Record<string, string | null>) => void;
}

export function useTableParams(defaultSort: SortingState = [], pageSize = 50): TableParams {
  const [searchParams, setSearchParams] = useSearchParams();

  const globalFilter = searchParams.get("q") || "";

  const sortParam = searchParams.get("sort");
  const sorting: SortingState = sortParam
    ? sortParam.split(",").map((s) => {
        const desc = s.startsWith("-");
        return { id: desc ? s.slice(1) : s, desc };
      })
    : defaultSort;

  const page = parseInt(searchParams.get("page") || "1", 10) - 1;
  const pagination: PaginationState = { pageIndex: Math.max(0, page), pageSize };

  const update = useCallback(
    (changes: Record<string, string | null>) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(changes)) {
          if (v === null || v === "") {
            next.delete(k);
          } else {
            next.set(k, v);
          }
        }
        return next;
      }, { replace: true });
    },
    [setSearchParams]
  );

  const setGlobalFilter = useCallback(
    (value: string) => {
      update({ q: value || null, page: null });
    },
    [update]
  );

  const setSorting = useCallback(
    (updater: SortingState | ((prev: SortingState) => SortingState)) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      const param = next.map((s) => (s.desc ? `-${s.id}` : s.id)).join(",");
      update({ sort: param || null, page: null });
    },
    [sorting, update]
  );

  const setPagination = useCallback(
    (updater: PaginationState | ((prev: PaginationState) => PaginationState)) => {
      const next = typeof updater === "function" ? updater(pagination) : updater;
      update({ page: next.pageIndex > 0 ? String(next.pageIndex + 1) : null });
    },
    [pagination, update]
  );

  return {
    globalFilter, sorting, pagination,
    setGlobalFilter, setSorting, setPagination,
    searchParams, updateParams: update,
  };
}
