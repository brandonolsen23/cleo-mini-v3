import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Trash, Check, X, CircleNotch, MagnifyingGlass } from "@phosphor-icons/react";
import { useKeywords, useKeywordMatches } from "../../api/keywords";
import { useParties } from "../../api/parties";
import type { KeywordMatch } from "../../types/keyword";
import type { PartySummary } from "../../types/party";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const FIELD_COLORS: Record<string, string> = {
  names: "bg-blue-100 text-blue-800",
  aliases: "bg-muted text-foreground",
  alternate_names: "bg-purple-100 text-purple-800",
  contacts: "bg-orange-100 text-orange-800",
};

const FIELD_LABELS: Record<string, string> = {
  names: "name",
  aliases: "alias",
  alternate_names: "alt name",
  contacts: "contact",
};

function FieldPill({ field }: { field: string }) {
  return (
    <span
      className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
        FIELD_COLORS[field] || "bg-muted text-muted-foreground"
      }`}
    >
      {FIELD_LABELS[field] || field}
    </span>
  );
}

function HighlightedSnippet({ text, keyword }: { text: string; keyword: string }) {
  if (!keyword) return <>{text}</>;
  const idx = text.toLowerCase().indexOf(keyword.toLowerCase());
  if (idx === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, idx)}
      <span className="bg-yellow-200 font-medium text-foreground">
        {text.slice(idx, idx + keyword.length)}
      </span>
      {text.slice(idx + keyword.length)}
    </>
  );
}

// ---------------------------------------------------------------------------
// Party picker — searchable dropdown of existing party groups
// ---------------------------------------------------------------------------

function PartyPicker({
  parties,
  value,
  onChange,
}: {
  parties: PartySummary[];
  value: PartySummary | null;
  onChange: (party: PartySummary | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return parties
      .filter(
        (p) =>
          p.display_name.toLowerCase().includes(q) ||
          p.group_id.toLowerCase().includes(q)
      )
      .slice(0, 20);
  }, [query, parties]);

  const handleSelect = useCallback(
    (party: PartySummary) => {
      onChange(party);
      setQuery("");
      setOpen(false);
    },
    [onChange]
  );

  if (value) {
    return (
      <div className="flex items-center gap-2">
        <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-accent border border-border rounded-lg text-sm">
          <span className="font-medium text-foreground">{value.display_name}</span>
          <span className="text-xs text-muted-foreground font-mono">{value.group_id}</span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onChange(null)}
            className="ml-1 h-auto w-auto p-0.5 text-muted-foreground hover:text-foreground"
          >
            <X size={14} />
          </Button>
        </span>
      </div>
    );
  }

  return (
    <div ref={ref} className="relative">
      <div className="relative">
        <MagnifyingGlass
          size={14}
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="text"
          placeholder="Search parent company..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => query.trim() && setOpen(true)}
          className="pl-8 pr-3 py-2 w-72 h-9 text-sm"
        />
      </div>
      {open && filtered.length > 0 && (
        <div className="absolute z-50 mt-1 w-80 max-h-60 overflow-auto bg-background border border-border rounded-lg shadow-lg">
          {filtered.map((p) => (
            <button
              key={p.group_id}
              onClick={() => handleSelect(p)}
              className="w-full text-left px-3 py-2 hover:bg-muted/50 transition-colors flex items-center gap-2"
            >
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-foreground truncate block">
                  {p.display_name}
                </span>
              </div>
              <span className="text-xs text-muted-foreground font-mono flex-none">
                {p.group_id}
              </span>
              <span className="text-xs text-muted-foreground flex-none">
                {p.transaction_count} txns
              </span>
            </button>
          ))}
        </div>
      )}
      {open && query.trim() && filtered.length === 0 && (
        <div className="absolute z-50 mt-1 w-80 bg-background border border-border rounded-lg shadow-lg px-3 py-2 text-sm text-muted-foreground">
          No matching party groups
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Match row
// ---------------------------------------------------------------------------

function MatchRow({
  match,
  keyword,
  parentLabel,
  parentGroupId,
  onReview,
}: {
  match: KeywordMatch;
  keyword: string;
  parentLabel: string;
  parentGroupId: string;
  onReview: (groupId: string, decision: "confirmed" | "denied") => void;
}) {
  const reviewed = match.review === "confirmed" || match.review === "denied";
  // Don't show the parent group itself in results
  if (match.group_id === parentGroupId) return null;

  return (
    <div
      className={cn(
        "flex items-center gap-4 px-6 py-3 border-b border-border",
        reviewed && "opacity-60"
      )}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Link
            to={`/parties/${match.group_id}`}
            className="text-sm font-medium text-primary hover:text-primary/80 hover:underline"
          >
            {match.display_name}
          </Link>
          <span className="text-xs text-muted-foreground font-mono">{match.group_id}</span>
          <span className="text-xs text-muted-foreground">{match.transaction_count} txns</span>
        </div>

        <div className="flex items-center gap-1.5 mt-1">
          {match.matched_fields.map((f) => (
            <FieldPill key={f} field={f} />
          ))}
          <span className="text-xs text-muted-foreground ml-1">
            {match.matched_snippets.map((snippet, i) => (
              <span key={i}>
                {i > 0 && <span className="mx-1 text-muted-foreground/40">|</span>}
                <HighlightedSnippet text={snippet} keyword={keyword} />
              </span>
            ))}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-2 flex-none">
        {match.review === "confirmed" ? (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-green-700 bg-green-50 rounded">
            <Check size={12} /> Yes, associated
          </span>
        ) : match.review === "denied" ? (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-destructive bg-red-50 rounded">
            <X size={12} /> Not associated
          </span>
        ) : (
          <>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onReview(match.group_id, "confirmed")}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 h-auto text-xs font-medium text-green-700 bg-green-50 hover:bg-green-100"
              title={`Yes, ${match.display_name} is associated with ${parentLabel}`}
            >
              <Check size={14} /> Yes
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onReview(match.group_id, "denied")}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 h-auto text-xs font-medium text-destructive bg-red-50 hover:bg-red-100"
              title={`No, ${match.display_name} is not associated with ${parentLabel}`}
            >
              <X size={14} /> No
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function KeywordsPage() {
  const { data: keywords, loading, error, addKeyword, deleteKeyword } = useKeywords();
  const { data: allParties, loading: partiesLoading } = useParties();
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);
  const {
    data: matches,
    loading: matchesLoading,
    reviewMatch,
  } = useKeywordMatches(selectedKeyword);

  const [newKeyword, setNewKeyword] = useState("");
  const [selectedParent, setSelectedParent] = useState<PartySummary | null>(null);
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState("");

  const handleAdd = async () => {
    if (!newKeyword.trim() || !selectedParent) return;
    setAdding(true);
    setAddError("");
    try {
      await addKeyword(
        newKeyword.trim(),
        selectedParent.display_name,
        selectedParent.group_id
      );
      setSelectedKeyword(newKeyword.trim());
      setNewKeyword("");
      setSelectedParent(null);
    } catch (e: any) {
      setAddError(e.message);
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (kw: string) => {
    if (!confirm(`Delete keyword "${kw}" and all its reviews?`)) return;
    await deleteKeyword(kw);
    if (selectedKeyword === kw) setSelectedKeyword(null);
  };

  const handleReview = async (groupId: string, decision: "confirmed" | "denied") => {
    try {
      await reviewMatch(groupId, decision);
    } catch (e: any) {
      console.error("Review failed:", e);
    }
  };

  const selectedMeta = keywords.find((k) => k.keyword === selectedKeyword);
  const parentLabel = selectedMeta?.display_name || selectedKeyword || "";
  const parentGroupId = selectedMeta?.parent_group_id || "";

  const reviewedCount = matches.filter(
    (m) => m.review === "confirmed" || m.review === "denied"
  ).length;
  const unreviewedMatches = matches.filter(
    (m) =>
      m.group_id !== parentGroupId &&
      m.review !== "confirmed" &&
      m.review !== "denied"
  );
  const reviewedMatches = matches.filter(
    (m) =>
      m.group_id !== parentGroupId &&
      (m.review === "confirmed" || m.review === "denied")
  );
  const visibleCount = unreviewedMatches.length + reviewedMatches.length;

  if (loading || partiesLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-destructive">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="flex-none px-6 py-4 bg-background border-b border-border">
        <h1 className="text-lg font-semibold text-foreground">Brand Keywords</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Search party data by keyword and review which groups are associated with a parent company
        </p>
      </div>

      {/* Add keyword */}
      <div className="flex-none px-6 py-4 bg-muted border-b border-border">
        <div className="flex items-center gap-3">
          <PartyPicker
            parties={allParties}
            value={selectedParent}
            onChange={setSelectedParent}
          />
          <Input
            type="text"
            placeholder="Search term (e.g. H&R)"
            value={newKeyword}
            onChange={(e) => setNewKeyword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            className="w-48 h-9 text-sm"
          />
          <Button
            onClick={handleAdd}
            disabled={adding || !newKeyword.trim() || !selectedParent}
            size="sm"
            className="gap-1.5"
          >
            {adding ? (
              <CircleNotch size={14} className="animate-spin" />
            ) : (
              <Plus size={14} />
            )}
            Add
          </Button>
          {addError && <span className="text-sm text-destructive">{addError}</span>}
        </div>

        {/* Keyword pills */}
        {keywords.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mt-3">
            {keywords.map((kw) => (
              <button
                key={kw.keyword}
                onClick={() => setSelectedKeyword(kw.keyword)}
                className={cn(
                  "group inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors",
                  selectedKeyword === kw.keyword
                    ? "bg-primary text-primary-foreground"
                    : "bg-background text-foreground border border-border hover:border-primary hover:text-primary"
                )}
              >
                <span>{kw.display_name || kw.keyword}</span>
                <span
                  className={cn(
                    "text-xs",
                    selectedKeyword === kw.keyword
                      ? "text-primary-foreground/60"
                      : "text-muted-foreground"
                  )}
                >
                  "{kw.keyword}"
                </span>
                <span
                  className={cn(
                    "text-xs",
                    selectedKeyword === kw.keyword
                      ? "text-primary-foreground/60"
                      : "text-muted-foreground"
                  )}
                >
                  {kw.reviewed_count}/{kw.match_count}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(kw.keyword);
                  }}
                  className={cn(
                    "ml-0.5 p-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity",
                    selectedKeyword === kw.keyword
                      ? "hover:bg-primary/80"
                      : "hover:bg-muted"
                  )}
                  title="Delete keyword"
                >
                  <Trash size={12} />
                </button>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Matches */}
      <div className="flex-1 overflow-auto">
        {!selectedKeyword ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            {keywords.length === 0
              ? "Add a keyword above to get started"
              : "Select a keyword to view matches"}
          </div>
        ) : matchesLoading ? (
          <div className="flex items-center justify-center h-32">
            <CircleNotch size={20} className="animate-spin text-muted-foreground" />
          </div>
        ) : visibleCount === 0 ? (
          <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
            No matches found for "{selectedKeyword}"
          </div>
        ) : (
          <>
            {/* Context banner */}
            <div className="px-6 py-3 bg-accent border-b border-border">
              <p className="text-sm text-foreground">
                Is each group below associated with{" "}
                <Link
                  to={`/parties/${parentGroupId}`}
                  className="font-semibold underline hover:text-primary"
                >
                  {parentLabel}
                </Link>
                <span className="text-muted-foreground text-xs ml-1 font-mono">
                  {parentGroupId}
                </span>
                ?
              </p>
              <p className="text-xs text-primary mt-0.5">
                {visibleCount} matches found — {reviewedCount} reviewed
                {unreviewedMatches.length > 0 && (
                  <span className="ml-1 text-amber-600 font-medium">
                    ({unreviewedMatches.length} pending)
                  </span>
                )}
              </p>
            </div>

            {/* Unreviewed first */}
            {unreviewedMatches.map((m) => (
              <MatchRow
                key={m.group_id}
                match={m}
                keyword={selectedKeyword}
                parentLabel={parentLabel}
                parentGroupId={parentGroupId}
                onReview={handleReview}
              />
            ))}

            {/* Reviewed section */}
            {reviewedMatches.length > 0 && unreviewedMatches.length > 0 && (
              <div className="px-6 py-2 bg-muted border-y border-border text-xs text-muted-foreground font-medium uppercase tracking-wider">
                Reviewed ({reviewedMatches.length})
              </div>
            )}
            {reviewedMatches.map((m) => (
              <MatchRow
                key={m.group_id}
                match={m}
                keyword={selectedKeyword}
                parentLabel={parentLabel}
                parentGroupId={parentGroupId}
                onReview={handleReview}
              />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
