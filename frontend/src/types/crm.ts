export interface CrmContact {
  crm_id: string;
  name: string;
  email: string;
  mobile: string;
  notes: string;
  tags: string[];
  computed_contact_id: string;
  party_group_ids: string[];
  created: string;
  updated: string;
  deal_count?: number;
}

export interface CrmContactDetail extends CrmContact {
  deals: DealSummary[];
}

export interface DealSummary {
  deal_id: string;
  title: string;
  prop_id: string;
  stage: DealStage;
  contact_ids: string[];
  notes: string;
  created: string;
  updated: string;
  property: PropertyRef | null;
  contacts: { crm_id: string; name: string; email?: string; mobile?: string }[];
}

export interface PropertyRef {
  prop_id: string;
  address: string;
  city: string;
}

export type DealStage =
  | "lead"
  | "contacted"
  | "negotiating"
  | "under_contract"
  | "closed_won"
  | "closed_lost";

export const DEAL_STAGES: DealStage[] = [
  "lead",
  "contacted",
  "negotiating",
  "under_contract",
  "closed_won",
  "closed_lost",
];

export const STAGE_LABELS: Record<DealStage, string> = {
  lead: "Lead",
  contacted: "Contacted",
  negotiating: "Negotiating",
  under_contract: "Under Contract",
  closed_won: "Closed Won",
  closed_lost: "Closed Lost",
};
