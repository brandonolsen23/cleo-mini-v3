import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Trash, PencilSimple, FloppyDisk, X } from "@phosphor-icons/react";
import { useCrmContact, updateCrmContact, deleteCrmContact } from "../../api/crm";
import { useContact } from "../../api/contacts";
import DealStageBadge from "./DealStageBadge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export default function CrmContactDetailPage() {
  const { crmId } = useParams<{ crmId: string }>();
  const { data, loading, error, reload } = useCrmContact(crmId!);
  const navigate = useNavigate();

  // Load computed contact data if linked
  const computedId = data?.computed_contact_id || undefined;
  const { data: computed } = useContact(computedId ?? "__none__");

  const [editing, setEditing] = useState(false);
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [notes, setNotes] = useState("");
  const [tagsStr, setTagsStr] = useState("");
  const [saving, setSaving] = useState(false);

  const startEdit = () => {
    if (!data) return;
    setEmail(data.email);
    setMobile(data.mobile);
    setNotes(data.notes);
    setTagsStr(data.tags.join(", "));
    setEditing(true);
  };

  const cancelEdit = () => setEditing(false);

  const saveEdit = async () => {
    if (!data) return;
    setSaving(true);
    try {
      const tags = tagsStr.split(",").map((t) => t.trim()).filter(Boolean);
      await updateCrmContact(data.crm_id, {
        email: email.trim(),
        mobile: mobile.trim(),
        notes: notes.trim(),
        tags,
      });
      setEditing(false);
      reload();
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!data) return;
    if (!confirm(`Delete CRM contact "${data.name}"?`)) return;
    await deleteCrmContact(data.crm_id);
    navigate("/crm/contacts");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-destructive">{error || "Contact not found"}</div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      {/* Back link */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate(-1)}
        className="h-auto px-0 py-0 text-sm text-muted-foreground hover:text-foreground hover:bg-transparent mb-4"
      >
        <ArrowLeft size={16} />
        Back
      </Button>

      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-foreground">{data.name}</h1>
            <Badge variant="outline" className="text-xs font-mono">{data.crm_id}</Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Created {data.created?.slice(0, 10)}
            {data.computed_contact_id && (
              <>
                {" \u2022 "}
                <button
                  className="text-primary hover:underline"
                  onClick={() =>
                    navigate(`/contacts/${encodeURIComponent(data.computed_contact_id)}`)
                  }
                >
                  View computed profile
                </button>
              </>
            )}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleDelete}
          className="text-destructive hover:text-destructive"
        >
          <Trash size={16} />
          Delete
        </Button>
      </div>

      <div className="space-y-5">
        {/* CRM Info Card */}
        <Card>
          <CardHeader className="px-5 py-3 border-b border-border flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider">
              CRM Info
            </CardTitle>
            {!editing && (
              <Button variant="ghost" size="sm" onClick={startEdit} className="h-auto px-2 py-1">
                <PencilSimple size={14} />
                Edit
              </Button>
            )}
          </CardHeader>
          <CardContent className="px-5 py-4">
            {editing ? (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">Email</label>
                    <Input value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1" />
                  </div>
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">Mobile</label>
                    <Input value={mobile} onChange={(e) => setMobile(e.target.value)} className="mt-1" />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Tags (comma-separated)</label>
                  <Input value={tagsStr} onChange={(e) => setTagsStr(e.target.value)} className="mt-1" />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Notes</label>
                  <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} className="mt-1" />
                </div>
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" size="sm" onClick={cancelEdit}>
                    <X size={14} />
                    Cancel
                  </Button>
                  <Button size="sm" onClick={saveEdit} disabled={saving}>
                    <FloppyDisk size={14} />
                    {saving ? "Saving..." : "Save"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                <div>
                  <dt className="text-xs text-muted-foreground font-medium mb-1">Email</dt>
                  <dd className="text-sm">{data.email || "\u2014"}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground font-medium mb-1">Mobile</dt>
                  <dd className="text-sm">{data.mobile || "\u2014"}</dd>
                </div>
                <div className="col-span-2">
                  <dt className="text-xs text-muted-foreground font-medium mb-1">Tags</dt>
                  <dd>
                    {data.tags.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {data.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    ) : (
                      <span className="text-sm text-muted-foreground">{"\u2014"}</span>
                    )}
                  </dd>
                </div>
                {data.notes && (
                  <div className="col-span-2">
                    <dt className="text-xs text-muted-foreground font-medium mb-1">Notes</dt>
                    <dd className="text-sm whitespace-pre-wrap">{data.notes}</dd>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Linked Deals */}
        {data.deals.length > 0 && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Deals ({data.deals.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Title</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Property</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Stage</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {data.deals.map((deal) => (
                    <tr
                      key={deal.deal_id}
                      className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                      onClick={() => navigate(`/crm/deals/${deal.deal_id}`)}
                    >
                      <td className="py-3 pr-4 text-sm font-medium">{deal.title}</td>
                      <td className="py-3 pr-4 text-xs text-muted-foreground">
                        {deal.property ? `${deal.property.address}, ${deal.property.city}` : deal.prop_id || "\u2014"}
                      </td>
                      <td className="py-3 pr-4"><DealStageBadge stage={deal.stage} /></td>
                      <td className="py-3 text-xs">{deal.updated?.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {/* Party Groups */}
        {data.party_group_ids.length > 0 && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Party Groups ({data.party_group_ids.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <div className="flex flex-wrap gap-2">
                {data.party_group_ids.map((gid) => (
                  <button
                    key={gid}
                    className="text-xs font-mono text-primary hover:underline"
                    onClick={() => navigate(`/parties/${gid}`)}
                  >
                    {gid}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Computed Transaction History */}
        {computed && computed.appearances && computed.appearances.length > 0 && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Transaction History ({computed.appearances.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">RT ID</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Role</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Entity</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Date</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">Address</th>
                  </tr>
                </thead>
                <tbody>
                  {computed.appearances.slice(0, 10).map((app, i) => (
                    <tr
                      key={`${app.rt_id}-${app.role}-${i}`}
                      className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                      onClick={() => navigate(`/transactions/${app.rt_id}`)}
                    >
                      <td className="py-3 pr-4 text-xs font-mono text-primary">{app.rt_id}</td>
                      <td className="py-3 pr-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${app.role === "buyer" ? "bg-green-100 text-green-700" : "bg-orange-100 text-orange-700"}`}>
                          {app.role === "buyer" ? "Buyer" : "Seller"}
                        </span>
                      </td>
                      <td className="py-3 pr-4 text-xs max-w-[180px] truncate">{app.entity_name}</td>
                      <td className="py-3 pr-4 text-xs">{app.sale_date_iso}</td>
                      <td className="py-3 text-xs">{app.prop_address}, {app.prop_city}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {computed.appearances.length > 10 && (
                <p className="text-xs text-muted-foreground mt-2">
                  Showing 10 of {computed.appearances.length}.{" "}
                  <button
                    className="text-primary hover:underline"
                    onClick={() => navigate(`/contacts/${encodeURIComponent(data.computed_contact_id)}`)}
                  >
                    View all
                  </button>
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Computed Entities */}
        {computed && computed.entities && computed.entities.length > 0 && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Entities ({computed.entities.length})
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <div className="space-y-0.5">
                {computed.entities.slice(0, 10).map((e, i) => (
                  <div key={i} className="text-sm">{e}</div>
                ))}
                {computed.entities.length > 10 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    +{computed.entities.length - 10} more
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
