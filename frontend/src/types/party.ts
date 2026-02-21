export interface PartySummary {
  group_id: string;
  display_name: string;
  is_company: boolean;
  names_count: number;
  names: string[];
  addresses_count: number;
  transaction_count: number;
  buy_count: number;
  sell_count: number;
  owns_count: number;
  contacts: string[];
  phones: string[];
  first_active_iso: string;
  last_active_iso: string;
  has_override: boolean;
  _search_text: string;
}

export interface PartyDetail {
  group_id: string;
  display_name: string;
  display_name_auto: string;
  display_name_override: string;
  url: string;
  is_company: boolean;
  names: string[];
  normalized_names: string[];
  addresses: string[];
  contacts: string[];
  phones: string[];
  aliases: string[];
  appearances: PartyAppearance[];
  transaction_count: number;
  buy_count: number;
  sell_count: number;
  first_active_iso: string;
  last_active_iso: string;
  rt_ids: string[];
  created: string;
  updated: string;
  linked_properties: LinkedProperty[];
  confirmed_names: string[];
}

export interface PartyAppearance {
  rt_id: string;
  role: string;
  name: string;
  sale_date_iso: string;
  sale_price: string;
  prop_address: string;
  prop_city: string;
  photos: string[];
}

export interface LinkedProperty {
  prop_id: string;
  address: string;
  city: string;
  transaction_count: number;
}

export interface PartySuggestion {
  group_id: string;
  display_name: string;
  is_company: boolean;
  transaction_count: number;
  names: string[];
  shared_phones: string[];
  shared_contacts: string[];
  shared_addresses: string[];
  evidence_score: number;
}
