import { useCallback, useEffect, useState } from "react";
import { fetchApi, mutateApi } from "./client";
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

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchApi<PropertyDetail>(`/properties/${propId}`)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [propId]);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load };
}

export function updateProperty(
  propId: string,
  fields: Record<string, string | number>,
) {
  return mutateApi(`/properties/${propId}`, "PATCH", fields);
}

export interface PlacesData {
  prop_id: string;
  place_id?: string;
  text_search_query?: string;
  text_search_at?: string;
  essentials?: {
    types?: string[];
    formattedAddress?: string;
    location?: { latitude: number; longitude: number };
    fetched_at?: string;
  };
  pro?: {
    businessStatus?: string;
    displayName?: { text: string; languageCode: string };
    primaryType?: string;
    googleMapsUri?: string;
    fetched_at?: string;
  };
  enterprise?: {
    rating?: number;
    userRatingCount?: number;
    websiteUri?: string;
    internationalPhoneNumber?: string;
    regularOpeningHours?: {
      periods?: Array<{
        open: { day: number; hour: number; minute: number };
        close: { day: number; hour: number; minute: number };
      }>;
      weekdayDescriptions?: string[];
    };
    fetched_at?: string;
  };
  streetview?: {
    has_coverage: boolean;
    pano_id?: string;
    date?: string;
    checked_at?: string;
    image_fetched?: boolean;
  };
  has_streetview_image?: boolean;
}

export function usePropertyPlaces(propId: string) {
  const [data, setData] = useState<PlacesData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchApi<PlacesData>(`/properties/${propId}/places`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [propId]);

  return { data, loading };
}

export interface Tenant {
  osm_id: string;
  name: string;
  brand?: string;
  tracked_brand?: string;
  match_type?: "confirmed" | "nearby";
  category?: string;
  lat: number;
  lng: number;
  address?: string;
  housenumber?: string;
  phone?: string;
  website?: string;
}

export interface TenantsData {
  prop_id: string;
  confirmed: Tenant[];
  confirmed_count: number;
}

export function usePropertyTenants(propId: string) {
  const [data, setData] = useState<TenantsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetchApi<TenantsData>(`/properties/${propId}/tenants`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [propId]);

  return { data, loading };
}
