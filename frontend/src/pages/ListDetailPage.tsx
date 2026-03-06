import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Text, Badge, Spinner } from "@radix-ui/themes";
import { ArrowLeft, Trash, X } from "@phosphor-icons/react";
import { fetchApi, mutateApi } from "@/api/client";
import { formatDate } from "@/lib/utils";

interface ListItem {
  type: string;
  property_id?: string;
  arn?: string;
  group_id?: string;
  contact_id?: string;
  name?: string;
}

interface CrmList {
  list_id: string;
  name: string;
  description: string;
  items: ListItem[];
  created_at: string;
  updated_at: string;
}

const TYPE_COLORS: Record<string, string> = {
  property: "blue",
  group: "amber",
  contact: "jade",
};

export function ListDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [list, setList] = useState<CrmList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showAdd, setShowAdd] = useState(false);

  const load = () => {
    if (!id) return;
    setLoading(true);
    fetchApi<CrmList>(`/crm/lists/${id}`)
      .then(setList)
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

  if (error || !list) {
    return (
      <div className="flex flex-col items-center justify-center py-20">
        <Text size="3" color="gray">{error || "List not found"}</Text>
        <button
          onClick={() => navigate("/lists")}
          className="mt-4 text-[13px] font-medium text-[var(--accent-11)] hover:underline"
        >
          Back to Lists
        </button>
      </div>
    );
  }

  const handleRemoveItem = async (index: number) => {
    const res = await mutateApi<{ list: CrmList }>(
      `/crm/lists/${list.list_id}/items/${index}`,
      "DELETE"
    );
    setList(res.list);
  };

  const handleDelete = async () => {
    if (!confirm("Delete this list?")) return;
    await mutateApi(`/crm/lists/${list.list_id}`, "DELETE");
    navigate("/lists");
  };

  const handleItemClick = (item: ListItem) => {
    if (item.type === "property" && item.property_id) {
      navigate(`/properties/${item.property_id}`);
    } else if (item.type === "group" && item.group_id) {
      navigate(`/groups/${item.group_id}`);
    } else if (item.type === "contact" && item.contact_id) {
      navigate(`/contacts/${item.contact_id}`);
    }
  };

  const propCount = list.items.filter((i) => i.type === "property").length;
  const groupCount = list.items.filter((i) => i.type === "group").length;
  const contactCount = list.items.filter((i) => i.type === "contact").length;

  return (
    <div className="flex flex-col gap-6">
      {/* Back + header */}
      <div>
        <button
          onClick={() => navigate("/lists")}
          className="mb-3 inline-flex items-center gap-1 text-[13px] font-medium text-[var(--gray-11)] hover:text-[var(--gray-12)]"
        >
          <ArrowLeft size={14} />
          Lists
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-[24px] font-medium leading-[32px] text-[var(--gray-12)]">
              {list.name}
            </h2>
            <div className="mt-1 flex items-center gap-2">
              <Text size="2" color="gray">{list.list_id}</Text>
              {list.description && (
                <>
                  <Text size="2" color="gray">&middot;</Text>
                  <Text size="2" color="gray">{list.description}</Text>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowAdd(true)}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-3 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] transition-colors"
            >
              Add Item
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

      {/* Stats */}
      <div className="flex gap-3">
        <Badge size="2" color="blue" variant="soft">
          {propCount} propert{propCount !== 1 ? "ies" : "y"}
        </Badge>
        <Badge size="2" color="amber" variant="soft">
          {groupCount} group{groupCount !== 1 ? "s" : ""}
        </Badge>
        <Badge size="2" color="jade" variant="soft">
          {contactCount} contact{contactCount !== 1 ? "s" : ""}
        </Badge>
      </div>

      {/* Items table */}
      <div className="rounded-[var(--card-radius)] border border-[var(--gray-6)]">
        <div className="flex items-center gap-2 border-b border-[var(--gray-4)] px-5 py-3">
          <Text size="2" weight="medium">
            Items ({list.items.length})
          </Text>
        </div>
        <div className="p-5">
          {list.items.length === 0 ? (
            <Text size="2" color="gray">
              No items in this list yet. Click "Add Item" to get started.
            </Text>
          ) : (
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--gray-4)] text-left text-[var(--gray-9)]">
                  <th className="pb-2 font-medium">Type</th>
                  <th className="pb-2 font-medium">ID</th>
                  <th className="pb-2 font-medium">Name</th>
                  <th className="pb-2 font-medium w-[40px]"></th>
                </tr>
              </thead>
              <tbody>
                {list.items.map((item, i) => {
                  const itemId =
                    item.property_id || item.group_id || item.contact_id || "";
                  const color = TYPE_COLORS[item.type] || "gray";
                  return (
                    <tr
                      key={i}
                      className="border-b border-[var(--gray-4)] last:border-0"
                    >
                      <td className="py-2 pr-4">
                        <Badge size="1" color={color as any} variant="soft">
                          {item.type}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4">
                        <button
                          onClick={() => handleItemClick(item)}
                          className="text-[var(--accent-11)] hover:underline"
                        >
                          {itemId}
                        </button>
                      </td>
                      <td className="py-2 pr-4 text-[var(--gray-11)]">
                        {item.name || "\u2014"}
                      </td>
                      <td className="py-2 text-right">
                        <button
                          onClick={() => handleRemoveItem(i)}
                          className="text-[var(--gray-9)] hover:text-[var(--red-9)]"
                        >
                          <X size={13} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <Text size="1" color="gray">
        Created {formatDate(list.created_at.split("T")[0])} &middot; Updated{" "}
        {formatDate(list.updated_at.split("T")[0])}
      </Text>

      {showAdd && (
        <AddItemModal
          listId={list.list_id}
          onClose={() => setShowAdd(false)}
          onAdded={(updated) => {
            setList(updated);
            setShowAdd(false);
          }}
        />
      )}
    </div>
  );
}

function AddItemModal({
  listId,
  onClose,
  onAdded,
}: {
  listId: string;
  onClose: () => void;
  onAdded: (list: CrmList) => void;
}) {
  const [type, setType] = useState<"property" | "group" | "contact">("property");
  const [itemId, setItemId] = useState("");
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemId.trim()) return;
    setSaving(true);
    try {
      const item: Record<string, string> = { type };
      if (type === "property") {
        item.property_id = itemId.trim();
      } else if (type === "group") {
        item.group_id = itemId.trim();
      } else {
        item.contact_id = itemId.trim();
      }
      if (name.trim()) item.name = name.trim();
      const res = await mutateApi<{ list: CrmList }>(
        `/crm/lists/${listId}/items`,
        "POST",
        item
      );
      onAdded(res.list);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-[400px] rounded-[var(--card-radius)] border border-[var(--gray-6)] bg-white shadow-lg">
        <div className="flex items-center justify-between border-b border-[var(--gray-4)] px-5 py-3">
          <Text size="3" weight="medium">Add Item</Text>
          <button onClick={onClose} className="text-[var(--gray-9)] hover:text-[var(--gray-11)]">
            <X size={16} />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 p-5">
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--gray-11)]">Type</label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as any)}
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-2 text-[13px] text-[var(--gray-12)] focus:border-[var(--accent-8)] focus:outline-none"
            >
              <option value="property">Property</option>
              <option value="group">Group</option>
              <option value="contact">Contact</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--gray-11)]">
              {type === "property" ? "Property ID" : type === "group" ? "Group ID" : "Contact ID"}{" "}
              <span className="text-[var(--red-9)]">*</span>
            </label>
            <input
              type="text"
              value={itemId}
              onChange={(e) => setItemId(e.target.value)}
              placeholder={
                type === "property"
                  ? "PRO_00001"
                  : type === "group"
                    ? "GRP_00001"
                    : "CON_00001"
              }
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
              autoFocus
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-[12px] font-medium text-[var(--gray-11)]">Label (optional)</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. 123 Main St or RioCan REIT"
              className="h-8 w-full rounded-[var(--radius-2)] border border-[var(--gray-7)] bg-white px-3 text-[14px] text-[var(--gray-12)] placeholder:text-[var(--gray-9)] focus:border-[var(--accent-8)] focus:outline-none"
            />
          </div>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--gray-7)] px-4 text-[13px] font-medium text-[var(--gray-11)] hover:bg-[var(--gray-2)]">
              Cancel
            </button>
            <button type="submit" disabled={saving || !itemId.trim()}
              className="h-8 rounded-[var(--radius-2)] border border-[var(--accent-7)] bg-[var(--accent-9)] px-4 text-[13px] font-medium text-white hover:bg-[var(--accent-10)] disabled:opacity-50 transition-colors">
              {saving ? "Adding..." : "Add"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
