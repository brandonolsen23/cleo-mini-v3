import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Text, Spinner } from "@radix-ui/themes";
import { createColumnHelper } from "@tanstack/react-table";
import { MagnifyingGlass, X, AddressBook, Funnel } from "@phosphor-icons/react";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState } from "@/components/ui/EmptyState";
import { fetchApi } from "@/api/client";
import { cn, titleCase, formatCompact } from "@/lib/utils";

interface ContactBrowseItem {
  id: string;
  name: string;
  phones: string[];
  primary_group: { group_id: string; name: string } | null;
  group_count: number;
  transaction_count: number;
  total_value: number;
  cities: string[];
  latest_date: string;
}

interface ContactBrowseResponse {
  results: ContactBrowseItem[];
  total: number;
  page: number;
  per_page: number;
}

interface ContactFiltersResponse {
  cities: string[];
  total_contacts: number;
}

function formatPhone(digits: string): string {
  if (digits.length === 10) {
    return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6)}`;
  }
  return digits;
}

const col = createColumnHelper<ContactBrowseItem>();

const columns = [
  col.accessor("name", {
    header: "Name",
    cell: (info) => (
      <Text size="2" weight="medium" className="block truncate max-w-[200px]">
        {info.getValue()}
      </Text>
    ),
  }),
  col.accessor("primary_group", {
    header: "Group",
    cell: (info) => {
      const pg = info.getValue();
      const count = info.row.original.group_count;
      if (!pg) return "\u2014";
      return (
        <div className="flex flex-col gap-0.5">
          <Text size="2" className="block truncate max-w-[180px]">
            {pg.name}
          </Text>
          {count > 1 && (
            <Text size="1" color="gray" className="block">
              +{count - 1} other{count - 1 !== 1 ? "s" : ""}
            </Text>
          )}
        </div>
      );
    },
    enableSorting: false,
  }),
  col.accessor("phones", {
    header: "Phone",
    cell: (info) => {
      const phones = info.getValue();
      if (!phones.length) return "\u2014";
      return (
        <Text size="2" className="block whitespace-nowrap">
          {formatPhone(phones[0])}
        </Text>
      );
    },
    enableSorting: false,
    size: 130,
  }),
  col.accessor("transaction_count", {
    header: "Txns",
    cell: (info) => info.getValue() || "\u2014",
    size: 70,
  }),
  col.accessor("cities", {
    header: "Cities",
    cell: (info) => {
      const cities = info.getValue();
      if (!cities.length) return "\u2014";
      const display = cities.slice(0, 2).map(titleCase).join(", ");
      return (
        <Text size="2" className="max-w-[160px] truncate block">
          {display}
          {cities.length > 2 ? ` +${cities.length - 2}` : ""}
        </Text>
      );
    },
    enableSorting: false,
  }),
  col.accessor("total_value", {
    header: "Volume",
    cell: (info) => {
      const v = info.getValue();
      if (!v) return "\u2014";
      return `$${formatCompact(v)}`;
    },
    size: 100,
  }),
  col.accessor("latest_date", {
    header: "Latest",
    cell: (info) => {
      const v = info.getValue();
      if (!v) return "\u2014";
      const d = new Date(v + "T00:00:00");
      if (isNaN(d.getTime())) return v;
      return (
        <span className="whitespace-nowrap">
          {d.toLocaleString("en-US", { month: "short" })} {d.getDate()},{" "}
          {d.getFullYear()}
        </span>
      );
    },
    size: 120,
  }),
];

export function ContactsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const urlQ = searchParams.get("q") ?? "";
  const urlCity = searchParams.get("city") ?? "";
  const urlPage = Number(searchParams.get("page")) || 1;
  const urlSort = searchParams.get("sort") ?? "transaction_count";
  const urlOrder = (searchParams.get("order") ?? "desc") as "asc" | "desc";

  const [searchInput, setSearchInput] = useState(urlQ);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const [data, setData] = useState<ContactBrowseResponse | null>(null);
  const [filters, setFilters] = useState<ContactFiltersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(!!urlCity);

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

  // Debounce search input
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (searchInput !== urlQ) {
        setParam({ q: searchInput });
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [searchInput]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setSearchInput(urlQ);
  }, [urlQ]);

  // Load filters once
  useEffect(() => {
    fetchApi<ContactFiltersResponse>("/contacts/filters").then(setFilters);
  }, []);

  // Load browse data
  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {
      page: String(urlPage),
      per_page: "25",
      sort: urlSort,
      order: urlOrder,
    };
    if (urlQ) params.name = urlQ;
    if (urlCity) params.city = urlCity;

    fetchApi<ContactBrowseResponse>("/contacts/browse", params)
      .then(setData)
      .finally(() => setLoading(false));
  }, [urlQ, urlCity, urlPage, urlSort, urlOrder]);

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;
  const hasFilters = !!urlCity;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Contacts"
        description={
          data
            ? `${data.total.toLocaleString()} contacts${hasFilters ? " (filtered)" : ""}`
            : "Individuals from transaction records."
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
              placeholder="Search by name, phone, group..."
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
                1
              </span>
            )}
          </button>

          {hasFilters && (
            <button
              onClick={() => setParam({ city: "" })}
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
              onRowClick={(row) => navigate(`/contacts/${row.id}`)}
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
            icon={<AddressBook size={40} />}
            title="No contacts found"
            description={
              urlQ || hasFilters
                ? "Try adjusting your search or filters."
                : "Run 'cleo contacts' to build the contact registry."
            }
          />
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Typeahead filter                                                     */
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

  useEffect(() => {
    setInput(value ? titleCase(value) : "");
  }, [value]);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        wrapperRef.current &&
        !wrapperRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = input
    ? options
        .filter((o) => o.toLowerCase().includes(input.toLowerCase()))
        .slice(0, 12)
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
            onClick={() => {
              setInput("");
              onChange("");
            }}
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
                  opt.toLowerCase() === value.toLowerCase() &&
                    "font-medium text-[var(--accent-11)]"
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
