import http from '@ohos.net.http';
import buffer from '@ohos.buffer';
import {
  AccountResponse,
  AuthTokenResponse,
  ChatMessageRequest,
  ChatResponse,
  CreateSessionRequest,
  ErrorResponse,
  ImportResultResponse,
  IndustryOption, InterviewKit, InterviewKitRequest, LearningTask, LearningTodayResponse,
  LearningTaskCommandRequest, LoginRequest,
  PlanGenerateRequest, PlanGenerateResponse, ReviewCheckinRequest, ReviewCheckinResponse, ReviewPlan,
  PracticeAttemptRequest,
  PracticeAttemptResponse,
  PracticeCategory,
  PracticeQuestionListResponse,
  RechargeRequest, RegisterRequest, ResumeImportRequest,
  ResumeRecord,
  SessionDetail,
  SessionSummary,
  StreamEvent,
  UserSettingsResponse, UserSettingsUpdateRequest
} from '../model/Models';

export class InterviewApiClient {
  private baseUrl: string;
  private token?: string;

  constructor(baseUrl: string, token?: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.token = token;
  }

  setToken(token?: string): void {
    this.token = token;
  }

  async register(email: string, password: string, displayName: string): Promise<AuthTokenResponse> {
    const body: RegisterRequest = {
      email: email.trim(),
      password: password.trim(),
      display_name: displayName.trim(),
      platform: 'harmony'
    };
    const response = await this.request('/auth/register', 'POST', JSON.stringify(body)) as AuthTokenResponse;
    this.token = response.access_token;
    return response;
  }

  async login(email: string, password: string): Promise<AuthTokenResponse> {
    const body: LoginRequest = {
      email: email.trim(),
      password: password.trim(),
      platform: 'harmony'
    };
    const response = await this.request('/auth/login', 'POST', JSON.stringify(body)) as AuthTokenResponse;
    this.token = response.access_token;
    return response;
  }

  logout(): void {
    this.token = undefined;
  }

  async account(): Promise<AccountResponse> {
    return await this.request('/account', 'GET') as AccountResponse;
  }

  async settings(): Promise<UserSettingsResponse> {
    return await this.request('/settings', 'GET') as UserSettingsResponse;
  }

  async updateDefaultInterviewMode(mode: string): Promise<UserSettingsResponse> {
    const body: UserSettingsUpdateRequest = {
      default_interview_mode: mode
    };
    return await this.request('/settings', 'PUT', JSON.stringify(body)) as UserSettingsResponse;
  }

  async recharge(amountCredits: string): Promise<AccountResponse> {
    const body: RechargeRequest = {
      amount_credits: amountCredits,
      payment_provider: 'harmony-mock',
      external_order_id: `harmony-${Date.now()}`
    };
    return await this.request('/account/recharge', 'POST', JSON.stringify(body)) as AccountResponse;
  }

  async health(): Promise<string> {
    const payload = await this.request('/health', 'GET');
    return String(payload['status'] ?? 'unknown');
  }

  async learningToday(): Promise<LearningTodayResponse> {
    return await this.request('/learning/today', 'GET') as LearningTodayResponse;
  }

  async commandLearningTask(task: LearningTask, action: string): Promise<LearningTask> {
    const body: LearningTaskCommandRequest = { action, expected_version: task.version };
    const response = await this.request(
      `/learning/tasks/${encodeURIComponent(task.id)}/commands`,
      'POST',
      JSON.stringify(body),
      `harmony-${Date.now()}-${task.id}`
    );
    return response['task'] as LearningTask;
  }

  async listReviewPlans(limit: number = 20, offset: number = 0): Promise<ReviewPlan[]> {
    return await this.request(`/review-site/plans?limit=${limit}&offset=${offset}`, 'GET') as ReviewPlan[];
  }

  async generateReviewPlan(body: PlanGenerateRequest): Promise<PlanGenerateResponse> {
    return await this.request('/review-site/planner/generate', 'POST', JSON.stringify(body)) as PlanGenerateResponse;
  }

  async checkin(planId: string, elapsedMinutes: number, note: string): Promise<ReviewCheckinResponse> {
    const body: ReviewCheckinRequest = {
      elapsed_minutes: elapsedMinutes,
      note
    };
    return await this.request(`/review-site/plans/${encodeURIComponent(planId)}/checkin`, 'POST', JSON.stringify(body)) as ReviewCheckinResponse;
  }

  async listInterviewKits(limit: number = 20, offset: number = 0): Promise<InterviewKit[]> {
    return await this.request(`/interviewer-workspace/kits?limit=${limit}&offset=${offset}`, 'GET') as InterviewKit[];
  }

  async createInterviewKit(body: InterviewKitRequest): Promise<InterviewKit> {
    return await this.request('/interviewer-workspace/kits', 'POST', JSON.stringify(body)) as InterviewKit;
  }

  async listIndustries(targetRole: string = 'AI 应用工程师'): Promise<IndustryOption[]> {
    const encoded = encodeURIComponent(targetRole);
    return await this.request(`/metadata/industries?target_role=${encoded}`, 'GET') as IndustryOption[];
  }

  async listPracticeCategories(): Promise<PracticeCategory[]> {
    return await this.request('/practice/categories', 'GET') as PracticeCategory[];
  }

  async listPracticeQuestions(category: string, limit: number = 20, offset: number = 0): Promise<PracticeQuestionListResponse> {
    const encoded = encodeURIComponent(category);
    return await this.request(`/practice/questions?category=${encoded}&limit=${limit}&offset=${offset}`, 'GET') as PracticeQuestionListResponse;
  }

  async seedPracticeQuestions(): Promise<ImportResultResponse> {
    return await this.request('/practice/questions/seed', 'POST') as ImportResultResponse;
  }

  async submitPracticeAttempt(questionId: string, answer: string, elapsedSeconds: number): Promise<PracticeAttemptResponse> {
    const body: PracticeAttemptRequest = {
      question_id: questionId,
      answer,
      elapsed_seconds: elapsedSeconds
    };
    return await this.request('/practice/attempt', 'POST', JSON.stringify(body)) as PracticeAttemptResponse;
  }

  async listResumes(limit: number = 20, offset: number = 0): Promise<ResumeRecord[]> {
    return await this.request(`/resumes?limit=${limit}&offset=${offset}`, 'GET') as ResumeRecord[];
  }

  async importResume(filename: string, text: string): Promise<ResumeRecord> {
    const encoded = buffer.from(text, 'utf-8').toString('base64');
    const body: ResumeImportRequest = {
      filename,
      content_base64: encoded
    };
    return await this.request('/resumes', 'POST', JSON.stringify(body)) as ResumeRecord;
  }

  async deleteResume(id: string): Promise<boolean> {
    const payload = await this.request(`/resumes/${id}`, 'DELETE');
    return Boolean(payload['deleted']);
  }

  async createSession(request: CreateSessionRequest): Promise<ChatResponse> {
    return await this.request('/sessions', 'POST', JSON.stringify(request)) as ChatResponse;
  }

  async listSessions(limit: number = 20, offset: number = 0): Promise<SessionSummary[]> {
    return await this.request(`/sessions?limit=${limit}&offset=${offset}`, 'GET') as SessionSummary[];
  }

  async getSession(id: string): Promise<SessionDetail> {
    return await this.request(`/sessions/${id}`, 'GET') as SessionDetail;
  }

  async deleteSession(id: string): Promise<boolean> {
    const payload = await this.request(`/sessions/${id}`, 'DELETE');
    return Boolean(payload['deleted']);
  }

  async sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
    const body: ChatMessageRequest = { message };
    return await this.request(`/sessions/${sessionId}/messages`, 'POST', JSON.stringify(body)) as ChatResponse;
  }

  async streamMessage(sessionId: string, message: string): Promise<StreamEvent[]> {
    const body: ChatMessageRequest = { message };
    const text = await this.requestText(`/sessions/${sessionId}/stream`, 'POST', JSON.stringify(body));
    return this.parseSse(text);
  }

  private async request(path: string, method: string, body?: string, idempotencyKey?: string): Promise<object> {
    const text = await this.requestText(path, method, body, idempotencyKey);
    return JSON.parse(text);
  }

  private async requestText(path: string, method: string, body?: string, idempotencyKey?: string): Promise<string> {
    const client = http.createHttp();
    const clientRequestId = `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      'X-Request-ID': clientRequestId,
      'X-Client-Request-Id': clientRequestId,
      'X-Client-Platform': 'harmony',
      'X-Client-Version': '0.1.0'
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }
    if (idempotencyKey) headers['Idempotency-Key'] = idempotencyKey;

    try {
      const response = await client.request(`${this.baseUrl}${path}`, {
        method: this.toHttpMethod(method),
        header: headers,
        extraData: body,
        expectDataType: http.HttpDataType.STRING
      });
      const status = response.responseCode;
      const text = String(response.result ?? '{}');
      if (status < 200 || status >= 300) {
        const payload = JSON.parse(text) as ErrorResponse;
        throw new Error(String(payload.detail ?? `HTTP ${status}`));
      }
      return text;
    } finally {
      client.destroy();
    }
  }

  private toHttpMethod(method: string): http.RequestMethod {
    if (method === 'POST') {
      return http.RequestMethod.POST;
    }
    if (method === 'PUT') {
      return http.RequestMethod.PUT;
    }
    if (method === 'DELETE') {
      return http.RequestMethod.DELETE;
    }
    return http.RequestMethod.GET;
  }

  private parseSse(text: string): StreamEvent[] {
    return text
      .split('\n\n')
      .map((block: string) => block.trim())
      .filter((block: string) => Boolean(block))
      .map((block: string): StreamEvent => {
        const lines = block.split('\n');
        const event = lines.find((line: string) => line.startsWith('event:'))?.replace('event:', '').trim() ?? 'message';
        const dataText = lines.find((line: string) => line.startsWith('data:'))?.replace('data:', '').trim() ?? '{}';
        const result: StreamEvent = {
          event,
          data: JSON.parse(dataText) as Record<string, Object>
        };
        return result;
      });
  }
}
