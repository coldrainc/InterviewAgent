import http from '@ohos.net.http';
import buffer from '@ohos.buffer';
import {
  AccountResponse,
  AuthTokenResponse,
  ChatResponse,
  CreateSessionRequest,
  ImportResultResponse,
  IndustryOption,
  PracticeAttemptResponse,
  PracticeCategory,
  PracticeQuestionListResponse,
  ResumeRecord,
  SessionDetail,
  SessionSummary,
  StreamEvent,
  UserSettingsResponse
} from '../model/Models';

export class InterviewApiClient {
  private baseUrl: string;
  private token?: string;

  constructor(baseUrl: string, token?: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, '');
    this.token = token;
  }

  async devLogin(userId: string = 'harmony-dev-user'): Promise<AuthTokenResponse> {
    const response = await this.request('/auth/dev-login', 'POST', {
      user_id: userId,
      display_name: '鸿蒙开发用户',
      platform: 'harmony'
    }) as AuthTokenResponse;
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
    return await this.request('/settings', 'PUT', {
      default_interview_mode: mode
    }) as UserSettingsResponse;
  }

  async recharge(amountCredits: string): Promise<AccountResponse> {
    return await this.request('/account/recharge', 'POST', {
      amount_credits: amountCredits,
      payment_provider: 'harmony-mock',
      external_order_id: `harmony-${Date.now()}`
    }) as AccountResponse;
  }

  async health(): Promise<string> {
    const payload = await this.request('/health', 'GET');
    return String(payload['status'] ?? 'unknown');
  }

  async listIndustries(targetRole: string = 'AI 应用工程师'): Promise<IndustryOption[]> {
    const encoded = encodeURIComponent(targetRole);
    return await this.request(`/metadata/industries?target_role=${encoded}`, 'GET') as IndustryOption[];
  }

  async listPracticeCategories(): Promise<PracticeCategory[]> {
    return await this.request('/practice/categories', 'GET') as PracticeCategory[];
  }

  async listPracticeQuestions(category: string, limit: number = 50): Promise<PracticeQuestionListResponse> {
    const encoded = encodeURIComponent(category);
    return await this.request(`/practice/questions?category=${encoded}&limit=${limit}`, 'GET') as PracticeQuestionListResponse;
  }

  async seedPracticeQuestions(): Promise<ImportResultResponse> {
    return await this.request('/practice/questions/seed', 'POST') as ImportResultResponse;
  }

  async submitPracticeAttempt(questionId: string, answer: string, elapsedSeconds: number): Promise<PracticeAttemptResponse> {
    return await this.request('/practice/attempt', 'POST', {
      question_id: questionId,
      answer,
      elapsed_seconds: elapsedSeconds
    }) as PracticeAttemptResponse;
  }

  async listResumes(): Promise<ResumeRecord[]> {
    return await this.request('/resumes', 'GET') as ResumeRecord[];
  }

  async importResume(filename: string, text: string): Promise<ResumeRecord> {
    const encoded = buffer.from(text, 'utf-8').toString('base64');
    return await this.request('/resumes', 'POST', {
      filename,
      content_base64: encoded
    }) as ResumeRecord;
  }

  async deleteResume(id: string): Promise<boolean> {
    const payload = await this.request(`/resumes/${id}`, 'DELETE');
    return Boolean(payload['deleted']);
  }

  async createSession(request: CreateSessionRequest): Promise<ChatResponse> {
    return await this.request('/sessions', 'POST', request) as ChatResponse;
  }

  async listSessions(limit: number = 50): Promise<SessionSummary[]> {
    return await this.request(`/sessions?limit=${limit}`, 'GET') as SessionSummary[];
  }

  async getSession(id: string): Promise<SessionDetail> {
    return await this.request(`/sessions/${id}`, 'GET') as SessionDetail;
  }

  async deleteSession(id: string): Promise<boolean> {
    const payload = await this.request(`/sessions/${id}`, 'DELETE');
    return Boolean(payload['deleted']);
  }

  async sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
    return await this.request(`/sessions/${sessionId}/messages`, 'POST', { message }) as ChatResponse;
  }

  async streamMessage(sessionId: string, message: string): Promise<StreamEvent[]> {
    const text = await this.requestText(`/sessions/${sessionId}/stream`, 'POST', { message });
    return this.parseSse(text);
  }

  private async request(path: string, method: string, body?: object): Promise<object> {
    const text = await this.requestText(path, method, body);
    return JSON.parse(text);
  }

  private async requestText(path: string, method: string, body?: object): Promise<string> {
    const client = http.createHttp();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    };
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await client.request(`${this.baseUrl}${path}`, {
        method: this.toHttpMethod(method),
        header: headers,
        extraData: body ? JSON.stringify(body) : undefined,
        expectDataType: http.HttpDataType.STRING
      });
      const status = response.responseCode;
      const text = String(response.result ?? '{}');
      if (status < 200 || status >= 300) {
        const payload = JSON.parse(text);
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
      .map((block: string) => {
        const lines = block.split('\n');
        const event = lines.find((line: string) => line.startsWith('event:'))?.replace('event:', '').trim() ?? 'message';
        const dataText = lines.find((line: string) => line.startsWith('data:'))?.replace('data:', '').trim() ?? '{}';
        return {
          event,
          data: JSON.parse(dataText) as Record<string, Object>
        };
      });
  }
}
