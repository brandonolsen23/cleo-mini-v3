import { useSearchParams } from "react-router-dom";
import { useCallback, useMemo } from "react";

interface TableParams {
  search: string;
  page: number;
  sort: string;
  order: "asc" | "desc";
}

export function useTableParams(defaults?: Partial<TableParams>) {
  const [searchParams, setSearchParams] = useSearchParams();

  const params: TableParams = useMemo(
    () => ({
      search: searchParams.get("q") ?? defaults?.search ?? "",
      page: Number(searchParams.get("page")) || defaults?.page || 1,
      sort: searchParams.get("sort") ?? defaults?.sort ?? "",
      order:
        (searchParams.get("order") as "asc" | "desc") ??
        defaults?.order ??
        "asc",
    }),
    [searchParams, defaults]
  );

  const setParam = useCallback(
    (key: string, value: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      });
    },
    [setSearchParams]
  );

  return { ...params, setParam, setSearchParams };
}
