import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface Props {
  initial?: {
    name?: string;
    email?: string;
    mobile?: string;
    notes?: string;
    tags?: string[];
    computed_contact_id?: string;
    party_group_ids?: string[];
  };
  onSubmit: (data: {
    name: string;
    email: string;
    mobile: string;
    notes: string;
    tags: string[];
    computed_contact_id: string;
    party_group_ids: string[];
  }) => Promise<void>;
  onCancel: () => void;
  submitLabel?: string;
}

export default function CrmContactForm({
  initial = {},
  onSubmit,
  onCancel,
  submitLabel = "Save",
}: Props) {
  const [name, setName] = useState(initial.name ?? "");
  const [email, setEmail] = useState(initial.email ?? "");
  const [mobile, setMobile] = useState(initial.mobile ?? "");
  const [notes, setNotes] = useState(initial.notes ?? "");
  const [tagsStr, setTagsStr] = useState((initial.tags ?? []).join(", "));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const tags = tagsStr
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
      await onSubmit({
        name: name.trim(),
        email: email.trim(),
        mobile: mobile.trim(),
        notes: notes.trim(),
        tags,
        computed_contact_id: initial.computed_contact_id ?? "",
        party_group_ids: initial.party_group_ids ?? [],
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="text-sm text-destructive">{error}</div>
      )}
      <div>
        <label className="text-xs font-medium text-muted-foreground">Name *</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="mt-1"
          autoFocus
        />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Email</label>
          <Input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Mobile</label>
          <Input
            value={mobile}
            onChange={(e) => setMobile(e.target.value)}
            className="mt-1"
          />
        </div>
      </div>
      <div>
        <label className="text-xs font-medium text-muted-foreground">
          Tags (comma-separated)
        </label>
        <Input
          value={tagsStr}
          onChange={(e) => setTagsStr(e.target.value)}
          placeholder="investor, repeat-buyer"
          className="mt-1"
        />
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
