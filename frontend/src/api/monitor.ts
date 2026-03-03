import { useEffect, useState } from "react";
import { fetchApi } from "./client";

export interface MonitorData {
  collected_at: string;
  ingest: Record<string, unknown>;
  parsed: Record<string, unknown>;
  normalized: Record<string, unknown>;
  expanded: Record<string, unknown>;
  geocoded: Record<string, unknown>;
  parcels: Record<string, unknown>;
  properties: Record<string, unknown>;
  geowarehouse: Record<string, unknown>;
  brands: Record<string, unknown>;
  gates: Gate[];
  legacy?: {
    parties: Record<string, unknown>;
  };
}

export interface Gate {
  id: string;
  level: "critical" | "warning" | "info";
  stage: string;
  name: string;
  message: string;
}

export function useMonitor() {
  const [data, setData] = useState<MonitorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<MonitorData>("/monitor")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const refresh = () => {
    setLoading(true);
    setError(null);
    fetchApi<MonitorData>("/monitor")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  return { data, loading, error, refresh };
}
