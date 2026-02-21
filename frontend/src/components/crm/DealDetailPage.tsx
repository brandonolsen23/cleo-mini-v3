import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Trash, FloppyDisk } from "@phosphor-icons/react";
import { useDeal, updateDeal, deleteDeal } from "../../api/crm";
import DealStageBadge from "./DealStageBadge";
import { DEAL_STAGES, STAGE_LABELS } from "../../types/crm";
import type { DealStage } from "../../types/crm";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export default function DealDetailPage() {
  const { dealId } = useParams<{ dealId: string }>();
  const { data, loading, error, reload } = useDeal(dealId!);
  const navigate = useNavigate();

  const [editingNotes, setEditingNotes] = useState(false);
  const [notes, setNotes] = useState("");
  const [savingNotes, setSavingNotes] = useState(false);

  const handleStageChange = async (newStage: DealStage) => {
    if (!data || newStage === data.stage) return;
    await updateDeal(data.deal_id, { stage: newStage });
    reload();
  };

  const startNotesEdit = () => {
    if (!data) return;
    setNotes(data.notes);
    setEditingNotes(true);
  };

  const saveNotes = async () => {
    if (!data) return;
    setSavingNotes(true);
    try {
      await updateDeal(data.deal_id, { notes: notes.trim() });
      setEditingNotes(false);
      reload();
    } finally {
      setSavingNotes(false);
    }
  };

  const handleDelete = async () => {
    if (!data) return;
    if (!confirm(`Delete deal "${data.title}"?`)) return;
    await deleteDeal(data.deal_id);
    navigate("/crm/deals");
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
        <div className="text-destructive">{error || "Deal not found"}</div>
      </div>
    );
  }

  const stageIndex = DEAL_STAGES.indexOf(data.stage);

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
            <h1 className="text-2xl font-semibold text-foreground">{data.title}</h1>
            <Badge variant="outline" className="text-xs font-mono">{data.deal_id}</Badge>
            <DealStageBadge stage={data.stage} />
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Created {data.created?.slice(0, 10)} &middot; Updated {data.updated?.slice(0, 10)}
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
        {/* Stage Pipeline */}
        <Card>
          <CardHeader className="px-5 py-3 border-b border-border">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider">
              Pipeline Stage
            </CardTitle>
          </CardHeader>
          <CardContent className="px-5 py-4">
            <div className="flex gap-1">
              {DEAL_STAGES.map((stage, i) => {
                const isCurrent = stage === data.stage;
                const isPast = i < stageIndex;
                return (
                  <button
                    key={stage}
                    onClick={() => handleStageChange(stage)}
                    className={cn(
                      "flex-1 py-2 px-2 text-xs font-medium rounded transition-colors text-center",
                      isCurrent
                        ? "bg-primary text-primary-foreground"
                        : isPast
                          ? "bg-primary/20 text-primary hover:bg-primary/30"
                          : "bg-muted text-muted-foreground hover:bg-accent",
                    )}
                  >
                    {STAGE_LABELS[stage]}
                  </button>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Property Card */}
        {data.property && (
          <Card>
            <CardHeader className="px-5 py-3 border-b border-border">
              <CardTitle className="text-sm font-semibold uppercase tracking-wider">
                Property
              </CardTitle>
            </CardHeader>
            <CardContent className="px-5 py-4">
              <button
                className="text-left hover:bg-accent rounded-lg p-2 -m-2 transition-colors w-full"
                onClick={() => navigate(`/properties/${data.property!.prop_id}`)}
              >
                <div className="text-sm font-medium">{data.property.address}</div>
                <div className="text-xs text-muted-foreground">
                  {data.property.city} &middot; {data.property.prop_id}
                </div>
              </button>
            </CardContent>
          </Card>
        )}

        {/* Contacts Card */}
        <Card>
          <CardHeader className="px-5 py-3 border-b border-border">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider">
              Contacts ({data.contacts.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="px-5 py-4">
            {data.contacts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No contacts linked.</p>
            ) : (
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">ID</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Name</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2 pr-4">Email</th>
                    <th className="text-left text-[10px] font-medium text-muted-foreground uppercase py-2">Mobile</th>
                  </tr>
                </thead>
                <tbody>
                  {data.contacts.map((c) => (
                    <tr
                      key={c.crm_id}
                      className="border-b border-border hover:bg-accent cursor-pointer transition-colors"
                      onClick={() => navigate(`/crm/contacts/${c.crm_id}`)}
                    >
                      <td className="py-3 pr-4 text-xs font-mono text-primary">{c.crm_id}</td>
                      <td className="py-3 pr-4 text-sm font-medium">{c.name}</td>
                      <td className="py-3 pr-4 text-xs text-muted-foreground">{c.email || "\u2014"}</td>
                      <td className="py-3 text-xs text-muted-foreground">{c.mobile || "\u2014"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>

        {/* Notes Card */}
        <Card>
          <CardHeader className="px-5 py-3 border-b border-border flex-row items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider">
              Notes
            </CardTitle>
            {!editingNotes && (
              <Button variant="ghost" size="sm" onClick={startNotesEdit} className="h-auto px-2 py-1 text-xs">
                Edit
              </Button>
            )}
          </CardHeader>
          <CardContent className="px-5 py-4">
            {editingNotes ? (
              <div className="space-y-3">
                <Textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={4}
                  autoFocus
                />
                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setEditingNotes(false)}
                  >
                    Cancel
                  </Button>
                  <Button size="sm" onClick={saveNotes} disabled={savingNotes}>
                    <FloppyDisk size={14} />
                    {savingNotes ? "Saving..." : "Save"}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-sm whitespace-pre-wrap">
                {data.notes || <span className="text-muted-foreground">No notes yet.</span>}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
