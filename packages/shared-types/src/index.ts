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

export type PasswordCredentialPayload = {
  email: string;
  password?: string;
  password_derived?: string;
  password_scheme?: "client_sha256_v1" | string;
  tenant_id?: string;
  platform?: string;
};

export type RegisterRequest = PasswordCredentialPayload & {
  display_name?: string;
};

export type PasswordLoginRequest = PasswordCredentialPayload;

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

export type LearningTaskStatus = "todo" | "in_progress" | "completed" | "blocked" | "skipped" | "expired";
export type LearningTaskAction = "start" | "complete" | "reopen" | "verify";

export type LearningTaskTarget = {
  plan_id: string;
  day_id: string;
  task_id: string;
  category?: string;
  question_id?: string;
  mode?: string;
  focus?: string;
  [key: string]: unknown;
};

export type LearningTask = {
  id: string;
  task_key: string;
  title: string;
  task_type: "interview" | "practice" | "review" | "material" | "checkin" | string;
  status: LearningTaskStatus;
  version: number;
  done: boolean;
  elapsed_minutes: number;
  verification: Record<string, unknown>;
  link_payload: LearningTaskTarget;
  primary_action?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type LearningTodayResponse = {
  contract_version: "learning.today.v1";
  today?: { tasks: LearningTask[]; total_tasks: number; tasks_done: number; [key: string]: unknown } | null;
  next_best_action?: Record<string, unknown> | null;
  risks: unknown[];
  [key: string]: unknown;
};

export type LearningTaskCommandRequest = {
  action: LearningTaskAction;
  expected_version?: number;
  elapsed_minutes?: number;
  mastery_score?: number;
  note?: string;
  evidence?: Record<string, unknown>;
};

export type LearningCommandResponse = {
  task: LearningTask;
  receipt: Record<string, unknown>;
  idempotent_replay: boolean;
};

export type LearningSyncEvent = {
  id: string;
  task_id: string;
  action: LearningTaskAction | string;
  occurred_at: string;
  [key: string]: unknown;
};

export type LearningSyncResponse = {
  schema_version: 1;
  authority: "server";
  events: LearningSyncEvent[];
  next_cursor?: string | null;
  has_more: boolean;
  server_time: string;
  bootstrap?: { today: string } | null;
};

export type DataDeletionRequest = {
  id: string;
  status: "scheduled" | "cancelled" | "executed";
  reason?: string | null;
  scope: Record<string, unknown>;
  requested_at: string;
  execute_after: string;
  cancelled_at?: string | null;
  executed_at?: string | null;
};

export type PrivacyDeletionResponse = {
  request: DataDeletionRequest | null;
  cooling_off_days: number;
};

export type UserDataExport = {
  schema_version: number;
  exported_at: string;
  tenant_id: string;
  user_id: string;
  excluded: string[];
  data: Record<string, Record<string, unknown[]>>;
};
