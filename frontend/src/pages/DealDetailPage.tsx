import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Text, Badge, Spinner } from "@radix-ui/themes";
import { ArrowLeft, Pencil, Trash } from "@phosphor-icons/react";
import { fetchApi, mutateApi } from "@/api/client";
import { formatCurrency, formatDate } from "@/lib/utils";

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

interface DealMeta {
  stages: string[];
  stage_labels: Record<string, string>;
  stage_phases: Record<string, string>;
}

interface Connection {
  connection_id: string;
  contact_id: string;
  contact_name: string;
  group_id: string;
  group_name: string;
  deal_id: string;
  type: string;
  direction: string;
  outcome: string;
  notes: string;
  logged_by: string;
  logged_at: string;
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

const PRIORITY_COLORS: Record<string, string> = {
  low: "gray",
  medium: "blue",
  high: "orange",
  urgent: "red",
};

export function DealDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [deal, setDeal] = useState<Deal | null>(null);
  const [meta, setMeta] = useState<DealMeta | null>(null);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      fetchApi<Deal>(`/crm/deals/${id}`),
      fetchApi<DealMeta>("/crm/deals/meta"),
      fetchApi<{ connections: Connection[] }>("/crm/connections", { deal_id: id }),
    ])
      .then(([d, m, c]) => {
        setDeal(d);
        setMeta(m);
        setConnections(c.connections);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="3" />
      </div>
    );
  }

  if (error || !deal || !meta) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Text size="3" color="gray">{error || "Deal not found"}</Text>
        <button
          onClick={() => navigate("/deals")}
          className="mt-4 text-[13px] font-medium text-[var(--accent-11)] hover:underline"
        >
          Back to Deals
        </button>
      </div>
    );
  }

  const handleStageChange = async (newStage: string) => {
    const res = await mutateApi<{ deal: Deal }>(`/crm/deals/${deal.deal_id}`, "PUT", {
      stage: newStage,
    });
    setDeal(res.deal);
  };

  const handleDelete = async () => {
    if (!confirm("Delete this deal?")) return;
    await mutateApi(`/crm/deals/${deal.deal_id}`, "DELETE");
    navigate("/deals");
  };

  const stageColor = STAGE_COLORS[deal.stage] || "gray";
  const priorityColor = PRIORITY_COLORS[deal.priority] || "gray";

  return (
    <div className="flex flex-col gap-6">
      {/* Back + header */}
      <div>
        <button
          onClick={() => navigate("/deals")}
          className="mb-3 inline-flex items-center gap-1 text-[13px] font-medium text-[var(--gray-11)] hover:text-[var(--gray-12)]"
        >
          <ArrowLeft size={14} />
          Deals
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-[24px] font-medium leading-[32px] text-[var(--gray-12)]">
              {deal.name}
            </h2>
            <div className="mt-1 flex items-center gap-2">
              <Text size="2" color="gray">{deal.deal_id}</Text>
              <Badge size="1" color={stageColor as any} variant="soft">
                {meta.stage_labels[deal.stage]}
              </Badge>
              <Badge size="1" color={priorityColor as any} variant="soft">
                {deal.priority}
              </Badge>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setEditing(true)}
              className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--gray-7)] px-3 text-[13px] font-medium text-[var(--gray-11)] hover:bg-[var(--gray-2)]"
            >
              <Pencil size={13} />
              Edit
            </button>
            <button
              onClick={handleDelete}
              className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--red-6)] px-3 text-[13px] font-medium text-[var(--red-11)] hover:bg-[var(--red-2)]"
            >
              <Trash size={13} />
            </button>
          </div>
        </div>
      </div>

      {/* Stage progression */}
      <div className="flex items-center gap-1">
        {meta.stages
          .filter((s) => s !== "lost")
          .map((s) => {
            const isCurrent = s === deal.stage;
            const idx = meta.stages.indexOf(s);
            const currentIdx = meta.stages.indexOf(deal.stage);
            const isPast = idx < currentIdx && deal.stage !== "lost";
            return (
              <button
                key={s}
                onClick={() => handleStageChange(s)}
                className={`h-8 flex-1 rounded-[var(--radius-2)] border text-[12px] font-medium transition-colors ${
                  isCurrent
                    ? "border-[var(--accent-7)] bg-[var(--accent-9)] text-white"
                    : isPast
                      ? "border-[var(--accent-6)] bg-[var(--accent-a2)] text-[var(--accent-11)]"
                      : "border-[var(--gray-5)] text-[var(--gray-9)] hover:bg-[var(--gray-2)]"
                }`}
              >
                {meta.stage_labels[s]}
              </button>
            );
          })}
        <button
          onClick={() => handleStageChange("lost")}
          className={`h-8 w-[80px] rounded-[var(--radius-2)] border text-[12px] font-medium transition-colors ${
            deal.stage === "lost"
              ? "border-[var(--red-7)] bg-[var(--red-9)] text-white"
              : "border-[var(--gray-5)] text-[var(--gray-9)] hover:bg-[var(--red-2)] hover:text-[var(--red-11)]"
          }`}
        >
          Lost
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Details card */}
        <Card title="Details">
          <div className="flex flex-col gap-2">
            <DetailRow label="Owner" value={deal.deal_owner} />
            <DetailRow
              label="Amount"
              value={deal.amount ? formatCurrency(deal.amount) : "\u2014"}
            />
            <DetailRow
              label="Close Date"
              value={deal.close_date ? formatDate(deal.close_date) : "\u2014"}
            />
            <DetailRow label="Phase" value={meta.stage_phases[deal.stage]} />
            <DetailRow label="Created" value={formatDate(deal.created_at.split("T")[0])} />
            <DetailRow label="Updated" value={formatDate(deal.updated_at.split("T")[0])} />
          </div>
        </Card>

        {/* References card */}
        <Card title="References">
          <div className="flex flex-col gap-2">
            {deal.property_id && (
              <DetailRow label="Property">
                <button
                  onClick={() => navigate(`/properties/${deal.property_id}`)}
                  className="text-[var(--accent-11)] hover:underline text-[14px]"
                >
                  {deal.property_id}
                </button>
              </DetailRow>
            )}
            {deal.group_id && (
              <DetailRow label="Group">
                <button
                  onClick={() => navigate(`/groups/${deal.group_id}`)}
                  className="text-[var(--accent-11)] hover:underline text-[14px]"
                >
                  {deal.group_id}
                </button>
              </DetailRow>
            )}
            {deal.arn && <DetailRow label="ARN" value={deal.arn} />}
            {deal.contact_ids.length > 0 && (
              <DetailRow label="Contacts">
                <div className="flex flex-wrap gap-1">
                  {deal.contact_ids.map((c) => (
                    <button
                      key={c}
                      onClick={() => navigate(`/contacts/${c}`)}
                      className="text-[var(--accent-11)] hover:underline text-[14px]"
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </DetailRow>
            )}
            {!deal.property_id && !deal.group_id && !deal.arn && deal.contact_ids.length === 0 && (
              <Text size="2" color="gray">No references linked yet.</Text>
            )}
          </div>
        </Card>
      </div>

      {/* Description / Next step */}
      {(deal.description || deal.next_step) && (
        <div className="grid grid-cols-2 gap-4">
          {deal.description && (
            <Card title="Description">
              <Text size="2" className="block whitespace-pre-wrap">
                {deal.description}
              </Text>
            </Card>
          )}
          {deal.next_step && (
            <Card title="Next Step">
              <Text size="2" className="block">
                {deal.next_step}
              </Text>
            </Card>
          )}
        </div>
      )}

      {deal.lost_reason && deal.stage === "lost" && (
        <Card title="Lost Reason">
          <Text size="2" className="block">
            {deal.lost_reason}
          </Text>
        </Card>
      )}

      {/* Connections */}
      <Card title={`Connections (${connections.length})`}>
        {connections.length === 0 ? (
          <Text size="2" color="gray">No connections logged for this deal.</Text>
        ) : (
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--gray-4)] text-left text-[var(--gray-9)]">
                <th className="pb-2 font-medium">Type</th>
                <th className="pb-2 font-medium">Contact</th>
                <th className="pb-2 font-medium">Outcome</th>
                <th className="pb-2 font-medium">Notes</th>
                <th className="pb-2 font-medium text-right">Date</th>
              </tr>
            </thead>
            <tbody>
              {connections.map((c) => (
                <tr key={c.connection_id} className="border-b border-[var(--gray-4)] last:border-0">
                  <td className="py-2 pr-4">
                    <Badge size="1" color="gray" variant="soft">
                      {c.type.replace("_", " ")}
                    </Badge>
                  </td>
                  <td className="py-2 pr-4 text-[var(--gray-11)]">
                    {c.contact_name || c.contact_id || "\u2014"}
                  </td>
                  <td className="py-2 pr-4 text-[var(--gray-11)]">
                    {c.outcome ? c.outcome.replace("_", " ") : "\u2014"}
                  </td>
                  <td className="py-2 pr-4 text-[var(--gray-11)] max-w-[200px] truncate">
                    {c.notes || "\u2014"}
                  </td>
                  <td className="py-2 text-right text-[var(--gray-11)]">
                    {c.logged_at ? formatDate(c.logged_at.split("T")[0]) : "\u2014"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Edit modal */}
      {editing && (
        <EditDealModal
          deal={deal}
          meta={meta}
          onClose={() => setEditing(false)}
          onSaved={(updated) => {
            setDeal(updated);
            setEditing(false);
          }}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                       */
/* ------------------------------------------------------------------ */

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)]">
      <div className="flex items-center gap-2 border-b border-[var(--gray-4)] px-5 py-3">
        <Text size="2" weight="medium">{title}</Text>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function DetailRow({
  label,
  value,
  children,
}: {
  label: string;
  value?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex justify-between">
      <Text size="2" color="gray">{label}</Text>
      {children || <Text size="2">{value}</Text>}
    </div>
  );
}

function EditDealModal({
  deal,
  meta,
  onClose,
  onSaved,
}: {
  deal: Deal;
  meta: DealMeta;
  onClose: () => void;
  onSaved: (deal: Deal) => void;
}) {
  const [name, setName] = useState(deal.name);
  const [stage, setStage] = useState(deal.stage);
  const [owner, setOwner] = useState(deal.deal_owner);
  const [amount, setAmount] = useState(deal.amount ? String(deal.amount) : "");
  const [closeDate, setCloseDate] = useState(deal.close_date || "");
  const [description, setDescription] = useState(deal.description);
  const [nextStep, setNextStep] = useState(deal.next_step);
  const [priority, setPriority] = useState(deal.priority);
  const [lostReason, setLostReason] = useState(deal.lost_reason);
  const [propertyId, setPropertyId] = useState(deal.property_id);
  const [groupId, setGroupId] = useState(deal.group_id);
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await mutateApi<{ deal: Deal }>(`/crm/deals/${deal.deal_id}`, "PUT", {
        name: name.trim(),
        stage,
        deal_owner: owner,
        amount: amount ? Number(amount) : null,
        close_date: closeDate || null,
        description: description.trim(),
        next_step: nextStep.trim(),
        priority,
        lost_reason: lostReason.trim(),
        property_id: propertyId.trim(),
        group_id: groupId.trim(),
      });
      onSaved(res.deal);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-[520px] max-h-[85vh] overflow-y-auto rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white shadow-lg">
        <div className="flex items-center justify-between border-b border-[var(--gray-4)] px-5 py-3">
          <Text size="3" weight="medium">Edit Deal</Text>
          <button onClick={onClose} className="text-[var(--gray-9)] hover:text-[var(--gray-11)]">
            <span className="text-[16px]">&times;</span>
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          <Field label="Deal Name">
            <input type="text" value={name} onChange={(e) => setName(e.target.value)}
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none" />
          </Field>
          <div className="grid grid-cols-3 gap-4">
            <Field label="Stage">
              <select value={stage} onChange={(e) => setStage(e.target.value)}
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-2 text-[13px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none">
                {meta.stages.map((s) => (
                  <option key={s} value={s}>{meta.stage_labels[s]}</option>
                ))}
              </select>
            </Field>
            <Field label="Owner">
              <select value={owner} onChange={(e) => setOwner(e.target.value)}
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-2 text-[13px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none">
                <option value="brandon">Brandon</option>
                <option value="jamie">Jamie</option>
              </select>
            </Field>
            <Field label="Priority">
              <select value={priority} onChange={(e) => setPriority(e.target.value)}
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-2 text-[13px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Amount">
              <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)}
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none" />
            </Field>
            <Field label="Close Date">
              <input type="date" value={closeDate} onChange={(e) => setCloseDate(e.target.value)}
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none" />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Property ID">
              <input type="text" value={propertyId} onChange={(e) => setPropertyId(e.target.value)} placeholder="PRO_00001"
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none" />
            </Field>
            <Field label="Group ID">
              <input type="text" value={groupId} onChange={(e) => setGroupId(e.target.value)} placeholder="GRP_00001"
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none" />
            </Field>
          </div>
          <Field label="Description">
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
              className="w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 py-2 text-[14px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none resize-none" />
          </Field>
          <Field label="Next Step">
            <input type="text" value={nextStep} onChange={(e) => setNextStep(e.target.value)}
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none" />
          </Field>
          {stage === "lost" && (
            <Field label="Lost Reason">
              <input type="text" value={lostReason} onChange={(e) => setLostReason(e.target.value)}
                className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none" />
            </Field>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--gray-7)] px-4 text-[13px] font-medium text-[var(--gray-11)] hover:bg-[var(--gray-2)]">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-4 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] disabled:opacity-50 transition-colors">
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[12px] font-medium text-[var(--gray-11)]">{label}</label>
      {children}
    </div>
  );
}
