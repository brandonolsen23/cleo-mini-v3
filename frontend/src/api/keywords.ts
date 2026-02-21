import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "./client";
import type { KeywordSummary, KeywordMatch } from "../types/keyword";

export function useKeywords() {
  const [data, setData] = useState<KeywordSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<KeywordSummary[]>("/keywords")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const addKeyword = useCallback(
    async (keyword: string, displayName: string, parentGroupId: string) => {
      const res = await fetch("/api/keywords", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword, display_name: displayName, parent_group_id: parentGroupId }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Failed: ${res.status}`);
      }
      reload();
    },
    [reload]
  );

  const deleteKeyword = useCallback(
    async (keyword: string) => {
      const res = await fetch(`/api/keywords/${encodeURIComponent(keyword)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
      reload();
    },
    [reload]
  );

  return { data, loading, error, reload, addKeyword, deleteKeyword };
}

export function useKeywordMatches(keyword: string | null) {
  const [data, setData] = useState<KeywordMatch[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    if (!keyword) {
      setData([]);
      return;
    }
    setLoading(true);
    setError(null);
    fetchApi<KeywordMatch[]>(`/keywords/${encodeURIComponent(keyword)}/matches`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [keyword]);

  useEffect(() => {
    reload();
  }, [reload]);

  const reviewMatch = useCallback(
    async (groupId: string, decision: "confirmed" | "denied", notes: string = "") => {
      if (!keyword) return;
      const res = await fetch(
        `/api/keywords/${encodeURIComponent(keyword)}/review/${groupId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ decision, notes }),
        }
      );
      if (!res.ok) throw new Error(`Review failed: ${res.status}`);
      // Update local state
      setData((prev) =>
        prev.map((m) =>
          m.group_id === groupId ? { ...m, review: decision, review_notes: notes } : m
        )
      );
    },
    [keyword]
  );

  return { data, loading, error, reload, reviewMatch };
}
