"""Application services for cases, agents and evidence-chain artifacts."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .ai_providers import AIProviderError, AIRequestConfig, generate_json
from .config import get_settings
from .models import (
    AgentRun,
    CaseRecord,
    Consultation,
    DocumentDraft,
    ImageAsset,
    IngestionRun,
    LegalSource,
    RiskAnalysis,
    SearchHit,
    SearchRecord,
    SourceDefinition,
    Trademark,
)
from .rag import (
    DISCLAIMER,
    answer_consultation,
    citation_from_document,
    generate_document_sections,
    generate_risk_narrative,
    hybrid_legal_retrieval,
    validate_document,
)
from .retrieval import risk_level, search_trademarks
from .serialization import json_compatible
from .sources import REGISTRY, sync_source

logger = logging.getLogger("marklens.agents")
AGENT_FAILURE_MESSAGE = "任务执行失败，请稍后重试；若问题持续，请向维护者提供任务编号。"


def create_agent_run(
    session: Session,
    agent_type: str,
    request_id: str | None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    owner_id: str | None = None,
    visibility: str = "user",
) -> AgentRun:
    settings = get_settings()
    run = AgentRun(
        agent_type=agent_type,
        request_id=request_id,
        resource_type=resource_type,
        resource_id=resource_id,
        model_name="user-supplied" if agent_type in {"document", "consultation"} else None,
        dataset_version="demo-2026.1",
        config_version=settings.retrieval_config_version,
        owner_id=owner_id,
        visibility=visibility,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def update_run(
    session: Session,
    run: AgentRun,
    *,
    status: str | None = None,
    progress: int | None = None,
    stage: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> None:
    if status is not None:
        run.status = status
    if progress is not None:
        run.progress = progress
    if stage is not None:
        run.stage = stage
    if resource_type is not None:
        run.resource_type = resource_type
    if resource_id is not None:
        run.resource_id = resource_id
    if status == "running" and run.started_at is None:
        run.started_at = datetime.utcnow()
    if status in {"completed", "failed"}:
        run.finished_at = datetime.utcnow()
    session.commit()


def agent_run_dict(run: AgentRun) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "agent_type": run.agent_type,
        "status": run.status,
        "progress": run.progress,
        "stage": run.stage,
        "resource_type": run.resource_type,
        "resource_id": run.resource_id,
        "error": (
            {"code": run.error_code, "message": run.error_message} if run.error_code else None
        ),
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def execute_agent(run_id: str, operation: Callable[[Session, AgentRun], None]) -> None:
    from .db import get_session_factory

    with get_session_factory()() as session:
        run = session.get(AgentRun, run_id)
        if run is None:
            return
        try:
            update_run(session, run, status="running", progress=5, stage="读取事实快照")
            operation(session, run)
        except Exception as exc:  # persist failure for polling clients
            session.rollback()
            run = session.get(AgentRun, run_id)
            if run is None:
                return
            cause = getattr(exc, "orig", None) or exc
            logger.error(
                "agent_execution_failed run_id=%s agent_type=%s error_type=%s cause_type=%s cause=%s",
                run.id,
                run.agent_type,
                type(exc).__name__,
                type(cause).__name__,
                str(cause)[:300],
            )
            run.error_code = "AGENT_EXECUTION_FAILED"
            run.error_message = AGENT_FAILURE_MESSAGE
            update_run(session, run, status="failed", stage="任务执行失败")


def case_dict(case: CaseRecord) -> dict[str, Any]:
    return {
        "case_id": case.id,
        "trademark_name": case.trademark_name,
        "business_description": case.business_description,
        "nice_classes": case.nice_classes,
        "image_asset_id": case.image_asset_id,
        "confirmed_ocr_text": case.confirmed_ocr_text,
        "facts_snapshot": case.facts_snapshot,
        "created_at": case.created_at,
    }


def search_dict(session: Session, search: SearchRecord) -> dict[str, Any]:
    rows = session.execute(
        select(SearchHit, Trademark, SourceDefinition)
        .join(Trademark, Trademark.id == SearchHit.trademark_id)
        .join(SourceDefinition, SourceDefinition.id == Trademark.source_id)
        .where(SearchHit.search_id == search.id)
        .order_by(SearchHit.rank)
    ).all()
    hits = []
    for hit, trademark, source in rows:
        hits.append(
            {
                "hit_id": hit.id,
                "rank": hit.rank,
                "trademark_id": trademark.id,
                "name": trademark.name,
                "application_number": trademark.application_number,
                "applicant": trademark.applicant,
                "nice_classes": trademark.nice_classes,
                "goods_services": trademark.goods_services,
                "status": trademark.status,
                "status_date": trademark.status_date,
                "image_asset_id": trademark.image_asset_id,
                "source_url": trademark.source_url,
                "source_name": source.name,
                "data_label": trademark.raw_record.get("data_label"),
                "data_notice": trademark.raw_record.get("data_notice"),
                "source_record_id": trademark.source_record_id,
                "jurisdiction": str(
                    trademark.raw_record.get("jurisdiction")
                    or ("DEMO" if trademark.is_demo else "unknown")
                ),
                "is_demo": trademark.is_demo,
                "scores": hit.scores,
                "reasons": hit.reasons,
                "ocr_evidence": hit.evidence.get("ocr_evidence"),
                "visual_review": hit.evidence.get("visual_review"),
                "model_versions": hit.evidence.get("model_versions", {}),
            }
        )
    return {
        "search_id": search.id,
        "case_id": search.case_id,
        "status": search.status,
        "query": search.query_snapshot,
        "top_k": search.top_k,
        "evidence_quality": search.evidence_quality,
        "methodology": {
            "config_version": search.config_version,
            "weights": {
                "visual": 0.30,
                "text": 0.30,
                "phonetic": 0.15,
                "semantic": 0.15,
                "category": 0.10,
            },
            "visual_mix": {"resnet50": 0.65, "phash": 0.35},
            "candidate_pool_per_channel": 30,
            "notice": "分数和阈值是课程演示启发式规则，不是官方审查标准。",
        },
        "hits": hits,
        "created_at": search.created_at,
    }


def risk_dict(analysis: RiskAnalysis) -> dict[str, Any]:
    return {
        "analysis_id": analysis.id,
        "search_id": analysis.search_id,
        "analysis_date": analysis.analysis_date,
        "risk_score": analysis.risk_score,
        "risk_level": analysis.risk_level,
        "evidence_quality": analysis.evidence_quality,
        "applicable_law_version": analysis.applicable_law_version,
        "methodology": analysis.methodology,
        "risk_factors": analysis.risk_factors,
        "counter_evidence": analysis.counter_evidence,
        "suggestions": analysis.suggestions,
        "citations": analysis.citations,
        "uncertainties": analysis.uncertainties,
        "model_metadata": analysis.model_metadata,
        "disclaimer": DISCLAIMER,
        "created_at": analysis.created_at,
    }


def document_dict(document: DocumentDraft) -> dict[str, Any]:
    return {
        "document_id": document.id,
        "analysis_id": document.analysis_id,
        "document_type": document.document_type,
        "title": document.title,
        "sections": document.sections,
        "citations": document.citations,
        "validation_errors": document.validation_errors,
        "warnings": document.warnings,
        "generation_mode": document.generation_mode,
        "can_export": not document.validation_errors,
        "updated_at": document.updated_at,
    }


def consultation_dict(item: Consultation) -> dict[str, Any]:
    return {
        "consultation_id": item.id,
        "question": item.question,
        "answer": item.answer or "",
        "citations": item.citations,
        "uncertainties": item.uncertainties,
        "disclaimer": item.disclaimer,
        "generation_mode": item.generation_mode,
        "created_at": item.created_at,
    }


def _safe_asset_bytes(asset: ImageAsset) -> bytes | None:
    """Read a local image only after validating it remains inside upload_dir."""
    settings = get_settings()
    root = settings.upload_dir.resolve()
    path = (root / asset.storage_key).resolve()
    if root not in path.parents or not path.is_file() or asset.byte_size > 3 * 1024 * 1024:
        return None
    return path.read_bytes()


def _visual_review(
    query_asset: ImageAsset | None,
    candidate_asset: ImageAsset | None,
    config: AIRequestConfig | None,
) -> dict[str, Any] | None:
    """Return a separate, non-scoring multimodal comparison for one candidate."""
    if not config or not config.can_review_images or not query_asset or not candidate_asset:
        return None
    supported = {"image/jpeg", "image/png", "image/webp"}
    if query_asset.mime_type not in supported or candidate_asset.mime_type not in supported:
        return {"status": "skipped", "reason": "图样格式不适合模型视觉复核。"}
    query_bytes, candidate_bytes = (
        _safe_asset_bytes(query_asset),
        _safe_asset_bytes(candidate_asset),
    )
    if not query_bytes or not candidate_bytes:
        return {"status": "skipped", "reason": "图样文件不可用或超过视觉复核大小限制。"}
    try:
        payload = generate_json(
            config,
            instruction=(
                "比较两张商标图样。第一张是待测标志，第二张是在先候选。"
                "只评价整体视觉印象、构图、主要图形元素和可能造成的识别混淆；"
                "不作法律结论，不调整系统检索分数。"
                "JSON 结构：{similarity:number(0到1), reason:string(不超过100字)}。"
            ),
            images=[
                (query_bytes, query_asset.mime_type),
                (candidate_bytes, candidate_asset.mime_type),
            ],
        )
        similarity = float(payload["similarity"])
        reason = str(payload["reason"]).strip()
        if not 0 <= similarity <= 1 or not reason or len(reason) > 160:
            raise ValueError("invalid visual review")
        return {
            "status": "completed",
            "score": round(similarity, 4),
            "reason": reason,
            "mode": config.generation_mode,
            "notice": "模型视觉复核为辅助意见，不参与确定性检索排序或风险评分。",
        }
    except (AIProviderError, KeyError, TypeError, ValueError) as exc:
        logger.warning("user_model_visual_review_unavailable error_type=%s", type(exc).__name__)
        return {
            "status": "unavailable",
            "reason": "模型视觉复核未返回可验证结果，已保留向量比对结果。",
        }


def build_search_operation(
    search_id: str, ai_config: AIRequestConfig | None = None
) -> Callable[[Session, AgentRun], None]:
    def operation(session: Session, run: AgentRun) -> None:
        search = session.get(SearchRecord, search_id)
        if search is None:
            raise ValueError("检索任务不存在")
        case = session.get(CaseRecord, search.case_id)
        if case is None:
            raise ValueError("案件不存在")
        update_run(session, run, progress=20, stage="执行多路候选召回")
        ranked = search_trademarks(session, case, search.top_k)
        query_asset = session.get(ImageAsset, case.image_asset_id) if case.image_asset_id else None
        reviews: dict[str, dict[str, Any]] = {}
        if ai_config and ai_config.can_review_images:
            update_run(session, run, progress=48, stage="模型复核候选图样")
            for item in ranked[:5]:
                candidate_asset_id = item["trademark"].image_asset_id
                candidate_asset = (
                    session.get(ImageAsset, candidate_asset_id) if candidate_asset_id else None
                )
                review = _visual_review(query_asset, candidate_asset, ai_config)
                if review:
                    reviews[item["trademark"].id] = review
        session.execute(delete(SearchHit).where(SearchHit.search_id == search.id))
        settings = get_settings()
        for rank, item in enumerate(ranked, start=1):
            session.add(
                SearchHit(
                    search_id=search.id,
                    trademark_id=item["trademark"].id,
                    rank=rank,
                    scores=item["scores"],
                    reasons=item["reasons"],
                    evidence={
                        "ocr_evidence": (
                            {"text": case.confirmed_ocr_text, "confirmed": True}
                            if case.confirmed_ocr_text
                            else None
                        ),
                        "model_versions": {
                            "text_embedding": settings.text_embedding_model,
                            "image_embedding": settings.image_embedding_model,
                            "ocr": settings.ocr_provider,
                            "scoring": settings.retrieval_config_version,
                        },
                        "visual_review": reviews.get(item["trademark"].id),
                    },
                )
            )
        search.status = "completed"
        search.evidence_quality = (
            "demo_only"
            if ranked and all(item["trademark"].is_demo for item in ranked)
            else ("sufficient" if ranked else "insufficient")
        )
        session.commit()
        update_run(
            session,
            run,
            status="completed",
            progress=100,
            stage="检索完成",
            resource_type="search",
            resource_id=search.id,
        )

    return operation


def _analysis_facts(session: Session, search: SearchRecord) -> dict[str, Any]:
    case = session.get(CaseRecord, search.case_id)
    bundle = search_dict(session, search)
    # A course product may be populated primarily with auditable foreign records.
    # They are still valuable evidence for a *similarity-screening* result even
    # though they cannot alone establish a Chinese prior-right conclusion.  The
    # jurisdiction remains in every candidate and the legal narrative continues
    # to state this boundary; we no longer turn an otherwise useful comparison
    # into a zero-score "evidence insufficient" screen merely because its source
    # is foreign.
    scored_hits = bundle["hits"]
    return json_compatible(
        {
            **(case.facts_snapshot if case else {}),
            "trademark_name": case.trademark_name if case else "待补充",
            "nice_classes": case.nice_classes if case else [],
            "top_candidate": scored_hits[0] if scored_hits else {},
            "candidates": [
                {
                    "name": item["name"],
                    "application_number": item["application_number"],
                    "applicant": item["applicant"],
                    "score": item["scores"]["overall"],
                    "jurisdiction": item["jurisdiction"],
                    "nice_classes": item["nice_classes"],
                    "goods_services": item["goods_services"],
                    "status": item["status"],
                    "status_date": item["status_date"],
                    "scores": item["scores"],
                    "reasons": item["reasons"],
                    "source_name": item["source_name"],
                    "is_demo": item["is_demo"],
                }
                for item in scored_hits[:5]
            ],
            "foreign_reference_candidates": [
                {
                    "name": item["name"],
                    "application_number": item["application_number"],
                    "applicant": item["applicant"],
                    "score": item["scores"]["overall"],
                    "jurisdiction": item["jurisdiction"],
                    "nice_classes": item["nice_classes"],
                    "goods_services": item["goods_services"],
                    "status": item["status"],
                    "status_date": item["status_date"],
                    "scores": item["scores"],
                    "reasons": item["reasons"],
                    "source_name": item["source_name"],
                    "is_demo": item["is_demo"],
                }
                for item in bundle["hits"]
                if item["jurisdiction"] not in {"CN", "DEMO"}
            ][:5],
        }
    )


def build_risk_operation(
    search_id: str, analysis_date: date
) -> Callable[[Session, AgentRun], None]:
    def operation(session: Session, run: AgentRun) -> None:
        search = session.get(SearchRecord, search_id)
        if search is None or search.status != "completed":
            raise ValueError("检索尚未完成")
        facts = _analysis_facts(session, search)
        top_score = float(facts.get("top_candidate", {}).get("scores", {}).get("overall", 0))
        has_evidence = bool(facts.get("candidates"))
        level = risk_level(top_score, has_evidence)
        facts["risk"] = {"score": top_score, "level": level}
        update_run(session, run, progress=35, stage="检索适用法律资料")
        documents = hybrid_legal_retrieval(
            session,
            f"商标近似 混淆 在先权利 {facts.get('trademark_name', '')}",
            analysis_date,
        )
        if not documents:
            level = "insufficient_evidence"
        update_run(session, run, progress=65, stage="生成受约束风险解释")
        narrative, mode = generate_risk_narrative(facts, documents, top_score, level)
        citations_by_id = {
            item["citation_id"]: item for item in map(citation_from_document, documents)
        }
        if documents and not narrative["citation_ids"]:
            narrative["citation_ids"] = [f"cite_{documents[0].metadata['chunk_id']}"]
        citations = [
            citations_by_id[item] for item in narrative["citation_ids"] if item in citations_by_id
        ]
        applicable = (
            "2026年修订商标法（2027-01-01起施行）"
            if analysis_date >= date(2027, 1, 1)
            else "2019年修正现行商标法"
        )
        analysis = RiskAnalysis(
            search_id=search.id,
            owner_id=search.owner_id,
            analysis_date=analysis_date,
            risk_score=top_score,
            risk_level=level,
            evidence_quality=search.evidence_quality if citations else "insufficient",
            applicable_law_version=applicable,
            methodology={
                "score_owner": "deterministic_engine",
                "thresholds": {"high": 0.75, "medium": 0.50},
                "config_version": get_settings().risk_config_version,
                "notice": "教学用启发式规则",
            },
            risk_factors=narrative["risk_factors"],
            counter_evidence=narrative["counter_evidence"],
            suggestions=narrative["suggestions"],
            citations=citations,
            uncertainties=narrative["uncertainties"],
            model_metadata={
                "generation_mode": mode,
                "model": "deterministic",
                "score_was_model_generated": False,
            },
        )
        session.add(analysis)
        session.commit()
        update_run(
            session,
            run,
            status="completed",
            progress=100,
            stage="风险分析完成",
            resource_type="risk_analysis",
            resource_id=analysis.id,
        )

    return operation


def build_document_operation(
    analysis_id: str, document_type: str, ai_config: AIRequestConfig
) -> Callable[[Session, AgentRun], None]:
    def operation(session: Session, run: AgentRun) -> None:
        analysis = session.get(RiskAnalysis, analysis_id)
        if analysis is None:
            raise ValueError("风险分析不存在")
        search = session.get(SearchRecord, analysis.search_id)
        if search is None:
            raise ValueError("检索不存在")
        facts = _analysis_facts(session, search)
        facts["risk"] = {"score": analysis.risk_score, "level": analysis.risk_level}
        update_run(session, run, progress=35, stage="装配事实和引用快照")
        documents = hybrid_legal_retrieval(
            session,
            f"商标注册近似风险报告 {facts.get('trademark_name', '')}",
            analysis.analysis_date,
        )
        citations = [citation_from_document(item) for item in documents]
        update_run(session, run, progress=65, stage="按固定模板生成文书")
        sections, mode = generate_document_sections(facts, documents, ai_config)
        errors = validate_document(sections, citations, facts, analysis.analysis_date)
        draft = DocumentDraft(
            analysis_id=analysis.id,
            owner_id=analysis.owner_id,
            document_type=document_type,
            title=f"“{facts.get('trademark_name', '待补充')}”商标注册风险评估报告",
            sections=sections,
            citations=citations,
            validation_errors=errors,
            warnings=[DISCLAIMER, "演示数据不覆盖完整官方商标库。"],
            facts_snapshot=json_compatible(facts),
            generation_mode=mode,
        )
        session.add(draft)
        session.commit()
        update_run(
            session,
            run,
            status="completed",
            progress=100,
            stage="文书初稿完成",
            resource_type="document",
            resource_id=draft.id,
        )

    return operation


def build_consultation_operation(
    consultation_id: str, ai_config: AIRequestConfig
) -> Callable[[Session, AgentRun], None]:
    def operation(session: Session, run: AgentRun) -> None:
        item = session.get(Consultation, consultation_id)
        if item is None:
            raise ValueError("咨询记录不存在")
        facts: dict[str, Any] = {}
        if item.project_id:
            from .models import Project

            project = session.get(Project, item.project_id)
            if project:
                facts["project"] = {
                    "name": project.name,
                    "business_description": project.business_description,
                }
        if item.case_id:
            case = session.get(CaseRecord, item.case_id)
            if case:
                facts.update(case.facts_snapshot)
                facts["mark"] = {
                    "trademark_name": case.trademark_name,
                    "business_description": case.business_description,
                    "nice_classes": case.nice_classes,
                }
        update_run(session, run, progress=35, stage="执行法律混合检索")
        documents = hybrid_legal_retrieval(session, item.question, item.analysis_date)
        update_run(session, run, progress=65, stage="生成带引用答复")
        payload, mode = answer_consultation(item.question, facts, documents, ai_config)
        citations_by_id = {
            citation["citation_id"]: citation for citation in map(citation_from_document, documents)
        }
        item.answer = payload["answer"]
        item.citations = [
            citations_by_id[citation_id]
            for citation_id in payload["citation_ids"]
            if citation_id in citations_by_id
        ]
        item.uncertainties = payload["uncertainties"]
        item.generation_mode = mode
        session.commit()
        update_run(
            session,
            run,
            status="completed",
            progress=100,
            stage="咨询答复完成",
            resource_type="consultation",
            resource_id=item.id,
        )

    return operation


def build_ingestion_operation(
    source_key: str,
    ingestion_run_id: str,
    cursor: str | None,
    page_size: int,
    max_pages: int,
) -> Callable[[Session, AgentRun], None]:
    def operation(session: Session, run: AgentRun) -> None:
        update_run(session, run, progress=20, stage="分页读取已注册数据源")
        ingestion = sync_source(
            session,
            source_key,
            cursor=cursor,
            page_size=page_size,
            max_pages=max_pages,
            ingestion_run_id=ingestion_run_id,
        )
        update_run(
            session,
            run,
            status="completed",
            progress=100,
            stage="同步完成",
            resource_type="ingestion_run",
            resource_id=ingestion.id,
        )

    return operation


def source_list(session: Session) -> list[dict[str, Any]]:
    sources = list(session.scalars(select(SourceDefinition).order_by(SourceDefinition.name)).all())
    counts = dict(
        session.execute(
            select(Trademark.source_id, func.count(Trademark.id)).group_by(Trademark.source_id)
        ).all()
    )
    result = []
    for source in sources:
        try:
            adapter = REGISTRY.get(source.source_key)
            healthy, detail = adapter.health_check()
        except KeyError:
            # An administrator-imported official snapshot has no reusable
            # network adapter, but is still a healthy auditable source.
            healthy, detail = True, "已归档的官方数据快照"
        result.append(
            {
                "source_key": source.source_key,
                "name": source.name,
                "adapter_type": source.adapter_type,
                "license_name": source.license_name,
                "license_url": source.license_url,
                "terms_summary": source.terms_summary,
                "allowed_domains": source.allowed_domains,
                "rate_limit_per_minute": source.rate_limit_per_minute,
                "enabled": source.enabled,
                "health": "ready" if healthy else detail,
                "record_count": int(counts.get(source.id, 0)),
                "last_synced_at": source.last_synced_at,
            }
        )
    return result


def ingestion_dict(session: Session, item: IngestionRun) -> dict[str, Any]:
    source = session.get(SourceDefinition, item.source_id)
    return {
        "ingestion_run_id": item.id,
        "source_key": source.source_key if source else "unknown",
        "status": item.status,
        "fetched_count": item.fetched_count,
        "created_count": item.created_count,
        "updated_count": item.updated_count,
        "skipped_count": item.skipped_count,
        "failed_count": item.failed_count,
        "errors": item.errors,
        "started_at": item.started_at,
        "finished_at": item.finished_at,
    }


def dashboard_dict(session: Session) -> dict[str, Any]:
    recent = list(
        session.scalars(select(CaseRecord).order_by(CaseRecord.created_at.desc()).limit(6)).all()
    )
    return {
        "recent_cases": [
            {
                "case_id": item.id,
                "trademark_name": item.trademark_name,
                "nice_classes": item.nice_classes,
                "created_at": item.created_at,
            }
            for item in recent
        ],
        "counts": {
            "trademarks": int(session.scalar(select(func.count(Trademark.id))) or 0),
            "legal_sources": int(session.scalar(select(func.count(LegalSource.id))) or 0),
            "cases": int(session.scalar(select(func.count(CaseRecord.id))) or 0),
        },
        "data_version": "demo-2026.1",
        "legal_version": "2019年修正现行商标法",
    }
