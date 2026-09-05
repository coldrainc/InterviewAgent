export interface IndustryOption {
  value: string;
  label: string;
  description: string;
  production_signals: string[];
  recommended_focus_areas: string[];
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  expires_at: number;
  tenant_id: string;
  user_id: string;
  platform: string;
  display_name: string;
  trial_uses_remaining: number;
  credit_balance: string;
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
