import { useState } from "react";
import { Link } from "react-router-dom";
import { Check, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { PropertyMatch, PartyMatch } from "../../types/operator";

function ConfidenceBadge({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  let variant: "default" | "secondary" | "outline" = "outline";
  let color = "text-muted-foreground";
  if (pct >= 95) {
    color = "text-green-600 border-green-300";
  } else if (pct >= 80) {
    color = "text-amber-600 border-amber-300";
  } else {
    color = "text-red-500 border-red-300";
  }
  return (
    <Badge variant={variant} className={`text-[10px] px-1.5 py-0 ${color}`}>
      {pct}%
    </Badge>
  );
}

function StatusBadge({ status }: { status: string }) {
  if (status === "confirmed") {
    return (
      <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-green-600 border-green-300">
        Confirmed
      </Badge>
    );
  }
  if (status === "rejected") {
    return (
      <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-red-500 border-red-300">
        Rejected
      </Badge>
    );
  }
  if (status === "no_match") {
    return (
      <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-muted-foreground">
        No match
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-amber-600 border-amber-300">
      Pending
    </Badge>
  );
}

export function PropertyMatchCard({
  match,
  index,
  onConfirm,
  onReject,
}: {
  match: PropertyMatch;
  index: number;
  onConfirm: (idx: number) => Promise<void>;
  onReject: (idx: number) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);

  const handleConfirm = async () => {
    setBusy(true);
    try { await onConfirm(index); } finally { setBusy(false); }
  };
  const handleReject = async () => {
    setBusy(true);
    try { await onReject(index); } finally { setBusy(false); }
  };

  return (
    <div className="border border-border rounded-lg p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium">
            {match.extracted_address}, {match.extracted_city}
          </div>
          {match.prop_id && (
            <div className="text-xs text-muted-foreground mt-0.5">
              <Link to={`/properties/${match.prop_id}`} className="text-blue-600 hover:underline" onClick={(e) => e.stopPropagation()}>
                {match.prop_id}
              </Link>
              {" \u2014 "}
              {match.registry_address || match.prop_address}, {match.registry_city || match.prop_city}
              {match.registry_transaction_count != null && (
                <span className="ml-1">({match.registry_transaction_count} txns)</span>
              )}
            </div>
          )}
          {match.reason && !match.prop_id && (
            <div className="text-xs text-muted-foreground mt-0.5">{match.reason}</div>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <ConfidenceBadge confidence={match.confidence} />
          <StatusBadge status={match.status} />
        </div>
      </div>
      {match.status === "pending" && match.prop_id && (
        <div className="flex gap-2 pt-1">
          <Button size="sm" variant="outline" disabled={busy} onClick={handleConfirm} className="h-7 text-xs text-green-600 border-green-300 hover:bg-green-50">
            <Check size={12} className="mr-1" /> Confirm
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={handleReject} className="h-7 text-xs text-red-500 border-red-300 hover:bg-red-50">
            <X size={12} className="mr-1" /> Reject
          </Button>
        </div>
      )}
    </div>
  );
}

export function PartyMatchCard({
  match,
  index,
  onConfirm,
  onReject,
}: {
  match: PartyMatch;
  index: number;
  onConfirm: (idx: number) => Promise<void>;
  onReject: (idx: number) => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);

  const handleConfirm = async () => {
    setBusy(true);
    try { await onConfirm(index); } finally { setBusy(false); }
  };
  const handleReject = async () => {
    setBusy(true);
    try { await onReject(index); } finally { setBusy(false); }
  };

  return (
    <div className="border border-border rounded-lg p-3 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium">
            <Link to={`/parties/${match.group_id}`} className="text-blue-600 hover:underline" onClick={(e) => e.stopPropagation()}>
              {match.party_display_name}
            </Link>
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">
            {match.match_type.replace(/_/g, " ")}
            {match.matched_name && <span> ({match.matched_name})</span>}
            {match.matched_contact && <span> (contact: {match.matched_contact})</span>}
            {match.party_transaction_count != null && (
              <span className="ml-1">{"\u2014"} {match.party_transaction_count} txns</span>
            )}
          </div>
          {match.party_names && match.party_names.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {match.party_names.map((n, i) => (
                <Badge key={i} variant="secondary" className="text-[10px] px-1.5 py-0">
                  {n}
                </Badge>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <ConfidenceBadge confidence={match.confidence} />
          <StatusBadge status={match.status} />
        </div>
      </div>
      {match.status === "pending" && (
        <div className="flex gap-2 pt-1">
          <Button size="sm" variant="outline" disabled={busy} onClick={handleConfirm} className="h-7 text-xs text-green-600 border-green-300 hover:bg-green-50">
            <Check size={12} className="mr-1" /> Confirm
          </Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={handleReject} className="h-7 text-xs text-red-500 border-red-300 hover:bg-red-50">
            <X size={12} className="mr-1" /> Reject
          </Button>
        </div>
      )}
    </div>
  );
}
