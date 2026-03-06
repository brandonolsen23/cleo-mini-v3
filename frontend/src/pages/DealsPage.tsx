import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Text, Badge, Spinner } from "@radix-ui/themes";
import { Plus, X } from "@phosphor-icons/react";
import { PageHeader } from "@/components/ui/PageHeader";
import { fetchApi, mutateApi } from "@/api/client";
import { formatCurrency } from "@/lib/utils";

interface Deal {
  deal_id: string;
  name: string;
  stage: string;
  arn: string;
  property_id: string;
  group_id: string;
  contact_ids: string[];
  amount: number | null;
  close_date: string | null;
  deal_owner: string;
  description: string;
  next_step: string;
  priority: string;
  lost_reason: string;
  created_at: string;
  updated_at: string;
}

interface PipelineResponse {
  stages: string[];
  stage_labels: Record<string, string>;
  stage_phases: Record<string, string>;
  pipeline: Record<string, Deal[]>;
}

interface DealStats {
  total: number;
  active: number;
  by_stage: Record<string, number>;
  pipeline_value: number;
}

const STAGE_COLORS: Record<string, string> = {
  long_shot: "gray",
  priority_deal: "blue",
  mandate: "blue",
  viable_deal: "amber",
  in_negotiation: "amber",
  under_contract: "orange",
  firm: "jade",
  closed: "jade",
  lost: "red",
};

export function DealsPage() {
  const navigate = useNavigate();
  const [pipeline, setPipeline] = useState<PipelineResponse | null>(null);
  const [stats, setStats] = useState<DealStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([
      fetchApi<PipelineResponse>("/crm/deals/pipeline"),
      fetchApi<DealStats>("/crm/deals/stats"),
    ])
      .then(([p, s]) => {
        setPipeline(p);
        setStats(s);
      })
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  if (loading || !pipeline || !stats) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="3" />
      </div>
    );
  }

  // Active stages (exclude closed/lost from main board)
  const activeStages = pipeline.stages.filter(
    (s) => s !== "closed" && s !== "lost"
  );
  const closedDeals = [
    ...(pipeline.pipeline.closed || []),
    ...(pipeline.pipeline.lost || []),
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <PageHeader
          title="Deals"
          description={
            stats.active > 0
              ? `${stats.active} active deal${stats.active !== 1 ? "s" : ""}${stats.pipeline_value ? ` \u2014 ${formatCurrency(stats.pipeline_value)} pipeline` : ""}`
              : "Track your deals through the pipeline."
          }
        />
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-3 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] transition-colors"
        >
          <Plus size={14} weight="bold" />
          New Deal
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-4 gap-4">
        <StatBox label="Active Deals" value={stats.active} />
        <StatBox
          label="Pipeline Value"
          value={stats.pipeline_value ? formatCurrency(stats.pipeline_value) : "\u2014"}
          raw
        />
        <StatBox label="Closed" value={stats.by_stage.closed || 0} />
        <StatBox label="Lost" value={stats.by_stage.lost || 0} />
      </div>

      {/* Pipeline board */}
      <div className="flex gap-3 overflow-x-auto pb-2">
        {activeStages.map((stage) => {
          const deals = pipeline.pipeline[stage] || [];
          return (
            <div
              key={stage}
              className="flex w-[220px] shrink-0 flex-col rounded-[var(--card-radius)] border border-[var(--gray-6)]"
            >
              <div className="flex items-center justify-between border-b border-[var(--gray-4)] px-3 py-2.5">
                <Text size="2" weight="medium">
                  {pipeline.stage_labels[stage]}
                </Text>
                <Badge size="1" color="gray" variant="soft">
                  {deals.length}
                </Badge>
              </div>
              <div className="flex flex-col gap-2 p-2 min-h-[80px]">
                {deals.length === 0 ? (
                  <Text size="1" color="gray" className="p-2 text-center">
                    No deals
                  </Text>
                ) : (
                  deals.map((d) => (
                    <DealCard
                      key={d.deal_id}
                      deal={d}
                      stageLabels={pipeline.stage_labels}
                      onClick={() => navigate(`/deals/${d.deal_id}`)}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Closed/Lost section */}
      {closedDeals.length > 0 && (
        <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)]">
          <div className="flex items-center gap-2 border-b border-[var(--gray-4)] px-5 py-3">
            <Text size="2" weight="medium">
              Closed / Lost ({closedDeals.length})
            </Text>
          </div>
          <div className="p-5">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--gray-4)] text-left text-[var(--gray-9)]">
                  <th className="pb-2 font-medium">Deal</th>
                  <th className="pb-2 font-medium">Stage</th>
                  <th className="pb-2 font-medium">Owner</th>
                  <th className="pb-2 font-medium text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {closedDeals.map((d) => (
                  <tr
                    key={d.deal_id}
                    className="border-b border-[var(--gray-4)] last:border-0 cursor-pointer hover:bg-[var(--gray-2)]"
                    onClick={() => navigate(`/deals/${d.deal_id}`)}
                  >
                    <td className="py-2 pr-4 text-[var(--gray-12)]">{d.name}</td>
                    <td className="py-2 pr-4">
                      <Badge
                        size="1"
                        color={d.stage === "closed" ? "jade" : "red"}
                        variant="soft"
                      >
                        {pipeline.stage_labels[d.stage]}
                      </Badge>
                    </td>
                    <td className="py-2 pr-4 text-[var(--gray-11)]">
                      {d.deal_owner}
                    </td>
                    <td className="py-2 text-right text-[var(--gray-11)]">
                      {d.amount ? formatCurrency(d.amount) : "\u2014"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <CreateDealModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            load();
          }}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                       */
/* ------------------------------------------------------------------ */

function DealCard({
  deal,
  onClick,
}: {
  deal: Deal;
  stageLabels?: Record<string, string>;
  onClick: () => void;
}) {
  const color = STAGE_COLORS[deal.stage] || "gray";
  return (
    <button
      onClick={onClick}
      className="w-full rounded-[var(--radius-2)] border border-[var(--gray-5)] bg-white p-2.5 text-left hover:border-[var(--gray-7)] transition-colors"
    >
      <Text size="2" weight="medium" className="block truncate">
        {deal.name}
      </Text>
      <div className="mt-1.5 flex items-center justify-between">
        {deal.amount ? (
          <Text size="1" color="gray">
            {formatCurrency(deal.amount)}
          </Text>
        ) : (
          <span />
        )}
        <Badge size="1" color={color as any} variant="soft">
          {deal.deal_owner}
        </Badge>
      </div>
      {deal.next_step && (
        <Text size="1" color="gray" className="mt-1 block truncate">
          Next: {deal.next_step}
        </Text>
      )}
    </button>
  );
}

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

function CreateDealModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [stage, setStage] = useState("long_shot");
  const [owner, setOwner] = useState("brandon");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [propertyId, setPropertyId] = useState("");
  const [groupId, setGroupId] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await mutateApi("/crm/deals", "POST", {
        name: name.trim(),
        stage,
        deal_owner: owner,
        amount: amount ? Number(amount) : null,
        description: description.trim(),
        property_id: propertyId.trim() || undefined,
        group_id: groupId.trim() || undefined,
      });
      onCreated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-[480px] rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white shadow-lg">
        <div className="flex items-center justify-between border-b border-[var(--gray-4)] px-5 py-3">
          <Text size="3" weight="medium">New Deal</Text>
          <button onClick={onClose} className="text-[var(--gray-9)] hover:text-[var(--gray-11)]">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          <Field label="Deal Name" required>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. 123 Main St London — Goldmanco"
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
              autoFocus
            />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Stage">
              <select
                value={stage}
                onChange={(e) => setStage(e.target.value)}
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-2 text-[13px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none"
              >
                <option value="long_shot">Long Shot</option>
                <option value="priority_deal">Priority Deal</option>
                <option value="mandate">Mandate</option>
                <option value="viable_deal">Viable Deal</option>
                <option value="in_negotiation">In Negotiation</option>
                <option value="under_contract">Under Contract</option>
                <option value="firm">Firm</option>
              </select>
            </Field>
            <Field label="Owner">
              <select
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-2 text-[13px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none"
              >
                <option value="brandon">Brandon</option>
                <option value="jamie">Jamie</option>
              </select>
            </Field>
          </div>
          <Field label="Amount">
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Expected deal value"
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
            />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Property ID">
              <input
                type="text"
                value={propertyId}
                onChange={(e) => setPropertyId(e.target.value)}
                placeholder="PRO_00001"
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
              />
            </Field>
            <Field label="Group ID">
              <input
                type="text"
                value={groupId}
                onChange={(e) => setGroupId(e.target.value)}
                placeholder="GRP_00001"
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
              />
            </Field>
          </div>
          <Field label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Notes, context, next steps..."
              rows={3}
              className="w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 py-2 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none resize-none"
            />
          </Field>
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
              {saving ? "Creating..." : "Create Deal"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[12px] font-medium text-[var(--gray-11)]">
        {label}
        {required && <span className="text-[var(--red-9)]"> *</span>}
      </label>
      {children}
    </div>
  );
}
