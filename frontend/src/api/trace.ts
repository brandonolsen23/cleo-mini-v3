import { useState } from "react";
import { fetchApi } from "./client";

export interface TraceResult {
  id: string;
  source: "realtrack" | "geowarehouse" | "brand";
  stages: {
    ingest?: Record<string, unknown>;
    parsed?: Record<string, unknown>;
    normalized?: Record<string, unknown>;
    expanded?: Record<string, unknown>;
    geocoded?: Record<string, Record<string, unknown>>;
    property?: Record<string, unknown>;
    parcel?: Record<string, unknown>;
    compiled?: Record<string, unknown>;
  };
}

export interface SearchResult {
  id: string;
  source: string;
  label: string;
}

export function useTrace() {
  const [data, setData] = useState<TraceResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const trace = (id: string) => {
    setLoading(true);
    setError(null);
    setData(null);
    fetchApi<TraceResult>(`/trace/${encodeURIComponent(id)}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return { data, loading, error, trace };
}

export function useTraceSearch() {
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  const search = (query: string) => {
    if (query.length < 2) {
      setResults([]);
      return;
    }
    setSearching(true);
    fetchApi<SearchResult[]>(`/trace/search/${encodeURIComponent(query)}`)
      .then(setResults)
      .catch(() => setResults([]))
      .finally(() => setSearching(false));
  };

  return { results, searching, search };
}
