"""Public contract-v0.2 schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


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
    source_record_id: str
    jurisdiction: str
    is_demo: bool
    scores: ScoreBreakdown
    reasons: list[str]
    ocr_evidence: dict[str, Any] | None = None
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
