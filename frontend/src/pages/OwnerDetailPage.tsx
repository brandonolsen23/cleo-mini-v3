import { useState, useEffect, useMemo, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { Text, Badge, Heading, Separator, Spinner } from "@radix-ui/themes";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  ArrowLeft,
  Phone,
  MapPin,
  ArrowSquareOut,
  Copy,
  Check,
  LinkSimple,
  TrendUp,
  TrendDown,
  ChartBar,
  PencilSimple,
  X,
  User,
  LinkedinLogo,
} from "@phosphor-icons/react";
import { cn, formatDate, formatStreet, titleCase } from "@/lib/utils";
import { fetchApi, mutateApi } from "@/api/client";
import { FlagIssueMenu } from "@/components/ui/FlagIssueMenu";
import type { EntityDetail, EntityTxn } from "@/types";

/** Compact currency: $1.25B, $73.8M, $450K, $5,100 */
function fmtMoney(n: number): string {
  if (!n) return "\u2014";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (abs >= 1_000_000_000) return `${sign}$${(abs / 1_000_000_000).toFixed(2)}B`;
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(0)}K`;
  return `${sign}$${abs.toLocaleString()}`;
}

export function EntityDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [owner, setOwner] = useState<EntityDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [saving, setSaving] = useState(false);

  // Link modal state
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkDisplayName, setLinkDisplayName] = useState("");
  const [linkReason, setLinkReason] = useState("");
  const [linking, setLinking] = useState(false);
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

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    fetchApi<EntityDetail>(`/owners/${id}`)
      .then(setOwner)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Build activity chart data (must be before early returns — Rules of Hooks)
  const chartData = useMemo(() => {
    if (!owner) return [];
    const byYear: Record<string, { year: string; buy: number; sell: number; buyCount: number; sellCount: number }> = {};

    for (const t of owner.buy_transactions) {
      const year = t.sale_date?.slice(0, 4);
      if (!year) continue;
      if (!byYear[year]) byYear[year] = { year, buy: 0, sell: 0, buyCount: 0, sellCount: 0 };
      byYear[year].buy += t.sale_price || 0;
      byYear[year].buyCount++;
    }

    for (const t of owner.seller_transactions) {
      const year = t.sale_date?.slice(0, 4);
      if (!year) continue;
      if (!byYear[year]) byYear[year] = { year, buy: 0, sell: 0, buyCount: 0, sellCount: 0 };
      byYear[year].sell -= (t.sale_price || 0);
      byYear[year].sellCount++;
    }

    return Object.values(byYear).sort((a, b) => a.year.localeCompare(b.year));
  }, [owner]);

  // Build combined transaction timeline (must be before early returns — Rules of Hooks)
  const timeline = useMemo(() => {
    if (!owner) return [];
    const entries: TimelineEntry[] = [];
    for (const t of owner.buy_transactions) {
      entries.push({ ...t, type: "buy" });
    }
    for (const t of owner.seller_transactions) {
      entries.push({ ...t, type: "sell" });
    }
    entries.sort((a, b) => (b.sale_date || "").localeCompare(a.sale_date || ""));
    return entries;
  }, [owner]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="3" />
      </div>
    );
  }

  if (error || !owner) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Text size="3" color="gray">
          {error || "Entity not found"}
        </Text>
        <button
          onClick={() => navigate(-1)}
          className="mt-4 text-[13px] font-medium text-[var(--accent-11)] hover:underline"
        >
          Back to Entities
        </button>
      </div>
    );
  }

  const displayName = owner.display_name || owner.name;
  const showChart = chartData.length >= 2;

  const handleSaveName = async () => {
    if (!editName.trim() || !owner) return;
    setSaving(true);
    try {
      await mutateApi(`/owners/${owner.id}/name`, "PUT", {
        display_name: editName.trim(),
      });
      const updated = await fetchApi<EntityDetail>(`/owners/${owner.id}`);
      setOwner(updated);
      setEditing(false);
    } catch (e) {
      console.error("Rename failed:", e);
    } finally {
      setSaving(false);
    }
  };

  const handleLink = async () => {
    if (!owner || !targetGroup) return;
    setLinking(true);
    const names = [...owner.all_names];
    // Include an anchor from the target group so backend merges into it
    if (targetGroup.members.length > 0) {
      const anchor = targetGroup.members[0];
      if (!names.includes(anchor)) names.push(anchor);
    }
    try {
      const resp = await mutateApi<{ ok: boolean; link: { id: string } }>("/owners/link", "POST", {
        names,
        display_name: linkDisplayName || undefined,
        reason: linkReason || "Linked from detail page",
      });
      setLinkModalOpen(false);
      setLinkDisplayName("");
      setLinkReason("");
      setTargetGroup(null);
      // Navigate to the merged entity (ID changes after linking)
      navigate(`/app/owners/${resp.link.id}`, { replace: true });
    } catch (e: any) {
      alert(`Link failed: ${e?.message || e}`);
    } finally {
      setLinking(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Back link */}
      <button
        onClick={() => navigate(-1)}
        className="inline-flex items-center gap-1.5 self-start rounded-[var(--radius-2)] px-2.5 py-1.5 text-[13px] font-medium text-[var(--accent-11)] hover:bg-[var(--accent-a3)]"
      >
        <ArrowLeft size={14} />
        Entities
      </button>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          {editing ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                autoFocus
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveName();
                  if (e.key === "Escape") setEditing(false);
                }}
                className="h-9 w-[320px] rounded-[var(--radius-2)] border border-[var(--accent-8)] bg-white px-3 text-[20px] font-medium text-[var(--gray-12)] focus:outline-none"
              />
              <button
                onClick={handleSaveName}
                disabled={saving || !editName.trim()}
                className="rounded-[var(--radius-2)] bg-[var(--accent-9)] px-3 py-1.5 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] disabled:opacity-50"
              >
                {saving ? "Saving..." : "Save"}
              </button>
              <button
                onClick={() => setEditing(false)}
                className="rounded-[var(--radius-2)] px-3 py-1.5 text-[13px] font-medium text-[var(--gray-11)] hover:bg-[var(--gray-3)]"
              >
                Cancel
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <Heading size="6" weight="medium">
                {displayName}
              </Heading>
              <button
                onClick={() => {
                  setEditName(displayName);
                  setEditing(true);
                }}
                className="shrink-0 rounded-[var(--radius-2)] p-1.5 text-[var(--gray-9)] hover:bg-[var(--gray-3)] hover:text-[var(--gray-11)]"
                title="Edit display name"
              >
                <PencilSimple size={15} />
              </button>
            </div>
          )}
          <div className="mt-1 flex items-center gap-2">
            <Text size="2" color="gray">
              {owner.property_count} owned
            </Text>
            <Text size="2" color="gray">|</Text>
            <Text size="2" color="gray">
              {owner.buy_count} {owner.buy_count === 1 ? "buy" : "buys"}
            </Text>
            {owner.sell_count > 0 && (
              <>
                <Text size="2" color="gray">|</Text>
                <Text size="2" color="gray">
                  {owner.sell_count} {owner.sell_count === 1 ? "sale" : "sales"}
                </Text>
              </>
            )}
            {owner.total_value > 0 && (
              <>
                <Text size="2" color="gray">|</Text>
                <Text size="2" color="gray">
                  {fmtMoney(owner.total_value)} bought
                </Text>
              </>
            )}
            {owner.total_sell_value > 0 && (
              <>
                <Text size="2" color="gray">|</Text>
                <Text size="2" color="gray">
                  {fmtMoney(owner.total_sell_value)} sold
                </Text>
              </>
            )}
            {owner.earliest_date && owner.latest_date && (
              <>
                <Text size="2" color="gray">|</Text>
                <Text size="2" color="gray">
                  {formatDate(owner.earliest_date)} &ndash; {formatDate(owner.latest_date)}
                </Text>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {owner.link_id && (
            <Badge size="2" variant="soft" color="jade">
              <LinkSimple size={12} className="mr-1" />
              Linked
            </Badge>
          )}
          <button
            onClick={() => setLinkModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-2)] bg-[var(--accent-9)] px-3 py-1.5 text-[13px] font-medium text-white hover:bg-[var(--accent-10)]"
          >
            <LinkSimple size={14} />
            Link
          </button>
          <FlagIssueMenu
            sourceId={owner.id}
            fields={["entity_name", "entity_grouping", "missing_transactions", "duplicate_entity", "wrong_link"]}
            page="entity_detail"
            context={displayName}
          />
        </div>
      </div>

      <Separator size="4" />

      {/* Activity Chart */}
      {showChart && (
        <Card
          title="Activity"
          icon={<ChartBar size={16} />}
        >
          <div className="flex items-center gap-4 mb-3">
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "var(--teal-9)" }} />
              <Text size="1" color="gray">Buys</Text>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "var(--red-9)" }} />
              <Text size="1" color="gray">Sells</Text>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} barCategoryGap="20%">
              <CartesianGrid
                strokeDasharray="none"
                vertical={false}
                stroke="var(--gray-4)"
              />
              <XAxis
                dataKey="year"
                tick={{ fontSize: 12, fill: "var(--gray-9)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--gray-4)" }}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "var(--gray-9)" }}
                tickLine={false}
                axisLine={false}
                tickFormatter={formatChartAxis}
              />
              <ReferenceLine y={0} stroke="var(--gray-6)" />
              <RechartsTooltip content={<ActivityTooltip />} />
              <Bar dataKey="buy" fill="var(--teal-9)" radius={[3, 3, 0, 0]} />
              <Bar dataKey="sell" fill="var(--red-9)" radius={[0, 0, 3, 3]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Transaction Cards */}
      {timeline.length > 0 && (
        <div className="flex flex-col gap-4">
          <Text size="2" weight="medium" className="text-[var(--gray-12)]">
            Transactions ({timeline.length})
          </Text>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {timeline.map((entry, i) => (
              <TransactionCard key={`${entry.rt_id}-${entry.type}-${i}`} entry={entry} />
            ))}
          </div>
        </div>
      )}

      {/* Bottom section: Link group + External links side by side */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Link Group Management */}
        {owner.link_id && owner.normalized_names.length > 1 && (
          <Card title="Link Group" icon={<LinkSimple size={16} />}>
            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between mb-2">
                <Text size="1" color="gray">{owner.link_id}</Text>
                <Text size="1" color="gray">{owner.normalized_names.length} members</Text>
              </div>
              {owner.normalized_names.map((norm) => (
                <div key={norm} className="flex items-center justify-between gap-2 rounded py-0.5 -mx-1 px-1 hover:bg-[var(--gray-2)]">
                  <Text size="2" className="block">
                    {norm}
                  </Text>
                  <button
                    onClick={async () => {
                      if (!confirm(`Remove "${norm}" from this group?`)) return;
                      try {
                        await mutateApi("/owners/unlink", "POST", {
                          name: norm,
                          link_id: owner.link_id,
                          reason: "Removed via detail page",
                        });
                        const updated = await fetchApi<EntityDetail>(`/owners/${owner.id}`);
                        setOwner(updated);
                      } catch (e: any) {
                        alert(`Unlink failed: ${e?.message || e}`);
                      }
                    }}
                    className="shrink-0 rounded p-0.5 text-[var(--gray-8)] hover:bg-[var(--red-a3)] hover:text-[var(--red-11)]"
                    title={`Remove ${norm} from group`}
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* External Links */}
        <Card title="External Links" icon={<ArrowSquareOut size={16} />}>
          <div className="flex flex-col gap-2">
            <ExternalLink
              label="Google Search"
              href={`https://www.google.com/search?q=${encodeURIComponent(displayName + " Ontario commercial real estate")}`}
            />
            {owner.corp_addresses.length > 0 && (
              <ExternalLink
                label="Canada411 (Address)"
                href={`https://www.canada411.ca/search/?stype=re&what=${encodeURIComponent(owner.corp_addresses[0].canonical.split(",")[0])}`}
              />
            )}
          </div>
        </Card>
      </div>

      {/* Link modal */}
      {linkModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="w-[420px] rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white p-5 shadow-[var(--elevation-4)]">
            <Text size="3" weight="medium" className="mb-4 block">
              Link {displayName}
            </Text>
            <div className="flex flex-col gap-3">
              <div ref={suggestRef} className="relative">
                <label className="mb-1 block text-[12px] font-medium text-[var(--gray-11)]">
                  Add to existing group or enter new group name
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
                  placeholder="e.g. First Capital REIT"
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
                  placeholder="Why should this entity be linked?"
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
                  disabled={linking || !targetGroup}
                  className="rounded-[var(--radius-2)] bg-[var(--accent-9)] px-3 py-1.5 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] disabled:opacity-50"
                >
                  {linking ? "Linking..." : "Add to Group"}
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
/* Types                                                               */
/* ------------------------------------------------------------------ */

type TimelineEntry = EntityTxn & { type: "buy" | "sell" };

/* ------------------------------------------------------------------ */
/* Transaction Card                                                    */
/* ------------------------------------------------------------------ */

function TransactionCard({ entry }: { entry: TimelineEntry }) {
  const isBuy = entry.type === "buy";
  const altNames = entry.alternate_names || [];
  const hasCorpAddr = entry.corp_address?.canonical;

  return (
    <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--gray-4)] px-5 py-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="shrink-0">
            {isBuy ? (
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--teal-a3)]">
                <TrendUp size={12} className="text-[var(--teal-11)]" />
              </div>
            ) : (
              <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--red-a3)]">
                <TrendDown size={12} className="text-[var(--red-11)]" />
              </div>
            )}
          </div>
          <Badge size="1" variant="soft" color={isBuy ? "teal" : "red"}>
            {isBuy ? "Buy" : "Sell"}
          </Badge>
          {isBuy && entry.is_owned && (
            <Badge size="1" variant="soft" color="indigo">
              Owned
            </Badge>
          )}
          <Link
            to={`/properties/${entry.property_id}`}
            className="truncate text-[14px] font-medium text-[var(--gray-12)] hover:text-[var(--accent-11)] hover:underline"
          >
            {formatStreet(entry.address)}
          </Link>
          <Text size="2" color="gray" className="shrink-0">
            {titleCase(entry.city)}
          </Text>
        </div>
        <div className="ml-3 flex items-center gap-2 shrink-0">
          {entry.sale_price ? (
            <Text size="2" weight="medium">{fmtMoney(entry.sale_price)}</Text>
          ) : (
            <Text size="2" color="gray">{"\u2014"}</Text>
          )}
          {entry.sale_date && (
            <>
              <Text size="1" color="gray">&middot;</Text>
              <Text size="2" color="gray" className="whitespace-nowrap">
                {formatDate(entry.sale_date)}
              </Text>
            </>
          )}
          <FlagIssueMenu
            sourceId={entry.rt_id}
            fields={
              isBuy
                ? ["buyer_company_name", "buyer_contact_name", "buyer_phone", "buyer_corp_address", "sale_price", "sale_date"]
                : ["seller_company_name", "seller_contact_name", "seller_phone", "seller_corp_address", "sale_price", "sale_date"]
            }
            page="entity_detail"
            context={entry.entity_name || ""}
          />
        </div>
      </div>

      {/* Detail rows */}
      <div className="px-5 py-3">
        <div className="grid grid-cols-[140px_1fr] gap-y-1.5 gap-x-4">
          {/* Primary Name */}
          <Text size="1" color="gray" className="text-right">Primary Name</Text>
          <Text size="2">{entry.entity_name || "\u2014"}</Text>

          {/* Contact */}
          {entry.contact && (
            <>
              <Text size="1" color="gray" className="text-right">Contact</Text>
              <div className="flex items-center gap-2">
                <User size={12} className="shrink-0 text-[var(--gray-9)]" />
                <Text size="2">{entry.contact}</Text>
                {entry.attention && entry.attention !== entry.contact && (
                  <Text size="1" color="gray">({entry.attention})</Text>
                )}
                <a
                  href={`https://www.linkedin.com/search/results/all/?keywords=${encodeURIComponent(entry.contact + (entry.corp_address?.city ? " " + entry.corp_address.city : ""))}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  title={`Search LinkedIn for ${entry.contact}`}
                  className="shrink-0 text-[var(--gray-8)] hover:text-[#0A66C2]"
                >
                  <LinkedinLogo size={14} weight="bold" />
                </a>
              </div>
            </>
          )}

          {/* Phone */}
          {entry.phone && (
            <>
              <Text size="1" color="gray" className="text-right">Phone</Text>
              <div className="flex items-center gap-2">
                <Phone size={12} className="shrink-0 text-[var(--gray-9)]" />
                <CopyableText value={entry.phone} />
                {(entry.phones || []).filter(p => p && p !== entry.phone).map(p => (
                  <CopyableText key={p} value={p} />
                ))}
              </div>
            </>
          )}

          {/* Corp Address */}
          {hasCorpAddr && (
            <>
              <Text size="1" color="gray" className="text-right">Corp Address</Text>
              <div className="flex items-center gap-2">
                <MapPin size={12} className="shrink-0 text-[var(--gray-9)]" />
                <a
                  href={`https://www.google.com/search?q=${encodeURIComponent(entry.corp_address!.canonical)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[14px] text-[var(--gray-12)] hover:text-[var(--accent-11)] hover:underline"
                >
                  {entry.corp_address!.canonical}
                </a>
              </div>
            </>
          )}

          {/* Alternate Names */}
          {altNames.length > 0 && (
            <>
              <Text size="1" color="gray" className="text-right">Alternate Names</Text>
              <div className="flex flex-col gap-0.5">
                {altNames.map((name, i) => (
                  <Text key={i} size="2" className="text-[var(--gray-11)]">{name}</Text>
                ))}
              </div>
            </>
          )}

          {/* RT ID */}
          <Text size="1" color="gray" className="text-right">RT ID</Text>
          <Text size="1" color="gray">{entry.rt_id}</Text>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Card wrapper                                                        */
/* ------------------------------------------------------------------ */

function Card({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5">
      <div className="mb-3 flex items-center gap-2 text-[var(--gray-11)]">
        {icon}
        <Text size="2" weight="medium" className="text-[var(--gray-12)]">
          {title}
        </Text>
      </div>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Copyable text                                                       */
/* ------------------------------------------------------------------ */

function CopyableText({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <span className="inline-flex items-center gap-1">
      <Text size="2">{value}</Text>
      <button
        onClick={handleCopy}
        className="shrink-0 text-[var(--gray-9)] hover:text-[var(--gray-11)]"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
      </button>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Activity chart helpers                                              */
/* ------------------------------------------------------------------ */

function formatChartAxis(v: number): string {
  if (v === 0) return "$0";
  return fmtMoney(v);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function ActivityTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  const buyEntry = payload.find((p: any) => p.dataKey === "buy");
  const sellEntry = payload.find((p: any) => p.dataKey === "sell");
  const buyVal = buyEntry?.payload?.buy || 0;
  const sellVal = Math.abs(sellEntry?.payload?.sell || 0);
  const buyCount = buyEntry?.payload?.buyCount || 0;
  const sellCount = sellEntry?.payload?.sellCount || 0;

  return (
    <div className="rounded-[var(--radius-3)] border border-[var(--gray-6)] bg-white px-3 py-2 shadow-[var(--elevation-2)]">
      <Text size="1" weight="medium" className="mb-1 block">
        {label}
      </Text>
      {buyCount > 0 && (
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: "var(--teal-9)" }} />
          <Text size="1" color="gray">
            {buyCount} {buyCount === 1 ? "buy" : "buys"}: {fmtMoney(buyVal)}
          </Text>
        </div>
      )}
      {sellCount > 0 && (
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: "var(--red-9)" }} />
          <Text size="1" color="gray">
            {sellCount} {sellCount === 1 ? "sale" : "sales"}: {fmtMoney(sellVal)}
          </Text>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* External link                                                       */
/* ------------------------------------------------------------------ */

function ExternalLink({ label, href }: { label: string; href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 text-[14px] text-[var(--accent-11)] hover:underline"
    >
      <ArrowSquareOut size={13} />
      {label}
    </a>
  );
}
