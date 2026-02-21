export interface KeywordSummary {
  keyword: string;
  display_name: string;
  parent_group_id: string;
  created: string;
  match_count: number;
  reviewed_count: number;
}

export interface KeywordMatch {
  group_id: string;
  display_name: string;
  transaction_count: number;
  matched_fields: string[];
  matched_snippets: string[];
  is_company: boolean;
  review: string;
  review_notes: string;
}
