import type {
  AuthTokenResponse,
  ChatResponse,
  CreateSessionRequest,
  DeleteResponse,
  DevLoginRequest,
  HealthResponse,
  IndustryOption,
  LearningCommandResponse,
  LearningSyncResponse,
  LearningTask,
  LearningTaskCommandRequest,
  LearningTodayResponse,
  MeResponse,
  ModelOption,
  PasswordLoginRequest,
  PhoneLoginRequest,
  ProviderLoginRequest,
  PrivacyDeletionResponse,
  RegisterRequest,
  ResumeImportRequest,
  ResumeRecord,
  SessionDetail,
  SessionSummary,
  StreamEvent,
  UserDataExport
} from "@interview-agent/shared-types";

export type InterviewApiClientOptions = {
  baseUrl: string;
  token?: string;
  fetchImpl?: typeof fetch;
  clientPlatform?: "web" | "desktop" | "android" | "ios" | "harmony" | "miniapp";
  clientVersion?: string;
};

export class InterviewApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
    readonly details?: unknown
  ) {
    super(message);
    this.name = "InterviewApiError";
  }
}

export class InterviewApiClient {
  private readonly baseUrl: string;
  private readonly token?: string;
  private readonly fetchImpl: typeof fetch;
  private readonly clientPlatform: string;
  private readonly clientVersion: string;

  constructor(options: InterviewApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/+$/u, "");
    this.token = options.token;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.clientPlatform = options.clientPlatform ?? "web";
    this.clientVersion = options.clientVersion ?? "0.1.0";
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

  async register(request: RegisterRequest): Promise<AuthTokenResponse> {
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify(await this.passwordAuthPayload(request))
    });
  }

  async passwordLogin(request: PasswordLoginRequest): Promise<AuthTokenResponse> {
    const body = await this.passwordAuthPayload(request);
    try {
      return await this.request("/auth/login", {
        method: "POST",
        body: JSON.stringify(body)
      });
    } catch (error) {
      if (!(error instanceof InterviewApiError) || error.status !== 401 || !body.password_derived) {
        throw error;
      }
      return this.request("/auth/login", {
        method: "POST",
        body: JSON.stringify(await this.passwordAuthPayload(request, { includePassword: true }))
      });
    }
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

  learningToday(): Promise<LearningTodayResponse> {
    return this.request("/learning/today");
  }

  getLearningTask(taskId: string): Promise<LearningTask> {
    return this.request(`/learning/tasks/${encodeURIComponent(taskId)}`);
  }

  executeLearningTask(
    taskId: string,
    command: LearningTaskCommandRequest,
    idempotencyKey: string
  ): Promise<LearningCommandResponse> {
    return this.request(`/learning/tasks/${encodeURIComponent(taskId)}/commands`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(command)
    });
  }

  pullLearningChanges(cursor?: string, limit = 100): Promise<LearningSyncResponse> {
    const query = new URLSearchParams({ limit: String(limit) });
    if (cursor) query.set("cursor", cursor);
    return this.request(`/learning/sync?${query.toString()}`);
  }

  exportUserData(): Promise<UserDataExport> {
    return this.request("/privacy/export");
  }

  getDeletionRequest(): Promise<PrivacyDeletionResponse> {
    return this.request("/privacy/deletion");
  }

  scheduleDeletion(reason = ""): Promise<PrivacyDeletionResponse["request"]> {
    return this.request("/privacy/deletion", {
      method: "POST",
      body: JSON.stringify({ confirmation: "DELETE", reason })
    });
  }

  cancelDeletion(): Promise<PrivacyDeletionResponse["request"]> {
    return this.request("/privacy/deletion", { method: "DELETE" });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.rawRequest(path, init);
    const text = await response.text();
    const payload = text ? JSON.parse(text) : {};
    if (!response.ok) {
      const details = payload.details ?? (typeof payload.detail === "object" ? payload.detail : undefined);
      const message = payload.message || (typeof payload.detail === "string" ? payload.detail : undefined);
      throw new InterviewApiError(
        message || `Interview Agent API ${response.status}`,
        response.status,
        payload.error || details?.code,
        details
      );
    }
    return payload as T;
  }

  private async rawRequest(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers);
    const requestId = globalThis.crypto.randomUUID();
    headers.set("Content-Type", "application/json");
    headers.set("X-Request-ID", requestId);
    headers.set("X-Client-Request-Id", requestId);
    headers.set("X-Client-Platform", this.clientPlatform);
    headers.set("X-Client-Version", this.clientVersion);
    if (this.token) {
      headers.set("Authorization", `Bearer ${this.token}`);
    }

    return this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers
    });
  }

  private async passwordAuthPayload<T extends PasswordLoginRequest | RegisterRequest>(
    request: T,
    options: { includePassword?: boolean } = {}
  ): Promise<T> {
    const email = String(request.email || "").trim().toLowerCase();
    const password = String(request.password || "").trim();
    const { password: _password, ...rest } = request;
    const derived = await deriveClientPassword(email, password);
    if (derived) {
      const next = {
        ...rest,
        email,
        password_derived: derived,
        password_scheme: "client_sha256_v1"
      };
      if (options.includePassword) {
        return { ...next, password } as T;
      }
      return next as T;
    }
    return { ...rest, email, password } as T;
  }
}

async function deriveClientPassword(email: string, password: string): Promise<string> {
  if (!password || typeof crypto === "undefined" || !crypto.subtle) return "";
  const input = new TextEncoder().encode(`interview-agent:password:v1:${email}\u0000${password}`);
  const digest = await crypto.subtle.digest("SHA-256", input);
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
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
