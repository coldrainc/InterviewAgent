import type {
  AuthTokenResponse,
  ChatResponse,
  CreateSessionRequest,
  DeleteResponse,
  DevLoginRequest,
  HealthResponse,
  IndustryOption,
  MeResponse,
  ModelOption,
  PhoneLoginRequest,
  ProviderLoginRequest,
  ResumeImportRequest,
  ResumeRecord,
  SessionDetail,
  SessionSummary,
  StreamEvent
} from "@interview-agent/shared-types";

export type InterviewApiClientOptions = {
  baseUrl: string;
  token?: string;
  fetchImpl?: typeof fetch;
};

export class InterviewApiClient {
  private readonly baseUrl: string;
  private readonly token?: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: InterviewApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/u, "");
    this.token = options.token;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  health(): Promise<HealthResponse> {
    return this.request("/health");
  }

  devLogin(request: DevLoginRequest = {}): Promise<AuthTokenResponse> {
    return this.request("/auth/dev-login", {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  wechatLogin(request: ProviderLoginRequest): Promise<AuthTokenResponse> {
    return this.request("/auth/wechat/login", {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  appleLogin(request: ProviderLoginRequest): Promise<AuthTokenResponse> {
    return this.request("/auth/apple/login", {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  phoneLogin(request: PhoneLoginRequest): Promise<AuthTokenResponse> {
    return this.request("/auth/phone/login", {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  me(): Promise<MeResponse> {
    return this.request("/me");
  }

  listIndustries(targetRole = "AI 应用工程师"): Promise<IndustryOption[]> {
    return this.request(`/metadata/industries?target_role=${encodeURIComponent(targetRole)}`);
  }

  listModels(): Promise<ModelOption[]> {
    return this.request("/metadata/models");
  }

  listResumes(): Promise<ResumeRecord[]> {
    return this.request("/resumes");
  }

  getResume(resumeId: string): Promise<ResumeRecord> {
    return this.request(`/resumes/${encodeURIComponent(resumeId)}`);
  }

  importResume(request: ResumeImportRequest): Promise<ResumeRecord> {
    return this.request("/resumes", {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  deleteResume(resumeId: string): Promise<DeleteResponse> {
    return this.request(`/resumes/${encodeURIComponent(resumeId)}`, { method: "DELETE" });
  }

  createSession(request: CreateSessionRequest): Promise<ChatResponse> {
    return this.request("/sessions", {
      method: "POST",
      body: JSON.stringify(request)
    });
  }

  listSessions(limit = 50): Promise<SessionSummary[]> {
    return this.request(`/sessions?limit=${limit}`);
  }

  getSession(sessionId: string): Promise<SessionDetail> {
    return this.request(`/sessions/${encodeURIComponent(sessionId)}`);
  }

  deleteSession(sessionId: string): Promise<DeleteResponse> {
    return this.request(`/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  }

  sendMessage(sessionId: string, message: string): Promise<ChatResponse> {
    return this.request(`/sessions/${encodeURIComponent(sessionId)}/messages`, {
      method: "POST",
      body: JSON.stringify({ message })
    });
  }

  async streamMessage(
    sessionId: string,
    message: string,
    onEvent: (event: StreamEvent) => void
  ): Promise<void> {
    const response = await this.rawRequest(`/sessions/${encodeURIComponent(sessionId)}/stream`, {
      method: "POST",
      body: JSON.stringify({ message })
    });
    const text = await response.text();
    parseSseEvents(text).forEach(onEvent);
  }

  transcript(sessionId: string): Promise<{ transcript: string }> {
    return this.request(`/sessions/${encodeURIComponent(sessionId)}/transcript`);
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.rawRequest(path, init);
    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) {
      throw new Error(payload.detail || `Interview Agent API ${response.status}`);
    }
    return payload as T;
  }

  private async rawRequest(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    headers.set("Content-Type", "application/json");
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    return this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers
    });
  }
}

export function createInterviewApiClient(options: InterviewApiClientOptions): InterviewApiClient {
  return new InterviewApiClient(options);
}

export function parseSseEvents(text: string): StreamEvent[] {
  return text
    .split(/\n\n/u)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const event = block
        .split("\n")
        .find((line) => line.startsWith("event:"))
        ?.replace(/^event:\s*/u, "") || "message";
      const dataLine = block
        .split("\n")
        .find((line) => line.startsWith("data:"))
        ?.replace(/^data:\s*/u, "") || "{}";
      return {
        event,
        data: JSON.parse(dataLine)
      };
    });
}
