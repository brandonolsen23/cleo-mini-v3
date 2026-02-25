import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { usePropertyOutreach, logContact, setOutreachStatus, convertToDeal } from "../../api/outreach";
import {
  CONTACT_METHODS,
  METHOD_LABELS,
  type ContactMethod,
  OUTCOMES,
  OUTCOME_LABELS,
  type OutcomeType,
  PIPELINE_STATUSES,
  PIPELINE_STATUS_LABELS,
} from "../../types/outreach";
import PipelineStatusBadge from "./PipelineStatusBadge";
import ContactMethodBadge from "./ContactMethodBadge";
import OutcomeBadge from "./OutcomeBadge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface Props {
  propId: string;
  address: string;
  city: string;
}

export default function PropertyOutreachCard({ propId, address, city }: Props) {
  const { data, loading, reload } = usePropertyOutreach(propId);
  const navigate = useNavigate();

  const [showLogForm, setShowLogForm] = useState(false);
  const [logMethod, setLogMethod] = useState<ContactMethod>("mail");
  const [logOutcome, setLogOutcome] = useState<OutcomeType | "">("");
  const [logDate, setLogDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [logNotes, setLogNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [converting, setConverting] = useState(false);

  const handleLogContact = async () => {
    setSaving(true);
    try {
      await logContact({
        prop_id: propId,
        method: logMethod,
        outcome: logOutcome || undefined,
        date: logDate,
        notes: logNotes || undefined,
      });
      setShowLogForm(false);
      setLogOutcome("");
      setLogNotes("");
      reload();
    } finally {
      setSaving(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    await setOutreachStatus(propId, newStatus);
    reload();
  };

  const handleConvertToDeal = async () => {
    setConverting(true);
    try {
      const result = await convertToDeal(propId, {
        title: `${address}, ${city}`,
      });
      reload();
      navigate(`/crm/deals/${result.deal_id}`);
    } finally {
      setConverting(false);
    }
  };

  if (loading) return null;

  const status = data?.outreach_status ?? "not_started";
  const entries = data?.entries ?? [];
  const canConvert = ["attempted_contact", "interested", "listed"].includes(status);

  return (
    <Card>
      <CardHeader className="px-5 py-3 border-b border-border flex-row items-center justify-between">
        <div className="flex items-center gap-2">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider">
            Outreach
          </CardTitle>
          <PipelineStatusBadge status={status} />
        </div>
        <div className="flex items-center gap-2">
          {canConvert && (
            <Button
              variant="outline"
              size="sm"
              className="h-auto px-2 py-1 text-xs"
              onClick={handleConvertToDeal}
              disabled={converting}
            >
              {converting ? "Converting..." : "Convert to Deal"}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-auto px-2 py-1 text-xs"
            onClick={() => setShowLogForm(!showLogForm)}
          >
            Log Contact
          </Button>
        </div>
      </CardHeader>
      <CardContent className="px-5 py-4">
        {/* Status override */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xs text-muted-foreground">Status:</span>
          <select
            value={status}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="h-7 rounded border border-input bg-background px-2 text-xs"
          >
            {PIPELINE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {PIPELINE_STATUS_LABELS[s]}
              </option>
            ))}
          </select>
        </div>

        {/* Log contact form */}
        {showLogForm && (
          <div className="mb-4 pb-4 border-b border-border space-y-2">
            <div className="flex items-center gap-2">
              <select
                value={logMethod}
                onChange={(e) => setLogMethod(e.target.value as ContactMethod)}
                className="h-8 rounded border border-input bg-background px-2 text-sm"
              >
                {CONTACT_METHODS.map((m) => (
                  <option key={m} value={m}>{METHOD_LABELS[m]}</option>
                ))}
              </select>
              <select
                value={logOutcome}
                onChange={(e) => setLogOutcome(e.target.value as OutcomeType | "")}
                className="h-8 rounded border border-input bg-background px-2 text-sm"
              >
                <option value="">Outcome...</option>
                {OUTCOMES.map((o) => (
                  <option key={o} value={o}>{OUTCOME_LABELS[o]}</option>
                ))}
              </select>
              <Input
                type="date"
                value={logDate}
                onChange={(e) => setLogDate(e.target.value)}
                className="h-8 w-36 text-sm"
              />
            </div>
            <Input
              value={logNotes}
              onChange={(e) => setLogNotes(e.target.value)}
              placeholder="Notes (optional)"
              className="h-8 text-sm"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={handleLogContact} disabled={saving}>
                {saving ? "Saving..." : "Save"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowLogForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Activity timeline */}
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No outreach activity yet.</p>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground font-medium">
              {entries.length} touchpoint{entries.length !== 1 ? "s" : ""}
            </p>
            {entries.map((entry) => (
              <div key={entry.entry_id} className="flex items-start gap-3 text-sm">
                <div className="text-xs text-muted-foreground w-20 flex-none pt-0.5">
                  {entry.date}
                </div>
                <div className="flex items-center gap-1.5 flex-none">
                  <ContactMethodBadge method={entry.method} />
                  {entry.outcome && <OutcomeBadge outcome={entry.outcome} />}
                </div>
                {entry.notes && (
                  <div className="text-xs text-muted-foreground truncate">
                    {entry.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
