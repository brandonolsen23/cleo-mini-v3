import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Text, Spinner } from "@radix-ui/themes";
import {
  MagnifyingGlass,
  X,
  Users,
  Funnel,
  LinkSimple,
  Info,
} from "@phosphor-icons/react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Pagination } from "@/components/ui/Pagination";
import { EmptyState } from "@/components/ui/EmptyState";
import { fetchApi, mutateApi } from "@/api/client";
import { cn, formatDate, titleCase } from "@/lib/utils";
import type {
  EntityBrowseItem,
  EntityBrowseResponse,
  EntityFiltersResponse,
} from "@/types";

function formatValue(v: number): string {
  if (!v) return "\u2014";
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(2)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toLocaleString()}`;
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function OwnersPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // URL state
  const urlName = searchParams.get("name") ?? "";
  const urlContact = searchParams.get("contact") ?? "";
  const urlPhone = searchParams.get("phone") ?? "";
  const urlAddress = searchParams.get("address") ?? "";
  const urlCity = searchParams.get("city") ?? "";
  const urlMinProps = searchParams.get("min_properties") ?? "";
  const urlPage = Number(searchParams.get("page")) || 1;
  const urlSort = searchParams.get("sort") ?? "property_count";
  const urlOrder = (searchParams.get("order") ?? "desc") as "asc" | "desc";

  // Local search inputs (debounced)
  const [nameInput, setNameInput] = useState(urlName);
  const [contactInput, setContactInput] = useState(urlContact);
  const [phoneInput, setPhoneInput] = useState(urlPhone);
  const [addressInput, setAddressInput] = useState(urlAddress);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Data state
  const [data, setData] = useState<EntityBrowseResponse | null>(null);
  const [filters, setFilters] = useState<EntityFiltersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(
    !!(urlCity || urlMinProps || urlPhone || urlAddress)
  );

  // Refresh counter — increment to force a re-fetch after link/unlink
  const [refreshKey, setRefreshKey] = useState(0);

  // Selection state for linking
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [linking, setLinking] = useState(false);
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkDisplayName, setLinkDisplayName] = useState("");
  const [linkReason, setLinkReason] = useState("");
  const [existingGroups, setExistingGroups] = useState<{ id: string; display_name: string; members: string[] }[]>([]);
  const [targetGroup, setTargetGroup] = useState<{ id: string; display_name: string; members: string[] } | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const suggestRef = useRef<HTMLDivElement>(null);

  // Fetch existing link groups when modal opens
  useEffect(() => {
    if (!linkModalOpen) return;
    fetchApi<{ links: { id: string; display_name: string; members: string[] }[] }>("/owners/links")
      .then((d) => setExistingGroups(d.links.filter((g) => g.display_name)))
      .catch(() => {});
  }, [linkModalOpen]);

  // Close suggestions on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (suggestRef.current && !suggestRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Set URL params
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

  // Debounce search inputs → URL
  useEffect(() => {
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const updates: Record<string, string> = {};
      if (nameInput !== urlName) updates.name = nameInput;
      if (contactInput !== urlContact) updates.contact = contactInput;
      if (phoneInput !== urlPhone) updates.phone = phoneInput;
      if (addressInput !== urlAddress) updates.address = addressInput;
      if (Object.keys(updates).length > 0) {
        setParam(updates);
      }
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [nameInput, contactInput, phoneInput, addressInput]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sync URL → local inputs
  useEffect(() => { setNameInput(urlName); }, [urlName]);
  useEffect(() => { setContactInput(urlContact); }, [urlContact]);
  useEffect(() => { setPhoneInput(urlPhone); }, [urlPhone]);
  useEffect(() => { setAddressInput(urlAddress); }, [urlAddress]);

  // Load filters once
  useEffect(() => {
    fetchApi<EntityFiltersResponse>("/owners/filters").then(setFilters);
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
    if (urlName) params.name = urlName;
    if (urlContact) params.contact = urlContact;
    if (urlPhone) params.phone = urlPhone;
    if (urlAddress) params.address = urlAddress;
    if (urlCity) params.city = urlCity;
    if (urlMinProps) params.min_properties = urlMinProps;

    fetchApi<EntityBrowseResponse>("/owners/browse", params)
      .then((d) => {
        setData(d);
        setSelected(new Set()); // clear selection on data change
      })
      .finally(() => setLoading(false));
  }, [urlName, urlContact, urlPhone, urlAddress, urlCity, urlMinProps, urlPage, urlSort, urlOrder, refreshKey]);

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;
  const hasFilters = !!(urlCity || urlMinProps || urlPhone || urlAddress);
  const hasSearch = !!(urlName || urlContact);

  // Toggle row selection
  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Link selected owners (or add to existing group)
  const handleLink = async () => {
    const minRequired = targetGroup ? 1 : 2;
    if (selected.size < minRequired) return;
    setLinking(true);

    // Collect all names from selected owners
    const names: string[] = [];
    for (const item of data?.results ?? []) {
      if (selected.has(item.id)) {
        for (const n of item.all_names) {
          if (!names.includes(n)) names.push(n);
        }
      }
    }

    // If adding to an existing group, include one of its members
    // so the backend merges into that group
    if (targetGroup && targetGroup.members.length > 0) {
      const anchor = targetGroup.members[0];
      if (!names.includes(anchor)) names.push(anchor);
    }

    try {
      await mutateApi("/owners/link", "POST", {
        names,
        display_name: linkDisplayName || undefined,
        reason: linkReason || "Manual link from owners page",
      });
      // Close modal, clear state, and re-fetch
      setLinkModalOpen(false);
      setLinkDisplayName("");
      setLinkReason("");
      setTargetGroup(null);
      setSelected(new Set());
      setRefreshKey((k) => k + 1);
    } catch (e: any) {
      console.error("Link failed:", e);
      alert(`Link failed: ${e?.message || e}`);
    } finally {
      setLinking(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title="Entities"
        description={
          data
            ? `${data.total.toLocaleString()} entities${hasFilters || hasSearch ? " (filtered)" : ""}`
            : "Browse entities across all transactions."
        }
      />

      <div className="flex flex-col gap-4">
        {/* Search row: name + contact inputs */}
        <div className="flex items-center gap-3">
          <SearchInput
            value={nameInput}
            onChange={setNameInput}
            onClear={() => { setNameInput(""); setParam({ name: "" }); }}
            placeholder="Search owner name..."
            maxWidth={280}
          />
          <SearchInput
            value={contactInput}
            onChange={setContactInput}
            onClear={() => { setContactInput(""); setParam({ contact: "" }); }}
            placeholder="Contact name..."
            maxWidth={200}
          />

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
                {[urlCity, urlMinProps, urlPhone, urlAddress].filter(Boolean).length}
              </span>
            )}
          </button>

          {(hasFilters || hasSearch) && (
            <button
              onClick={() => {
                setNameInput("");
                setContactInput("");
                setPhoneInput("");
                setAddressInput("");
                setParam({ name: "", contact: "", phone: "", address: "", city: "", min_properties: "" });
              }}
              className="text-[13px] text-[var(--gray-11)] hover:text-[var(--gray-12)]"
            >
              Clear all
            </button>
          )}
        </div>

        {/* Expanded filter bar */}
        {filtersOpen && filters && (
          <div className="flex flex-wrap items-center gap-3 rounded-[var(--radius-2)] border border-[var(--gray-4)] bg-[var(--gray-2)] px-4 py-3">
            <SearchInput
              value={phoneInput}
              onChange={setPhoneInput}
              onClear={() => { setPhoneInput(""); setParam({ phone: "" }); }}
              placeholder="Phone..."
              maxWidth={160}
              small
            />
            <SearchInput
              value={addressInput}
              onChange={setAddressInput}
              onClear={() => { setAddressInput(""); setParam({ address: "" }); }}
              placeholder="Corp address..."
              maxWidth={200}
              small
            />
            <FilterTypeahead
              label="City"
              value={urlCity}
              options={filters.cities}
              onChange={(v) => setParam({ city: v })}
            />
            <FilterSelect
              label="Min Properties"
              value={urlMinProps}
              options={["2", "3", "5", "10", "20", "50"]}
              onChange={(v) => setParam({ min_properties: v })}
            />
          </div>
        )}

        {/* Table with checkbox column */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <Spinner size="3" />
          </div>
        ) : data && data.results.length > 0 ? (
          <>
            <OwnerTable
              data={data.results}
              selected={selected}
              onToggleSelect={toggleSelect}
              onRowClick={(row) => navigate(`/owners/${row.id}`)}
              nameQuery={urlName}
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
            title="No entities found"
            description={
              hasSearch || hasFilters
                ? "Try adjusting your search or filters."
                : "Run 'cleo properties' to build the property registry."
            }
          />
        )}
      </div>

      {/* Floating action bar when items selected */}
      {selected.size >= 1 && (
        <div className="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-[var(--radius-3)] border border-[var(--gray-6)] bg-white px-4 py-2.5 shadow-[var(--elevation-3)]">
          <Text size="2" weight="medium">
            {selected.size} entities selected
          </Text>
          <button
            onClick={() => setLinkModalOpen(true)}
            disabled={linking}
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--accent-9)] px-3 py-1.5 text-[13px] font-medium text-white transition-colors hover:bg-[var(--accent-10)]"
          >
            <LinkSimple size={14} />
            {linking ? "Linking..." : "Link Selected"}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-[13px] text-[var(--gray-11)] hover:text-[var(--gray-12)]"
          >
            Clear
          </button>
        </div>
      )}

      {/* Link modal */}
      {linkModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="w-[420px] rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white p-5 shadow-[var(--elevation-4)]">
            <Text size="3" weight="medium" className="mb-4 block">
              {selected.size === 1 ? "Add to Group" : `Link ${selected.size} Entities`}
            </Text>
            <div className="flex flex-col gap-3">
              <div ref={suggestRef} className="relative">
                <label className="mb-1 block text-[12px] font-medium text-[var(--gray-11)]">
                  {selected.size === 1
                    ? "Add to existing group or enter new name"
                    : "Display Name (existing group or new name)"}
                </label>
                <input
                  type="text"
                  value={linkDisplayName}
                  onChange={(e) => {
                    setLinkDisplayName(e.target.value);
                    setTargetGroup(null);
                    setShowSuggestions(true);
                  }}
                  onFocus={() => setShowSuggestions(true)}
                  placeholder="e.g. RioCan REIT"
                  className={cn(
                    "h-8 w-full rounded-[var(--radius-2)] border bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:outline-none",
                    targetGroup
                      ? "border-[var(--accent-8)] bg-[var(--accent-a2)]"
                      : "border-[var(--gray-7)] focus:border-[var(--accent-8)]"
                  )}
                />
                {targetGroup && (
                  <Text size="1" className="mt-1 block text-[var(--accent-11)]">
                    Will add to existing group: {targetGroup.id} ({targetGroup.members.length} members)
                  </Text>
                )}
                {showSuggestions && linkDisplayName.length >= 2 && !targetGroup && (
                  (() => {
                    const q = linkDisplayName.toLowerCase();
                    const matches = existingGroups.filter((g) =>
                      g.display_name.toLowerCase().includes(q)
                    );
                    if (matches.length === 0) return null;
                    return (
                      <div className="absolute left-0 right-0 top-full z-10 mt-1 max-h-[160px] overflow-y-auto rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white shadow-sm">
                        {matches.map((g) => (
                          <button
                            key={g.id}
                            onClick={() => {
                              setTargetGroup(g);
                              setLinkDisplayName(g.display_name);
                              setShowSuggestions(false);
                            }}
                            className="flex w-full items-center justify-between px-3 py-2 text-left text-[13px] hover:bg-[var(--gray-3)]"
                          >
                            <span className="font-medium text-[var(--gray-12)]">{g.display_name}</span>
                            <span className="text-[var(--gray-9)]">{g.members.length} members</span>
                          </button>
                        ))}
                      </div>
                    );
                  })()
                )}
              </div>
              <div>
                <label className="mb-1 block text-[12px] font-medium text-[var(--gray-11)]">
                  Reason
                </label>
                <textarea
                  value={linkReason}
                  onChange={(e) => setLinkReason(e.target.value)}
                  placeholder="Why are these the same entity?"
                  rows={2}
                  className="w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 py-2 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
                />
              </div>
              <div className="mt-1 flex items-center justify-end gap-2">
                <button
                  onClick={() => {
                    setLinkModalOpen(false);
                    setLinkDisplayName("");
                    setLinkReason("");
                    setTargetGroup(null);
                  }}
                  className="rounded-[var(--radius-2)] px-3 py-1.5 text-[13px] font-medium text-[var(--gray-11)] hover:bg-[var(--gray-3)]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleLink}
                  disabled={linking || (selected.size < 2 && !targetGroup)}
                  className="rounded-[var(--radius-2)] bg-[var(--accent-9)] px-3 py-1.5 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] disabled:opacity-50"
                >
                  {linking ? "Linking..." : targetGroup ? "Add to Group" : "Confirm Link"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Owner table with checkbox column                                    */
/* ------------------------------------------------------------------ */

function OwnerTable({
  data,
  selected,
  onToggleSelect,
  onRowClick,
  nameQuery,
}: {
  data: EntityBrowseItem[];
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
  onRowClick: (row: EntityBrowseItem) => void;
  nameQuery: string;
}) {
  return (
    <div className="overflow-x-auto rounded-[var(--radius-4)] border border-[var(--gray-6)]">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-[var(--gray-6)] bg-[var(--gray-2)]">
            <th className="w-10 px-3 py-2.5">
              <span className="sr-only">Select</span>
            </th>
            <th className="px-4 py-2.5">
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Owner</span>
            </th>
            <th className="px-4 py-2.5">
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Contact</span>
            </th>
            <th className="px-4 py-2.5" style={{ width: 70 }}>
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Owned</span>
            </th>
            <th className="px-4 py-2.5" style={{ width: 60 }}>
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Buys</span>
            </th>
            <th className="px-4 py-2.5" style={{ width: 60 }}>
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Sells</span>
            </th>
            <th className="px-4 py-2.5" style={{ width: 90 }}>
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Owned</span>
            </th>
            <th className="px-4 py-2.5" style={{ width: 90 }}>
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Acquired</span>
            </th>
            <th className="px-4 py-2.5" style={{ width: 90 }}>
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Disposed</span>
            </th>
            <th className="px-4 py-2.5" style={{ width: 120 }}>
              <span className="text-[12px] font-medium leading-[16px] text-[var(--gray-11)]">Latest</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((row) => (
            <tr
              key={row.id}
              className="border-b border-[var(--gray-4)] last:border-b-0 hover:bg-[var(--gray-2)]"
            >
              <td className="w-10 px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={selected.has(row.id)}
                  onChange={(e) => {
                    e.stopPropagation();
                    onToggleSelect(row.id);
                  }}
                  className="h-3.5 w-3.5 rounded border-[var(--gray-7)] accent-[var(--accent-9)]"
                />
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
              >
                <div className="flex items-center gap-2">
                  <Text size="2" weight="medium" className="max-w-[220px] truncate block">
                    {row.display_name || row.name}
                  </Text>
                  {row.link_id && (
                    <LinkSimple size={12} className="shrink-0 text-[var(--accent-9)]" />
                  )}
                  {row.alt_name_groups && row.alt_name_groups.length > 0 && (
                    <AltNamesHover groups={row.alt_name_groups} query={nameQuery} />
                  )}
                </div>
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
              >
                {row.contacts.length > 0 ? (
                  <Text size="2" className="max-w-[140px] truncate block">
                    {row.contacts[0]}
                    {row.contacts.length > 1 ? ` +${row.contacts.length - 1}` : ""}
                  </Text>
                ) : "\u2014"}
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
                style={{ width: 70 }}
              >
                {row.property_count}
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
                style={{ width: 60 }}
              >
                {row.buy_count}
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
                style={{ width: 60 }}
              >
                {row.sell_count || "\u2014"}
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
                style={{ width: 90 }}
              >
                {formatValue(row.owned_value)}
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
                style={{ width: 90 }}
              >
                {formatValue(row.total_value)}
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
                style={{ width: 90 }}
              >
                {formatValue(row.total_sell_value)}
              </td>
              <td
                className="cursor-pointer px-4 py-2.5 text-[14px] leading-[20px] text-[var(--gray-12)]"
                onClick={() => onRowClick(row)}
                style={{ width: 120 }}
              >
                {row.latest_date ? (
                  <span className="whitespace-nowrap">{formatDate(row.latest_date)}</span>
                ) : "\u2014"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Alternate names hover popup                                         */
/* ------------------------------------------------------------------ */

function HighlightText({ text, query }: { text: string; query: string }) {
  if (!query) return <>{text}</>;
  const q = query.toLowerCase();
  const lower = text.toLowerCase();
  const idx = lower.indexOf(q);
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <span className="font-medium text-[var(--gray-12)]">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}

function AltNamesHover({ groups, query }: { groups: string[][]; query: string }) {
  return (
    <span
      className="group/alt relative inline-flex shrink-0 items-center"
      onClick={(e) => e.stopPropagation()}
    >
      <span className="inline-flex cursor-default rounded p-0.5 text-[var(--gray-9)] group-hover/alt:text-[var(--gray-11)]">
        <Info size={13} />
      </span>
      <span className="pointer-events-none absolute left-1/2 bottom-full z-50 mb-1 hidden w-max max-w-[280px] -translate-x-1/2 rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-3 py-2 shadow-[var(--elevation-3)] group-hover/alt:block">
        <span className="block text-[11px] font-medium text-[var(--gray-9)] mb-1">Alternate Names</span>
        {groups.map((group, gi) => (
          <span key={gi}>
            {gi > 0 && (
              <span className="my-1 block border-t border-[var(--gray-4)]" />
            )}
            {group.map((name, ni) => (
              <span key={ni} className="block text-[12px] text-[var(--gray-11)]">
                <HighlightText text={name} query={query} />
              </span>
            ))}
          </span>
        ))}
      </span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Search input component                                              */
/* ------------------------------------------------------------------ */

function SearchInput({
  value,
  onChange,
  onClear,
  placeholder,
  maxWidth = 280,
  small = false,
}: {
  value: string;
  onChange: (v: string) => void;
  onClear: () => void;
  placeholder: string;
  maxWidth?: number;
  small?: boolean;
}) {
  const h = small ? "h-7" : "h-8";
  return (
    <div className="relative" style={{ maxWidth, width: "100%" }}>
      <MagnifyingGlass
        size={small ? 13 : 15}
        className={cn(
          "absolute left-3 top-1/2 -translate-y-1/2 text-[var(--gray-9)]",
        )}
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={cn(
          h,
          "w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white pl-8 pr-7 text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none",
          small ? "text-[13px]" : "text-[14px]",
        )}
      />
      {value && (
        <button
          onClick={onClear}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--gray-9)] hover:text-[var(--gray-11)]"
        >
          <X size={small ? 11 : 13} />
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Filter helpers (same pattern as PropertiesPage)                     */
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
            {opt}
          </option>
        ))}
      </select>
    </div>
  );
}

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
