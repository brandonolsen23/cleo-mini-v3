export interface ContactSummary {
  contact_id: string;
  name: string;
  transaction_count: number;
  entity_count: number;
  phones: string[];
  roles: { buyer: number; seller: number };
  first_active_iso: string;
  last_active_iso: string;
  sample_entities: string[];
  alt_entities: string[];
  _search_text: string;
}

export interface ContactDetail {
  contact_id: string;
  name: string;
  phones: string[];
  addresses: string[];
  transaction_count: number;
  entity_count: number;
  first_active_iso: string;
  last_active_iso: string;
  appearances: ContactAppearance[];
  entities: string[];
  party_groups: { group_id: string; display_name: string; transaction_count: number }[];
}

export interface ContactAppearance {
  rt_id: string;
  role: string;
  entity_name: string;
  sale_date_iso: string;
  sale_price: string;
  prop_address: string;
  prop_city: string;
  phone: string;
  address: string;
}
