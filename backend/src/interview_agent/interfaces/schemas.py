from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class SessionRequest(BaseModel):
    offline: bool = False
    web_search: bool = False
    mode: str | None = None
    industry: str | None = None
    candidate_name: str | None = None
    target_role: str | None = None
    seniority: str | None = None
    resume_summary: str | None = None
    resume_text: str | None = None
    project_experience: str | None = None
    interview_goal: str | None = None
    focus_areas: list[str] | None = None
    resume_id: str | None = None
    plan_task_id: str | None = None
    interviewer_kit_id: str | None = None
    model_id: str | None = None
    thinking_enabled: bool | None = None
    reasoning_effort: str | None = Field(default=None, pattern="^(low|medium|high|max)$")


class MessageRequest(BaseModel):
    message: str


class SessionRewindRequest(BaseModel):
    turn_index: int = Field(..., ge=1)


class DevLoginRequest(BaseModel):
    user_id: str = "dev-user"
    tenant_id: str | None = None
    display_name: str = "本地开发用户"
    platform: str = "dev"


class ProviderLoginRequest(BaseModel):
    code: str
    platform: str | None = None
    tenant_id: str | None = None
    display_name: str | None = None


class PhoneLoginRequest(BaseModel):
    phone: str
    verification_code: str
    tenant_id: str | None = None
    platform: str = "mobile"


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str = ""
    token_type: str = "bearer"
    expires_at: int
    refresh_expires_at: int = 0
    tenant_id: str
    user_id: str
    platform: str
    role: str = "user"
    display_name: str = ""
    trial_uses_remaining: int = 0
    credit_balance: str = "0"


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=512)
    tenant_id: str | None = Field(default=None, max_length=64)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=512)
    revoke_all: bool = False


class RoleGrantRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    role: str = Field(pattern="^(user|support|admin)$")
    metadata: dict = Field(default_factory=dict)


class RoleRevokeRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=128)
    role: str = Field(pattern="^(support|admin)$")


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(default="", max_length=128)
    password_derived: str = Field(default="", max_length=256)
    password_scheme: str = Field(default="", max_length=64)
    display_name: str = ""
    tenant_id: str | None = None
    platform: str = "web"

    @field_validator("email", mode="before")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return str(value or "").strip().lower()

    @field_validator("password", mode="before")
    @classmethod
    def _clean_password(cls, value: str) -> str:
        return str(value or "").strip()


class PasswordLoginRequest(BaseModel):
    email: str
    password: str = ""
    password_derived: str = Field(default="", max_length=256)
    password_scheme: str = Field(default="", max_length=64)
    tenant_id: str | None = None
    platform: str = "web"

    @field_validator("email", mode="before")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        return str(value or "").strip().lower()

    @field_validator("password", mode="before")
    @classmethod
    def _clean_password(cls, value: str) -> str:
        return str(value or "").strip()


class MeResponse(BaseModel):
    tenant_id: str
    user_id: str
    platform: str
    role: str = "user"
    authenticated: bool
    trial_uses_remaining: int = 0
    credit_balance: str = "0"
    credit_balance_micros: int = 0


class UserSettingsResponse(BaseModel):
    default_interview_mode: str = "interviewer"


class UpdateUserSettingsRequest(BaseModel):
    default_interview_mode: str | None = Field(default=None, pattern="^(interviewer|candidate)$")


class JobCreateRequest(BaseModel):
    job_type: str = Field(default="workflow", pattern="^(workflow|evaluation|multi_agent)$")
    title: str | None = Field(default=None, max_length=255)
    input: dict = Field(default_factory=dict)


class WorkflowRunRequest(BaseModel):
    workflow_type: str = Field(default="workflow", pattern="^(workflow|multi_agent)$")
    title: str | None = Field(default=None, max_length=255)
    input: dict = Field(default_factory=dict)


class EvalRunCreateRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    cases: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class AccountResponse(BaseModel):
    tenant_id: str
    user_id: str
    display_name: str
    email: str | None = None
    platform: str
    role: str = "user"
    trial_uses_remaining: int
    credit_balance: str
    credit_balance_micros: int
    settings: UserSettingsResponse = Field(default_factory=UserSettingsResponse)


class RechargeRequest(BaseModel):
    amount_credits: Decimal = Field(gt=0)
    payment_provider: str = "mock"
    external_order_id: str | None = None
    target_user_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class PaymentWebhookPayload(BaseModel):
    tenant_id: str = "default"
    user_id: str
    amount_credits: Decimal = Field(gt=0)
    payment_provider: str = Field(min_length=1, max_length=64)
    external_order_id: str = Field(min_length=1, max_length=128)
    status: str = "paid"
    currency: str = "CREDIT"
    metadata: dict = Field(default_factory=dict)


class CreatePaymentOrderRequest(BaseModel):
    amount_credits: Decimal = Field(gt=0)
    plan_code: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9_-]{1,63}$")
    payment_provider: str = Field(min_length=1, max_length=64)
    external_order_id: str | None = Field(default=None, max_length=128)
    metadata: dict = Field(default_factory=dict)


class PaymentOrderResponse(BaseModel):
    tenant_id: str
    user_id: str
    amount_credits: str
    amount_micros: int
    credited_amount: str
    credited_amount_micros: int
    payment_provider: str
    external_order_id: str
    status: str
    created: bool
    pay_url: str | None = None
    code_url: str | None = None
    metadata: dict = Field(default_factory=dict)


class PaymentWebhookResponse(BaseModel):
    accepted: bool
    applied: bool
    status: str
    external_order_id: str
    account: AccountResponse | None = None


class ModelOptionResponse(BaseModel):
    id: str
    provider: str
    display_name: str
    category: str = "通用模型"
    runtime_supported: bool = False
    runtime_integration: str = ""
    input_credits_per_1m: str
    output_credits_per_1m: str
    input_usd_per_1m: str
    output_usd_per_1m: str
    context_window: int | None = None
    notes: str = ""


class UsageResponse(BaseModel):
    model_id: str
    provider: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_credits: str
    cost_credits_micros: int
    trial_used: bool
    trial_uses_remaining: int
    credit_balance: str
    credit_balance_micros: int


class ResumeParseRequest(BaseModel):
    filename: str
    content_base64: str


class ResumeParseResponse(BaseModel):
    filename: str
    file_type: str
    text: str
    summary: str
    truncated: bool = False


class ResumeImportRequest(BaseModel):
    filename: str
    content_base64: str
    source_path: str | None = None


class ResumeRecordResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    summary: str
    text: str
    truncated: bool = False
    created_at: str
    updated_at: str
    source_path: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    message: str
    completed: bool
    fallback_used: bool = False
    guardrails: list[str] = []
    model_id: str = ""
    usage: UsageResponse | None = None
    turn_index: int | None = None
    orchestration: dict | None = None


class SessionSummaryResponse(BaseModel):
    id: str
    resume_id: str | None = None
    mode: str
    industry: str
    candidate_name: str
    target_role: str
    seniority: str
    status: str
    plan_task_id: str | None = None
    interviewer_kit_id: str | None = None
    created_at: str
    updated_at: str


class SessionDetailResponse(SessionSummaryResponse):
    config: dict
    state: dict
    turns: list[dict]


class DeleteResponse(BaseModel):
    deleted: bool


class IndustryOptionResponse(BaseModel):
    value: str
    label: str
    description: str
    scenario_keywords: list[str]
    interview_focus: list[str]
    production_signals: list[str]
    risk_controls: list[str]
    follow_up_angles: list[str]
    answer_expectations: list[str]
    recommended_focus_areas: list[str]


class CivilServiceQuestionImportRequest(BaseModel):
    questions: list[dict]


class CivilServiceQuestionListResponse(BaseModel):
    items: list[dict]
    total: int
    limit: int
    offset: int
    has_more: bool = False
    next_offset: int | None = None


class PracticeAttemptRequest(BaseModel):
    question_id: str = Field(min_length=1, max_length=128)
    answer: str = Field(default="", max_length=8000)
    elapsed_seconds: int | None = Field(default=None, ge=0, le=24 * 60 * 60)


class PracticeAttemptResponse(BaseModel):
    question_id: str
    correct: bool | None
    score: int
    feedback: str
    reference_answer: str
    explanation: str
    suggestions: list[str]
    elapsed_seconds: int | None = None


class ImportResultResponse(BaseModel):
    created: int
    updated: int
    total: int


class ReviewPlanListItem(BaseModel):
    id: str
    plan_key: str = ""
    title: str = ""
    subtitle: str = ""
    status: str = "draft"
    created_at: str | None = None
    updated_at: str | None = None


class ReviewPhaseResponse(BaseModel):
    id: str
    phase_key: str = ""
    title: str = ""
    range_label: str = ""
    goal: str = ""
    sort_order: int = 0


class ReviewTaskResponse(BaseModel):
    id: str
    task_key: str = ""
    title: str = ""
    tags: list = []
    critical: bool = False
    simulation: bool = False
    docs: list = []
    reason: str | None = None
    source: str = "plan"
    link_type: str = "none"
    link_payload: dict = {}
    sort_order: int = 0


class ReviewDayResponse(BaseModel):
    id: str
    day_key: str = ""
    day_label: str = ""
    phase_key: str = ""
    title: str = ""
    acceptance: str | None = None
    scheduled_date: str | None = None
    sort_order: int = 0
    tasks: list[ReviewTaskResponse] = []


class ReviewProgressResponse(BaseModel):
    id: str
    plan_id: str
    day_id: str
    task_id: str
    done: bool = False
    note: str | None = None
    elapsed_minutes: int | None = None
    mastery_score: int | None = None
    done_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class ReviewPlanResponse(BaseModel):
    id: str
    plan_key: str = ""
    title: str = ""
    subtitle: str = ""
    description: str = ""
    status: str = "draft"
    source_root: str = ""
    source_documents: list = []
    commercial_positioning: list = []
    phases: list[ReviewPhaseResponse] = []
    days: list[ReviewDayResponse] = []
    progresses: list[ReviewProgressResponse] = []
    intro_scripts: list = []
    star_cards: list = []
    a4_memory: list = []
    metadata: dict = {}
    created_at: str | None = None
    updated_at: str | None = None


class ReviewPlanCreateRequest(BaseModel):
    title: str = Field(default="", max_length=255)
    plan_key: str | None = Field(default=None, max_length=128)
    template: str | None = Field(default=None, max_length=128)


class ReviewProgressUpdateRequest(BaseModel):
    done: bool | None = None
    note: str | None = Field(default=None, max_length=4000)
    elapsed_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    mastery_score: int | None = Field(default=None, ge=0, le=5)


class ReviewCheckinRequest(BaseModel):
    elapsed_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    note: str | None = Field(default=None, max_length=2000)


class IntroScriptResponse(BaseModel):
    id: str
    script_key: str = ""
    label: str = ""
    duration_seconds: int = 0
    scenario: str = ""
    text: str = ""
    sort_order: int = 0


class StarCardResponse(BaseModel):
    id: str
    card_key: str = ""
    title: str = ""
    tag: str = ""
    background: str = ""
    challenge: str = ""
    solution: str = ""
    result: str = ""
    sort_order: int = 0


class A4MemoryResponse(BaseModel):
    id: str
    content: str = ""
    side: str = "ALL"
    sort_order: int = 0


class PracticeQuestionResponse(BaseModel):
    id: str
    practice_category: str = "internet"
    source: str = "manual"
    source_url: str | None = None
    subject: str | None = None
    question_type: str | None = None
    prompt: str = ""
    choices: list = []
    answer: str | None = None
    answer_detail: str | None = None
    difficulty: str = "medium"
    tags: list = []
    content_hash: str = ""
    created_at: str | None = None
    updated_at: str | None = None


class PracticeQuestionListResponse(BaseModel):
    items: list[PracticeQuestionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool = False
    next_offset: int | None = None


class PlanGenerateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    target_role: str = Field(default="", max_length=255)
    seniority: str = Field(default="", max_length=128)
    target_company: str | None = Field(default=None, max_length=255)
    total_days: int = Field(default=14, ge=3, le=90)
    hours_per_day: float = Field(default=3.0, ge=0.5, le=12.0)
    focus_areas: list[str] | None = Field(default=None)
    template: str | None = Field(default=None, max_length=128)
    resume_id: str | None = Field(default=None, max_length=64)
    use_history: bool = Field(default=True)


class PlanGenerateResponse(BaseModel):
    plan_id: str
    estimated_daily_hours: float
    breakdown_phases: list[dict] = []
    generated_by: str = "rule"


class ReviewDayUpsertRequest(BaseModel):
    day_key: str | None = Field(default=None, max_length=64)
    day_label: str | None = Field(default=None, max_length=64)
    phase_key: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    acceptance: str | None = Field(default=None, max_length=2000)
    scheduled_date: str | None = Field(default=None, max_length=32)
    sort_order: int | None = Field(default=None, ge=0)


class ReviewTaskUpsertRequest(BaseModel):
    task_key: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = None
    critical: bool | None = None
    simulation: bool | None = None
    docs: list | None = None
    reason: str | None = Field(default=None, max_length=500)
    link_type: str | None = Field(default=None, max_length=32)
    link_payload: dict | None = None
    sort_order: int | None = Field(default=None, ge=0)


class MaterialItemRequest(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    script_key: str | None = Field(default=None, max_length=64)
    duration_seconds: int | None = Field(default=None, ge=0)
    scenario: str | None = Field(default=None, max_length=255)
    text: str | None = None
    card_key: str | None = Field(default=None, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    tag: str | None = Field(default=None, max_length=64)
    background: str | None = None
    challenge: str | None = None
    solution: str | None = None
    result: str | None = None
    content: str | None = None
    side: str | None = Field(default=None, max_length=16)
    sort_order: int | None = Field(default=None, ge=0)


class PracticeQuestionMarkRequest(BaseModel):
    mark_type: str | None = Field(default=None, max_length=32)
    mastery_level: int | None = Field(default=None, ge=0, le=5)
    note: str | None = Field(default=None, max_length=4000)


class PracticeQuestionAttemptRequest(BaseModel):
    answer: str = Field(default="", max_length=8000)
    elapsed_seconds: int | None = Field(default=None, ge=0, le=24 * 60 * 60)
