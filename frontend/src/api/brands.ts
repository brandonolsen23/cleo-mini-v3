import { useEffect, useState } from "react";
import { fetchApi } from "./client";
import type { BrandStore } from "../types/brand";

export function useBrands() {
  const [data, setData] = useState<BrandStore[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<BrandStore[]>("/brands")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}
