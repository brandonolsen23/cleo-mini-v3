export interface ParcelBrand {
  name: string;
  type: string;
  lat: number;
  lng: number;
}

export interface ParcelTransaction {
  rt_id: string;
  date: string;
  price: number | null;
  buyer: string;
  seller: string;
}

export interface ParcelAssessment {
  value: number | null;
  property_code: string;
  property_description: string;
  legal_desc: string;
  zoning: string;
  frontage: string;
  owner: string;
  owner_address: string;
}

export interface ParcelSummary {
  arn: string;
  pid: string | null;
  pin: string | null;
  city: string | null;
  address: string;
  addresses: string[];
  population: number | null;
  zoning: string | null;
  area_sqm: number | null;
  brand_count: number;
  brands: string[];
  transaction_count: number;
  latest_price: number | null;
  latest_date: string | null;
  latest_buyer: string | null;
  has_assessment: boolean;
  sources: string[];
  centroid: [number, number] | null;
}

export interface ParcelDetail {
  arn: string;
  pid: string | null;
  pin: string | null;
  city: string | null;
  addresses: string[];
  area_sqm: number | null;
  zoning: string | null;
  population: number | null;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon | null;
  centroid: [number, number] | null;
  brands: ParcelBrand[];
  transactions: ParcelTransaction[];
  assessment: ParcelAssessment | null;
  discovered_via: string;
  sources: string[];
}

export interface ParcelListResponse {
  total: number;
  offset: number;
  limit: number;
  results: ParcelSummary[];
}

export interface ParcelFilter {
  name: string;
  count: number;
}

export interface ParcelFiltersResponse {
  cities: ParcelFilter[];
  brands: ParcelFilter[];
}

export interface ParcelStatsResponse {
  meta: {
    total: number;
    generated_at: string;
    sources: Record<string, number>;
    stats: Record<string, number>;
  };
  city_counts: Record<string, number>;
  total_parcels: number;
}
