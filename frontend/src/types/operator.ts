export interface OperatorSummary {
  op_id: string;
  slug: string;
  name: string;
  url: string;
  contacts_count: number;
  properties_count: number;
  photos_count: number;
  pending_property_matches: number;
  confirmed_property_matches: number;
  pending_party_matches: number;
  confirmed_party_matches: number;
  crawled_pages: number;
  updated: string;
}

export interface OperatorContact {
  name: string;
  title: string | null;
  email: string | null;
  phone: string | null;
}

export interface ExtractedProperty {
  address: string;
  city: string;
  province: string;
  plaza_name: string | null;
  size_sqft: string | null;
  year_built: string | null;
  tenants: string[];
  description: string | null;
}

export interface OperatorPhoto {
  url: string;
  caption: string | null;
  property_context: string | null;
}

export interface PropertyMatch {
  extracted_address: string;
  extracted_city: string;
  prop_id: string | null;
  prop_address?: string;
  prop_city?: string;
  confidence: number;
  status: "pending" | "confirmed" | "rejected" | "no_match";
  reason?: string;
  registry_address?: string;
  registry_city?: string;
  registry_sources?: string[];
  registry_transaction_count?: number;
}

export interface PartyMatch {
  group_id: string;
  party_display_name: string;
  match_type: string;
  matched_name?: string;
  matched_contact?: string;
  confidence: number;
  status: "pending" | "confirmed" | "rejected";
  party_type?: string;
  party_transaction_count?: number;
  party_names?: string[];
}

export interface OperatorDetail {
  op_id: string;
  slug: string;
  name: string;
  url: string;
  legal_names: string[];
  description: string;
  contacts: OperatorContact[];
  extracted_properties: ExtractedProperty[];
  photos: OperatorPhoto[];
  property_matches: PropertyMatch[];
  party_matches: PartyMatch[];
  created: string;
  updated: string;
}

export interface OperatorStats {
  total_operators: number;
  total_contacts: number;
  total_extracted_properties: number;
  total_photos: number;
  property_matches: {
    pending: number;
    confirmed: number;
    rejected: number;
  };
  party_matches: {
    pending: number;
    confirmed: number;
  };
}

export interface LinkedOperator {
  op_id: string;
  name: string;
  slug: string;
  url: string;
}
