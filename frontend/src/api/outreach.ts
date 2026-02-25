import { useCallback, useEffect, useState } from "react";
import { fetchApi, mutateApi } from "./client";
import type {
  OutreachList,
  OutreachListDetail,
  OutreachItem,
  OutreachFilters,
  FilterOptions,
  PropertyOutreachHistory,
} from "../types/outreach";

// ---------------------------------------------------------------------------
// Filter options
// ---------------------------------------------------------------------------

export function useFilterOptions() {
  const [data, setData] = useState<FilterOptions>({
    cities: [],
    brands: [],
    brand_categories: {},
    category_labels: {},
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<FilterOptions>("/outreach/filter-options")
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return { data, loading };
}

// ---------------------------------------------------------------------------
// Preview
// ---------------------------------------------------------------------------

export async function previewOutreach(
  filters: OutreachFilters,
): Promise<{ items: OutreachItem[]; total: number }> {
  return mutateApi("/outreach/preview", "POST", { filters });
}

// ---------------------------------------------------------------------------
// Lists
// ---------------------------------------------------------------------------

export function useOutreachLists() {
  const [data, setData] = useState<OutreachList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    fetchApi<OutreachList[]>("/outreach/lists")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(reload, [reload]);

  return { data, loading, error, reload };
}

export function useOutreachList(listId: string) {
  const [data, setData] = useState<OutreachListDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<OutreachListDetail>(`/outreach/lists/${listId}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [listId]);

  useEffect(reload, [reload]);

  return { data, loading, error, reload };
}

export async function createOutreachList(body: {
  name: string;
  description: string;
  filters: OutreachFilters;
  prop_ids: string[];
}) {
  return mutateApi<OutreachList>("/outreach/lists", "POST", body);
}

export async function updateOutreachList(
  listId: string,
  body: { name?: string; description?: string },
) {
  return mutateApi<OutreachList>(`/outreach/lists/${listId}`, "PUT", body);
}

export async function deleteOutreachList(listId: string) {
  return mutateApi<{ ok: boolean }>(`/outreach/lists/${listId}`, "DELETE");
}

// ---------------------------------------------------------------------------
// Contact log
// ---------------------------------------------------------------------------

export async function logContact(body: {
  list_id?: string;
  prop_id: string;
  owner_group_id?: string;
  method: string;
  outcome?: string;
  date: string;
  notes?: string;
}) {
  return mutateApi("/outreach/log", "POST", body);
}

export async function logContactsBulk(body: {
  list_id?: string;
  items: { prop_id: string; owner_group_id: string }[];
  method: string;
  outcome?: string;
  date: string;
  notes?: string;
}) {
  return mutateApi("/outreach/log/bulk", "POST", body);
}

// ---------------------------------------------------------------------------
// Per-property outreach
// ---------------------------------------------------------------------------

export function usePropertyOutreach(propId: string) {
  const [data, setData] = useState<PropertyOutreachHistory | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    fetchApi<PropertyOutreachHistory>(`/outreach/properties/${propId}/history`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [propId]);

  useEffect(reload, [reload]);

  return { data, loading, reload };
}

export async function setOutreachStatus(propId: string, status: string) {
  return mutateApi<{ ok: boolean }>(`/outreach/properties/${propId}/status`, "PUT", { status });
}

export const setPipelineStatus = setOutreachStatus;

export async function convertToDeal(propId: string, body?: { title?: string; contact_ids?: string[] }) {
  return mutateApi<{ deal_id: string }>(`/outreach/properties/${propId}/convert-to-deal`, "POST", body ?? {});
}
