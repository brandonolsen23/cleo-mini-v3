export interface OutreachFilters {
  cities: string[];
  brands: string[];
  brand_categories: string[];
  sale_date_from: string;
  sale_date_to: string;
  price_min: number | null;
  price_max: number | null;
  owner_type: string | null;
  exclude_contacted: boolean;
  exclude_by_owner: boolean;
}

export interface OutreachItem {
  prop_id: string;
  address: string;
  city: string;
  brands: string[];
  latest_sale_date: string;
  latest_sale_date_iso: string;
  latest_sale_price: string;
  owner: string;
  owner_type: string;
  owner_group_id: string;
  corporate_address: string;
  contact_names: string[];
  phones: string[];
  contact_status: { method: string; outcome?: string | null; date: string } | null;
}

export interface OutreachList {
  list_id: string;
  name: string;
  description: string;
  filters: OutreachFilters;
  prop_ids: string[];
  item_count: number;
  contacted_count?: number;
  created: string;
  updated: string;
}

export interface OutreachListDetail extends OutreachList {
  items: OutreachItem[];
}

export interface OutreachLogEntry {
  entry_id: string;
  list_id: string;
  prop_id: string;
  owner_group_id: string;
  method: string;
  outcome?: string | null;
  date: string;
  notes: string;
  created: string;
}

export interface FilterOptions {
  cities: string[];
  brands: string[];
  brand_categories: Record<string, string>;
  category_labels: Record<string, string>;
}

export type ContactMethod = "mail" | "email" | "called";

export const CONTACT_METHODS: ContactMethod[] = ["mail", "email", "called"];

export const METHOD_LABELS: Record<ContactMethod, string> = {
  mail: "Mail",
  email: "Email",
  called: "Called",
};

export type OutcomeType = "no_answer" | "left_vm" | "sent" | "spoke_with" | "bounced";

export const OUTCOMES: OutcomeType[] = ["no_answer", "left_vm", "sent", "spoke_with", "bounced"];

export const OUTCOME_LABELS: Record<OutcomeType, string> = {
  no_answer: "No Answer",
  left_vm: "Left VM",
  sent: "Sent",
  spoke_with: "Spoke With",
  bounced: "Bounced",
};

export type PipelineStatus =
  | "not_started"
  | "attempted_contact"
  | "interested"
  | "listed"
  | "do_not_contact";

export const PIPELINE_STATUSES: PipelineStatus[] = [
  "not_started",
  "attempted_contact",
  "interested",
  "listed",
  "do_not_contact",
];

export const PIPELINE_STATUS_LABELS: Record<PipelineStatus, string> = {
  not_started: "Not Started",
  attempted_contact: "Attempted Contact",
  interested: "Interested",
  listed: "Listed",
  do_not_contact: "Do Not Contact",
};

/** @deprecated Use PipelineStatus instead */
export type OutreachStatus = PipelineStatus;
/** @deprecated Use PIPELINE_STATUSES instead */
export const OUTREACH_STATUSES = PIPELINE_STATUSES;
/** @deprecated Use PIPELINE_STATUS_LABELS instead */
export const OUTREACH_STATUS_LABELS = PIPELINE_STATUS_LABELS;

export interface PropertyOutreachHistory {
  prop_id: string;
  outreach_status: PipelineStatus;
  entries: OutreachLogEntry[];
}

export const DEFAULT_FILTERS: OutreachFilters = {
  cities: [],
  brands: [],
  brand_categories: [],
  sale_date_from: "",
  sale_date_to: "",
  price_min: null,
  price_max: null,
  owner_type: null,
  exclude_contacted: true,
  exclude_by_owner: false,
};
