import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, DownloadSimple, Trash, PencilSimple, Check } from "@phosphor-icons/react";
import {
  useOutreachList,
  deleteOutreachList,
  updateOutreachList,
  logContact,
  logContactsBulk,
} from "../../api/outreach";
import type { OutreachItem } from "../../types/outreach";
import { CONTACT_METHODS, METHOD_LABELS, type ContactMethod, OUTCOMES, OUTCOME_LABELS, type OutcomeType } from "../../types/outreach";
import ContactMethodBadge from "./ContactMethodBadge";
import OutcomeBadge from "./OutcomeBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function OutreachListDetailPage() {
  const { listId } = useParams<{ listId: string }>();
  const { data, loading, error, reload } = useOutreachList(listId!);
  const navigate = useNavigate();

  // Edit name/description
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");

  // Inline contact logging
  const [loggingPropId, setLoggingPropId] = useState<string | null>(null);
  const [logMethod, setLogMethod] = useState<ContactMethod>("mail");
  const [logOutcome, setLogOutcome] = useState<OutcomeType | "">("");
  const [logDate, setLogDate] = useState(() => new Date().toISOString().slice(0, 10));

  // Bulk contact
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [bulkLogging, setBulkLogging] = useState(false);

  const handleDelete = async () => {
    if (!confirm("Delete this outreach list?")) return;
    await deleteOutreachList(listId!);
    navigate("/outreach");
  };

  const handleSaveEdit = async () => {
    await updateOutreachList(listId!, {
      name: editName,
      description: editDesc,
    });
    setEditing(false);
    reload();
  };

  const handleLogContact = async (item: OutreachItem) => {
    await logContact({
      list_id: listId!,
      prop_id: item.prop_id,
      owner_group_id: item.owner_group_id,
      method: logMethod,
      outcome: logOutcome || undefined,
      date: logDate,
    });
    setLoggingPropId(null);
    setLogOutcome("");
    reload();
  };

  const handleBulkLog = async () => {
    if (selectedIds.size === 0 || !data) return;
    setBulkLogging(true);
    const items = data.items
      .filter((i) => selectedIds.has(i.prop_id))
      .map((i) => ({ prop_id: i.prop_id, owner_group_id: i.owner_group_id }));
    await logContactsBulk({
      list_id: listId!,
      items,
      method: logMethod,
      outcome: logOutcome || undefined,
      date: logDate,
    });
    setBulkLogging(false);
    setSelectedIds(new Set());
    reload();
  };

  const toggleItem = (propId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(propId)) next.delete(propId);
      else next.add(propId);
      return next;
    });
  };

  const exportUrl = `/api/outreach/lists/${listId}/export.csv`;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading list...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-destructive">Error: {error || "List not found"}</div>
      </div>
    );
  }

  const contactedCount = data.items.filter((i) => i.contact_status).length;

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex-none px-6 py-4 bg-background border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/outreach")}
              className="text-muted-foreground hover:text-foreground"
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              {editing ? (
                <div className="space-y-1">
                  <Input
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="h-8 text-sm font-semibold"
                  />
                  <Input
                    value={editDesc}
                    onChange={(e) => setEditDesc(e.target.value)}
                    placeholder="Description..."
                    className="h-7 text-xs"
                  />
                  <div className="flex gap-1">
                    <Button size="sm" variant="outline" onClick={handleSaveEdit}>
                      Save
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setEditing(false)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <h1 className="text-lg font-semibold text-foreground">
                      {data.name}
                    </h1>
                    <button
                      onClick={() => {
                        setEditName(data.name);
                        setEditDesc(data.description);
                        setEditing(true);
                      }}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <PencilSimple size={14} />
                    </button>
                  </div>
                  <p className="text-sm text-muted-foreground mt-0.5">
                    {data.items.length} properties, {contactedCount} contacted
                    {data.description && ` \u2014 ${data.description}`}
                  </p>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a href={exportUrl} download>
              <Button variant="outline" size="sm">
                <DownloadSimple size={14} />
                Export CSV
              </Button>
            </a>
            <Button variant="outline" size="sm" onClick={handleDelete}>
              <Trash size={14} />
              Delete
            </Button>
          </div>
        </div>
      </div>

      {/* Bulk actions */}
      {selectedIds.size > 0 && (
        <div className="flex-none px-6 py-3 bg-muted/50 border-b border-border flex items-center gap-3">
          <span className="text-sm text-muted-foreground">
            {selectedIds.size} selected
          </span>
          <select
            value={logMethod}
            onChange={(e) => setLogMethod(e.target.value as ContactMethod)}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
          >
            {CONTACT_METHODS.map((m) => (
              <option key={m} value={m}>
                {METHOD_LABELS[m]}
              </option>
            ))}
          </select>
          <select
            value={logOutcome}
            onChange={(e) => setLogOutcome(e.target.value as OutcomeType | "")}
            className="h-8 rounded-md border border-input bg-background px-2 text-sm"
          >
            <option value="">Outcome...</option>
            {OUTCOMES.map((o) => (
              <option key={o} value={o}>
                {OUTCOME_LABELS[o]}
              </option>
            ))}
          </select>
          <Input
            type="date"
            value={logDate}
            onChange={(e) => setLogDate(e.target.value)}
            className="h-8 w-36 text-sm"
          />
          <Button
            size="sm"
            onClick={handleBulkLog}
            disabled={bulkLogging}
          >
            <Check size={14} />
            {bulkLogging ? "Logging..." : "Log Contact for Selected"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setSelectedIds(new Set())}
          >
            Clear
          </Button>
        </div>
      )}

      {/* Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full">
          <thead className="sticky top-0 bg-muted z-10">
            <tr>
              <th className="w-10 px-3 py-2.5">
                <input
                  type="checkbox"
                  checked={
                    selectedIds.size === data.items.length && data.items.length > 0
                  }
                  onChange={() => {
                    if (selectedIds.size === data.items.length) {
                      setSelectedIds(new Set());
                    } else {
                      setSelectedIds(new Set(data.items.map((i) => i.prop_id)));
                    }
                  }}
                  className="rounded border-input"
                />
              </th>
              <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                Property
              </th>
              <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                Owner
              </th>
              <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                Corporate Address
              </th>
              <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                Contact
              </th>
              <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                Last Sale
              </th>
              <th className="text-left text-[10px] font-medium text-muted-foreground uppercase tracking-wider px-3 py-2.5">
                Status
              </th>
              <th className="w-24 px-3 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr
                key={item.prop_id}
                className="border-b border-border hover:bg-accent/50 transition-colors"
              >
                <td className="px-3 py-2.5">
                  <input
                    type="checkbox"
                    checked={selectedIds.has(item.prop_id)}
                    onChange={() => toggleItem(item.prop_id)}
                    className="rounded border-input"
                  />
                </td>
                <td className="px-3 py-2.5">
                  <div className="text-sm font-medium">{item.address}</div>
                  <div className="text-xs text-muted-foreground">
                    {item.city}
                    {item.brands.length > 0 && (
                      <span className="ml-1">({item.brands.join(", ")})</span>
                    )}
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <div className="text-sm">{item.owner || "\u2014"}</div>
                  <div className="text-xs text-muted-foreground">
                    {item.owner_type || ""}
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <div className="text-sm truncate max-w-[200px]">
                    {item.corporate_address || "\u2014"}
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  <div className="text-sm">
                    {item.contact_names.length > 0
                      ? item.contact_names.join(", ")
                      : "\u2014"}
                  </div>
                  {item.phones.length > 0 && (
                    <div className="text-xs text-muted-foreground">
                      {item.phones.join(", ")}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <div className="text-sm">{item.latest_sale_date || "\u2014"}</div>
                  <div className="text-xs text-muted-foreground">
                    {item.latest_sale_price || ""}
                  </div>
                </td>
                <td className="px-3 py-2.5">
                  {item.contact_status ? (
                    <div>
                      <div className="flex items-center gap-1">
                        <ContactMethodBadge method={item.contact_status.method} />
                        {item.contact_status.outcome && (
                          <OutcomeBadge outcome={item.contact_status.outcome} />
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {item.contact_status.date}
                      </div>
                    </div>
                  ) : (
                    <span className="text-xs text-muted-foreground">Not contacted</span>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  {loggingPropId === item.prop_id ? (
                    <div className="flex items-center gap-1">
                      <select
                        value={logMethod}
                        onChange={(e) =>
                          setLogMethod(e.target.value as ContactMethod)
                        }
                        className="h-7 rounded border border-input bg-background px-1 text-xs"
                      >
                        {CONTACT_METHODS.map((m) => (
                          <option key={m} value={m}>
                            {METHOD_LABELS[m]}
                          </option>
                        ))}
                      </select>
                      <select
                        value={logOutcome}
                        onChange={(e) =>
                          setLogOutcome(e.target.value as OutcomeType | "")
                        }
                        className="h-7 rounded border border-input bg-background px-1 text-xs"
                      >
                        <option value="">Outcome</option>
                        {OUTCOMES.map((o) => (
                          <option key={o} value={o}>
                            {OUTCOME_LABELS[o]}
                          </option>
                        ))}
                      </select>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 text-xs px-2"
                        onClick={() => handleLogContact(item)}
                      >
                        <Check size={12} />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 text-xs px-1"
                        onClick={() => setLoggingPropId(null)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 text-xs"
                      onClick={() => setLoggingPropId(item.prop_id)}
                    >
                      Log Contact
                    </Button>
                  )}
                </td>
              </tr>
            ))}
            {data.items.length === 0 && (
              <tr>
                <td
                  colSpan={8}
                  className="px-4 py-12 text-center text-sm text-muted-foreground"
                >
                  This list has no properties.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
