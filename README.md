# MarkLens

MarkLens 是面向中国大陆商标学习与注册风险初筛的产品化教学系统。它提供面向用户的学习中心、案例实训、私有品牌项目、多模态检索、确定性风险评分和可编辑报告；同时以独立运营后台维护数据源与平台运行。

系统同时包含明确标识的课程样本及可追溯的公开境外商标记录。系统结果不构成法律意见，也不替代官方数据库查询、律师审查或行政司法机关判断。

先从[文档导航](docs/README.md)开始。首次运行、日常使用与腾讯云部署见[完整使用说明](docs/guides/使用说明.md)；四人协作和实验报告写作见[分工方案](docs/reports/四人分工.md)；真实数据来源、许可和法域边界见[真实商标数据说明](docs/10-real-data.md)。

课程答辩可直接从[答辩资料导航](docs/defense/README.md)进入：其中包含功能到代码索引、8-10 分钟演示脚本与架构追问要点。

## 项目结构

```text
apps/web/       React 用户端与运营端界面
apps/api/       FastAPI、业务服务、迁移与测试
infra/          Nginx 和 systemd 的生产部署模板
scripts/        初始化、示例资料与部署脚本
docs/           使用、部署、答辩与报告文档
output/         可提交的示例注册附件（PDF / DOCX / PNG）
```

前端只通过 `/api` 调用业务能力；鉴权、数据隔离、文件读取和任务执行均在 `apps/api` 服务端完成。更细的源码导航分别见 [Web](apps/web/src/README.md) 和 [API](apps/api/app/README.md)。

## 技术栈

- Web：React 19、TypeScript、Vite、Radix Themes、React Query、React Hook Form、Zod、Phosphor Icons、Recharts、Motion；
- API：Python 3.12、FastAPI、SQLAlchemy 2、Alembic、PyMySQL；
- 数据库：MySQL 8.0+，字符集 `utf8mb4`，不使用 MySQL 专有向量类型；
- 生成：DeepSeek API 和官方 `langchain-deepseek`，默认模型 `deepseek-v4-flash`；
- RAG：LangChain LCEL、BGE 稠密检索、BM25、加权 RRF、日期与法域过滤；
- 本地模型：FastEmbed `BAAI/bge-small-zh-v1.5`、`Qdrant/resnet50-onnx`、RapidOCR、pHash。

## 产品角色与边界

- `user`：学习知识、完成实训，且只能访问自己的品牌项目、图样、分析和报告；
- `operator`：进入 `/ops` 维护数据源与运营内容；
- `admin`：在运营能力基础上管理角色与审计；
- 用户端不展示数据库、模型、数据同步或任务调度的内部信息；所有访问控制由 API 在服务端执行，而非前端隐藏菜单。

首次执行 `make seed` 会创建演示运营账户。账号由 `.env` 的 `DEMO_ADMIN_EMAIL` 和 `DEMO_ADMIN_PASSWORD` 控制；部署前务必修改密码、`AUTH_SECRET`，并将 `COOKIE_SECURE=true`。

## 快速启动

要求 Python 3.12、Node.js 22 和 pnpm 10+。macOS 默认由 `make db-up` 管理项目独立的 Homebrew MySQL 8.4；Docker 用户可改用 `make db-up-docker`。

```bash
cp .env.example .env
make setup
make db-up
make db-migrate
make seed
make models-download
```

然后分别启动：

```bash
make dev-api
make dev-web
```

- Web：`http://localhost:5173`
- API：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`

在 `.env` 中填写 `DEEPSEEK_API_KEY` 后，风险解释、法律咨询和文书生成链才会运行。未配置时，多模态检索仍可使用，模型任务会以 `MODEL_NOT_CONFIGURED` 明确失败。

首次本地模型下载约数百 MB，可提前执行：

```bash
make models-download
```

如只需运行测试而不下载模型，可设置：

```bash
MODEL_RUNTIME_ENABLED=false make check
```

这会使用固定 512 维字符 n-gram 测试向量，不改变生产配置。

## 数据初始化

`make seed` 是幂等命令，会创建：

- 60 条合成商标演示记录；
- 12 张程序生成并明确标注的演示图样；
- JSON 和 CSV 数据源定义及导入审计记录；
- 现行 2019 商标法、2021 审查审理指南和 2027 年起适用的未来版本资料。

分析日期早于 `2027-01-01` 时，未来版本不会进入适用法律检索。

## 核心接口

耗时操作返回 `202 AgentRun`，前端只会看到与自身项目关联的简化进度；运行详情和同步错误留在运营域。旧的无鉴权接口会返回 `410 Gone`，不得作为产品接口使用。

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
GET/POST /api/v1/app/projects
POST /api/v1/app/projects/{id}/marks
POST /api/v1/app/searches
POST /api/v1/app/risk-analyses
POST /api/v1/app/documents
GET  /api/v1/app/learn/topics
GET  /api/v1/app/practice/questions
GET  /api/v1/ops/overview
GET  /api/v1/ops/sources
POST /api/v1/ops/sources/{key}/sync
```

## 数据源边界

数据源只能由服务端注册。仓库内置 JSON 和 CSV 适配器，支持分页、字段校验、`source_key + source_record_id` 幂等更新、原始记录哈希、失败记录与同步统计。未来 HTTP 适配器必须在代码中声明域名白名单、许可说明和限速，API 不接受用户传入任意 URL。

## 质量检查

```bash
make check
```

该命令执行 v0.1 和 v0.2 契约校验、Python lint 与测试、前端测试及生产构建。GitHub Actions 额外启动 MySQL 8.4，执行迁移、幂等种子和真实数据库检索集成测试。

## 安全边界

- 不提交 API Key、数据库密码、上传原图、抓取原始数据或模型缓存；
- DeepSeek 不接收用户原图，只接收确认事实、候选结构和隔离后的法律证据；
- 风险分数与等级归确定性引擎，模型无权修改；
- 无有效证据时拒绝输出确定性法律结论；
- 引用失效、引用不存在或事实不一致会阻止正式导出。
