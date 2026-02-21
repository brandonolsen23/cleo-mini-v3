import { useEffect, useState } from "react";
import { fetchApi } from "./client";
import type { TransactionSummary, TransactionDetail } from "../types/transaction";

export function useTransactions() {
  const [data, setData] = useState<TransactionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<TransactionSummary[]>("/transactions")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

export function useTransaction(rtId: string) {
  const [data, setData] = useState<TransactionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchApi<TransactionDetail>(`/active/${rtId}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [rtId]);

  return { data, loading, error };
}
