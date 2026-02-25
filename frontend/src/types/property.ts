export interface PropertySummary {
  prop_id: string;
  address: string;
  city: string;
  municipality: string;
  population: number | null;
  province: string;
  postal_code: string;
  lat: number | null;
  lng: number | null;
  transaction_count: number;
  rt_ids: string[];
  sources: string[];
  has_photos: boolean;
  primary_photo: string | null;
  latest_sale_year: string;
  earliest_sale_year: string;
  latest_sale_date: string;
  latest_sale_date_iso: string;
  latest_sale_price: string;
  owner: string;
  has_contact: boolean;
  has_phone: boolean;
  building_sf: string;
  site_area: string;
  brands: string[];
  has_gw_data: boolean;
  pipeline_status: string;
  pin_status: string;
  _search_text: string;
}

export interface LinkedOperator {
  op_id: string;
  name: string;
  slug: string;
  url: string;
}

export interface PropertyDetail {
  prop_id: string;
  address: string;
  city: string;
  municipality: string;
  province: string;
  postal_code: string;
  lat: number | null;
  lng: number | null;
  rt_ids: string[];
  transaction_count: number;
  sources: string[];
  created: string;
  updated: string;
  transactions: PropertyTransaction[];
  brands: string[];
  gw_records: GWRecord[];
  linked_operators: LinkedOperator[];
}

export interface PropertyTransaction {
  rt_id: string;
  sale_price: string;
  sale_date: string;
  sale_date_iso: string;
  seller: string;
  buyer: string;
  seller_group_id?: string | null;
  buyer_group_id?: string | null;
  buyer_contact: string;
  buyer_contact_id?: string | null;
  buyer_phone: string;
  building_sf: string;
  ppsf: string | null;
  photos: string[];
}

// GeoWarehouse types

export interface GWRecord {
  gw_id: string;
  pin: string;
  gw_source_file: string;
  summary: GWSummary;
  registry: GWRegistry;
  site_structure: GWSiteStructure;
  sales_history: GWSale[];
}

export interface GWSummary {
  address: string;
  owner_names: string;
  last_sale_price: string;
  last_sale_date: string;
  lot_size_area: string;
  lot_size_perimeter: string;
  legal_description: string;
}

export interface GWRegistry {
  gw_address: string;
  land_registry_office: string;
  owner_names: string;
  ownership_type: string;
  land_registry_status: string;
  property_type: string;
  registration_type: string;
  pin: string;
}

export interface GWSiteStructure {
  arn: string;
  frontage: string;
  zoning: string;
  depth: string;
  property_description: string;
  property_code: string;
  current_assessed_value: string;
  valuation_date: string;
  assessment_legal_description: string;
  site_area: string;
  property_address: string;
  municipality: string;
  owner_names_mpac: string;
  owner_mailing_address: string;
}

export interface GWSale {
  sale_date: string;
  sale_amount: string;
  type: string;
  party_to: string;
  notes: string;
}
