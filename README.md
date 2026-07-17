# MarkLens

MarkLens 是面向中国大陆商标注册风险初筛的多模态检索与可信法律 RAG 教学系统。MVP 已实现案件事实确认、图样上传与 OCR、文字与图像近似检索、确定性风险评分、带引用法律咨询、风险报告生成、文书编辑校验和数据源同步审计。

所有样本商标均明确标注为合成演示数据。系统结果不构成法律意见，也不替代官方数据库查询、律师审查或行政司法机关判断。

首次安装和开发环境配置请阅读[《MarkLens 环境配置与启动手册》](docs/11-environment-setup.md)；页面操作、API 调用和维护见[《MarkLens 个人使用与维护手册》](docs/09-user-guide.md)。真实数据来源、许可和法域边界见[《真实商标数据说明》](docs/10-real-data.md)。

## 技术栈

- Web：React 19、TypeScript、Vite、Radix Themes、React Query、React Hook Form、Zod、Phosphor Icons、Recharts、Motion；
- API：Python 3.12、FastAPI、SQLAlchemy 2、Alembic、PyMySQL；
- 数据库：MySQL 8.0+，字符集 `utf8mb4`，不使用 MySQL 专有向量类型；
- 生成：DeepSeek API 和官方 `langchain-deepseek`，默认模型 `deepseek-v4-flash`；
- RAG：LangChain LCEL、BGE 稠密检索、BM25、加权 RRF、日期与法域过滤；
- 本地模型：FastEmbed `BAAI/bge-small-zh-v1.5`、`Qdrant/resnet50-onnx`、RapidOCR、pHash。

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

耗时操作返回 `202 AgentRun`，前端轮询任务完成后读取对应资源。公共契约见 [contract-v0.2](contracts/v0.2/README.md)。v0.1 作为历史 Mock 保留。

```text
POST /api/v1/assets
POST/GET /api/v1/cases
POST /api/v1/searches
POST /api/v1/risk-analyses
POST /api/v1/documents
POST /api/v1/consultations
GET  /api/v1/agent-runs/{id}
GET  /api/v1/sources
POST /api/v1/sources/{key}/sync
GET  /api/v1/ingestion-runs/{id}
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
