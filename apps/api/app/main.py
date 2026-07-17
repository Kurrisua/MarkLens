"""MarkLens contract-v0.2 FastAPI application."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, File, Request, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import database_health, get_db
from .errors import AppError
from .models import (
    AgentRun,
    CaseRecord,
    Consultation,
    DocumentDraft,
    ImageAsset,
    IngestionRun,
    RiskAnalysis,
    SearchRecord,
    SourceDefinition,
)
from .retrieval import save_asset
from .schemas import (
    AgentRunResponse,
    AssetResult,
    CaseContext,
    CaseCreate,
    ConsultationAnswer,
    ConsultationCreate,
    DashboardResponse,
    DocumentCreate,
    DocumentDraftResponse,
    DocumentUpdate,
    EvidenceBundle,
    HealthResponse,
    IngestionRunResponse,
    RiskAnalysisCreate,
    RiskAssessment,
    SearchCreate,
    SourceDefinitionResponse,
    SourceSyncCreate,
)
from .services import (
    agent_run_dict,
    build_consultation_operation,
    build_document_operation,
    build_ingestion_operation,
    build_risk_operation,
    build_search_operation,
    case_dict,
    consultation_dict,
    create_agent_run,
    dashboard_dict,
    document_dict,
    execute_agent,
    ingestion_dict,
    risk_dict,
    search_dict,
    source_list,
)
from .sources import REGISTRY

settings = get_settings()
logging.basicConfig(level=settings.app_log_level)
logger = logging.getLogger("marklens.api")
app = FastAPI(
    title="MarkLens API",
    version="0.2.0",
    description=(
        "面向中国大陆商标注册风险初筛的教学 MVP。检索分数为启发式规则，生成内容不构成法律意见。"
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


def request_id(request: Request) -> str:
    return getattr(
        request.state,
        "request_id",
        request.headers.get("X-Request-ID", f"req_{uuid4().hex}"),
    )


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> JSONResponse:
    current_request_id = request_id(request)
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": current_request_id,
                    "details": details,
                }
            }
        ),
        headers={"X-Request-ID": current_request_id},
    )


@app.middleware("http")
async def request_audit_middleware(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID", f"req_{uuid4().hex}")
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(
        "request_complete request_id=%s method=%s path=%s status=%s elapsed_ms=%s model=%s dataset=%s config=%s",
        request.state.request_id,
        request.method,
        request.url.path,
        response.status_code,
        round((time.perf_counter() - started) * 1000, 2),
        settings.deepseek_model,
        "demo-2026.1",
        settings.retrieval_config_version,
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exception: AppError) -> JSONResponse:
    return error_response(
        request,
        exception.status_code,
        exception.code,
        exception.message,
        exception.details,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exception: RequestValidationError
) -> JSONResponse:
    return error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "VALIDATION_ERROR",
        "请求字段不符合 contract-v0.2。",
        {"issues": jsonable_encoder(exception.errors())},
    )


@app.exception_handler(Exception)
async def unknown_error_handler(request: Request, exception: Exception) -> JSONResponse:
    return error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_ERROR",
        "服务器未能完成请求。请根据 request_id 检查日志。",
        {"type": type(exception).__name__} if settings.app_env == "development" else None,
    )


def require[T](session: Session, model: type[T], object_id: str, label: str) -> T:
    item = session.get(model, object_id)
    if item is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", f"{label}不存在。")
    return item


def schedule(
    background_tasks: BackgroundTasks,
    run: AgentRun,
    operation,
) -> None:
    if settings.agent_eager:
        execute_agent(run.id, operation)
    else:
        background_tasks.add_task(execute_agent, run.id, operation)


@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    database_ready, database_detail = database_health()
    model_ready = bool(settings.deepseek_api_key)
    dependencies = {
        "mysql": {
            "status": "ready" if database_ready else "unavailable",
            "detail": database_detail,
        },
        "deepseek": {
            "status": "ready" if model_ready else "degraded",
            "detail": f"configured: {settings.deepseek_model}"
            if model_ready
            else "DEEPSEEK_API_KEY 未配置",
        },
        "local_models": {
            "status": "ready" if settings.model_runtime_enabled else "degraded",
            "detail": "lazy loading enabled"
            if settings.model_runtime_enabled
            else "MODEL_RUNTIME_ENABLED=false，使用确定性测试向量",
        },
    }
    return {
        "status": "ok" if database_ready and model_ready else "degraded",
        "contract_version": "v0.2",
        "mode": settings.app_env,
        "dependencies": dependencies,
        "data_version": "demo-2026.1",
    }


@app.get("/api/v1/dashboard", response_model=DashboardResponse)
def dashboard(session: Session = Depends(get_db)) -> dict:
    return dashboard_dict(session)


@app.post("/api/v1/assets", response_model=AssetResult, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> dict:
    content = await file.read(settings.max_upload_bytes + 1)
    asset = save_asset(session, content, file.filename)
    return {
        "asset_id": asset.id,
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
        "sha256": asset.sha256,
        "ocr_text": asset.ocr_text,
        "ocr_confidence": asset.ocr_confidence,
        "ocr_requires_confirmation": bool(asset.ocr_text) and (asset.ocr_confidence or 0) < 0.85,
        "phash": asset.phash,
        "created_at": asset.created_at,
    }


@app.get("/api/v1/assets/{asset_id}/content", response_class=FileResponse)
def asset_content(asset_id: str, session: Session = Depends(get_db)) -> FileResponse:
    asset = require(session, ImageAsset, asset_id, "图片资产")
    root = settings.upload_dir.resolve()
    path = (root / asset.storage_key).resolve()
    if root not in path.parents or not path.exists():
        raise AppError(404, "ASSET_FILE_NOT_FOUND", "图片文件不存在。")
    return FileResponse(path, media_type=asset.mime_type, filename=asset.original_filename)


@app.post("/api/v1/cases", response_model=CaseContext, status_code=status.HTTP_201_CREATED)
def create_case(payload: CaseCreate, session: Session = Depends(get_db)) -> dict:
    asset = None
    if payload.image_asset_id:
        asset = require(session, ImageAsset, payload.image_asset_id, "图片资产")
    confirmed_ocr = payload.confirmed_ocr_text
    if asset and asset.ocr_text and confirmed_ocr is None and (asset.ocr_confidence or 0) < 0.85:
        raise AppError(
            409,
            "OCR_CONFIRMATION_REQUIRED",
            "OCR 置信度较低，请确认或修改识别文字后再创建案件。",
            {"asset_id": asset.id, "ocr_text": asset.ocr_text, "confidence": asset.ocr_confidence},
        )
    facts = {
        "trademark_name": payload.trademark_name,
        "business_description": payload.business_description,
        "nice_classes": payload.nice_classes,
        "image_asset_id": payload.image_asset_id,
        "confirmed_ocr_text": confirmed_ocr,
        "confirmed_at": datetime.utcnow().isoformat(),
    }
    item = CaseRecord(
        trademark_name=payload.trademark_name,
        business_description=payload.business_description,
        nice_classes=payload.nice_classes,
        image_asset_id=payload.image_asset_id,
        confirmed_ocr_text=confirmed_ocr,
        facts_snapshot=facts,
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return case_dict(item)


@app.get("/api/v1/cases", response_model=list[CaseContext])
def list_cases(session: Session = Depends(get_db)) -> list[dict]:
    items = session.scalars(
        select(CaseRecord).order_by(CaseRecord.created_at.desc()).limit(50)
    ).all()
    return [case_dict(item) for item in items]


@app.get("/api/v1/cases/{case_id}", response_model=CaseContext)
def get_case(case_id: str, session: Session = Depends(get_db)) -> dict:
    return case_dict(require(session, CaseRecord, case_id, "案件"))


@app.post("/api/v1/searches", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED)
def create_search(
    payload: SearchCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> dict:
    case = require(session, CaseRecord, payload.case_id, "案件")
    item = SearchRecord(
        case_id=case.id,
        query_snapshot=case.facts_snapshot,
        config_version=settings.retrieval_config_version,
        top_k=payload.top_k,
    )
    session.add(item)
    session.commit()
    run = create_agent_run(session, "search", request_id(request), "search", item.id)
    schedule(background_tasks, run, build_search_operation(item.id))
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


@app.get("/api/v1/searches/{search_id}", response_model=EvidenceBundle)
def get_search(search_id: str, session: Session = Depends(get_db)) -> dict:
    return search_dict(session, require(session, SearchRecord, search_id, "检索"))


@app.post(
    "/api/v1/risk-analyses", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED
)
def create_risk_analysis(
    payload: RiskAnalysisCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> dict:
    require(session, SearchRecord, payload.search_id, "检索")
    run = create_agent_run(session, "risk", request_id(request))
    schedule(background_tasks, run, build_risk_operation(payload.search_id, payload.analysis_date))
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


@app.get("/api/v1/risk-analyses/{analysis_id}", response_model=RiskAssessment)
def get_risk_analysis(analysis_id: str, session: Session = Depends(get_db)) -> dict:
    return risk_dict(require(session, RiskAnalysis, analysis_id, "风险分析"))


@app.post(
    "/api/v1/documents", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED
)
def create_document(
    payload: DocumentCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> dict:
    require(session, RiskAnalysis, payload.analysis_id, "风险分析")
    run = create_agent_run(session, "document", request_id(request))
    schedule(
        background_tasks, run, build_document_operation(payload.analysis_id, payload.document_type)
    )
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


@app.get("/api/v1/documents/{document_id}", response_model=DocumentDraftResponse)
def get_document(document_id: str, session: Session = Depends(get_db)) -> dict:
    return document_dict(require(session, DocumentDraft, document_id, "文书"))


@app.put("/api/v1/documents/{document_id}", response_model=DocumentDraftResponse)
def update_document(
    document_id: str,
    payload: DocumentUpdate,
    session: Session = Depends(get_db),
) -> dict:
    item = require(session, DocumentDraft, document_id, "文书")
    analysis = require(session, RiskAnalysis, item.analysis_id, "风险分析")
    item.sections = [section.model_dump() for section in payload.sections]
    from .rag import validate_document

    item.validation_errors = validate_document(
        item.sections,
        item.citations,
        item.facts_snapshot,
        analysis.analysis_date,
    )
    session.commit()
    session.refresh(item)
    return document_dict(item)


@app.post("/api/v1/documents/{document_id}/validate", response_model=DocumentDraftResponse)
def validate_document_endpoint(document_id: str, session: Session = Depends(get_db)) -> dict:
    item = require(session, DocumentDraft, document_id, "文书")
    analysis = require(session, RiskAnalysis, item.analysis_id, "风险分析")
    from .rag import validate_document

    item.validation_errors = validate_document(
        item.sections,
        item.citations,
        item.facts_snapshot,
        analysis.analysis_date,
    )
    session.commit()
    return document_dict(item)


@app.post(
    "/api/v1/consultations", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED
)
def create_consultation(
    payload: ConsultationCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> dict:
    if payload.case_id:
        require(session, CaseRecord, payload.case_id, "案件")
    item = Consultation(
        case_id=payload.case_id,
        question=payload.question,
        analysis_date=payload.analysis_date,
        disclaimer="本结果仅用于课程演示，不构成法律意见。",
    )
    session.add(item)
    session.commit()
    run = create_agent_run(session, "consultation", request_id(request), "consultation", item.id)
    schedule(background_tasks, run, build_consultation_operation(item.id))
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


@app.get("/api/v1/consultations/{consultation_id}", response_model=ConsultationAnswer)
def get_consultation(consultation_id: str, session: Session = Depends(get_db)) -> dict:
    return consultation_dict(require(session, Consultation, consultation_id, "咨询记录"))


@app.get("/api/v1/agent-runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(run_id: str, session: Session = Depends(get_db)) -> dict:
    return agent_run_dict(require(session, AgentRun, run_id, "智能体任务"))


@app.get("/api/v1/sources", response_model=list[SourceDefinitionResponse])
def get_sources(session: Session = Depends(get_db)) -> list[dict]:
    return source_list(session)


@app.post(
    "/api/v1/sources/{source_key}/sync",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def sync_registered_source(
    source_key: str,
    payload: SourceSyncCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> dict:
    try:
        REGISTRY.get(source_key)
    except KeyError as exc:
        raise AppError(404, "SOURCE_NOT_REGISTERED", "数据源未在服务端注册。") from exc
    source = session.scalar(
        select(SourceDefinition).where(SourceDefinition.source_key == source_key)
    )
    if source is None:
        raise AppError(404, "SOURCE_NOT_INITIALIZED", "请先运行 make seed 初始化数据源定义。")
    ingestion = IngestionRun(source_id=source.id, cursor_started=payload.cursor)
    session.add(ingestion)
    session.commit()
    run = create_agent_run(session, "ingestion", request_id(request), "ingestion_run", ingestion.id)
    schedule(
        background_tasks,
        run,
        build_ingestion_operation(
            source_key,
            ingestion.id,
            payload.cursor,
            payload.page_size,
            payload.max_pages,
        ),
    )
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


@app.get("/api/v1/ingestion-runs/{ingestion_run_id}", response_model=IngestionRunResponse)
def get_ingestion_run(ingestion_run_id: str, session: Session = Depends(get_db)) -> dict:
    return ingestion_dict(
        session,
        require(session, IngestionRun, ingestion_run_id, "导入任务"),
    )
