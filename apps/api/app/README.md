# API 源码导航（答辩定位版）

`app/` 是后端业务边界：浏览器不直接读取数据库、上传目录或模型服务，所有请求必须经过 `main.py` 的鉴权路由。图样文件由 `apps/api/data/uploads/` 管理，且绝不进入 Git；旧版本遗留在根目录 `data/uploads/` 的已关联文件会在首次读取时安全迁移，避免升级后变成空白图样。

`main.py` 目前是明确的 FastAPI 路由入口；领域逻辑、数据模型和可信生成已拆在相邻模块。答辩时可按功能从路由入口进入对应服务。

| 功能 | 路由/入口 | 继续查看 | 关键数据 |
|---|---|---|---|
| 认证、令牌、角色 | `main.py`：`/api/v1/auth/*` | `auth.py` | `User`、`UserRole`、`AuthSession` |
| 用户项目资源 | `main.py`：`/api/v1/app/*` | `auth.py` 的 `require_owned_*` | `Project`、`CaseRecord`、`ImageAsset` |
| 初筛与风险 | `main.py`：`app_create_search`、`app_create_risk` | `services.py`、`retrieval.py`、`rag.py` | `SearchRecord`、`RiskAnalysis` |
| 报告复用与导出 | `main.py`：`app_create_document`、`app_export_document_pdf` | `services.py`、`pdf_export.py` | `DocumentDraft` |
| 学习与实训 | `main.py`：`/learn/*`、`/practice/*` | `seed.py` | `LearningTopic`、`PracticeQuestion` |
| 运营后台 | `main.py`：`/api/v1/ops/*` | `sources.py`、`seed.py` | `SourceDefinition`、`AgentRun` |
| 管理与审计 | `main.py`：`/api/v1/admin/*` | `auth.py` 的 `audit` | `AuditEvent` |
| 输入/输出契约 | `schemas.py` | `contracts/v0.2/` | Pydantic 响应模型 |
| 数据库与迁移 | `models.py`、`db.py` | `alembic/versions/` | SQLAlchemy 模型 |

快速查找：

```bash
rg -n "def app_create_document|def app_export_document_pdf" apps/api/app
rg -n "def require_owned|def require_roles|def audit" apps/api/app/auth.py
rg -n "def build_search_operation|def build_risk_operation" apps/api/app/services.py
```

完整演示索引见 [`docs/defense/01-feature-map.md`](../../../docs/defense/01-feature-map.md)。
