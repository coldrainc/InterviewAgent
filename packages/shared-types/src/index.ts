export type InterviewMode = "interviewer" | "candidate";

export type Industry =
  | "internet"
  | "ai_application"
  | "ecommerce"
  | "fintech"
  | "enterprise_saas";

export type HealthResponse = {
  status: "ok";
  qdrant_url: string;
  embedding_service_url: string;
  database: string;
  storage_backend: string;
  object_storage_backend: string;
  object_storage_bucket: string;
  auth_required: boolean;
};

export type AuthTokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_at: number;
  tenant_id: string;
  user_id: string;
  platform: string;
  display_name: string;
};

export type DevLoginRequest = {
  user_id?: string;
  tenant_id?: string;
  display_name?: string;
  platform?: string;
};

export type ProviderLoginRequest = {
  code: string;
  platform?: string;
  tenant_id?: string;
  display_name?: string;
};

export type PhoneLoginRequest = {
  phone: string;
  verification_code: string;
  tenant_id?: string;
  platform?: string;
};

export type MeResponse = {
  tenant_id: string;
  user_id: string;
  platform: string;
  authenticated: boolean;
};

export type IndustryOption = {
  value: Industry;
  label: string;
  description: string;
  scenario_keywords: string[];
  interview_focus: string[];
  production_signals: string[];
  risk_controls: string[];
  follow_up_angles: string[];
  answer_expectations: string[];
  recommended_focus_areas: string[];
};

export type ModelOption = {
  id: string;
  provider: string;
  display_name: string;
  category: string;
  runtime_supported: boolean;
  runtime_integration: string;
  input_credits_per_1m: string;
  output_credits_per_1m: string;
  input_usd_per_1m: string;
  output_usd_per_1m: string;
  context_window?: number | null;
  notes?: string;
};

export type ResumeRecord = {
  id: string;
  filename: string;
  file_type: "pdf" | "markdown" | string;
  summary: string;
  text: string;
  truncated: boolean;
  created_at: string;
  updated_at: string;
  source_path?: string | null;
};

export type CreateSessionRequest = {
  offline?: boolean;
  web_search?: boolean;
  mode?: InterviewMode;
  industry?: Industry;
  candidate_name?: string;
  target_role?: string;
  seniority?: string;
  resume_summary?: string;
  resume_text?: string;
  project_experience?: string;
  interview_goal?: string;
  focus_areas?: string[];
  resume_id?: string;
};

export type ChatResponse = {
  session_id: string;
  message: string;
  completed: boolean;
  fallback_used: boolean;
  guardrails: string[];
};

export type SessionSummary = {
  id: string;
  resume_id?: string | null;
  mode: InterviewMode;
  industry: Industry;
  candidate_name: string;
  target_role: string;
  seniority: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type SessionTurn = {
  stage: string;
  interviewer: string;
  candidate?: string | null;
  created_at?: string;
  updated_at?: string;
  fallback_used?: boolean;
};

export type SessionDetail = SessionSummary & {
  config: Record<string, unknown>;
  state: Record<string, unknown>;
  turns: SessionTurn[];
};

export type ResumeImportRequest = {
  filename: string;
  content_base64: string;
  source_path?: string;
};

export type DeleteResponse = {
  deleted: boolean;
};

export type StreamEventName = "tool.notice" | "guardrail.notice" | "message.delta" | "message.done" | "error";

export type StreamEvent<T = unknown> = {
  event: StreamEventName | string;
  data: T;
};
