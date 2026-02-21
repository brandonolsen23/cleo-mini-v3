import { useState, useEffect } from "react";
import { useFeedback } from "../../api/feedback";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";

export default function DataIssueCard({ entityId }: { entityId: string }) {
  const { data, loading, saving, saved, save } = useFeedback(entityId);
  const [hasIssue, setHasIssue] = useState(false);
  const [notes, setNotes] = useState("");

  useEffect(() => {
    setHasIssue(data.has_issue);
    setNotes(data.notes);
  }, [data]);

  if (loading) return null;

  const dirty =
    hasIssue !== data.has_issue || notes !== data.notes;

  return (
    <Card>
      <CardHeader className="border-b border-border">
        <CardTitle>Feedback</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <label className="flex items-center gap-2 cursor-pointer">
          <Checkbox
            checked={hasIssue}
            onCheckedChange={(checked) => setHasIssue(checked === true)}
          />
          <span className="text-sm">Data issue</span>
        </label>
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes (optional)"
          rows={2}
          className="resize-none"
        />
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            onClick={() => save({ has_issue: hasIssue, notes })}
            disabled={saving || !dirty}
          >
            {saving ? "Saving..." : "Save"}
          </Button>
          {saved && (
            <span className="text-sm text-green-600">Saved</span>
          )}
          {data.date && !dirty && (
            <span className="text-xs text-muted-foreground">
              Last saved {data.date}
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
