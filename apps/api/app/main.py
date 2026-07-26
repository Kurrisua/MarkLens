"""MarkLens product API with private user resources and an operations domain."""

from __future__ import annotations

import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import (
    BackgroundTasks,
    Cookie,
    Depends,
    FastAPI,
    File,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ai_providers import AIConfigurationError, AIRequestConfig
from .attachments import extract_attachment
from .auth import (
    ROLE_ADMIN,
    ROLE_OPERATOR,
    CurrentUser,
    audit,
    consume_refresh_token,
    create_access_token,
    current_user,
    hash_password,
    issue_refresh_token,
    require_project_access,
    require_roles,
    roles_for,
    verify_password,
)
from .config import REPOSITORY_ROOT, get_settings
from .db import database_health, get_db
from .errors import AppError
from .models import (
    AgentRun,
    AuditEvent,
    CaseRecord,
    Consultation,
    DocumentDraft,
    ImageAsset,
    IngestionRun,
    LearningArticle,
    LearningAttempt,
    LearningTopic,
    LearningVideo,
    PracticeQuestion,
    Project,
    ProjectAttachment,
    RiskAnalysis,
    SearchRecord,
    SourceDefinition,
    Trademark,
    User,
    UserRole,
)
from .pdf_export import render_document_pdf
from .retrieval import save_asset
from .schemas import (
    AdminUserResponse,
    AdminUserRolesUpdate,
    AgentRunResponse,
    AppDashboardResponse,
    AssetResult,
    AuthResponse,
    CaseContext,
    CaseCreate,
    ConsultationAnswer,
    ConsultationCreate,
    CurrentUserResponse,
    DashboardResponse,
    DocumentCreate,
    DocumentDraftResponse,
    DocumentUpdate,
    EvidenceBundle,
    HealthResponse,
    IngestionRunResponse,
    LearningArticleResponse,
    LearningTopicResponse,
    LearningVideoResponse,
    LoginCreate,
    OpsLearningTopicUpsert,
    OpsLearningVideoCreate,
    OpsOverviewResponse,
    OpsPracticeQuestionCreate,
    OpsPracticeQuestionResponse,
    PracticeAttemptCreate,
    PracticeAttemptResponse,
    PracticeQuestionResponse,
    ProjectAdvisorMessage,
    ProjectAdvisorQuestionCreate,
    ProjectAttachmentResponse,
    ProjectCreate,
    ProjectResponse,
    RegisterCreate,
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
    update_run,
)
from .sources import REGISTRY

settings = get_settings()
logging.basicConfig(level=settings.app_log_level)
logger = logging.getLogger("marklens.api")
app = FastAPI(
    title="MarkLens API",
    version="0.3.0",
    description=(
        "面向中国大陆商标学习与注册风险初筛的产品 API。检索分数为启发式规则，生成内容不构成法律意见。"
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


def resolved_asset_path(asset: ImageAsset) -> Path:
    """Return an app-owned asset path, recovering the pre-product storage layout once.

    Earlier local builds stored uploads in ``<repository>/data/uploads``.  The
    product API now owns its data below ``apps/api/data/uploads``.  Existing
    database rows keep their relative storage key, so copying a legacy file on
    first read preserves uploaded evidence instead of turning valid records
    into a broken-image placeholder after an upgrade.
    """
    root = settings.upload_dir.resolve()
    path = (root / asset.storage_key).resolve()
    if root not in path.parents:
        raise AppError(404, "ASSET_FILE_NOT_FOUND", "图片文件路径无效。")
    if path.exists():
        return path

    legacy_root = (REPOSITORY_ROOT / "data" / "uploads").resolve()
    legacy_path = (legacy_root / asset.storage_key).resolve()
    if legacy_root in legacy_path.parents and legacy_path.exists() and legacy_path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy_path, path)
        logger.info("Recovered legacy image asset %s into API storage", asset.id)
        return path
    raise AppError(404, "ASSET_FILE_NOT_FOUND", "图片文件不存在。")


def request_id(request: Request) -> str:
    return getattr(
        request.state,
        "request_id",
        request.headers.get("X-Request-ID", f"req_{uuid4().hex}"),
    )


def optional_ai_config(request: Request) -> AIRequestConfig | None:
    """Use a browser-only model configuration only when one was supplied."""
    if not request.headers.get("X-Marklens-AI-Provider"):
        return None
    try:
        return AIRequestConfig.from_headers(request.headers)
    except AIConfigurationError as exc:
        raise AppError(422, "AI_CONFIGURATION_INVALID", str(exc)) from exc


def require_user_ai_config(request: Request) -> AIRequestConfig:
    config = optional_ai_config(request)
    if config is None:
        raise AppError(
            422,
            "AI_CONFIGURATION_REQUIRED",
            "此功能需要你在 AI 设置中填写自己的模型和 API Key；系统不会使用服务端默认模型。",
        )
    return config


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
    legacy_paths = (
        "/api/v1/dashboard",
        "/api/v1/assets",
        "/api/v1/cases",
        "/api/v1/searches",
        "/api/v1/risk-analyses",
        "/api/v1/documents",
        "/api/v1/consultations",
        "/api/v1/agent-runs",
        "/api/v1/sources",
        "/api/v1/ingestion-runs",
    )
    if any(
        request.url.path == path or request.url.path.startswith(f"{path}/") for path in legacy_paths
    ):
        return error_response(
            request,
            status.HTTP_410_GONE,
            "LEGACY_ENDPOINT_RETIRED",
            "该接口已迁移至受权限保护的产品接口。",
        )
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    logger.info(
        "request_complete request_id=%s method=%s path=%s status=%s elapsed_ms=%s model_mode=%s dataset=%s config=%s",
        request.state.request_id,
        request.method,
        request.url.path,
        response.status_code,
        round((time.perf_counter() - started) * 1000, 2),
        "user_supplied_or_deterministic",
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
        "服务器暂时未能完成请求，请稍后重试。",
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


def user_response(actor: CurrentUser) -> dict:
    return {
        "user_id": actor.user.id,
        "email": actor.user.email,
        "display_name": actor.user.display_name,
        "roles": sorted(actor.roles),
    }


def project_response(session: Session, item: Project) -> dict:
    return {
        "project_id": item.id,
        "name": item.name,
        "business_description": item.business_description,
        "status": item.status,
        "owner_id": item.owner_id,
        "case_count": session.scalar(
            select(func.count(CaseRecord.id)).where(CaseRecord.project_id == item.id)
        )
        or 0,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def require_owned_case(session: Session, case_id: str, actor: CurrentUser) -> CaseRecord:
    item = require(session, CaseRecord, case_id, "商标方案")
    if item.project_id:
        require_project_access(session, item.project_id, actor)
    elif not actor.is_admin and item.owner_id != actor.user.id:
        raise AppError(403, "PERMISSION_DENIED", "你无权访问此商标方案。")
    return item


@app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterCreate,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> dict:
    email = payload.email.strip().lower()
    if session.scalar(select(User).where(User.email == email)):
        raise AppError(409, "EMAIL_ALREADY_REGISTERED", "该邮箱已注册，请直接登录。")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
    )
    session.add(user)
    session.flush()
    session.add(UserRole(user_id=user.id, role="user"))
    actor = CurrentUser(user, {"user"})
    refresh_token = issue_refresh_token(session, user, request.headers.get("User-Agent"))
    audit(session, request, actor, "auth.register", "user", user.id)
    session.commit()
    response.set_cookie(
        "marklens_refresh",
        refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )
    return {"access_token": create_access_token(user, actor.roles), "user": user_response(actor)}


@app.post("/api/v1/auth/login", response_model=AuthResponse)
def login(
    payload: LoginCreate,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
) -> dict:
    user = session.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if (
        user is None
        or user.status != "active"
        or not verify_password(payload.password, user.password_hash)
    ):
        raise AppError(401, "INVALID_CREDENTIALS", "邮箱或密码不正确。")
    user.last_login_at = datetime.utcnow()
    actor = CurrentUser(user, roles_for(session, user.id))
    refresh_token = issue_refresh_token(session, user, request.headers.get("User-Agent"))
    audit(session, request, actor, "auth.login", "user", user.id)
    session.commit()
    response.set_cookie(
        "marklens_refresh",
        refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )
    return {"access_token": create_access_token(user, actor.roles), "user": user_response(actor)}


@app.post("/api/v1/auth/refresh", response_model=AuthResponse)
def refresh(
    request: Request,
    response: Response,
    marklens_refresh: str | None = Cookie(default=None),
    session: Session = Depends(get_db),
) -> dict:
    if not marklens_refresh:
        raise AppError(401, "REFRESH_TOKEN_INVALID", "登录状态已失效，请重新登录。")
    user = consume_refresh_token(session, marklens_refresh)
    actor = CurrentUser(user, roles_for(session, user.id))
    next_token = issue_refresh_token(session, user, request.headers.get("User-Agent"))
    audit(session, request, actor, "auth.refresh", "user", user.id)
    session.commit()
    response.set_cookie(
        "marklens_refresh",
        next_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/api/v1/auth",
    )
    return {"access_token": create_access_token(user, actor.roles), "user": user_response(actor)}


@app.post("/api/v1/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    marklens_refresh: str | None = Cookie(default=None),
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> Response:
    if marklens_refresh:
        from hashlib import sha256

        from .models import AuthSession

        item = session.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == sha256(marklens_refresh.encode()).hexdigest()
            )
        )
        if item and item.user_id == actor.user.id:
            item.revoked_at = datetime.utcnow()
    audit(session, request, actor, "auth.logout", "user", actor.user.id)
    session.commit()
    response.delete_cookie("marklens_refresh", path="/api/v1/auth")
    return response


@app.get("/api/v1/auth/me", response_model=CurrentUserResponse)
def me(actor: CurrentUser = Depends(current_user)) -> dict:
    return user_response(actor)


@app.get("/api/v1/app/dashboard", response_model=AppDashboardResponse)
def app_dashboard(
    session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> dict:
    projects = session.scalars(
        select(Project)
        .where(Project.owner_id == actor.user.id)
        .order_by(Project.updated_at.desc())
        .limit(12)
    ).all()
    attempts = (
        session.scalar(
            select(func.count(LearningAttempt.id)).where(LearningAttempt.user_id == actor.user.id)
        )
        or 0
    )
    correct = (
        session.scalar(
            select(func.count(LearningAttempt.id)).where(
                LearningAttempt.user_id == actor.user.id, LearningAttempt.is_correct.is_(True)
            )
        )
        or 0
    )
    return {
        "projects": [project_response(session, item) for item in projects],
        "learning_progress": {"attempts": attempts, "correct": correct},
    }


@app.post(
    "/api/v1/app/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED
)
def create_project(
    payload: ProjectCreate,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> dict:
    project = Project(
        owner_id=actor.user.id,
        name=payload.name.strip(),
        business_description=payload.business_description.strip(),
    )
    session.add(project)
    session.flush()
    audit(session, request, actor, "project.create", "project", project.id)
    session.commit()
    session.refresh(project)
    return project_response(session, project)


@app.get("/api/v1/app/projects", response_model=list[ProjectResponse])
def list_projects(
    session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> list[dict]:
    items = session.scalars(
        select(Project).where(Project.owner_id == actor.user.id).order_by(Project.updated_at.desc())
    ).all()
    return [project_response(session, item) for item in items]


@app.get("/api/v1/app/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> dict:
    return project_response(session, require_project_access(session, project_id, actor))


@app.post("/api/v1/app/assets", response_model=AssetResult, status_code=status.HTTP_201_CREATED)
async def app_upload_asset(
    file: UploadFile = File(...),
    project_id: str | None = None,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> dict:
    if project_id:
        require_project_access(session, project_id, actor)
    content = await file.read(settings.max_upload_bytes + 1)
    asset = save_asset(session, content, file.filename)
    asset.owner_id = actor.user.id
    asset.project_id = project_id
    session.commit()
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


@app.post("/api/v1/app/projects/{project_id}/attachments", response_model=ProjectAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def app_upload_project_attachment(project_id: str, file: UploadFile = File(...), session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)) -> dict:
    require_project_access(session, project_id, actor)
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise AppError(413, "FILE_TOO_LARGE", "附件不能超过 5MB。")
    try:
        extracted = extract_attachment(session, content, file.filename or "attachment", file.content_type or "application/octet-stream")
    except ValueError as exc:
        raise AppError(422, "UNSUPPORTED_ATTACHMENT", str(exc)) from exc
    item = ProjectAttachment(project_id=project_id, owner_id=actor.user.id, filename=(file.filename or "attachment")[:255], mime_type=file.content_type or "application/octet-stream", raw_content=content, **extracted)
    session.add(item)
    session.commit()
    session.refresh(item)
    return {"attachment_id": item.id, "filename": item.filename, "mime_type": item.mime_type, "normalized_text": item.normalized_text, "structure": item.structure, "extracted_image_asset_id": item.extracted_image_asset_id, "created_at": item.created_at}


@app.get("/api/v1/app/projects/{project_id}/attachments", response_model=list[ProjectAttachmentResponse])
def app_list_project_attachments(project_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)) -> list[dict]:
    require_project_access(session, project_id, actor)
    items = session.scalars(select(ProjectAttachment).where(ProjectAttachment.project_id == project_id).order_by(ProjectAttachment.created_at.desc())).all()
    return [{"attachment_id": item.id, "filename": item.filename, "mime_type": item.mime_type, "normalized_text": item.normalized_text, "structure": item.structure, "extracted_image_asset_id": item.extracted_image_asset_id, "created_at": item.created_at} for item in items]


@app.post(
    "/api/v1/app/projects/{project_id}/marks",
    response_model=CaseContext,
    status_code=status.HTTP_201_CREATED,
)
def create_project_mark(
    project_id: str,
    payload: CaseCreate,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> dict:
    require_project_access(session, project_id, actor)
    asset = (
        require(session, ImageAsset, payload.image_asset_id, "图片资产")
        if payload.image_asset_id
        else None
    )
    if asset and (asset.owner_id != actor.user.id or asset.project_id not in {None, project_id}):
        raise AppError(403, "PERMISSION_DENIED", "你无权使用此图样。")
    confirmed_ocr = payload.confirmed_ocr_text
    if asset and asset.ocr_text and confirmed_ocr is None and (asset.ocr_confidence or 0) < 0.85:
        raise AppError(
            409, "OCR_CONFIRMATION_REQUIRED", "OCR 置信度较低，请确认或修改识别文字后再创建方案。"
        )
    item = CaseRecord(
        owner_id=actor.user.id,
        project_id=project_id,
        trademark_name=payload.trademark_name,
        business_description=payload.business_description,
        nice_classes=payload.nice_classes,
        image_asset_id=payload.image_asset_id,
        confirmed_ocr_text=confirmed_ocr,
        facts_snapshot={
            "trademark_name": payload.trademark_name,
            "business_description": payload.business_description,
            "nice_classes": payload.nice_classes,
            "image_asset_id": payload.image_asset_id,
            "confirmed_ocr_text": confirmed_ocr,
            "confirmed_at": datetime.utcnow().isoformat(),
        },
    )
    session.add(item)
    session.flush()
    audit(session, request, actor, "mark.create", "case", item.id, {"project_id": project_id})
    session.commit()
    return case_dict(item)


@app.get("/api/v1/app/assets/{asset_id}/content", response_class=FileResponse)
def app_asset_content(
    asset_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> FileResponse:
    asset = require(session, ImageAsset, asset_id, "图片资产")
    if asset.owner_id != actor.user.id and not actor.is_admin:
        raise AppError(403, "PERMISSION_DENIED", "你无权访问此图样。")
    path = resolved_asset_path(asset)
    return FileResponse(path, media_type=asset.mime_type, filename=asset.original_filename)


@app.get("/api/v1/app/trademarks/{trademark_id}/image", response_class=FileResponse)
def app_trademark_image(
    trademark_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> FileResponse:
    """Serve a source-trademark image as public comparison evidence to signed-in users."""
    trademark = require(session, Trademark, trademark_id, "候选商标")
    if not trademark.image_asset_id:
        raise AppError(404, "TRADEMARK_IMAGE_NOT_FOUND", "该候选记录未提供可展示的图样。")
    asset = require(session, ImageAsset, trademark.image_asset_id, "候选图样")
    path = resolved_asset_path(asset)
    return FileResponse(path, media_type=asset.mime_type, filename=asset.original_filename)


@app.get("/api/v1/app/projects/{project_id}/marks", response_model=list[CaseContext])
def list_project_marks(
    project_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> list[dict]:
    require_project_access(session, project_id, actor)
    items = session.scalars(
        select(CaseRecord)
        .where(CaseRecord.project_id == project_id)
        .order_by(CaseRecord.created_at.desc())
    ).all()
    return [case_dict(item) for item in items]


@app.post(
    "/api/v1/app/searches", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED
)
def app_create_search(
    payload: SearchCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
    ai_config: AIRequestConfig | None = Depends(optional_ai_config),
) -> dict:
    case = require_owned_case(session, payload.case_id, actor)
    item = SearchRecord(
        case_id=case.id,
        owner_id=case.owner_id,
        query_snapshot=case.facts_snapshot,
        config_version=settings.retrieval_config_version,
        top_k=payload.top_k,
    )
    session.add(item)
    session.commit()
    run = create_agent_run(
        session, "search", request_id(request), "search", item.id, owner_id=actor.user.id
    )
    schedule(background_tasks, run, build_search_operation(item.id, ai_config))
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


def require_owned_search(session: Session, search_id: str, actor: CurrentUser) -> SearchRecord:
    item = require(session, SearchRecord, search_id, "检索")
    if item.owner_id != actor.user.id and not actor.is_admin:
        raise AppError(403, "PERMISSION_DENIED", "你无权访问此检索。")
    return item


@app.get("/api/v1/app/searches/{search_id}", response_model=EvidenceBundle)
def app_get_search(
    search_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> dict:
    return search_dict(session, require_owned_search(session, search_id, actor))


@app.get(
    "/api/v1/app/projects/{project_id}/advisor/messages",
    response_model=list[ProjectAdvisorMessage],
)
def list_project_advisor_messages(
    project_id: str,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> list[dict]:
    require_project_access(session, project_id, actor)
    items = session.scalars(
        select(Consultation)
        .where(Consultation.project_id == project_id, Consultation.owner_id == actor.user.id)
        .order_by(Consultation.created_at.asc())
        .limit(80)
    ).all()
    return [
        {**consultation_dict(item), "project_id": project_id, "case_id": item.case_id}
        for item in items
    ]


@app.post(
    "/api/v1/app/projects/{project_id}/advisor/messages",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_project_advisor_message(
    project_id: str,
    payload: ProjectAdvisorQuestionCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
    ai_config: AIRequestConfig = Depends(require_user_ai_config),
) -> dict:
    require_project_access(session, project_id, actor)
    if payload.case_id:
        case = require_owned_case(session, payload.case_id, actor)
        if case.project_id != project_id:
            raise AppError(422, "CASE_PROJECT_MISMATCH", "选择的商标方案不属于当前项目。")
    item = Consultation(
        owner_id=actor.user.id,
        project_id=project_id,
        case_id=payload.case_id,
        question=payload.question.strip(),
        analysis_date=payload.analysis_date,
        disclaimer="本结果仅用于课程演示和商标风险初筛，不构成法律意见。",
    )
    session.add(item)
    session.flush()
    audit(
        session, request, actor, "advisor.ask", "consultation", item.id, {"project_id": project_id}
    )
    session.commit()
    run = create_agent_run(
        session,
        "consultation",
        request_id(request),
        "consultation",
        item.id,
        owner_id=actor.user.id,
    )
    schedule(background_tasks, run, build_consultation_operation(item.id, ai_config))
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


@app.post(
    "/api/v1/app/risk-analyses",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def app_create_risk(
    payload: RiskAnalysisCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> dict:
    search = require_owned_search(session, payload.search_id, actor)
    run = create_agent_run(session, "risk", request_id(request), owner_id=search.owner_id)
    schedule(background_tasks, run, build_risk_operation(search.id, payload.analysis_date))
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


def require_owned_analysis(session: Session, analysis_id: str, actor: CurrentUser) -> RiskAnalysis:
    item = require(session, RiskAnalysis, analysis_id, "风险分析")
    if item.owner_id != actor.user.id and not actor.is_admin:
        raise AppError(403, "PERMISSION_DENIED", "你无权访问此风险分析。")
    return item


@app.get("/api/v1/app/risk-analyses/{analysis_id}", response_model=RiskAssessment)
def app_get_risk(
    analysis_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> dict:
    return risk_dict(require_owned_analysis(session, analysis_id, actor))


@app.get("/api/v1/app/risk-analyses/{analysis_id}/document", response_model=DocumentDraftResponse)
def app_get_saved_document(
    analysis_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> dict:
    analysis = require_owned_analysis(session, analysis_id, actor)
    item = session.scalar(
        select(DocumentDraft)
        .where(DocumentDraft.analysis_id == analysis.id, DocumentDraft.owner_id == actor.user.id)
        .order_by(DocumentDraft.updated_at.desc())
    )
    if item is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "该风险分析尚未生成报告。")
    return document_dict(item)


def require_owned_document(session: Session, document_id: str, actor: CurrentUser) -> DocumentDraft:
    item = require(session, DocumentDraft, document_id, "报告")
    if item.owner_id != actor.user.id and not actor.is_admin:
        raise AppError(403, "PERMISSION_DENIED", "你无权访问此报告。")
    return item


@app.post(
    "/api/v1/app/documents", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED
)
def app_create_document(
    payload: DocumentCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
    ai_config: AIRequestConfig = Depends(require_user_ai_config),
) -> dict:
    analysis = require_owned_analysis(session, payload.analysis_id, actor)
    existing = session.scalar(
        select(DocumentDraft)
        .where(
            DocumentDraft.analysis_id == analysis.id,
            DocumentDraft.owner_id == actor.user.id,
            DocumentDraft.document_type == payload.document_type,
        )
        .order_by(DocumentDraft.updated_at.desc())
    )
    if existing is not None:
        run = create_agent_run(session, "document", request_id(request), owner_id=analysis.owner_id)
        update_run(
            session,
            run,
            status="completed",
            progress=100,
            stage="已打开已保存的报告",
            resource_type="document",
            resource_id=existing.id,
        )
        audit(session, request, actor, "document.reuse", "document", existing.id)
        session.commit()
        session.refresh(run)
        return agent_run_dict(run)
    run = create_agent_run(session, "document", request_id(request), owner_id=analysis.owner_id)
    schedule(background_tasks, run, build_document_operation(analysis.id, payload.document_type, ai_config))
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


@app.get("/api/v1/app/documents/{document_id}", response_model=DocumentDraftResponse)
def app_get_document(
    document_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> dict:
    return document_dict(require_owned_document(session, document_id, actor))


@app.get("/api/v1/app/documents/{document_id}/export.pdf")
def app_export_document_pdf(
    document_id: str,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> Response:
    item = require_owned_document(session, document_id, actor)
    audit(session, request, actor, "document.export", "document", item.id)
    session.commit()
    return Response(
        content=render_document_pdf(item),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="marklens-report-{item.id}.pdf"'},
    )


@app.put("/api/v1/app/documents/{document_id}", response_model=DocumentDraftResponse)
def app_update_document(
    document_id: str,
    payload: DocumentUpdate,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> dict:
    item = require_owned_document(session, document_id, actor)
    analysis = require_owned_analysis(session, item.analysis_id, actor)
    from .rag import validate_document

    item.sections = [section.model_dump() for section in payload.sections]
    item.validation_errors = validate_document(
        item.sections, item.citations, item.facts_snapshot, analysis.analysis_date
    )
    audit(session, request, actor, "document.update", "document", item.id)
    session.commit()
    return document_dict(item)


@app.get("/api/v1/app/runs/{run_id}", response_model=AgentRunResponse)
def app_get_run(
    run_id: str, session: Session = Depends(get_db), actor: CurrentUser = Depends(current_user)
) -> dict:
    run = require(session, AgentRun, run_id, "分析任务")
    if run.owner_id != actor.user.id and not actor.is_admin:
        raise AppError(403, "PERMISSION_DENIED", "你无权访问此分析任务。")
    payload = agent_run_dict(run)
    if run.status == "failed":
        payload["error"] = {
            "code": run.error_code or "TASK_FAILED",
            "message": "分析未能完成，请稍后重试。",
        }
    return payload


@app.get("/api/v1/app/learn/topics", response_model=list[LearningTopicResponse])
def list_learning_topics(session: Session = Depends(get_db)) -> list[dict]:
    topics = session.scalars(
        select(LearningTopic)
        .where(LearningTopic.is_published.is_(True))
        .order_by(LearningTopic.order_index)
    ).all()
    return [
        {
            "topic_id": topic.id,
            "slug": topic.slug,
            "title": topic.title,
            "summary": topic.summary,
            "article_count": session.scalar(
                select(func.count(LearningArticle.id)).where(
                    LearningArticle.topic_id == topic.id, LearningArticle.is_published.is_(True)
                )
            )
            or 0,
        }
        for topic in topics
    ]


@app.get("/api/v1/app/learn/topics/{slug}", response_model=list[LearningArticleResponse])
def get_learning_topic(slug: str, session: Session = Depends(get_db)) -> list[dict]:
    topic = session.scalar(
        select(LearningTopic).where(
            LearningTopic.slug == slug, LearningTopic.is_published.is_(True)
        )
    )
    if topic is None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "学习主题不存在。")
    items = session.scalars(
        select(LearningArticle)
        .where(LearningArticle.topic_id == topic.id, LearningArticle.is_published.is_(True))
        .order_by(LearningArticle.order_index)
    ).all()
    return [
        {"article_id": item.id, "title": item.title, "body": item.body, "citations": item.citations}
        for item in items
    ]


@app.get("/api/v1/app/learn/videos", response_model=list[LearningVideoResponse])
def list_learning_videos(session: Session = Depends(get_db)) -> list[dict]:
    rows = session.execute(
        select(LearningVideo, LearningTopic)
        .join(LearningTopic, LearningTopic.id == LearningVideo.topic_id)
        .where(LearningVideo.is_published.is_(True), LearningTopic.is_published.is_(True))
        .order_by(LearningTopic.order_index, LearningVideo.order_index, LearningVideo.created_at)
    ).all()
    return [learning_video_dict(video, topic) for video, topic in rows]


@app.get("/api/v1/app/practice/questions", response_model=list[PracticeQuestionResponse])
def list_practice_questions(session: Session = Depends(get_db)) -> list[dict]:
    items = session.scalars(
        select(PracticeQuestion)
        .where(PracticeQuestion.is_published.is_(True))
        .order_by(PracticeQuestion.created_at.desc())
    ).all()
    return [
        {
            "question_id": item.id,
            "title": item.title,
            "prompt": item.prompt,
            "options": item.options,
            "difficulty": item.difficulty,
        }
        for item in items
    ]


@app.post(
    "/api/v1/app/practice/questions/{question_id}/attempts",
    response_model=PracticeAttemptResponse,
    status_code=status.HTTP_201_CREATED,
)
def answer_practice_question(
    question_id: str,
    payload: PracticeAttemptCreate,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(current_user),
) -> dict:
    item = require(session, PracticeQuestion, question_id, "练习题")
    if not item.is_published:
        raise AppError(404, "RESOURCE_NOT_FOUND", "练习题不存在。")
    attempt = LearningAttempt(
        user_id=actor.user.id,
        question_id=item.id,
        selected_option=payload.selected_option,
        is_correct=payload.selected_option == item.correct_option,
    )
    session.add(attempt)
    audit(
        session,
        request,
        actor,
        "practice.answer",
        "practice_question",
        item.id,
        {"is_correct": attempt.is_correct},
    )
    session.commit()
    return {
        "attempt_id": attempt.id,
        "is_correct": attempt.is_correct,
        "explanation": item.explanation,
    }


@app.get("/api/v1/ops/overview", response_model=OpsOverviewResponse)
def ops_overview(
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict:
    statuses = session.execute(
        select(AgentRun.status, func.count(AgentRun.id)).group_by(AgentRun.status)
    ).all()
    return {
        "users": session.scalar(select(func.count(User.id))) or 0,
        "projects": session.scalar(select(func.count(Project.id))) or 0,
        "runs": {status: count for status, count in statuses},
        "published_topics": session.scalar(
            select(func.count(LearningTopic.id)).where(LearningTopic.is_published.is_(True))
        )
        or 0,
    }


@app.get("/api/v1/ops/learning/topics", response_model=list[LearningTopicResponse])
def ops_list_learning_topics(
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> list[dict]:
    items = session.scalars(
        select(LearningTopic).order_by(LearningTopic.order_index, LearningTopic.created_at)
    ).all()
    return [
        {
            "topic_id": item.id,
            "slug": item.slug,
            "title": item.title,
            "summary": item.summary,
            "article_count": session.scalar(
                select(func.count(LearningArticle.id)).where(LearningArticle.topic_id == item.id)
            )
            or 0,
        }
        for item in items
    ]


@app.post(
    "/api/v1/ops/learning/topics",
    response_model=LearningTopicResponse,
    status_code=status.HTTP_201_CREATED,
)
def ops_create_learning_topic(
    payload: OpsLearningTopicUpsert,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict:
    if session.scalar(select(LearningTopic).where(LearningTopic.slug == payload.slug)):
        raise AppError(409, "RESOURCE_ALREADY_EXISTS", "该学习主题标识已存在。")
    topic = LearningTopic(
        slug=payload.slug,
        title=payload.title,
        summary=payload.summary,
        order_index=session.scalar(select(func.count(LearningTopic.id))) or 0,
        is_published=payload.is_published,
    )
    session.add(topic)
    session.flush()
    session.add(
        LearningArticle(
            topic_id=topic.id,
            title=payload.title,
            body=payload.body,
            citations=[],
            is_published=payload.is_published,
        )
    )
    audit(
        session,
        request,
        actor,
        "learning_topic.create",
        "learning_topic",
        topic.id,
        {"published": payload.is_published},
    )
    session.commit()
    return {
        "topic_id": topic.id,
        "slug": topic.slug,
        "title": topic.title,
        "summary": topic.summary,
        "article_count": 1,
    }


def learning_video_dict(video: LearningVideo, topic: LearningTopic) -> dict:
    return {
        "video_id": video.id,
        "topic_slug": topic.slug,
        "topic_title": topic.title,
        "title": video.title,
        "provider": video.provider,
        "external_url": video.external_url,
        "duration_label": video.duration_label,
        "learning_objective": video.learning_objective,
        "is_published": video.is_published,
    }


@app.get("/api/v1/ops/learning/videos", response_model=list[LearningVideoResponse])
def ops_list_learning_videos(
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> list[dict]:
    rows = session.execute(
        select(LearningVideo, LearningTopic)
        .join(LearningTopic, LearningTopic.id == LearningVideo.topic_id)
        .order_by(LearningTopic.order_index, LearningVideo.order_index, LearningVideo.created_at)
    ).all()
    return [learning_video_dict(video, topic) for video, topic in rows]


@app.post(
    "/api/v1/ops/learning/videos",
    response_model=LearningVideoResponse,
    status_code=status.HTTP_201_CREATED,
)
def ops_create_learning_video(
    payload: OpsLearningVideoCreate,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict:
    topic = session.scalar(select(LearningTopic).where(LearningTopic.slug == payload.topic_slug))
    if topic is None:
        raise AppError(422, "LEARNING_TOPIC_NOT_FOUND", "请先选择一个已存在的学习主题。")
    if session.scalar(select(LearningVideo).where(LearningVideo.external_url == payload.external_url)):
        raise AppError(409, "RESOURCE_ALREADY_EXISTS", "该视频链接已经在学习中心中。")
    item = LearningVideo(
        topic_id=topic.id,
        title=payload.title.strip(),
        provider=payload.provider.strip(),
        external_url=payload.external_url,
        duration_label=payload.duration_label.strip(),
        learning_objective=payload.learning_objective.strip(),
        order_index=session.scalar(
            select(func.count(LearningVideo.id)).where(LearningVideo.topic_id == topic.id)
        )
        or 0,
        is_published=payload.is_published,
    )
    session.add(item)
    session.flush()
    audit(
        session,
        request,
        actor,
        "learning_video.create",
        "learning_video",
        item.id,
        {"topic_slug": topic.slug, "published": item.is_published, "provider": item.provider},
    )
    session.commit()
    return learning_video_dict(item, topic)


@app.post(
    "/api/v1/ops/practice/questions",
    response_model=PracticeQuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
def ops_create_practice_question(
    payload: OpsPracticeQuestionCreate,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict:
    option_ids = {item.get("id") for item in payload.options}
    if payload.correct_option not in option_ids:
        raise AppError(422, "VALIDATION_ERROR", "正确答案必须是某个选项的 id。")
    item = PracticeQuestion(
        title=payload.title,
        prompt=payload.prompt,
        options=payload.options,
        correct_option=payload.correct_option,
        explanation=payload.explanation,
        difficulty=payload.difficulty,
        is_published=payload.is_published,
    )
    session.add(item)
    session.flush()
    audit(
        session,
        request,
        actor,
        "practice_question.create",
        "practice_question",
        item.id,
        {"published": payload.is_published},
    )
    session.commit()
    return {
        "question_id": item.id,
        "title": item.title,
        "prompt": item.prompt,
        "options": item.options,
        "difficulty": item.difficulty,
    }


@app.get("/api/v1/ops/practice/questions", response_model=list[OpsPracticeQuestionResponse])
def ops_list_practice_questions(
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> list[dict]:
    """Return the operational question bank, including draft state and answer key."""
    items = session.scalars(
        select(PracticeQuestion).order_by(PracticeQuestion.created_at.desc()).limit(200)
    ).all()
    return [
        {
            "question_id": item.id,
            "title": item.title,
            "prompt": item.prompt,
            "options": item.options,
            "difficulty": item.difficulty,
            "correct_option": item.correct_option,
            "explanation": item.explanation,
            "is_published": item.is_published,
        }
        for item in items
    ]


@app.get("/api/v1/ops/runs", response_model=list[AgentRunResponse])
def ops_list_runs(
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> list[dict]:
    """Recent operational activity without exposing user project facts or asset content."""
    items = session.scalars(select(AgentRun).order_by(AgentRun.updated_at.desc()).limit(30)).all()
    return [agent_run_dict(item) for item in items]


@app.get("/api/v1/ops/sources", response_model=list[SourceDefinitionResponse])
def ops_sources(
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> list[dict]:
    return source_list(session)


@app.post(
    "/api/v1/ops/sources/{source_key}/sync",
    response_model=AgentRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ops_sync_source(
    source_key: str,
    payload: SourceSyncCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict:
    try:
        REGISTRY.get(source_key)
    except KeyError as exc:
        raise AppError(404, "SOURCE_NOT_REGISTERED", "数据源未在服务端注册。") from exc
    source = session.scalar(
        select(SourceDefinition).where(SourceDefinition.source_key == source_key)
    )
    if source is None:
        raise AppError(404, "SOURCE_NOT_INITIALIZED", "请先初始化数据源定义。")
    ingestion = IngestionRun(source_id=source.id, cursor_started=payload.cursor)
    session.add(ingestion)
    session.commit()
    run = create_agent_run(
        session,
        "ingestion",
        request_id(request),
        "ingestion_run",
        ingestion.id,
        owner_id=actor.user.id,
        visibility="ops",
    )
    audit(session, request, actor, "source.sync", "source", source.id, {"source_key": source_key})
    session.commit()
    schedule(
        background_tasks,
        run,
        build_ingestion_operation(
            source_key, ingestion.id, payload.cursor, payload.page_size, payload.max_pages
        ),
    )
    if settings.agent_eager:
        session.refresh(run)
    return agent_run_dict(run)


@app.get("/api/v1/admin/audit", response_model=list[dict])
def admin_audit(
    session: Session = Depends(get_db), actor: CurrentUser = Depends(require_roles(ROLE_ADMIN))
) -> list[dict]:
    items = session.scalars(
        select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100)
    ).all()
    return [
        {
            "event_id": item.id,
            "actor_id": item.actor_id,
            "action": item.action,
            "resource_type": item.resource_type,
            "resource_id": item.resource_id,
            "result": item.result,
            "created_at": item.created_at,
        }
        for item in items
    ]


@app.get("/api/v1/admin/users", response_model=list[AdminUserResponse])
def admin_list_users(
    session: Session = Depends(get_db), actor: CurrentUser = Depends(require_roles(ROLE_ADMIN))
) -> list[dict]:
    users = session.scalars(select(User).order_by(User.created_at.desc()).limit(200)).all()
    return [
        {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status,
            "roles": sorted(roles_for(session, user.id)),
            "created_at": user.created_at,
        }
        for user in users
    ]


@app.put("/api/v1/admin/users/{user_id}/roles", response_model=AdminUserResponse)
def admin_update_user_roles(
    user_id: str,
    payload: AdminUserRolesUpdate,
    request: Request,
    session: Session = Depends(get_db),
    actor: CurrentUser = Depends(require_roles(ROLE_ADMIN)),
) -> dict:
    user = require(session, User, user_id, "用户")
    roles = set(payload.roles)
    if actor.user.id == user.id and ROLE_ADMIN not in roles:
        raise AppError(409, "ADMIN_ROLE_REQUIRED", "不能移除当前管理员自己的管理员角色。")
    session.query(UserRole).filter(UserRole.user_id == user.id).delete()
    session.add_all([UserRole(user_id=user.id, role=role) for role in roles])
    audit(session, request, actor, "user.roles.update", "user", user.id, {"roles": sorted(roles)})
    session.commit()
    return {
        "user_id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status,
        "roles": sorted(roles),
        "created_at": user.created_at,
    }


@app.get("/health", response_model=HealthResponse)
def health(request: Request) -> dict:
    if settings.app_env != "development" and (
        not settings.health_check_secret
        or request.headers.get("X-Health-Check-Key") != settings.health_check_secret
    ):
        raise AppError(404, "RESOURCE_NOT_FOUND", "资源不存在。")
    database_ready, database_detail = database_health()
    dependencies = {
        "mysql": {
            "status": "ready" if database_ready else "unavailable",
            "detail": database_detail,
        },
        "user_supplied_ai": {
            "status": "ready",
            "detail": "生成式功能仅使用用户在当前会话中提供的模型配置；服务器不保存默认模型密钥。",
        },
        "local_models": {
            "status": "ready" if settings.model_runtime_enabled else "degraded",
            "detail": "lazy loading enabled"
            if settings.model_runtime_enabled
            else "MODEL_RUNTIME_ENABLED=false，使用确定性测试向量",
        },
    }
    return {
        "status": "ok" if database_ready else "degraded",
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
