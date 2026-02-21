import { useEffect, useState, useCallback } from "react";
import { fetchApi } from "./client";

interface Feedback {
  has_issue: boolean;
  notes: string;
  date?: string;
}

const EMPTY: Feedback = { has_issue: false, notes: "" };

export function useFeedback(entityId: string) {
  const [data, setData] = useState<Feedback>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setLoading(true);
    setSaved(false);
    fetchApi<Feedback | Record<string, never>>(`/feedback/${entityId}`)
      .then((res) => {
        if (res && "has_issue" in res) {
          setData(res as Feedback);
        } else {
          setData(EMPTY);
        }
      })
      .catch(() => setData(EMPTY))
      .finally(() => setLoading(false));
  }, [entityId]);

  const save = useCallback(
    async (feedback: Feedback) => {
      setSaving(true);
      setSaved(false);
      try {
        await fetch(`/api/feedback/${entityId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(feedback),
        });
        setData(feedback);
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } finally {
        setSaving(false);
      }
    },
    [entityId]
  );

  return { data, loading, saving, saved, save };
}
