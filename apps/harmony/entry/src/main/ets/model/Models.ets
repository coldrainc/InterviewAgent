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

export interface CreateSessionRequest {
  offline: boolean;
  web_search: boolean;
  mode: string;
  industry: string;
  target_role: string;
  seniority: string;
  interview_goal: string;
  focus_areas: string[];
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
