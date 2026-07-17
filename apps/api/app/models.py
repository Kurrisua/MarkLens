"""SQLAlchemy models for the MarkLens evidence chain."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SourceDefinition(Base, TimestampMixin):
    __tablename__ = "source_definitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(40), nullable=False)
    license_name: Mapped[str] = mapped_column(String(160), nullable=False)
    license_url: Mapped[str | None] = mapped_column(String(500))
    terms_summary: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_domains: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime)


class IngestionRun(Base, TimestampMixin):
    __tablename__ = "ingestion_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_definitions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    cursor_started: Mapped[str | None] = mapped_column(String(255))
    cursor_finished: Mapped[str | None] = mapped_column(String(255))
    fetched_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Trademark(Base, TimestampMixin):
    __tablename__ = "trademarks"
    __table_args__ = (
        UniqueConstraint("source_id", "source_record_id", name="uq_trademark_source_record"),
        Index("ix_trademark_application_number", "application_number"),
        Index("ix_trademark_normalized_name", "normalized_name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_definitions.id"), nullable=False)
    source_record_id: Mapped[str] = mapped_column(String(160), nullable=False)
    raw_record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    application_number: Mapped[str] = mapped_column(String(80), nullable=False)
    applicant: Mapped[str] = mapped_column(String(255), nullable=False)
    nice_classes: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    goods_services: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False)
    status_date: Mapped[date | None] = mapped_column(Date)
    application_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(String(700), nullable=False)
    image_asset_id: Mapped[str | None] = mapped_column(ForeignKey("image_assets.id"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class TrademarkClass(Base):
    __tablename__ = "trademark_classes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trademark_id: Mapped[str] = mapped_column(ForeignKey("trademarks.id"), nullable=False)
    nice_class: Mapped[int] = mapped_column(Integer, nullable=False)
    class_title: Mapped[str | None] = mapped_column(String(255))


class GoodsServiceItem(Base):
    __tablename__ = "goods_service_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trademark_id: Mapped[str] = mapped_column(ForeignKey("trademarks.id"), nullable=False)
    nice_class: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(500), nullable=False)
    group_code: Mapped[str | None] = mapped_column(String(40))


class ImageAsset(Base, TimestampMixin):
    __tablename__ = "image_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    storage_key: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_model: Mapped[str | None] = mapped_column(String(160))
    phash: Mapped[str | None] = mapped_column(String(32))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TrademarkFeature(Base, TimestampMixin):
    __tablename__ = "trademark_features"
    __table_args__ = (
        UniqueConstraint(
            "trademark_id",
            "feature_type",
            "model_name",
            "preprocess_version",
            name="uq_trademark_feature_version",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trademark_id: Mapped[str] = mapped_column(ForeignKey("trademarks.id"), nullable=False)
    feature_type: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    preprocess_version: Mapped[str] = mapped_column(String(80), nullable=False)
    vector_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class LegalSource(Base, TimestampMixin):
    __tablename__ = "legal_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authority: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(String(700), nullable=False)
    source_type: Mapped[str] = mapped_column(String(80), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(80), default="CN", nullable=False)
    version_label: Mapped[str] = mapped_column(String(160), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    verification_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LegalChunk(Base, TimestampMixin):
    __tablename__ = "legal_chunks"
    __table_args__ = (Index("ix_legal_chunk_locator", "locator"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    legal_source_id: Mapped[str] = mapped_column(ForeignKey("legal_sources.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    locator: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding_blob: Mapped[bytes | None] = mapped_column(LargeBinary)
    embedding_model: Mapped[str | None] = mapped_column(String(160))
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    preprocess_version: Mapped[str | None] = mapped_column(String(80))


class CaseRecord(Base, TimestampMixin):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trademark_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_description: Mapped[str] = mapped_column(Text, nullable=False)
    nice_classes: Mapped[list[int]] = mapped_column(JSON, default=list, nullable=False)
    image_asset_id: Mapped[str | None] = mapped_column(ForeignKey("image_assets.id"))
    confirmed_ocr_text: Mapped[str | None] = mapped_column(Text)
    facts_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class SearchRecord(Base, TimestampMixin):
    __tablename__ = "searches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    query_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    config_version: Mapped[str] = mapped_column(String(80), nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    evidence_quality: Mapped[str] = mapped_column(String(40), default="unknown", nullable=False)


class SearchHit(Base, TimestampMixin):
    __tablename__ = "search_hits"
    __table_args__ = (UniqueConstraint("search_id", "rank", name="uq_search_hit_rank"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    search_id: Mapped[str] = mapped_column(ForeignKey("searches.id"), nullable=False)
    trademark_id: Mapped[str] = mapped_column(ForeignKey("trademarks.id"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class RiskAnalysis(Base, TimestampMixin):
    __tablename__ = "risk_analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    search_id: Mapped[str] = mapped_column(ForeignKey("searches.id"), nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(40), nullable=False)
    evidence_quality: Mapped[str] = mapped_column(String(40), nullable=False)
    applicable_law_version: Mapped[str] = mapped_column(String(160), nullable=False)
    methodology: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_factors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    counter_evidence: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    suggestions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    uncertainties: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    model_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class DocumentDraft(Base, TimestampMixin):
    __tablename__ = "document_drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("risk_analyses.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    validation_errors: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    facts_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(40), default="template", nullable=False)


class Consultation(Base, TimestampMixin):
    __tablename__ = "consultations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str | None] = mapped_column(ForeignKey("cases.id"))
    question: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_date: Mapped[date] = mapped_column(Date, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    uncertainties: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    generation_mode: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    agent_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stage: Mapped[str] = mapped_column(String(160), default="等待执行", nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    request_id: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str | None] = mapped_column(String(160))
    dataset_version: Mapped[str | None] = mapped_column(String(80))
    config_version: Mapped[str | None] = mapped_column(String(80))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
