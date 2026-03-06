import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Text, Spinner } from "@radix-ui/themes";
import { createColumnHelper } from "@tanstack/react-table";
import { MagnifyingGlass, X, Users, Funnel, Plus } from "@phosphor-icons/react";
import { PageHeader } from "@/components/ui/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState } from "@/components/ui/EmptyState";
import { fetchApi, mutateApi } from "@/api/client";
import { cn, titleCase, formatCompact } from "@/lib/utils";

interface GroupBrowseItem {
  id: string;
  name: string;
  display_name: string | null;
  property_count: number;
  buy_count: number;
  sell_count: number;
  cities: string[];
  total_value: number;
  total_sell_value: number;
  owned_value: number;
  latest_date: string;
  contacts: string[];
  phones: string[];
  all_names: string[];
  known_names: string[];
}

interface GroupBrowseResponse {
  results: GroupBrowseItem[];
  total: number;
  page: number;
  per_page: number;
}

interface GroupFiltersResponse {
  cities: string[];
  max_property_count: number;
  total_groups: number;
}

const col = createColumnHelper<GroupBrowseItem>();

const columns = [
  col.accessor("name", {
    header: "Name",
    cell: (info) => {
      const row = info.row.original;
      const display = row.display_name || row.name;
      return (
        <div className="flex flex-col gap-0.5">
          <Text size="2" weight="medium" className="block truncate max-w-[240px]">
            {display}
          </Text>
          {row.known_names.length > 1 && (
            <Text size="1" color="gray" className="block truncate max-w-[240px]">
              {row.known_names.length} linked names
            </Text>
          )}
        </div>
      );
    },
  }),
  col.accessor("property_count", {
    header: "Properties",
    cell: (info) => info.getValue() || "\u2014",
    size: 90,
  }),
  col.accessor("buy_count", {
    header: "Buys",
    cell: (info) => info.getValue() || "\u2014",
    size: 70,
  }),
  col.accessor("sell_count", {
    header: "Sells",
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
  col.accessor("contacts", {
    header: "Contact",
    cell: (info) => {
      const contacts = info.getValue();
      if (!contacts.length) return "\u2014";
      return (
        <Text size="2" className="max-w-[140px] truncate block">
          {contacts[0]}
        </Text>
      );
    },
    enableSorting: false,
  }),
  col.accessor("total_value", {
    header: "Buy Volume",
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

export function GroupsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const urlQ = searchParams.get("q") ?? "";
  const urlCity = searchParams.get("city") ?? "";
  const urlMinProps = searchParams.get("min_properties") ?? "";
  const urlPage = Number(searchParams.get("page")) || 1;
  const urlSort = searchParams.get("sort") ?? "property_count";
  const urlOrder = (searchParams.get("order") ?? "desc") as "asc" | "desc";

  const [searchInput, setSearchInput] = useState(urlQ);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const [data, setData] = useState<GroupBrowseResponse | null>(null);
  const [filters, setFilters] = useState<GroupFiltersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(!!(urlCity || urlMinProps));
  const [showCreate, setShowCreate] = useState(false);

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
    fetchApi<GroupFiltersResponse>("/groups/filters").then(setFilters);
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
    if (urlMinProps) params.min_properties = urlMinProps;

    fetchApi<GroupBrowseResponse>("/groups/browse", params)
      .then(setData)
      .finally(() => setLoading(false));
  }, [urlQ, urlCity, urlMinProps, urlPage, urlSort, urlOrder]);

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;
  const hasFilters = !!(urlCity || urlMinProps);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <PageHeader
          title="Groups"
          description={
            data
              ? `${data.total.toLocaleString()} groups${hasFilters ? " (filtered)" : ""}`
              : "Companies, individuals, and ownership groups."
          }
        />
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-3 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] transition-colors"
        >
          <Plus size={14} weight="bold" />
          New Group
        </button>
      </div>

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
              placeholder="Search by name, contact, phone..."
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
                {(urlCity ? 1 : 0) + (urlMinProps ? 1 : 0)}
              </span>
            )}
          </button>

          {hasFilters && (
            <button
              onClick={() => setParam({ city: "", min_properties: "" })}
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
              label="Min Properties"
              value={urlMinProps}
              options={["2", "5", "10", "25", "50"]}
              onChange={(v) => setParam({ min_properties: v })}
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
              onRowClick={(row) => navigate(`/groups/${row.id}`)}
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
            icon={<Users size={40} />}
            title="No groups found"
            description={
              urlQ || hasFilters
                ? "Try adjusting your search or filters."
                : "Run 'cleo groups' to build the group registry."
            }
          />
        )}
      </div>

      {showCreate && (
        <CreateGroupModal
          onClose={() => setShowCreate(false)}
          onCreated={(gid) => {
            setShowCreate(false);
            navigate(`/groups/${gid}`);
          }}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Create group modal                                                    */
/* ------------------------------------------------------------------ */

function CreateGroupModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (groupId: string) => void;
}) {
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      const res = await mutateApi<{ ok: boolean; group: { id: string } }>(
        "/groups",
        "POST",
        { name: name.trim() },
      );
      onCreated(res.group.id);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-[420px] rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white shadow-lg">
        <div className="flex items-center justify-between border-b border-[var(--gray-4)] px-5 py-3">
          <Text size="3" weight="medium">
            New Group
          </Text>
          <button
            onClick={onClose}
            className="text-[var(--gray-9)] hover:text-[var(--gray-11)]"
          >
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--gray-11)]">
              Company / Group Name{" "}
              <span className="text-[var(--red-9)]">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Southside Group Inc."
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
              autoFocus
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--gray-7)] px-4 text-[13px] font-medium text-[var(--gray-11)] hover:bg-[var(--gray-2)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || !name.trim()}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-4 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] disabled:opacity-50 transition-colors"
            >
              {saving ? "Creating..." : "Create Group"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Filter select                                                        */
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
        <option value="">Any</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}+
          </option>
        ))}
      </select>
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
