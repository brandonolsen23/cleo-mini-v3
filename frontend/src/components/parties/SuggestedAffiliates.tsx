import { useState } from "react";
import { Link } from "react-router-dom";
import { CaretDown, CaretUp, ArrowsMerge, XCircle } from "@phosphor-icons/react";
import { useSuggestions } from "../../api/parties";
import type { PartySuggestion } from "../../types/party";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function EvidencePill({
  type,
  value,
}: {
  type: "phone" | "contact" | "address";
  value: string;
}) {
  const styles = {
    phone: "bg-blue-100 text-blue-700",
    contact: "bg-orange-100 text-orange-700",
    address: "bg-green-100 text-green-700",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${styles[type]}`}
    >
      {value}
    </span>
  );
}

function SuggestionRow({
  suggestion,
  onMerge,
  onDismiss,
}: {
  suggestion: PartySuggestion;
  onMerge: (sourceGroup: string, reason: string) => Promise<void>;
  onDismiss: (suggestedGroup: string, reason: string) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [merging, setMerging] = useState(false);
  const [mergeReason, setMergeReason] = useState("");
  const [acting, setActing] = useState(false);

  const handleMerge = async () => {
    setActing(true);
    try {
      await onMerge(suggestion.group_id, mergeReason);
    } finally {
      setActing(false);
      setMerging(false);
    }
  };

  const handleDismiss = async () => {
    setActing(true);
    try {
      await onDismiss(suggestion.group_id, "");
    } finally {
      setActing(false);
    }
  };

  return (
    <div className="border-b border-border last:border-0">
      {/* Collapsed row */}
      <div
        className="flex items-center gap-3 py-3 px-1 cursor-pointer hover:bg-accent transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-none text-muted-foreground">
          {expanded ? <CaretUp size={14} /> : <CaretDown size={14} />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <Link
              to={`/parties/${suggestion.group_id}`}
              onClick={(e) => e.stopPropagation()}
              className="text-sm font-medium text-primary hover:text-primary/80 truncate"
            >
              {suggestion.display_name}
            </Link>
            <span className="text-xs text-muted-foreground font-mono flex-none">
              {suggestion.group_id}
            </span>
            <span className="text-xs text-muted-foreground flex-none">
              {suggestion.transaction_count} txn{suggestion.transaction_count !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex flex-wrap gap-1 mt-1">
            {suggestion.shared_phones.map((p) => (
              <EvidencePill key={`p-${p}`} type="phone" value={p} />
            ))}
            {suggestion.shared_contacts.map((c) => (
              <EvidencePill key={`c-${c}`} type="contact" value={c} />
            ))}
            {suggestion.shared_addresses.map((a) => (
              <EvidencePill key={`a-${a}`} type="address" value={a} />
            ))}
          </div>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="pl-8 pr-2 pb-3 space-y-2">
          {/* Name list */}
          {suggestion.names.length > 0 && (
            <div>
              <div className="text-xs text-muted-foreground font-medium mb-1">
                Names in this group
              </div>
              <div className="space-y-0.5">
                {suggestion.names.map((n, i) => (
                  <div key={i} className="text-sm text-foreground">
                    {n}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          {!merging ? (
            <div className="flex items-center gap-2 pt-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setMerging(true)}
                disabled={acting}
                className="text-xs text-primary bg-accent border-primary/20 hover:bg-accent/80"
              >
                <ArrowsMerge size={13} /> Merge into this group
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDismiss}
                disabled={acting}
                className="text-xs"
              >
                <XCircle size={13} /> Dismiss
              </Button>
            </div>
          ) : (
            <div className="p-3 bg-accent/50 rounded border border-primary/10 space-y-2">
              <div className="text-xs text-muted-foreground font-medium">
                Merge {suggestion.display_name} ({suggestion.group_id}) into
                this group?
              </div>
              <input
                type="text"
                value={mergeReason}
                onChange={(e) => setMergeReason(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleMerge();
                  if (e.key === "Escape") setMerging(false);
                }}
                placeholder="Reason (optional)"
                className="w-full px-2 py-1 text-sm border border-border rounded bg-background focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent"
                autoFocus
              />
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  onClick={handleMerge}
                  disabled={acting}
                  className="text-xs"
                >
                  {acting ? "Merging..." : "Confirm Merge"}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setMerging(false)}
                  className="text-xs"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SuggestedAffiliates({
  groupId,
  onMerge,
}: {
  groupId: string;
  onMerge: () => void;
}) {
  const { suggestions, loading, merge, dismiss } = useSuggestions(groupId);

  if (loading || suggestions.length === 0) return null;

  const handleMerge = async (sourceGroup: string, reason: string) => {
    await merge(sourceGroup, reason);
    onMerge();
  };

  const handleDismiss = async (suggestedGroup: string, reason: string) => {
    await dismiss(suggestedGroup, reason);
  };

  return (
    <Card>
      <CardHeader className="px-5 py-3 border-b border-border">
        <CardTitle className="text-sm font-semibold uppercase tracking-wider">
          Suggested Affiliates ({suggestions.length})
        </CardTitle>
      </CardHeader>
      <CardContent className="px-5 py-2">
        {suggestions.map((s) => (
          <SuggestionRow
            key={s.group_id}
            suggestion={s}
            onMerge={handleMerge}
            onDismiss={handleDismiss}
          />
        ))}
      </CardContent>
    </Card>
  );
}
