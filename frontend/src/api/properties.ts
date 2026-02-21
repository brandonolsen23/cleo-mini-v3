import { useEffect, useState } from "react";
import { fetchApi } from "./client";
import type { PropertySummary, PropertyDetail } from "../types/property";

export function useProperties() {
  const [data, setData] = useState<PropertySummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<PropertySummary[]>("/properties")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

export function useProperty(propId: string) {
  const [data, setData] = useState<PropertyDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchApi<PropertyDetail>(`/properties/${propId}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [propId]);

  return { data, loading, error };
}
