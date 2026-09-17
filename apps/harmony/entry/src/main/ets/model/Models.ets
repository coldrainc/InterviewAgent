export interface IndustryOption {
  value: string;
  label: string;
  description: string;
  production_signals: string[];
  recommended_focus_areas: string[];
}

export interface AuthTokenResponse {
  access_token: string;
  refresh_token?: string;
  token_type: string;
  expires_at: number;
  tenant_id: string;
  user_id: string;
  platform: string;
  display_name: string;
  trial_uses_remaining: number;
  credit_balance: string;
}

export interface LearningAction {
  command: string;
  label: string;
}

export interface LearningTask {
  id: string;
  title: string;
  task_type: string;
  status: string;
  version: number;
  done: boolean;
  elapsed_minutes?: number;
  primary_action: LearningAction;
  link_payload?: LearningTaskTarget;
}

export interface LearningTaskTarget {
  plan_id?: string;
  day_id?: string;
  task_id?: string;
  category?: string;
  question_id?: string;
  mode?: string;
  focus?: string;
}

export interface LearningTodaySummary {
  tasks: LearningTask[];
  total_tasks: number;
  tasks_done: number;
}

export interface LearningStreak {
  current_streak: number;
}

export interface LearningAdvice {
  text?: string;
}

export interface LearningNextAction {
  title?: string;
  reason?: string;
  kind?: string;
}

export interface LearningTodayResponse {
  today?: LearningTodaySummary;
  streak?: LearningStreak;
  advice?: LearningAdvice;
  next_best_action?: LearningNextAction;
}

export interface ReviewPlan {
  id: string;
  title: string;
  subtitle?: string;
  status: string;
  total_days?: number;
  completed_tasks?: number;
  total_tasks?: number;
}

export interface PlanGenerateRequest {
  title: string;
  target_role: string;
  seniority: string;
  total_days: number;
  hours_per_day: number;
  focus_areas: string[];
  resume_id?: string;
  use_history: boolean;
}

export interface PlanGenerateResponse {
  plan_id: string;
}

export interface ReviewCheckinResponse {
  streak?: LearningStreak;
}

export interface InterviewKitQuestion {
  key?: string;
  title: string;
  dimension?: string;
}

export interface InterviewKit {
  id: string;
  title: string;
  target_role: string;
  seniority?: string;
  duration_minutes: number;
  version: number;
  questions?: InterviewKitQuestion[];
}

export interface InterviewKitRequest {
  title: string;
  target_role: string;
  seniority: string;
  duration_minutes: number;
  dimensions: string[];
}

export interface AccountResponse {
  tenant_id: string;
  user_id: string;
  display_name: string;
  email?: string;
  platform: string;
  trial_uses_remaining: number;
  credit_balance: string;
  credit_balance_micros: number;
}

export interface UserSettingsResponse {
  default_interview_mode: string;
}

export interface PracticeCategory {
  value: string;
  label: string;
  description: string;
  subjects: string[];
}

export interface PracticeQuestion {
  id: string;
  practice_category: string;
  exam_year: number;
  exam_name: string;
  subject: string;
  question_type: string;
  prompt: string;
  choices: string[];
  answer?: string;
  explanation?: string;
  difficulty: string;
}

export interface PracticeQuestionListResponse {
  items: PracticeQuestion[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
  next_offset?: number;
}

export interface PracticeAttemptResponse {
  question_id: string;
  correct?: boolean;
  score: number;
  feedback: string;
  reference_answer: string;
  explanation: string;
  suggestions: string[];
  elapsed_seconds?: number;
}

export interface ImportResultResponse {
  created: number;
  updated: number;
  total: number;
}

export interface ResumeRecord {
  id: string;
  filename: string;
  file_type: string;
  summary: string;
  text: string;
  truncated: boolean;
  created_at: string;
  updated_at: string;
}

export interface SessionSummary {
  id: string;
  resume_id?: string;
  mode: string;
  industry: string;
  candidate_name: string;
  target_role: string;
  seniority: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail {
  id: string;
  turns: TurnPayload[];
}

export interface TurnPayload {
  interviewer?: string;
  candidate?: string;
}

export interface CreateSessionRequest {
  offline: boolean;
  web_search: boolean;
  mode: string;
  industry: string;
  target_role: string;
  seniority: string;
  interview_goal: string;
  focus_areas: string[];
  resume_id?: string;
  plan_task_id?: string;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  completed: boolean;
  fallback_used: boolean;
  guardrails: string[];
}

export interface ChatMessage {
  role: 'user' | 'agent' | 'system';
  text: string;
}

export interface StreamEvent {
  event: string;
  data: Record<string, Object>;
}

export interface IdentifiableRecord {
  id: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
  platform: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  platform: string;
}

export interface UserSettingsUpdateRequest {
  default_interview_mode: string;
}

export interface RechargeRequest {
  amount_credits: string;
  payment_provider: string;
  external_order_id: string;
}

export interface LearningTaskCommandRequest {
  action: string;
  expected_version: number;
}

export interface ReviewCheckinRequest {
  elapsed_minutes: number;
  note: string;
}

export interface PracticeAttemptRequest {
  question_id: string;
  answer: string;
  elapsed_seconds: number;
}

export interface ResumeImportRequest {
  filename: string;
  content_base64: string;
}

export interface ChatMessageRequest {
  message: string;
}

export interface ErrorResponse {
  detail?: string;
}
