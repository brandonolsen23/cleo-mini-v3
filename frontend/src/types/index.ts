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
/* Entity types                                                        */
/* ------------------------------------------------------------------ */

/** Entity summary from /api/owners/browse */
export interface EntityBrowseItem {
  id: string;
  name: string;
  display_name: string | null;
  link_id: string | null;
  property_count: number;
  buy_count: number;
  sell_count: number;
  cities: string[];
  total_value: number;
  total_sell_value: number;
  owned_value: number;
  latest_date: string;
  contacts: string[];
  corp_address_cities: string[];
  phones: string[];
  all_names: string[];
  alt_name_groups: string[][];
}

/** Paginated response from /api/owners/browse */
export interface EntityBrowseResponse {
  results: EntityBrowseItem[];
  total: number;
  page: number;
  per_page: number;
}

/** Filter options from /api/owners/filters */
export interface EntityFiltersResponse {
  cities: string[];
  max_property_count: number;
  total_owners: number;
}

/** Corp address */
export interface EntityAddress {
  canonical: string;
  city?: string;
  lat?: number;
  lng?: number;
  rt_ids: string[];
  entity_names: string[];
}

/** Contact entry */
export interface EntityContact {
  name: string;
  phone: string;
  source_ids: string[];
}

/** Property in entity portfolio */
export interface EntityProperty {
  property_id: string;
  address: string;
  city: string;
  sale_price: number | null;
  sale_date: string;
  rt_id: string;
}

/** Transaction entry (buy or sell) */
export interface EntityTxn {
  property_id: string;
  address: string;
  city: string;
  sale_price: number | null;
  sale_date: string;
  rt_id: string;
  entity_name?: string;
  alternate_names?: string[];
  contact?: string;
  phone?: string;
  phones?: string[];
  corp_address?: { canonical: string; city?: string; lat?: number; lng?: number } | null;
  attention?: string;
  is_owned?: boolean;
}

/** Alternate name with provenance */
export interface EntityNameEvidence {
  value: string;
  rt_ids: string[];
}

/** Full entity detail from /api/owners/{id} */
export interface EntityDetail {
  id: string;
  name: string;
  display_name: string | null;
  link_id: string | null;
  normalized_names: string[];
  all_names: string[];
  aliases: EntityNameEvidence[];
  company_lines: EntityNameEvidence[];
  contacts: EntityContact[];
  corp_addresses: EntityAddress[];
  phones: string[];
  properties: EntityProperty[];
  property_count: number;
  buy_transactions: EntityTxn[];
  buy_count: number;
  seller_transactions: EntityTxn[];
  sell_count: number;
  cities: string[];
  total_value: number;
  total_sell_value: number;
  latest_date: string;
  earliest_date: string;
}

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
