import http from '@ohos.net.http';
import { AccountResponse, AuthTokenResponse, ChatResponse, CreateSessionRequest, IndustryOption, StreamEvent } from '../model/Models';

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

  async createSession(request: CreateSessionRequest): Promise<ChatResponse> {
    return await this.request('/sessions', 'POST', request) as ChatResponse;
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
        method: method === 'POST' ? http.RequestMethod.POST : http.RequestMethod.GET,
        header: headers,
        extraData: body ? JSON.stringify(body) : undefined,
        expectDataType: http.HttpDataType.STRING
      });
      const status = response.responseCode;
      const text = String(response.result ?? '{}');
      const payload = JSON.parse(text);
      if (status < 200 || status >= 300) {
        throw new Error(String(payload.detail ?? `HTTP ${status}`));
      }
      return text;
    } finally {
      client.destroy();
    }
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
