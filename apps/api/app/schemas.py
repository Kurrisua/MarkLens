"""Public contract-v0.2 schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class RegisterCreate(ContractModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=10, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginCreate(ContractModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class CurrentUserResponse(ContractModel):
    user_id: str
    email: str
    display_name: str
    roles: list[Literal["user", "operator", "admin"]]


class AuthResponse(ContractModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: CurrentUserResponse


class ProjectCreate(ContractModel):
    name: str = Field(min_length=1, max_length=160)
    business_description: str = Field(default="", max_length=4000)


class ProjectResponse(ContractModel):
    project_id: str
    name: str
    business_description: str
    status: str
    owner_id: str
    case_count: int = 0
    created_at: datetime
    updated_at: datetime


class AppDashboardResponse(ContractModel):
    projects: list[ProjectResponse]
    learning_progress: dict[str, int]


class PracticeQuestionResponse(ContractModel):
    question_id: str
    title: str
    prompt: str
    options: list[dict[str, str]]
    difficulty: str


class PracticeAttemptCreate(ContractModel):
    selected_option: str = Field(min_length=1, max_length=80)


class PracticeAttemptResponse(ContractModel):
    attempt_id: str
    is_correct: bool
    explanation: str


class LearningTopicResponse(ContractModel):
    topic_id: str
    slug: str
    title: str
    summary: str
    article_count: int


class LearningArticleResponse(ContractModel):
    article_id: str
    title: str
    body: str
    citations: list[dict[str, Any]]


class LearningVideoResponse(ContractModel):
    video_id: str
    topic_slug: str
    topic_title: str
    title: str
    provider: str
    external_url: str
    duration_label: str
    learning_objective: str
    is_published: bool


class OpsLearningVideoCreate(ContractModel):
    topic_slug: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=200)
    provider: str = Field(default="bilibili", min_length=2, max_length=80)
    external_url: str = Field(min_length=20, max_length=700)
    duration_label: str = Field(default="外部视频", min_length=2, max_length=80)
    learning_objective: str = Field(min_length=2, max_length=500)
    is_published: bool = False

    @field_validator("external_url")
    @classmethod
    def validate_video_url(cls, value: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(value.strip())
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("视频链接必须是 HTTPS 地址。")
        if not (parsed.hostname == "bilibili.com" or parsed.hostname.endswith(".bilibili.com")):
            raise ValueError("当前仅支持哔哩哔哩视频链接。")
        return value.strip()


class OpsOverviewResponse(ContractModel):
    users: int
    projects: int
    runs: dict[str, int]
    published_topics: int


class AdminUserResponse(ContractModel):
    user_id: str
    email: str
    display_name: str
    status: str
    roles: list[Literal["user", "operator", "admin"]]
    created_at: datetime


class AdminUserRolesUpdate(ContractModel):
    roles: list[Literal["user", "operator", "admin"]] = Field(min_length=1, max_length=3)


class OpsLearningTopicUpsert(ContractModel):
    slug: str = Field(min_length=2, max_length=120, pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=2, max_length=160)
    summary: str = Field(min_length=2, max_length=500)
    body: str = Field(min_length=2, max_length=12000)
    is_published: bool = False


class OpsPracticeQuestionCreate(ContractModel):
    title: str = Field(min_length=2, max_length=200)
    prompt: str = Field(min_length=2, max_length=4000)
    options: list[dict[str, str]] = Field(min_length=2, max_length=6)
    correct_option: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=2, max_length=8000)
    difficulty: Literal["basic", "intermediate", "advanced"] = "basic"
    is_published: bool = False


class OpsPracticeQuestionResponse(PracticeQuestionResponse):
    """运营侧题目视图；正确答案只会在受角色保护的后台返回。"""

    correct_option: str
    explanation: str
    is_published: bool


class ErrorBody(ContractModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None


class ErrorResponse(ContractModel):
    error: ErrorBody


class DependencyState(ContractModel):
    status: Literal["ready", "degraded", "unavailable"]
    detail: str


class HealthResponse(ContractModel):
    status: Literal["ok", "degraded"]
    contract_version: str = "v0.2"
    mode: str
    dependencies: dict[str, DependencyState]
    data_version: str


class AssetResult(ContractModel):
    asset_id: str
    mime_type: str
    width: int
    height: int
    sha256: str
    ocr_text: str | None = None
    ocr_confidence: float | None = None
    ocr_requires_confirmation: bool
    phash: str | None = None
    created_at: datetime


class ProjectAttachmentResponse(ContractModel):
    attachment_id: str
    filename: str
    mime_type: str
    normalized_text: str
    structure: dict[str, Any]
    extracted_image_asset_id: str | None = None
    created_at: datetime


class CaseCreate(ContractModel):
    trademark_name: str = Field(min_length=1, max_length=255)
    business_description: str = Field(min_length=2, max_length=4000)
    nice_classes: list[int] = Field(min_length=1, max_length=45)
    image_asset_id: str | None = None
    confirmed_ocr_text: str | None = Field(default=None, max_length=1000)

    @field_validator("nice_classes")
    @classmethod
    def validate_classes(cls, value: list[int]) -> list[int]:
        if any(item < 1 or item > 45 for item in value):
            raise ValueError("国际分类必须在 1 到 45 之间")
        return sorted(set(value))


class CaseContext(ContractModel):
    case_id: str
    trademark_name: str
    business_description: str
    nice_classes: list[int]
    image_asset_id: str | None = None
    confirmed_ocr_text: str | None = None
    facts_snapshot: dict[str, Any]
    created_at: datetime


class SearchCreate(ContractModel):
    case_id: str
    top_k: int = Field(default=10, ge=1, le=30)


class ScoreBreakdown(ContractModel):
    visual: float | None = None
    visual_basis: str | None = None
    text: float | None = None
    phonetic: float | None = None
    semantic: float | None = None
    category: float | None = None
    overall: float
    applied_weights: dict[str, float]


class TrademarkEvidence(ContractModel):
    hit_id: str
    rank: int
    trademark_id: str
    name: str
    application_number: str
    applicant: str
    nice_classes: list[int]
    goods_services: list[str]
    status: str
    status_date: date | None = None
    image_asset_id: str | None = None
    source_url: str
    source_name: str
    data_label: str | None = None
    data_notice: str | None = None
    source_record_id: str
    jurisdiction: str
    is_demo: bool
    scores: ScoreBreakdown
    reasons: list[str]
    ocr_evidence: dict[str, Any] | None = None
    visual_review: dict[str, Any] | None = None
    model_versions: dict[str, str]


class EvidenceBundle(ContractModel):
    search_id: str
    case_id: str
    status: str
    query: dict[str, Any]
    top_k: int
    evidence_quality: str
    methodology: dict[str, Any]
    hits: list[TrademarkEvidence]
    created_at: datetime


class RiskAnalysisCreate(ContractModel):
    search_id: str
    analysis_date: date = Field(default_factory=date.today)


class Citation(ContractModel):
    citation_id: str
    source_id: str
    title: str
    authority: str
    locator: str
    source_url: str
    excerpt: str
    effective_from: date
    effective_to: date | None = None


class RiskAssessment(ContractModel):
    analysis_id: str
    search_id: str
    analysis_date: date
    risk_score: float
    risk_level: Literal["low", "medium", "high", "insufficient_evidence"]
    evidence_quality: str
    applicable_law_version: str
    methodology: dict[str, Any]
    risk_factors: list[dict[str, Any]]
    counter_evidence: list[str]
    suggestions: list[str]
    citations: list[Citation]
    uncertainties: list[str]
    model_metadata: dict[str, Any]
    disclaimer: str
    created_at: datetime


class DocumentCreate(ContractModel):
    analysis_id: str
    document_type: Literal["trademark_registration_risk_report"] = (
        "trademark_registration_risk_report"
    )


class DocumentSection(ContractModel):
    section_id: str
    title: str
    content: str
    citation_ids: list[str] = Field(default_factory=list)


class DocumentDraftResponse(ContractModel):
    document_id: str
    analysis_id: str
    document_type: str
    title: str
    sections: list[DocumentSection]
    citations: list[Citation]
    validation_errors: list[dict[str, Any]]
    warnings: list[str]
    generation_mode: str
    can_export: bool
    updated_at: datetime


class DocumentUpdate(ContractModel):
    sections: list[DocumentSection]


class ConsultationCreate(ContractModel):
    question: str = Field(min_length=3, max_length=4000)
    case_id: str | None = None
    analysis_date: date = Field(default_factory=date.today)


class ConsultationAnswer(ContractModel):
    consultation_id: str
    question: str
    answer: str
    citations: list[Citation]
    uncertainties: list[str]
    disclaimer: str
    generation_mode: str
    created_at: datetime


class ProjectAdvisorQuestionCreate(ConsultationCreate):
    """A legal/brand question grounded in one private project."""


class ProjectAdvisorMessage(ConsultationAnswer):
    project_id: str
    case_id: str | None = None


class AgentRunResponse(ContractModel):
    run_id: str
    agent_type: str
    status: Literal["queued", "running", "waiting_for_user", "completed", "failed"]
    progress: int
    stage: str
    resource_type: str | None = None
    resource_id: str | None = None
    error: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class SourceDefinitionResponse(ContractModel):
    source_key: str
    name: str
    adapter_type: str
    license_name: str
    license_url: str | None
    terms_summary: str
    allowed_domains: list[str]
    rate_limit_per_minute: int | None
    enabled: bool
    health: str
    record_count: int
    last_synced_at: datetime | None


class SourceSyncCreate(ContractModel):
    cursor: str | None = None
    page_size: int = Field(default=100, ge=1, le=1000)
    max_pages: int = Field(default=100, ge=1, le=1000)


class SourceEnabledUpdate(ContractModel):
    enabled: bool


class IngestionRunResponse(ContractModel):
    ingestion_run_id: str
    source_key: str
    status: str
    fetched_count: int
    created_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    errors: list[dict[str, Any]]
    started_at: datetime | None
    finished_at: datetime | None


class RecentCase(ContractModel):
    case_id: str
    trademark_name: str
    nice_classes: list[int]
    created_at: datetime


class DashboardResponse(ContractModel):
    recent_cases: list[RecentCase]
    counts: dict[str, int]
    data_version: str
    legal_version: str
