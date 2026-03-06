import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Text, Badge } from "@radix-ui/themes";
import { ArrowRight, Check, Plus } from "@phosphor-icons/react";
import { fetchApi, mutateApi } from "@/api/client";
import { formatCurrency, formatDate } from "@/lib/utils";
import { categoryColor } from "@/lib/theme";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ParcelPopupProps {
  arn: string;
  pin: string;
  property_id: string;
  address: string;
  city: string;
  owner: string;
  group_id: string;
  group_name: string;
  latest_price: number | null;
  latest_date: string;
  tenants: string[];
  tenant_categories: string[];
  categories: string[];
  sources: string[];
  transaction_count: number;
  parcel_method: string;
  photo: string;
}

interface GroupSearchResult {
  id: string;
  name: string;
  property_count: number;
}

interface CrmList {
  list_id: string;
  name: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toTitleCase(s: string): string {
  return s
    .toLowerCase()
    .replace(/(?:^|\s|[-/])\S/g, (ch) => ch.toUpperCase());
}

function shortAddress(raw: string): string {
  const parts = raw.split(",").map((p) => p.trim());
  const kept: string[] = [];
  for (const part of parts) {
    if (
      /^(ONTARIO|ON|ALBERTA|AB|BRITISH COLUMBIA|BC|QUEBEC|QC|MANITOBA|MB|SASKATCHEWAN|SK|NOVA SCOTIA|NS|NEW BRUNSWICK|NB|PEI|PE|NL|NT|NU|YT)$/i.test(
        part,
      )
    )
      break;
    if (/^[A-Z]\d[A-Z]\s*\d[A-Z]\d$/i.test(part)) break;
    kept.push(part);
  }
  return toTitleCase(kept.join(", "));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ParcelPopupContent({ props }: { props: ParcelPopupProps }) {
  const navigate = useNavigate();
  const [groupOpen, setGroupOpen] = useState(false);
  const [listOpen, setListOpen] = useState(false);

  return (
    <div className="flex flex-col gap-1.5">
      {/* Property photo */}
      {props.photo && (
        <img
          src={props.photo}
          alt=""
          className="w-full rounded-[var(--radius-2)] object-cover"
          style={{ maxHeight: 160 }}
        />
      )}

      {/* Address */}
      <Text size="2" weight="medium" className="text-[var(--gray-12)]">
        {shortAddress(props.address) || props.city || "Unknown"}
      </Text>

      {/* Group / Owner */}
      {props.group_name ? (
        <button
          className="text-left text-xs font-medium text-[var(--accent-11)] hover:underline"
          onClick={() => navigate(`/groups/${props.group_id}`)}
        >
          {props.group_name}
        </button>
      ) : props.owner ? (
        <Text size="1" className="text-[var(--gray-11)]">
          {props.owner}
        </Text>
      ) : null}

      {/* Last sale price + date */}
      {props.latest_price != null && (
        <div className="flex items-center gap-2">
          <Text size="1" weight="medium" className="text-[var(--gray-12)]">
            {formatCurrency(props.latest_price)}
          </Text>
          {props.latest_date && (
            <Text size="1" className="text-[var(--gray-9)]">
              {formatDate(props.latest_date)}
            </Text>
          )}
        </div>
      )}

      {/* Tenant badges */}
      {props.tenants.length > 0 && (
        <div className="flex flex-wrap gap-1 pt-0.5">
          {props.tenants.map((t, i) => (
            <Badge
              key={t}
              size="1"
              variant="soft"
              color={categoryColor(props.tenant_categories[i] || "")}
            >
              {t}
            </Badge>
          ))}
        </div>
      )}

      {/* View property link */}
      {props.property_id && (
        <button
          className="mt-1 flex items-center gap-1 text-xs font-medium text-[var(--accent-11)] hover:underline"
          onClick={() => navigate(`/properties/${props.property_id}`)}
        >
          View property
          <ArrowRight size={12} />
        </button>
      )}

      {/* Prospecting actions */}
      {props.property_id && (
        <>
          <div className="mt-1 border-t border-[var(--gray-4)] pt-2">
            <Text
              size="1"
              weight="medium"
              className="text-[var(--gray-9)] block mb-1.5"
            >
              Prospecting
            </Text>
            <div className="flex flex-col gap-1">
              <button
                onClick={() => {
                  setGroupOpen(!groupOpen);
                  setListOpen(false);
                }}
                className="flex items-center gap-1 text-xs font-medium text-[var(--gray-11)] hover:text-[var(--gray-12)]"
              >
                <Plus size={12} />
                Add to Group
              </button>
              {groupOpen && (
                <AddToGroupInline
                  arn={props.arn}
                  propertyId={props.property_id}
                  onDone={() => setGroupOpen(false)}
                />
              )}

              <button
                onClick={() => {
                  setListOpen(!listOpen);
                  setGroupOpen(false);
                }}
                className="flex items-center gap-1 text-xs font-medium text-[var(--gray-11)] hover:text-[var(--gray-12)]"
              >
                <Plus size={12} />
                Add to List
              </button>
              {listOpen && (
                <AddToListInline
                  propertyId={props.property_id}
                  address={shortAddress(props.address)}
                  onDone={() => setListOpen(false)}
                />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add to Group — inline typeahead
// ---------------------------------------------------------------------------

function AddToGroupInline({
  arn,
  propertyId,
  onDone,
}: {
  arn: string;
  propertyId: string;
  onDone: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GroupSearchResult[]>([]);
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (!query.trim()) {
      setResults([]);
      return;
    }
    debounceRef.current = setTimeout(() => {
      fetchApi<{ results: GroupSearchResult[] }>("/groups/search", {
        q: query.trim(),
        limit: "6",
      }).then((r) => setResults(r.results));
    }, 200);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  const handleSelect = async (groupId: string, groupName: string) => {
    setSaving(true);
    try {
      await mutateApi(`/groups/${groupId}/properties`, "POST", {
        arn,
        property_id: propertyId,
      });
      setSuccess(groupName);
      setTimeout(onDone, 1200);
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async () => {
    if (!query.trim()) return;
    setSaving(true);
    try {
      const res = await mutateApi<{ ok: boolean; group: { id: string } }>(
        "/groups",
        "POST",
        { name: query.trim() },
      );
      await mutateApi(`/groups/${res.group.id}/properties`, "POST", {
        arn,
        property_id: propertyId,
      });
      setSuccess(query.trim());
      setTimeout(onDone, 1200);
    } finally {
      setSaving(false);
    }
  };

  if (success) {
    return (
      <div className="flex items-center gap-1 rounded-[var(--radius-2)] bg-[var(--green-2)] px-2 py-1">
        <Check size={12} className="text-[var(--green-11)]" />
        <Text size="1" className="text-[var(--green-11)]">
          Added to {success}
        </Text>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search groups..."
        disabled={saving}
        className="h-7 w-full rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-2 text-xs text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
      />
      {results.length > 0 && (
        <div className="flex flex-col rounded-[var(--radius-2)] border border-[var(--gray-6)] max-h-[160px] overflow-y-auto">
          {results.map((g) => (
            <button
              key={g.id}
              onClick={() =>
                handleSelect(g.id, g.name)
              }
              disabled={saving}
              className="px-2 py-1.5 text-left text-xs text-[var(--gray-12)] hover:bg-[var(--gray-2)] border-b border-[var(--gray-4)] last:border-0 disabled:opacity-50"
            >
              <span className="font-medium">{g.name}</span>
              <span className="ml-1 text-[var(--gray-9)]">
                ({g.property_count} properties)
              </span>
            </button>
          ))}
        </div>
      )}
      {query.trim() &&
        results.length === 0 && (
          <button
            onClick={handleCreate}
            disabled={saving}
            className="px-2 py-1.5 text-left text-xs text-[var(--accent-11)] hover:bg-[var(--accent-2)] rounded-[var(--radius-2)] border border-[var(--gray-6)] disabled:opacity-50"
          >
            Create "{query.trim()}" and add property
          </button>
        )}
      {query.trim() && results.length > 0 && (
        <button
          onClick={handleCreate}
          disabled={saving}
          className="px-2 py-1 text-left text-xs text-[var(--accent-11)] hover:underline disabled:opacity-50"
        >
          Create new group "{query.trim()}"
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Add to List — inline typeahead
// ---------------------------------------------------------------------------

function AddToListInline({
  propertyId,
  address,
  onDone,
}: {
  propertyId: string;
  address: string;
  onDone: () => void;
}) {
  const [query, setQuery] = useState("");
  const [lists, setLists] = useState<CrmList[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [success, setSuccess] = useState("");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    fetchApi<{ lists: CrmList[] }>("/crm/lists")
      .then((r) => setLists(r.lists))
      .finally(() => setLoaded(true));
  }, []);

  const filtered = query.trim()
    ? lists.filter((l) =>
        l.name.toLowerCase().includes(query.toLowerCase()),
      )
    : lists;

  const exactMatch = lists.some(
    (l) => l.name.toLowerCase() === query.trim().toLowerCase(),
  );

  const handleAddToList = async (listId: string, listName: string) => {
    setSaving(true);
    try {
      await mutateApi(`/crm/lists/${listId}/items`, "POST", {
        type: "property",
        property_id: propertyId,
        name: address,
      });
      setSuccess(listName);
      setTimeout(onDone, 1200);
    } finally {
      setSaving(false);
    }
  };

  const handleCreateAndAdd = async () => {
    if (!query.trim()) return;
    setSaving(true);
    try {
      const res = await mutateApi<{ list: CrmList }>("/crm/lists", "POST", {
        name: query.trim(),
      });
      await mutateApi(`/crm/lists/${res.list.list_id}/items`, "POST", {
        type: "property",
        property_id: propertyId,
        name: address,
      });
      setSuccess(query.trim());
      setTimeout(onDone, 1200);
    } finally {
      setSaving(false);
    }
  };

  if (success) {
    return (
      <div className="flex items-center gap-1 rounded-[var(--radius-2)] bg-[var(--green-2)] px-2 py-1">
        <Check size={12} className="text-[var(--green-11)]" />
        <Text size="1" className="text-[var(--green-11)]">
          Added to {success}
        </Text>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={loaded ? "Search or create list..." : "Loading..."}
        disabled={saving || !loaded}
        className="h-7 w-full rounded-[var(--radius-2)] border border-[var(--gray-6)] bg-white px-2 text-xs text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
      />
      {loaded && filtered.length > 0 && (
        <div className="flex flex-col rounded-[var(--radius-2)] border border-[var(--gray-6)] max-h-[160px] overflow-y-auto">
          {filtered.slice(0, 8).map((l) => (
            <button
              key={l.list_id}
              onClick={() => handleAddToList(l.list_id, l.name)}
              disabled={saving}
              className="px-2 py-1.5 text-left text-xs text-[var(--gray-12)] hover:bg-[var(--gray-2)] border-b border-[var(--gray-4)] last:border-0 disabled:opacity-50"
            >
              {l.name}
            </button>
          ))}
        </div>
      )}
      {loaded && query.trim() && !exactMatch && (
        <button
          onClick={handleCreateAndAdd}
          disabled={saving}
          className="px-2 py-1.5 text-left text-xs text-[var(--accent-11)] hover:bg-[var(--accent-2)] rounded-[var(--radius-2)] border border-[var(--gray-6)] disabled:opacity-50"
        >
          Create "{query.trim()}" and add property
        </button>
      )}
    </div>
  );
}
