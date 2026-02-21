import { useEffect, useRef, useState } from "react";

export interface SearchHit {
  id: string;
  label: string;
  sublabel: string;
}

export interface SearchResults {
  transactions: SearchHit[];
  properties: SearchHit[];
  parties: SearchHit[];
  contacts: SearchHit[];
}

const EMPTY: SearchResults = {
  transactions: [],
  properties: [],
  parties: [],
  contacts: [],
};

export function useSearch(query: string, debounceMs = 300) {
  const [results, setResults] = useState<SearchResults>(EMPTY);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults(EMPTY);
      setLoading(false);
      return;
    }

    setLoading(true);
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch(
          `/api/search?q=${encodeURIComponent(trimmed)}&limit=5`,
          { signal: controller.signal },
        );
        if (res.ok) {
          setResults(await res.json());
        }
      } catch {
        // aborted or network error — ignore
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }, debounceMs);

    return () => {
      clearTimeout(timer);
      abortRef.current?.abort();
    };
  }, [query, debounceMs]);

  return { results, loading };
}
