import { useCallback, useEffect, useState } from "react";
import { fetchApi, mutateApi } from "./client";
import type { CrmContact, CrmContactDetail, DealSummary } from "../types/crm";

// ---------------------------------------------------------------------------
// CRM Contacts
// ---------------------------------------------------------------------------

export function useCrmContacts() {
  const [data, setData] = useState<CrmContact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    fetchApi<CrmContact[]>("/crm/contacts")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(reload, [reload]);

  return { data, loading, error, reload };
}

export function useCrmContact(crmId: string) {
  const [data, setData] = useState<CrmContactDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<CrmContactDetail>(`/crm/contacts/${crmId}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [crmId]);

  useEffect(reload, [reload]);

  return { data, loading, error, reload };
}

export function useCrmContactByComputed(computedId: string | undefined) {
  const [data, setData] = useState<CrmContact | null>(null);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!computedId) return;
    setLoading(true);
    setNotFound(false);
    fetchApi<CrmContact>(`/crm/contacts/by-computed/${encodeURIComponent(computedId)}`)
      .then(setData)
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [computedId]);

  return { data, loading, notFound };
}

export async function createCrmContact(body: Partial<CrmContact>) {
  return mutateApi<CrmContact>("/crm/contacts", "POST", body);
}

export async function updateCrmContact(crmId: string, body: Partial<CrmContact>) {
  return mutateApi<CrmContact>(`/crm/contacts/${crmId}`, "PUT", body);
}

export async function deleteCrmContact(crmId: string) {
  return mutateApi<{ ok: boolean }>(`/crm/contacts/${crmId}`, "DELETE");
}

// ---------------------------------------------------------------------------
// Deals
// ---------------------------------------------------------------------------

export function useDeals() {
  const [data, setData] = useState<DealSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    fetchApi<DealSummary[]>("/crm/deals")
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(reload, [reload]);

  return { data, loading, error, reload };
}

export function useDeal(dealId: string) {
  const [data, setData] = useState<DealSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<DealSummary>(`/crm/deals/${dealId}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [dealId]);

  useEffect(reload, [reload]);

  return { data, loading, error, reload };
}

export function usePropertyDeals(propId: string | undefined) {
  const [data, setData] = useState<DealSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(() => {
    if (!propId) return;
    setLoading(true);
    fetchApi<DealSummary[]>(`/crm/properties/${propId}/deals`)
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, [propId]);

  useEffect(reload, [reload]);

  return { data, loading, reload };
}

export async function createDeal(body: Partial<DealSummary>) {
  return mutateApi<DealSummary>("/crm/deals", "POST", body);
}

export async function updateDeal(dealId: string, body: Partial<DealSummary>) {
  return mutateApi<DealSummary>(`/crm/deals/${dealId}`, "PUT", body);
}

export async function deleteDeal(dealId: string) {
  return mutateApi<{ ok: boolean }>(`/crm/deals/${dealId}`, "DELETE");
}
