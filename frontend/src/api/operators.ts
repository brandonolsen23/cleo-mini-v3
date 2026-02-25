import { useCallback, useEffect, useState } from "react";
import { fetchApi, mutateApi } from "./client";
import type {
  OperatorSummary,
  OperatorDetail,
  OperatorStats,
} from "../types/operator";

export function useOperators() {
  const [data, setData] = useState<OperatorSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    fetchApi<OperatorSummary[]>("/operators")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(reload, [reload]);

  return { data, loading, error, reload };
}

export function useOperator(opId: string) {
  const [data, setData] = useState<OperatorDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<OperatorDetail>(`/operators/${opId}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [opId]);

  useEffect(reload, [reload]);

  return { data, loading, error, reload };
}

export function useOperatorStats() {
  const [data, setData] = useState<OperatorStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<OperatorStats>("/operators/stats")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return { data, loading };
}

export async function confirmPropertyMatch(opId: string, idx: number) {
  return mutateApi<{ ok: boolean }>(`/operators/${opId}/property-matches/${idx}/confirm`, "POST");
}

export async function rejectPropertyMatch(opId: string, idx: number) {
  return mutateApi<{ ok: boolean }>(`/operators/${opId}/property-matches/${idx}/reject`, "POST");
}

export async function confirmPartyMatch(opId: string, idx: number) {
  return mutateApi<{ ok: boolean }>(`/operators/${opId}/party-matches/${idx}/confirm`, "POST");
}

export async function rejectPartyMatch(opId: string, idx: number) {
  return mutateApi<{ ok: boolean }>(`/operators/${opId}/party-matches/${idx}/reject`, "POST");
}

export async function addOperator(name: string, url: string) {
  return mutateApi<{ slug: string; name: string; url: string }>(
    "/operators/config",
    "POST",
    { name, url },
  );
}

export async function removeOperator(slug: string) {
  return mutateApi<{ ok: boolean }>(`/operators/config/${slug}`, "DELETE");
}

export async function runOperatorPipeline(
  command: string,
  slug?: string,
): Promise<Response> {
  return fetch("/api/operators/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command, slug }),
  });
}

export async function killOperatorPipeline() {
  return mutateApi<{ ok: boolean }>("/operators/kill", "POST");
}
