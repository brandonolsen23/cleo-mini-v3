/** Property summary from /api/properties/browse */
export interface PropertyBrowseItem {
  property_id: string;
  arn: string;
  primary_address: string;
  city: string;
  current_owner: string;
  latest_sale_date: string;
  latest_sale_price: number | null;
  sources: string[];
  transaction_count: number;
  tenants: string[];
  tenant_count: number;
}

/** Paginated response from /api/properties/browse */
export interface BrowseResponse {
  results: PropertyBrowseItem[];
  total: number;
  page: number;
  per_page: number;
}

/** Filter options from /api/properties/filters */
export interface FiltersResponse {
  cities: string[];
  categories: string[];
  brands: string[];
}

/** Transaction within a property detail */
export interface PropertyTransaction {
  rt_id: string;
  sale_date: string;
  sale_price: number | null;
  sale_price_display: string;
  seller_name: string;
  seller_contact: string;
  seller_phone: string;
  seller_phones: string[];
  seller_attention: string;
  seller_aliases: string[];
  seller_company_lines: string[];
  buyer_name: string;
  buyer_contact: string;
  buyer_phone: string;
  buyer_phones: string[];
  buyer_attention: string;
  buyer_aliases: string[];
  buyer_company_lines: string[];
  consideration: {
    cash: number | null;
    assumed_debt: number | null;
    chattels: string;
    verbatim: string;
    chargees: string[];
  };
  broker_name: string;
  broker_phone: string;
  building_sf: number | null;
  site_area: number | null;
  site_area_units: string;
  zoning: string;
  legal_description: string;
  description: string;
  photos: string[];
}

/** Tenant on a property */
export interface PropertyTenant {
  source_id: string;
  source: "brand" | "osm";
  address?: string;
  brand?: string;
  store_name?: string;
  category?: string;
  name?: string;
  phone?: string;
  website?: string;
}

/** Contact on a property */
export interface PropertyContact {
  name: string;
  contact: string;
  phone: string;
  phones: string[];
  role: "seller" | "buyer";
  source_id: string;
}

/** Current owner */
export interface PropertyOwner {
  name: string;
  contact: string;
  phone: string;
  phones: string[];
  attention: string;
  aliases: string[];
  company_lines: string[];
  from_transaction: string;
}

/* ------------------------------------------------------------------ */
/* Group / Contact / CRM types — to be built with anchor layer         */
/* (see docs/anchor-layer-plan.md and docs/definitions.md)             */
/* ------------------------------------------------------------------ */

/** Full property detail from /api/properties/{id} */
export interface PropertyDetail {
  property_id: string;
  arn: string;
  primary_address: string;
  city: string;
  all_addresses: string[];
  centroid_lat: number | null;
  centroid_lng: number | null;
  parcel_method: string;
  parcel_confidence: string;
  source_records: string[];
  sources: string[];
  current_owner: PropertyOwner | null;
  transactions: PropertyTransaction[];
  transaction_count: number;
  latest_transaction: {
    rt_id: string;
    sale_date: string;
    sale_price: number | null;
  } | null;
  all_contacts: PropertyContact[];
  all_party_names: string[];
  tenants: PropertyTenant[];
  building_sf: number | null;
  site_area: number | null;
  site_area_units: string;
  zoning: string;
  legal_description: string;
  broker: string;
  description: string;
  brand_count: number;
  osm_count: number;
  arn_disagreement: boolean;
  pins: string[];
}
