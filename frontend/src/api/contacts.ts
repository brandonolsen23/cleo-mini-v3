import { useEffect, useState } from "react";
import { fetchApi } from "./client";
import type { ContactSummary, ContactDetail } from "../types/contact";

export function useContacts() {
  const [data, setData] = useState<ContactSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchApi<ContactSummary[]>("/contacts")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

export function useContact(contactId: string) {
  const [data, setData] = useState<ContactDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchApi<ContactDetail>(`/contacts/${encodeURIComponent(contactId)}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [contactId]);

  return { data, loading, error };
}
