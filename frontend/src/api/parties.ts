import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "./client";
import type { PartySummary, PartyDetail, PartySuggestion } from "../types/party";

export function useParties() {
  const [data, setData] = useState<PartySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<PartySummary[]>("/parties")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

export function useParty(groupId: string) {
  const [data, setData] = useState<PartyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<PartyDetail>(`/parties/${groupId}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [groupId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const saveOverrides = useCallback(
    async (overrides: { display_name: string; url: string }) => {
      setSaving(true);
      setSaved(false);
      try {
        const res = await fetch(`/api/parties/${groupId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(overrides),
        });
        if (!res.ok) throw new Error(`Save failed: ${res.status}`);
        setData((prev) =>
          prev
            ? {
                ...prev,
                display_name: overrides.display_name || prev.display_name_auto,
                display_name_override: overrides.display_name,
                url: overrides.url,
              }
            : prev
        );
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
      } catch (e: any) {
        setError(e.message);
      } finally {
        setSaving(false);
      }
    },
    [groupId]
  );

  const disconnectName = useCallback(
    async (name: string, targetGroup: string, reason: string) => {
      setSaving(true);
      try {
        const res = await fetch(`/api/parties/${groupId}/disconnect`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, target_group: targetGroup, reason }),
        });
        if (!res.ok) throw new Error(`Disconnect failed: ${res.status}`);
        const result = await res.json();
        reload();
        return result;
      } catch (e: any) {
        setError(e.message);
        return null;
      } finally {
        setSaving(false);
      }
    },
    [groupId, reload]
  );

  const confirmName = useCallback(
    async (name: string) => {
      setSaving(true);
      try {
        const res = await fetch(`/api/parties/${groupId}/confirm`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name }),
        });
        if (!res.ok) throw new Error(`Confirm failed: ${res.status}`);
        setData((prev) =>
          prev
            ? {
                ...prev,
                confirmed_names: [...prev.confirmed_names, name.toUpperCase().replace(/\s+/g, " ").trim()],
              }
            : prev
        );
      } catch (e: any) {
        setError(e.message);
      } finally {
        setSaving(false);
      }
    },
    [groupId]
  );

  return { data, loading, error, saving, saved, saveOverrides, disconnectName, confirmName, reload };
}

export interface KnownAttributes {
  phones: Record<string, string[]>;
  contacts: Record<string, string[]>;
  addresses: Record<string, string[]>;
}

const EMPTY_KNOWN: KnownAttributes = { phones: {}, contacts: {}, addresses: {} };

export function useKnownAttributes() {
  const [data, setData] = useState<KnownAttributes>(EMPTY_KNOWN);

  useEffect(() => {
    fetchApi<KnownAttributes>("/parties/known-attributes")
      .then(setData)
      .catch(() => {});
  }, []);

  return data;
}

export interface GroupingReason {
  type: "phone" | "contact" | "alias";
  value: string;
  linked_names: string[];
  rt_ids: string[];
  detail: string;
}

export function useGroupingReason(groupId: string, name: string | null) {
  const [reasons, setReasons] = useState<GroupingReason[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!name) {
      setReasons([]);
      return;
    }
    setLoading(true);
    fetchApi<GroupingReason[]>(
      `/parties/${groupId}/grouping-reason?name=${encodeURIComponent(name)}`
    )
      .then(setReasons)
      .catch(() => setReasons([]))
      .finally(() => setLoading(false));
  }, [groupId, name]);

  return { reasons, loading };
}

export function useTransactionDetails(rtIds: string[]) {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (rtIds.length === 0) return;
    setLoading(true);
    const idsToFetch = rtIds.filter((id) => !(id in data));
    if (idsToFetch.length === 0) {
      setLoading(false);
      return;
    }
    Promise.all(
      idsToFetch.map((id) =>
        fetchApi<any>(`/active/${id}`)
          .then((res) => ({ id, res }))
          .catch(() => ({ id, res: null }))
      )
    ).then((results) => {
      setData((prev) => {
        const next = { ...prev };
        for (const { id, res } of results) {
          if (res) next[id] = res;
        }
        return next;
      });
      setLoading(false);
    });
  }, [rtIds.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading };
}

export function useSuggestions(groupId: string) {
  const [suggestions, setSuggestions] = useState<PartySuggestion[]>([]);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    fetchApi<PartySuggestion[]>(`/parties/${groupId}/suggestions`)
      .then(setSuggestions)
      .catch(() => setSuggestions([]))
      .finally(() => setLoading(false));
  }, [groupId]);

  useEffect(() => {
    reload();
  }, [reload]);

  const merge = useCallback(
    async (sourceGroup: string, reason: string) => {
      const res = await fetch(`/api/parties/${groupId}/merge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_group: sourceGroup, reason }),
      });
      if (!res.ok) throw new Error(`Merge failed: ${res.status}`);
      // Optimistically remove from local state
      setSuggestions((prev) => prev.filter((s) => s.group_id !== sourceGroup));
      return res.json();
    },
    [groupId]
  );

  const dismiss = useCallback(
    async (suggestedGroup: string, reason: string) => {
      const res = await fetch(`/api/parties/${groupId}/dismiss-suggestion`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ suggested_group: suggestedGroup, reason }),
      });
      if (!res.ok) throw new Error(`Dismiss failed: ${res.status}`);
      // Optimistically remove from local state
      setSuggestions((prev) =>
        prev.filter((s) => s.group_id !== suggestedGroup)
      );
      return res.json();
    },
    [groupId]
  );

  return { suggestions, loading, merge, dismiss, reload };
}
