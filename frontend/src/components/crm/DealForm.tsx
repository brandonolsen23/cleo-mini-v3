import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DEAL_STAGES, STAGE_LABELS } from "../../types/crm";
import type { DealStage, CrmContact } from "../../types/crm";
import type { PropertySummary } from "../../types/property";
import { fetchApi } from "../../api/client";

interface Props {
  initial?: {
    title?: string;
    prop_id?: string;
    stage?: DealStage;
    contact_ids?: string[];
    notes?: string;
  };
  onSubmit: (data: {
    title: string;
    prop_id: string;
    stage: DealStage;
    contact_ids: string[];
    notes: string;
  }) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
}

export default function DealForm({
  initial = {},
  onSubmit,
  onCancel,
  submitLabel = "Save",
}: Props) {
  const [title, setTitle] = useState(initial.title ?? "");
  const [propId, setPropId] = useState(initial.prop_id ?? "");
  const [stage, setStage] = useState<DealStage>(initial.stage ?? "lead");
  const [contactIds, setContactIds] = useState<string[]>(initial.contact_ids ?? []);
  const [contactIdInput, setContactIdInput] = useState("");
  const [notes, setNotes] = useState(initial.notes ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Property search
  const [propSearch, setPropSearch] = useState("");
  const [propResults, setPropResults] = useState<PropertySummary[]>([]);
  const [propLabel, setPropLabel] = useState(initial.prop_id ?? "");
  const [showPropSearch, setShowPropSearch] = useState(!initial.prop_id);

  // Contact search
  const [contactSearch, setContactSearch] = useState("");
  const [contactResults, setContactResults] = useState<CrmContact[]>([]);

  useEffect(() => {
    if (propSearch.length < 2) {
      setPropResults([]);
      return;
    }
    const timer = setTimeout(() => {
      fetchApi<PropertySummary[]>("/properties")
        .then((all) => {
          const q = propSearch.toLowerCase();
          setPropResults(
            all
              .filter(
                (p) =>
                  p.address.toLowerCase().includes(q) ||
                  p.city.toLowerCase().includes(q) ||
                  p.prop_id.toLowerCase().includes(q),
              )
              .slice(0, 8),
          );
        })
        .catch(() => setPropResults([]));
    }, 200);
    return () => clearTimeout(timer);
  }, [propSearch]);

  useEffect(() => {
    if (contactSearch.length < 1) {
      setContactResults([]);
      return;
    }
    const timer = setTimeout(() => {
      fetchApi<CrmContact[]>("/crm/contacts")
        .then((all) => {
          const q = contactSearch.toLowerCase();
          setContactResults(
            all
              .filter(
                (c) =>
                  !contactIds.includes(c.crm_id) &&
                  (c.name.toLowerCase().includes(q) || c.crm_id.toLowerCase().includes(q)),
              )
              .slice(0, 5),
          );
        })
        .catch(() => setContactResults([]));
    }, 200);
    return () => clearTimeout(timer);
  }, [contactSearch, contactIds]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setError("Title is required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        title: title.trim(),
        prop_id: propId,
        stage,
        contact_ids: contactIds,
        notes: notes.trim(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <div className="text-sm text-destructive">{error}</div>}
      <div>
        <label className="text-xs font-medium text-muted-foreground">Title *</label>
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. 123 Main St Acquisition"
          className="mt-1"
          autoFocus
        />
      </div>

      {/* Property picker */}
      <div>
        <label className="text-xs font-medium text-muted-foreground">Property</label>
        {!showPropSearch && propId ? (
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm">{propLabel}</span>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-auto px-1 py-0 text-xs"
              onClick={() => {
                setShowPropSearch(true);
                setPropId("");
                setPropLabel("");
              }}
            >
              Change
            </Button>
          </div>
        ) : (
          <div className="relative mt-1">
            <Input
              value={propSearch}
              onChange={(e) => setPropSearch(e.target.value)}
              placeholder="Search properties..."
            />
            {propResults.length > 0 && (
              <div className="absolute z-20 mt-1 w-full bg-popover border border-border rounded-md shadow-md max-h-48 overflow-auto">
                {propResults.map((p) => (
                  <button
                    key={p.prop_id}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors"
                    onClick={() => {
                      setPropId(p.prop_id);
                      setPropLabel(`${p.address}, ${p.city} (${p.prop_id})`);
                      setShowPropSearch(false);
                      setPropSearch("");
                      setPropResults([]);
                    }}
                  >
                    <div className="font-medium">{p.address}</div>
                    <div className="text-xs text-muted-foreground">
                      {p.city} &middot; {p.prop_id}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div>
        <label className="text-xs font-medium text-muted-foreground">Stage</label>
        <select
          value={stage}
          onChange={(e) => setStage(e.target.value as DealStage)}
          className="mt-1 w-full h-9 rounded-md border border-input bg-background px-3 text-sm"
        >
          {DEAL_STAGES.map((s) => (
            <option key={s} value={s}>{STAGE_LABELS[s]}</option>
          ))}
        </select>
      </div>

      {/* Contact picker */}
      <div>
        <label className="text-xs font-medium text-muted-foreground">Contacts</label>
        {contactIds.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1 mb-2">
            {contactIds.map((cid) => (
              <span
                key={cid}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-secondary text-secondary-foreground text-xs"
              >
                {cid}
                <button
                  type="button"
                  onClick={() => setContactIds(contactIds.filter((id) => id !== cid))}
                  className="hover:text-destructive"
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
        )}
        <div className="flex gap-2 mt-1">
          <div className="relative flex-1">
            <Input
              value={contactSearch}
              onChange={(e) => setContactSearch(e.target.value)}
              placeholder="Search CRM contacts..."
            />
            {contactResults.length > 0 && (
              <div className="absolute z-20 mt-1 w-full bg-popover border border-border rounded-md shadow-md max-h-36 overflow-auto">
                {contactResults.map((c) => (
                  <button
                    key={c.crm_id}
                    type="button"
                    className="w-full text-left px-3 py-2 text-sm hover:bg-accent transition-colors"
                    onClick={() => {
                      setContactIds([...contactIds, c.crm_id]);
                      setContactSearch("");
                      setContactResults([]);
                    }}
                  >
                    {c.name}{" "}
                    <span className="text-xs text-muted-foreground">{c.crm_id}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="flex gap-1">
            <Input
              value={contactIdInput}
              onChange={(e) => setContactIdInput(e.target.value)}
              placeholder="C00001"
              className="w-24"
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                const id = contactIdInput.trim();
                if (id && !contactIds.includes(id)) {
                  setContactIds([...contactIds, id]);
                  setContactIdInput("");
                }
              }}
            >
              Add
            </Button>
          </div>
        </div>
      </div>

      <div>
        <label className="text-xs font-medium text-muted-foreground">Notes</label>
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={3}
          className="mt-1"
        />
      </div>

      <div className="flex gap-2 justify-end pt-2">
        <Button type="button" variant="outline" size="sm" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" size="sm" disabled={saving}>
          {saving ? "Saving..." : submitLabel}
        </Button>
      </div>
    </form>
  );
}
