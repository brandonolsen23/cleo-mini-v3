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
  | "active_deal"
  | "in_negotiation"
  | "under_contract"
  | "closed_won"
  | "lost_cancelled"
  // legacy
  | "lead"
  | "contacted"
  | "qualifying"
  | "negotiating"
  | "closed_lost";

/** Active stages for new deals */
export const DEAL_STAGES: DealStage[] = [
  "active_deal",
  "in_negotiation",
  "under_contract",
  "closed_won",
  "lost_cancelled",
];

export const STAGE_LABELS: Record<DealStage, string> = {
  active_deal: "Active Deal",
  in_negotiation: "In Negotiation",
  under_contract: "Under Contract",
  closed_won: "Closed / Won",
  lost_cancelled: "Lost / Cancelled",
  lead: "Lead",
  contacted: "Contacted",
  qualifying: "Qualifying",
  negotiating: "Negotiating",
  closed_lost: "Closed Lost",
};
