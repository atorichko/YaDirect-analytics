export type Me = {
  id: string;
  full_name: string;
  email: string;
  role: "admin" | "specialist";
  is_active: boolean;
};

export type AdAccount = {
  id: string;
  external_id: string;
  name: string;
  login: string;
  platform: string;
  timezone: string;
  is_active: boolean;
  last_audit_at: string | null;
};

export type Campaign = {
  id: string;
  name: string | null;
  status: string | null;
};

export type Finding = {
  id: string;
  account_id: string;
  campaign_external_id: string | null;
  group_external_id: string | null;
  ad_external_id: string | null;
  rule_code: string;
  rule_name: string;
  level: string;
  severity: "warning" | "high" | "critical";
  issue_location: string;
  impact_ru: string;
  recommendation_ru: string;
  status: "new" | "existing" | "fixed" | "reopened" | "ignored" | "false_positive";
  suspected_sabotage: boolean;
  created_at: string;
};

export type JobResponse = {
  task_id: string;
  task_name: string;
  status: string;
};
