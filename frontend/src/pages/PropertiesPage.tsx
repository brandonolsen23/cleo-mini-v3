import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Text, Spinner } from "@radix-ui/themes";
import { createColumnHelper } from "@tanstack/react-table";
import { MagnifyingGlass, X, Buildings, Funnel } from "@phosphor-icons/react";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState } from "@/components/ui/EmptyState";
import { fetchApi } from "@/api/client";
import { cn, formatDate, formatStreet, titleCase } from "@/lib/utils";
import type {
  PropertyBrowseItem,
  BrowseResponse,
  FiltersResponse,
} from "@/types";

const col = createColumnHelper<PropertyBrowseItem>();

const columns = [
  col.accessor("primary_address", {
    header: "Address",
    cell: (info) => (
      <Text size="2" weight="medium" className="whitespace-nowrap">
        {formatStreet(info.getValue())}
      </Text>
    ),
  }),
  col.accessor("city", {
    header: "City",
    cell: (info) => titleCase(info.getValue()),
  }),
  col.accessor("current_owner", {
    header: "Owner",
    cell: (info) => (
      <Text size="2" className="max-w-[160px] truncate block">
        {info.getValue() || "\u2014"}
      </Text>
    ),
  }),
  col.accessor("transaction_count", {
    header: "Txns",
    cell: (info) => info.getValue() || "\u2014",
    size: 70,
  }),
  col.accessor("tenants", {
    header: "Tenants",
    cell: (info) => {
      const names = info.getValue();
      if (!names.length) return "\u2014";
      const display = names.slice(0, 2).join(", ");
      return (
        <Text size="2" className="max-w-[180px] truncate block">
          {display}
          {names.length > 2 ? ` +${names.length - 2}` : ""}
        </Text>
      );
    },
    enableSorting: false,
  }),
  col.accessor("latest_sale_price", {
    header: "Sale Price",
    cell: (info) => {
      const v = info.getValue();
      if (!v) return "\u2014";
      if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
      if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
      return `$${v.toLocaleString()}`;
    },
    size: 90,
  }),
  col.accessor("latest_sale_date", {
    header: "Date",
    cell: (info) => {
      const v = info.getValue();
      if (!v) return "\u2014";
      return <span className="whitespace-nowrap">{formatDate(v)}</span>;
    },
    size: 120,
  }),
];

export function PropertiesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // Read URL state
  const urlQ = searchParams.get("q") ?? "";
  const urlCity = searchParams.get("city") ?? "";
  const urlCategory = searchParams.get("category") ?? "";
  const urlPage = Number(searchParams.get("page")) || 1;
  const urlSort = searchParams.get("sort") ?? "latest_sale_date";
  const urlOrder = (searchParams.get("order") ?? "desc") as "asc" | "desc";

  // Local search input (debounced before URL update)
  const [searchInput, setSearchInput] = useState(urlQ);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Data state
  const [data, setData] = useState<BrowseResponse | null>(null);
  const [filters, setFilters] = useState<FiltersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(
    !!(urlCity || urlCategory)
  );

  // Set a URL param, resetting page to 1 for filter changes
  const setParam = useCallback(
    (updates: Record<string, string>, resetPage = true) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(updates)) {
          if (v) next.set(k, v);
          else next.delete(k);
        }
        if (resetPage) next.delete("page");
        return next;
      });
    },
    [setSearchParams]
  );

  // Debounce search input → URL
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (searchInput !== urlQ) {
        setParam({ q: searchInput });
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync URL → local input when URL changes externally
  useEffect(() => {
    setSearchInput(urlQ);
  }, [urlQ]);

  // Load filters once
  useEffect(() => {
    fetchApi<FiltersResponse>("/properties/filters").then(setFilters);
  }, []);

  // Load browse data when URL params change
  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {
      page: String(urlPage),
      per_page: "25",
      sort: urlSort,
      order: urlOrder,
    };
    if (urlQ) params.q = urlQ;
    if (urlCity) params.city = urlCity;
    if (urlCategory) params.category = urlCategory;

    fetchApi<BrowseResponse>("/properties/browse", params)
      .then(setData)
      .finally(() => setLoading(false));
  }, [urlQ, urlCity, urlCategory, urlPage, urlSort, urlOrder]);

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;
  const hasFilters = !!(urlCity || urlCategory);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Properties"
        description={
          data
            ? `${data.total.toLocaleString()} properties${hasFilters ? " (filtered)" : ""}`
            : "Browse all resolved properties by ARN."
        }
      />

      <div className="flex flex-col gap-4">
        {/* Search + filter toggle */}
        <div className="flex items-center gap-3">
          <div className="relative w-full max-w-[400px]">
            <MagnifyingGlass
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--gray-9)]"
            />
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by address, city, owner, ARN..."
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white pl-9 pr-8 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
            />
            {searchInput && (
              <button
                onClick={() => {
                  setSearchInput("");
                  setParam({ q: "" });
                }}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--gray-9)] hover:text-[var(--gray-11)]"
              >
                <X size={13} />
              </button>
            )}
          </div>

          <button
            onClick={() => setFiltersOpen((v) => !v)}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-2)] border px-3 text-[13px] font-medium transition-colors",
              filtersOpen || hasFilters
                ? "border-[var(--accent-7)] bg-[var(--accent-a2)] text-[var(--accent-11)]"
                : "border-[var(--gray-7)] text-[var(--gray-11)] hover:bg-[var(--gray-2)]"
            )}
          >
            <Funnel size={13} />
            Filters
            {hasFilters && (
              <span className="ml-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-[var(--accent-9)] text-[10px] font-medium text-white">
                {(urlCity ? 1 : 0) + (urlCategory ? 1 : 0)}
              </span>
            )}
          </button>

          {hasFilters && (
            <button
              onClick={() => setParam({ city: "", category: "" })}
              className="text-[13px] text-[var(--gray-11)] hover:text-[var(--gray-12)]"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Filter bar */}
        {filtersOpen && filters && (
          <div className="flex flex-wrap items-center gap-3 rounded-[var(--radius-2)] border border-[var(--gray-4)] bg-[var(--gray-2)] px-4 py-3">
            <FilterTypeahead
              label="City"
              value={urlCity}
              options={filters.cities}
              onChange={(v) => setParam({ city: v })}
            />
            <FilterSelect
              label="Brand Category"
              value={urlCategory}
              options={filters.categories}
              onChange={(v) => setParam({ category: v })}
            />
          </div>
        )}

        {/* Table */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner size="3" />
          </div>
        ) : data && data.results.length > 0 ? (
          <>
            <DataTable
              data={data.results}
              columns={columns}
              pageSize={data.per_page}
              onRowClick={(row) =>
                navigate(`/properties/${row.property_id}`)
              }
            />
            {totalPages > 1 && (
              <Pagination
                currentPage={urlPage}
                totalPages={totalPages}
                onPageChange={(p) =>
                  setParam({ page: String(p) }, false)
                }
              />
            )}
          </>
        ) : (
          <EmptyState
            icon={<Buildings size={40} />}
            title="No properties found"
            description={
              urlQ || hasFilters
                ? "Try adjusting your search or filters."
                : "Run 'cleo properties' to build the property registry."
            }
          />
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Filter select component                                             */
/* ------------------------------------------------------------------ */

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-[12px] font-medium text-[var(--gray-11)]">
        {label}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-7 rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-2 text-[13px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none"
      >
        <option value="">All</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {titleCase(opt)}
          </option>
        ))}
      </select>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Typeahead filter component                                          */
/* ------------------------------------------------------------------ */

function FilterTypeahead({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const [input, setInput] = useState(value ? titleCase(value) : "");
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Sync external value → input display
  useEffect(() => {
    setInput(value ? titleCase(value) : "");
  }, [value]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = input
    ? options.filter((o) => o.toLowerCase().includes(input.toLowerCase())).slice(0, 12)
    : options.slice(0, 12);

  return (
    <div className="flex items-center gap-2" ref={wrapperRef}>
      <label className="text-[12px] font-medium text-[var(--gray-11)]">
        {label}
      </label>
      <div className="relative">
        <input
          type="text"
          value={input}
          placeholder="All"
          onChange={(e) => {
            setInput(e.target.value);
            setOpen(true);
            if (!e.target.value) onChange("");
          }}
          onFocus={() => setOpen(true)}
          className="h-7 w-[180px] rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-2 text-[13px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
        />
        {value && (
          <button
            onClick={() => { setInput(""); onChange(""); }}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[var(--gray-9)] hover:text-[var(--gray-11)]"
          >
            <X size={11} />
          </button>
        )}
        {open && filtered.length > 0 && (
          <div className="absolute left-0 top-full z-50 mt-1 max-h-[240px] w-[220px] overflow-y-auto rounded-[var(--radius-3)] border border-[var(--gray-6)] bg-white shadow-[var(--elevation-3)]">
            {filtered.map((opt) => (
              <button
                key={opt}
                className={cn(
                  "block w-full px-3 py-1.5 text-left text-[13px] hover:bg-[var(--gray-3)]",
                  opt.toLowerCase() === value.toLowerCase() && "font-medium text-[var(--accent-11)]"
                )}
                onMouseDown={(e) => {
                  e.preventDefault();
                  onChange(opt);
                  setInput(titleCase(opt));
                  setOpen(false);
                }}
              >
                {titleCase(opt)}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

