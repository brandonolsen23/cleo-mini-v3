import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Text, Badge, Spinner } from "@radix-ui/themes";
import {
  ArrowLeft,
  Buildings,
  User,
  MapPin,
  Copy,
  Check,
  Plus,
  X,
} from "@phosphor-icons/react";
import { fetchApi, mutateApi } from "@/api/client";
import { formatCurrency, formatDate, formatStreet, titleCase } from "@/lib/utils";

interface GroupDetail {
  id: string;
  name: string;
  display_name: string | null;
  known_names: string[];
  all_names: string[];
  contacts: { name: string; phone: string; source_ids: string[] }[];
  corp_addresses: {
    canonical: string;
    city?: string;
    lat?: number;
    lng?: number;
    rt_ids: string[];
  }[];
  phones: string[];
  properties: {
    property_id: string;
    address: string;
    city: string;
    sale_price: number | null;
    sale_date: string;
    rt_id: string;
  }[];
  property_count: number;
  owned_value: number;
  buy_transactions: {
    property_id: string;
    address: string;
    city: string;
    sale_price: number | null;
    sale_date: string;
    rt_id: string;
    contact: string;
    phone: string;
    is_owned: boolean;
  }[];
  buy_count: number;
  seller_transactions: {
    property_id: string;
    address: string;
    city: string;
    sale_price: number | null;
    sale_date: string;
    rt_id: string;
    contact: string;
    phone: string;
  }[];
  sell_count: number;
  cities: string[];
  total_value: number;
  total_sell_value: number;
  latest_date: string;
  earliest_date: string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="ml-1 inline-flex text-[var(--gray-9)] hover:text-[var(--gray-11)]"
    >
      {copied ? <Check size={13} /> : <Copy size={13} />}
    </button>
  );
}

export function GroupDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [group, setGroup] = useState<GroupDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"buys" | "sells">("buys");
  const [showAddProperty, setShowAddProperty] = useState(false);

  const load = () => {
    if (!id) return;
    setLoading(true);
    fetchApi<GroupDetail>(`/groups/${id}`)
      .then(setGroup)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="3" />
      </div>
    );
  }

  if (error || !group) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Text size="3" color="gray">
          {error || "Group not found"}
        </Text>
        <button
          onClick={() => navigate("/groups")}
          className="mt-4 text-[13px] font-medium text-[var(--accent-11)] hover:underline"
        >
          Back to Groups
        </button>
      </div>
    );
  }

  const displayName = group.display_name || group.name;
  const txns = activeTab === "buys" ? group.buy_transactions : group.seller_transactions;

  return (
    <div className="flex flex-col gap-6">
      {/* Back + header */}
      <div>
        <button
          onClick={() => navigate("/groups")}
          className="mb-3 inline-flex items-center gap-1 text-[13px] font-medium text-[var(--gray-11)] hover:text-[var(--gray-12)]"
        >
          <ArrowLeft size={14} />
          Groups
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-[24px] font-medium leading-[32px] text-[var(--gray-12)]">
              {displayName}
            </h2>
            <Text size="2" color="gray">
              {group.id}
            </Text>
          </div>
          <button
            onClick={() => setShowAddProperty(true)}
            className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-3 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] transition-colors"
          >
            <Plus size={14} weight="bold" />
            Add Property
          </button>
        </div>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-4 gap-4">
        <StatBox label="Properties Owned" value={group.property_count} />
        <StatBox
          label="Owned Value"
          value={group.owned_value ? formatCurrency(group.owned_value) : "\u2014"}
          raw
        />
        <StatBox label="Buy Transactions" value={group.buy_count} />
        <StatBox label="Sell Transactions" value={group.sell_count} />
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Contacts card */}
        <Card title="Contacts" icon={<User size={15} />}>
          {group.contacts.length === 0 ? (
            <Text size="2" color="gray">No contacts on record.</Text>
          ) : (
            <div className="flex flex-col gap-2">
              {group.contacts.slice(0, 8).map((c, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div>
                    <Text size="2" weight="medium" className="block">
                      {c.name}
                    </Text>
                    {c.phone && (
                      <Text size="1" color="gray" className="block">
                        {c.phone}
                        <CopyButton text={c.phone} />
                      </Text>
                    )}
                  </div>
                  <Badge size="1" color="gray" variant="soft">
                    {c.source_ids.length} txn{c.source_ids.length !== 1 ? "s" : ""}
                  </Badge>
                </div>
              ))}
              {group.contacts.length > 8 && (
                <Text size="1" color="gray">
                  +{group.contacts.length - 8} more
                </Text>
              )}
            </div>
          )}
        </Card>

        {/* Addresses card */}
        <Card title="Corporate Addresses" icon={<MapPin size={15} />}>
          {group.corp_addresses.length === 0 ? (
            <Text size="2" color="gray">No addresses on record.</Text>
          ) : (
            <div className="flex flex-col gap-2">
              {group.corp_addresses.slice(0, 5).map((a, i) => (
                <div key={i}>
                  <Text size="2" className="block">
                    {formatStreet(a.canonical)}
                  </Text>
                  {a.city && (
                    <Text size="1" color="gray" className="block">
                      {titleCase(a.city)}
                    </Text>
                  )}
                </div>
              ))}
              {group.corp_addresses.length > 5 && (
                <Text size="1" color="gray">
                  +{group.corp_addresses.length - 5} more
                </Text>
              )}
            </div>
          )}
        </Card>

        {/* Known names card */}
        <Card title="Known Names" icon={<Buildings size={15} />}>
          <div className="flex flex-col gap-1">
            {group.all_names.map((n, i) => (
              <Text key={i} size="2" className="block">
                {n}
              </Text>
            ))}
          </div>
          {group.known_names.length > group.all_names.length && (
            <Text size="1" color="gray" className="mt-2 block">
              {group.known_names.length} normalized variants
            </Text>
          )}
        </Card>
      </div>

      {/* Owned properties */}
      {group.properties.length > 0 && (
        <Card title={`Owned Properties (${group.property_count})`} icon={<Buildings size={15} />} full>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--gray-4)] text-left text-[var(--gray-9)]">
                <th className="pb-2 font-medium">Address</th>
                <th className="pb-2 font-medium">City</th>
                <th className="pb-2 font-medium text-right">Sale Price</th>
                <th className="pb-2 font-medium text-right">Date</th>
              </tr>
            </thead>
            <tbody>
              {group.properties.map((p) => (
                <tr
                  key={p.property_id}
                  className="border-b border-[var(--gray-4)] last:border-0 cursor-pointer hover:bg-[var(--gray-2)]"
                  onClick={() => navigate(`/properties/${p.property_id}`)}
                >
                  <td className="py-2 pr-4 text-[var(--gray-12)]">
                    {formatStreet(p.address)}
                  </td>
                  <td className="py-2 pr-4 text-[var(--gray-11)]">
                    {titleCase(p.city)}
                  </td>
                  <td className="py-2 pr-4 text-right text-[var(--gray-11)]">
                    {p.sale_price ? formatCurrency(p.sale_price) : "\u2014"}
                  </td>
                  <td className="py-2 text-right text-[var(--gray-11)]">
                    {p.sale_date ? formatDate(p.sale_date) : "\u2014"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {/* Transaction history */}
      <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)]">
        <div className="flex items-center gap-4 border-b border-[var(--gray-4)] px-5 pt-4 pb-0">
          <TabButton
            active={activeTab === "buys"}
            onClick={() => setActiveTab("buys")}
            label={`Purchases (${group.buy_count})`}
          />
          <TabButton
            active={activeTab === "sells"}
            onClick={() => setActiveTab("sells")}
            label={`Sales (${group.sell_count})`}
          />
        </div>
        <div className="p-5">
          {txns.length === 0 ? (
            <Text size="2" color="gray">
              No {activeTab === "buys" ? "purchase" : "sale"} transactions.
            </Text>
          ) : (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--gray-4)] text-left text-[var(--gray-9)]">
                  <th className="pb-2 font-medium">Address</th>
                  <th className="pb-2 font-medium">City</th>
                  <th className="pb-2 font-medium">Contact</th>
                  <th className="pb-2 font-medium text-right">Price</th>
                  <th className="pb-2 font-medium text-right">Date</th>
                </tr>
              </thead>
              <tbody>
                {txns.map((t, i) => (
                  <tr
                    key={`${t.rt_id}-${i}`}
                    className="border-b border-[var(--gray-4)] last:border-0 cursor-pointer hover:bg-[var(--gray-2)]"
                    onClick={() => navigate(`/properties/${t.property_id}`)}
                  >
                    <td className="py-2 pr-4 text-[var(--gray-12)]">
                      <div className="flex items-center gap-1.5">
                        {formatStreet(t.address)}
                        {"is_owned" in t && (t as { is_owned: boolean }).is_owned && (
                          <Badge size="1" color="jade" variant="soft">
                            owned
                          </Badge>
                        )}
                      </div>
                    </td>
                    <td className="py-2 pr-4 text-[var(--gray-11)]">
                      {titleCase(t.city)}
                    </td>
                    <td className="py-2 pr-4 text-[var(--gray-11)]">
                      {t.contact || "\u2014"}
                    </td>
                    <td className="py-2 pr-4 text-right text-[var(--gray-11)]">
                      {t.sale_price ? formatCurrency(t.sale_price) : "\u2014"}
                    </td>
                    <td className="py-2 text-right text-[var(--gray-11)]">
                      {t.sale_date ? formatDate(t.sale_date) : "\u2014"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Cities + activity range */}
      <div className="grid grid-cols-2 gap-4">
        <Card title="Active Cities" icon={<MapPin size={15} />}>
          <div className="flex flex-wrap gap-1.5">
            {group.cities.map((c) => (
              <Badge key={c} size="1" color="gray" variant="soft">
                {titleCase(c)}
              </Badge>
            ))}
          </div>
        </Card>
        <Card title="Activity Range" icon={<Buildings size={15} />}>
          <div className="flex flex-col gap-1">
            <div className="flex justify-between">
              <Text size="2" color="gray">First seen</Text>
              <Text size="2">{group.earliest_date ? formatDate(group.earliest_date) : "\u2014"}</Text>
            </div>
            <div className="flex justify-between">
              <Text size="2" color="gray">Last seen</Text>
              <Text size="2">{group.latest_date ? formatDate(group.latest_date) : "\u2014"}</Text>
            </div>
            <div className="flex justify-between">
              <Text size="2" color="gray">Total buy volume</Text>
              <Text size="2">{group.total_value ? formatCurrency(group.total_value) : "\u2014"}</Text>
            </div>
            <div className="flex justify-between">
              <Text size="2" color="gray">Total sell volume</Text>
              <Text size="2">{group.total_sell_value ? formatCurrency(group.total_sell_value) : "\u2014"}</Text>
            </div>
          </div>
        </Card>
      </div>

      {showAddProperty && (
        <AddPropertyModal
          groupId={group.id}
          onClose={() => setShowAddProperty(false)}
          onAdded={() => {
            setShowAddProperty(false);
            load();
          }}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Add Property modal                                                    */
/* ------------------------------------------------------------------ */

interface PropertySearchResult {
  property_id: string;
  arn: string;
  primary_address: string;
  city: string;
  current_owner: string;
}

function AddPropertyModal({
  groupId,
  onClose,
  onAdded,
}: {
  groupId: string;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PropertySearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (!query.trim() || query.trim().length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    debounceRef.current = setTimeout(() => {
      fetchApi<PropertySearchResult[]>("/properties/search", {
        q: query.trim(),
        limit: "8",
      })
        .then(setResults)
        .finally(() => setSearching(false));
    }, 250);
    return () => clearTimeout(debounceRef.current);
  }, [query]);

  const handleLink = async (prop: PropertySearchResult) => {
    setSaving(true);
    try {
      await mutateApi(`/groups/${groupId}/properties`, "POST", {
        arn: prop.arn,
        property_id: prop.property_id,
      });
      setSuccess(`Added ${formatStreet(prop.primary_address)}`);
      setTimeout(onAdded, 800);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-[520px] rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white shadow-lg">
        <div className="flex items-center justify-between border-b border-[var(--gray-4)] px-5 py-3">
          <Text size="3" weight="medium">
            Add Property to Group
          </Text>
          <button
            onClick={onClose}
            className="text-[var(--gray-9)] hover:text-[var(--gray-11)]"
          >
            <X size={16} />
          </button>
        </div>
        <div className="flex flex-col gap-3 p-5">
          {success ? (
            <div className="flex items-center gap-2 rounded-[var(--radius-2)] bg-[var(--green-2)] px-3 py-2">
              <Check size={14} className="text-[var(--green-11)]" />
              <Text size="2" className="text-[var(--green-11)]">
                {success}
              </Text>
            </div>
          ) : (
            <>
              <div className="flex flex-col gap-1">
                <label className="text-[12px] font-medium text-[var(--gray-11)]">
                  Search by address, city, owner, or property ID
                </label>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. 3050 Wonderland Road"
                  className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
                  autoFocus
                />
              </div>

              {searching && (
                <div className="flex items-center justify-center py-4">
                  <Spinner size="2" />
                </div>
              )}

              {!searching && results.length > 0 && (
                <div className="flex flex-col rounded-[var(--radius-2)] border border-[var(--gray-6)]">
                  {results.map((p) => (
                    <button
                      key={p.property_id}
                      onClick={() => handleLink(p)}
                      disabled={saving}
                      className="flex items-center justify-between border-b border-[var(--gray-4)] px-3 py-2 text-left last:border-0 hover:bg-[var(--gray-2)] disabled:opacity-50"
                    >
                      <div>
                        <Text size="2" weight="medium" className="block">
                          {formatStreet(p.primary_address)}
                        </Text>
                        <Text size="1" color="gray" className="block">
                          {titleCase(p.city)} &middot; {p.property_id}
                          {p.current_owner
                            ? ` \u2014 ${p.current_owner}`
                            : ""}
                        </Text>
                      </div>
                      <Plus
                        size={14}
                        className="shrink-0 text-[var(--gray-9)]"
                      />
                    </button>
                  ))}
                </div>
              )}

              {!searching && query.trim().length >= 2 && results.length === 0 && (
                <Text size="2" color="gray" className="text-center py-4">
                  No properties found matching "{query}"
                </Text>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Shared sub-components                                                */
/* ------------------------------------------------------------------ */

function StatBox({
  label,
  value,
  raw,
}: {
  label: string;
  value: string | number;
  raw?: boolean;
}) {
  return (
    <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5">
      <div className="text-[28px] font-medium leading-[36px] tracking-[-0.4px] text-[var(--gray-12)]">
        {raw ? value : typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div className="mt-1 text-[12px] font-medium text-[var(--gray-11)]">
        {label}
      </div>
    </div>
  );
}

function Card({
  title,
  icon,
  children,
  full,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
  full?: boolean;
}) {
  return (
    <div
      className={`rounded-[var(--card-radius)] border border-[var(--gray-6)] ${full ? "" : ""}`}
    >
      <div className="flex items-center gap-2 border-b border-[var(--gray-4)] px-5 py-3">
        {icon && <span className="text-[var(--gray-9)]">{icon}</span>}
        <Text size="2" weight="medium">
          {title}
        </Text>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`pb-3 text-[14px] font-medium transition-colors ${
        active
          ? "border-b-2 border-[var(--accent-9)] text-[var(--gray-12)]"
          : "text-[var(--gray-9)] hover:text-[var(--gray-11)]"
      }`}
    >
      {label}
    </button>
  );
}
