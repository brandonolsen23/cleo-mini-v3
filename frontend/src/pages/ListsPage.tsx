import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Text, Badge, Spinner } from "@radix-ui/themes";
import { Plus, X, ListBullets } from "@phosphor-icons/react";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { fetchApi, mutateApi } from "@/api/client";
import { formatDate } from "@/lib/utils";

interface CrmList {
  list_id: string;
  name: string;
  description: string;
  items: { type: string; property_id?: string; group_id?: string; contact_id?: string }[];
  created_at: string;
  updated_at: string;
}

export function ListsPage() {
  const navigate = useNavigate();
  const [lists, setLists] = useState<CrmList[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = () => {
    setLoading(true);
    fetchApi<{ lists: CrmList[] }>("/crm/lists")
      .then((r) => setLists(r.lists))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner size="3" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <PageHeader
          title="Lists"
          description={
            lists.length > 0
              ? `${lists.length} prospecting list${lists.length !== 1 ? "s" : ""}`
              : "Organize properties, groups, and contacts for prospecting."
          }
        />
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-3 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] transition-colors"
        >
          <Plus size={14} weight="bold" />
          New List
        </button>
      </div>

      {lists.length === 0 ? (
        <EmptyState
          icon={<ListBullets size={40} />}
          title="No lists yet"
          description="Create a list to organize properties, groups, and contacts for prospecting."
        />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {lists.map((lst) => {
            const propCount = lst.items.filter((i) => i.type === "property").length;
            const groupCount = lst.items.filter((i) => i.type === "group").length;
            const contactCount = lst.items.filter((i) => i.type === "contact").length;
            return (
              <button
                key={lst.list_id}
                onClick={() => navigate(`/lists/${lst.list_id}`)}
                className="flex flex-col gap-2 rounded-[var(--card-radius)] border border-[var(--gray-6)] p-5 text-left hover:border-[var(--gray-8)] transition-colors"
              >
                <Text size="3" weight="medium" className="block">
                  {lst.name}
                </Text>
                {lst.description && (
                  <Text size="2" color="gray" className="block truncate">
                    {lst.description}
                  </Text>
                )}
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {propCount > 0 && (
                    <Badge size="1" color="blue" variant="soft">
                      {propCount} propert{propCount !== 1 ? "ies" : "y"}
                    </Badge>
                  )}
                  {groupCount > 0 && (
                    <Badge size="1" color="amber" variant="soft">
                      {groupCount} group{groupCount !== 1 ? "s" : ""}
                    </Badge>
                  )}
                  {contactCount > 0 && (
                    <Badge size="1" color="jade" variant="soft">
                      {contactCount} contact{contactCount !== 1 ? "s" : ""}
                    </Badge>
                  )}
                  {lst.items.length === 0 && (
                    <Badge size="1" color="gray" variant="soft">
                      empty
                    </Badge>
                  )}
                </div>
                <Text size="1" color="gray" className="mt-1 block">
                  Updated {formatDate(lst.updated_at.split("T")[0])}
                </Text>
              </button>
            );
          })}
        </div>
      )}

      {showCreate && (
        <CreateListModal
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

function CreateListModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await mutateApi("/crm/lists", "POST", {
        name: name.trim(),
        description: description.trim(),
      });
      onCreated();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-[420px] rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white shadow-lg">
        <div className="flex items-center justify-between border-b border-[var(--gray-4)] px-5 py-3">
          <Text size="3" weight="medium">New List</Text>
          <button onClick={onClose} className="text-[var(--gray-9)] hover:text-[var(--gray-11)]">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--gray-11)]">
              Name <span className="text-[var(--red-9)]">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. London Retail Owners Q1 2026"
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
              autoFocus
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--gray-11)]">Description</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What is this list for?"
              rows={2}
              className="w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 py-2 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none resize-none"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--gray-7)] px-4 text-[13px] font-medium text-[var(--gray-11)] hover:bg-[var(--gray-2)]">
              Cancel
            </button>
            <button type="submit" disabled={saving || !name.trim()}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-4 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] disabled:opacity-50 transition-colors">
              {saving ? "Creating..." : "Create List"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
