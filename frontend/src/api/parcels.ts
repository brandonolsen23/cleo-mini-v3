import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "./client";
import type {
  ParcelDetail,
  ParcelListResponse,
  ParcelFiltersResponse,
  ParcelStatsResponse,
} from "../types/parcel";

export function useParcels(params?: Record<string, string>) {
  const [data, setData] = useState<ParcelListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const serialized = params ? JSON.stringify(params) : "";

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const qs = params
      ? "?" + new URLSearchParams(params).toString()
      : "";
    fetchApi<ParcelListResponse>(`/parcels/registry${qs}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [serialized]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load };
}

export function useParcel(arn: string) {
  const [data, setData] = useState<ParcelDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<ParcelDetail>(`/parcels/registry/${arn}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [arn]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load };
}

export function useParcelFilters() {
  const [data, setData] = useState<ParcelFiltersResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<ParcelFiltersResponse>("/parcels/registry/filters")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading };
}

export function useParcelStats() {
  const [data, setData] = useState<ParcelStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi<ParcelStatsResponse>("/parcels/registry/stats")
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading };
}
