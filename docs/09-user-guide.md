# MarkLens 个人使用与维护手册

从一台未配置过的新电脑开始安装时，请优先阅读[《MarkLens 环境配置与启动手册》](11-environment-setup.md)。本文主要用于已经完成安装后的日常使用、页面操作、API 调用和维护。

## 0. 你平时主要看这一节

这份文档是给你自己使用和维护 MarkLens 的操作手册。平时不需要从头阅读，按当前场景执行对应命令即可。

### 第一次安装

```bash
cd /Users/zhangzuhao/Documents/Code/01_school/2025-2026-2/anthropic-langchain-lab
cp .env.example .env
make setup
make db-up
make db-migrate
make seed
make models-download
```

然后打开 `.env`，填入：

```text
DEEPSEEK_API_KEY=你的密钥
```

### 每天启动

先确认 MySQL 已经运行：

```bash
make db-up
```

终端一：

```bash
make dev-api
```

终端二：

```bash
make dev-web
```

浏览器打开：

```text
http://localhost:5173
```

### 每次改完代码

```bash
make check
```

### 重建或补齐演示数据

```bash
make db-migrate
make seed
```

`make seed` 可以重复执行，不会重复插入同一批商标。

### 快速检查哪里出了问题

```bash
curl http://localhost:8000/health
```

优先看三个字段：

- `mysql` 不是 `ready`：检查数据库；
- `deepseek` 不是 `ready`：检查 `.env` 中的 Key；
- `local_models` 不是 `ready`：检查模型开关和模型缓存。

### 正常关闭

开发服务器在各自终端按 `Ctrl+C`。本机 MySQL 通常可以保持运行；需要停止 MarkLens 独立实例时执行：

```bash
make db-down
```

该命令不会删除数据库数据。Docker 用户使用 `make db-down-docker`。

## 1. 文档说明

MarkLens 当前是课程实训和功能验证用途的 MVP，服务范围限定为中国大陆商标注册风险初筛。系统提供的是辅助检索、风险提示和可编辑文书初稿，不是正式法律意见，也不能替代国家知识产权局相关系统的官方查询结果、律师审查或行政司法机关的判断。

后面的章节按“安装、页面使用、演示、API、维护、排错”的顺序展开。你只想运行项目时看第 5 至第 9 节；需要改代码或接数据源时再看第 10 节以后。

## 2. 已实现功能

当前版本已经实现以下完整流程：

1. 创建商标分析案件并保存结构化事实快照；
2. 上传 PNG、JPEG 或 WebP 商标图样；
3. 在本地执行图片校验、EXIF 清理、OCR、pHash 和图像向量提取；
4. 通过文字、拼音、语义、图像和国际分类进行多通道召回；
5. 返回 Top-10 近似候选、多维评分、来源和相似原因；
6. 使用确定性规则计算风险分数与低、中、高风险等级；
7. 使用 LangChain、法律 RAG 和 DeepSeek 生成受约束的风险解释；
8. 生成商标注册风险评估报告初稿；
9. 编辑文书段落，校验事实、申请号、申请人和引用有效性；
10. 进行带来源引用的商标法律咨询；
11. 管理服务端注册的数据源，查看同步统计和失败记录；
12. 通过持久化 `AgentRun` 查看异步任务状态。

系统不包含账号、计费、多租户、正式申请提交、诉讼文书、律师函或真实商标网站爬虫。

## 3. 系统工作方式

一次完整分析会形成以下证据链：

```text
用户确认事实
    ↓
CaseContext 案件快照
    ↓
EvidenceBundle 多模态检索证据包
    ↓
RiskAssessment 确定性风险评估
    ↓
DocumentDraft 带引用文书初稿
```

检索分数和风险等级由确定性程序计算。DeepSeek 只能生成解释、风险点、建议和文书措辞，不能修改确定性分数。

法律咨询和文书生成只允许引用 RAG 上下文中提供的引用 ID。知识库文本被当作证据数据，不会被当作系统指令，也不能触发额外工具。

## 4. 环境要求

### 4.1 必需软件

建议使用以下版本：

| 软件 | 要求 | 用途 |
|---|---:|---|
| Python | 3.12 | FastAPI、本地模型和测试 |
| Node.js | 22 | React 前端 |
| pnpm | 10 或更高版本 | 前端依赖和脚本 |
| MySQL | 8.0 或更高版本 | 唯一业务数据库 |
| Git | 任意较新版本 | 团队协作 |

Docker 不是必需项。在 macOS 上，项目默认使用 Homebrew 的 MySQL 8.4，并在 `data/mysql84-instance` 保存独立数据，不会改动电脑上已有的 MySQL 数据库。Docker 用户也可以使用仓库内的 Compose 配置。

### 4.2 检查版本

在项目根目录执行：

```bash
python3.12 --version
node --version
pnpm --version
mysql --version
docker --version
```

如果使用本机 MySQL，可以忽略 Docker 版本检查。

### 4.3 硬件和磁盘建议

- 至少预留 2 GB 可用磁盘空间；
- 首次运行允许下载数百 MB 的文本、图像和 OCR 模型；
- 8 GB 内存可以运行教学演示，16 GB 或更高会更稳定；
- 本地模型首次加载较慢，后续请求会明显加快。

## 5. 首次安装

以下命令都应在项目根目录执行：

```bash
cd /Users/zhangzuhao/Documents/Code/01_school/2025-2026-2/anthropic-langchain-lab
```

### 5.1 创建环境配置

复制配置模板：

```bash
cp .env.example .env
```

打开 `.env`，至少检查数据库连接：

```text
DATABASE_URL=mysql+pymysql://marklens:marklens@127.0.0.1:3307/marklens?charset=utf8mb4
```

如果需要使用风险解释、法律咨询和文书生成，还要填写：

```text
DEEPSEEK_API_KEY=你的真实密钥
```

不要把填写过密钥的 `.env` 提交到 Git。

### 5.2 安装后端和前端依赖

```bash
make setup
```

该命令会：

- 在 `apps/api/.venv` 创建 Python 虚拟环境；
- 安装 FastAPI、SQLAlchemy、Alembic、LangChain、FastEmbed、RapidOCR 等依赖；
- 安装 React、Radix Themes、React Query、Recharts、Motion 等前端依赖。

如果只需要安装某一端，可以使用：

```bash
make setup-api
make setup-web
```

### 5.3 启动 MySQL

#### 方案 A：macOS 本机独立实例（当前推荐）

```bash
brew install mysql@8.4
make db-up
make db-status
```

`make db-up` 会在首次执行时初始化数据目录、启动服务并幂等创建应用数据库与账号：

| 配置 | 默认值 |
|---|---|
| 数据库 | `marklens` |
| 用户名 | `marklens` |
| 密码 | `marklens` |
| 端口 | `3307` |
| 字符集 | `utf8mb4` |

数据保存在 `data/mysql84-instance`，由 `.gitignore` 排除。服务由当前 macOS 用户的 `launchd` 托管，与电脑上可能已有的 3306 端口 MySQL 隔离。

#### 方案 B：使用 Docker

```bash
make db-up-docker
docker compose -f infra/compose.yaml ps
```

Compose 同样把容器 3306 映射到宿主机 3307，因此无需修改默认 `.env`。停止时执行 `make db-down-docker`。

#### 方案 C：使用已有 MySQL

使用管理员账号进入 MySQL，然后创建数据库和开发用户：

```sql
CREATE DATABASE marklens
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'marklens'@'localhost' IDENTIFIED BY '请替换为本地密码';
GRANT ALL PRIVILEGES ON marklens.* TO 'marklens'@'localhost';
FLUSH PRIVILEGES;
```

随后修改 `.env` 中的 `DATABASE_URL`。如果密码包含 `@`、`:`、`/` 等字符，需要先进行 URL 编码。

### 5.4 执行数据库迁移

```bash
make db-migrate
```

成功时，Alembic 会把数据库升级到当前版本，并建立数据源、导入记录、商标、图片资产、向量特征、法律资料、案件、检索、风险分析、文书、咨询和智能体任务等表。

查看当前迁移版本：

```bash
cd apps/api
.venv/bin/alembic current
cd ../..
```

### 5.5 初始化演示数据

```bash
make seed
```

该命令是幂等的，可以重复执行。它会创建：

- 60 条明确标注为演示数据的合成商标；
- 12 张程序生成的演示商标图样；
- JSON 和 CSV 数据源定义；
- 商标文字特征和可用的图像特征；
- 现行 2019 商标法资料；
- 2021 商标审查审理指南资料；
- 2027 年起适用的未来版本资料。

重复执行不会重复创建同一商标。系统按 `source_key + source_record_id` 进行幂等更新。

### 5.6 提前下载本地模型

这一步不是强制的。也可以等待第一次请求时自动下载。

```bash
make models-download
```

需要下载的主要模型：

```text
BAAI/bge-small-zh-v1.5
Qdrant/resnet50-onnx
RapidOCR 所需 OCR 模型
```

模型默认保存在 `.model-cache`，该目录不会提交到 Git。

## 6. 启动系统

开发环境需要同时运行 API 和 Web。

### 6.1 启动 API

打开第一个终端：

```bash
make dev-api
```

默认地址：

- API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`
- OpenAPI JSON：`http://localhost:8000/openapi.json`
- 健康检查：`http://localhost:8000/health`

### 6.2 启动 Web

打开第二个终端：

```bash
make dev-web
```

浏览器访问：

```text
http://localhost:5173
```

Vite 会把 `/api` 和 `/health` 请求代理到 `http://localhost:8000`。

### 6.3 检查系统状态

```bash
curl http://localhost:8000/health
```

响应会分别展示：

- MySQL 是否可连接；
- DeepSeek 是否已配置；
- 本地模型运行是否启用；
- 当前 contract 和数据版本。

状态含义：

| 状态 | 含义 |
|---|---|
| `ready` | 依赖正常 |
| `degraded` | 可以启动，但部分功能受限 |
| `unavailable` | 关键依赖不可用 |

未配置 DeepSeek 时，MySQL 检索仍可使用，风险解释、法律咨询和文书生成任务会返回 `MODEL_NOT_CONFIGURED`。

## 7. 环境变量说明

| 变量 | 默认值或示例 | 说明 |
|---|---|---|
| `APP_ENV` | `development` | 应用环境名称 |
| `APP_LOG_LEVEL` | `INFO` | 日志级别 |
| `DATABASE_URL` | `mysql+pymysql://...` | MySQL SQLAlchemy URL，只支持 MySQL |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek 密钥，不得提交 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 地址 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 使用的 DeepSeek 模型 |
| `DEEPSEEK_THINKING` | `disabled` | Thinking 模式配置 |
| `TEXT_EMBEDDING_MODEL` | `BAAI/bge-small-zh-v1.5` | 512 维中文文本模型 |
| `IMAGE_EMBEDDING_MODEL` | `Qdrant/resnet50-onnx` | 图像向量模型 |
| `OCR_PROVIDER` | `rapidocr` | OCR 实现 |
| `MODEL_CACHE_DIR` | `.model-cache` | 模型缓存目录 |
| `UPLOAD_DIR` | `data/uploads` | 清理后的上传图片目录 |
| `SOURCE_DATA_DIR` | `data/sources` | JSON、CSV 演示数据目录 |
| `CORS_ORIGINS` | `http://localhost:5173` | 允许访问 API 的前端来源，多个值用逗号分隔 |
| `MODEL_RUNTIME_ENABLED` | `true` | 是否启用真实本地模型 |
| `AGENT_EAGER` | `false` | 是否在请求中立即运行任务，正常开发保持 `false` |

`MODEL_RUNTIME_ENABLED=false` 只建议用于测试和 CI。此时文本语义通道使用固定 512 维字符 n-gram 测试向量，OCR 和图像向量不会加载真实模型。

## 8. 页面使用说明

### 8.1 工作台首页

首页展示：

- MySQL、DeepSeek 和本地模型状态；
- 当前商标数据量、法律资料量和案件量；
- 当前适用法律版本；
- 最近创建的案件；
- 检索、评分、RAG 和文书证据链说明。

如果首页提示 MySQL 不可用，请先检查数据库和 `DATABASE_URL`，不要直接进入分析流程。

### 8.2 新建分析

点击“新建分析”，填写：

1. 商标名称；
2. 商品或服务业务描述；
3. 国际分类；
4. 可选商标图样。

国际分类应填写 1 至 45 的整数，多个类别使用逗号分隔，例如：

```text
9, 35, 42
```

图片限制：

- 只接受 PNG、JPEG、WebP；
- 文件最大 5 MB；
- 校验真实文件头，不仅依赖扩展名；
- 校验解码结果和像素总量；
- 自动移除 EXIF；
- 使用随机文件名保存；
- 原图不会发送给 DeepSeek。

如果 OCR 置信度较低，页面会要求确认或修改识别文字。确认后的文字才会进入文字、拼音和语义检索通道。

点击“启动检索”后，系统会创建案件事实快照和异步检索任务。

### 8.3 任务进度页

检索、风险分析、文书生成、咨询和数据源同步都是异步任务。

任务状态包括：

| 状态 | 说明 |
|---|---|
| `queued` | 已入队，等待执行 |
| `running` | 正在处理 |
| `waiting_for_user` | 等待用户确认信息 |
| `completed` | 已完成，可以读取产物 |
| `failed` | 执行失败，页面会显示错误码 |

页面会自动轮询。任务完成后自动跳转到检索、风险、文书、咨询或导入结果页。

### 8.4 检索结果页

检索结果最多展示 Top-10 候选。每个候选包含：

- 商标名称；
- 商标图样；
- 申请号；
- 申请人；
- 国际分类；
- 商品或服务；
- 当前状态和状态日期；
- 数据来源；
- 是否为演示数据；
- 各通道分数和综合分；
- 相似原因；
- 模型与评分配置版本。

默认权重：

```text
视觉相似度  0.30
文字相似度  0.30
拼音相似度  0.15
语义相似度  0.15
类别相关性  0.10
```

图像分数默认由以下部分组成：

```text
0.65 × ResNet50 余弦相似度
+ 0.35 × pHash 相似度
```

如果某个通道缺失，系统会把剩余通道权重重新归一化，不会把缺失值直接当作 0。

当前演示库中的候选会显示“演示”标记。演示数据不对应真实商标权利，不能据此决定是否提交真实商标申请。

### 8.5 风险分析页

点击“生成风险分析”后，系统会：

1. 读取最高候选和完整证据包；
2. 由确定性引擎计算风险分数；
3. 按分析日期检索有效法律资料；
4. 使用 BGE 稠密检索和 BM25 稀疏检索；
5. 使用加权 RRF 合并结果；
6. 把确认事实、结构化候选和法律证据交给 DeepSeek；
7. 校验结构化输出和引用 ID。

风险阈值：

| 风险等级 | 条件 |
|---|---|
| 高风险 | 分数大于或等于 0.75 |
| 中风险 | 分数大于或等于 0.50，且低于 0.75 |
| 低风险 | 分数低于 0.50 |
| 证据不足 | 没有有效来源或关键证据为空 |

这些阈值是教学用启发式规则，不是国家知识产权局的官方审查标准。

风险页会展示：

- 确定性分数和等级；
- 主要风险因素；
- 反向证据；
- 修改建议；
- 不确定性；
- 当前适用法版本；
- 法律引用、发布机关、定位和来源链接；
- 不替代律师意见的免责声明。

分析日期早于 `2027-01-01` 时，2026 年修订、2027 年生效的未来版本不会被当作现行法引用。

### 8.6 文书编辑页

点击“生成报告”后，系统生成商标注册风险评估报告初稿，固定包含：

1. 使用说明；
2. 事实摘要；
3. 检索方法；
4. 近似候选；
5. 风险分析；
6. 法律依据；
7. 修改建议；
8. 限制与引用。

每一节都可以在页面中修改。建议操作顺序：

1. 检查事实摘要；
2. 检查申请号和申请人；
3. 检查法律依据与引用侧栏；
4. 修改措辞；
5. 点击“保存”；
6. 点击“校验”；
7. 确认没有错误后使用“打印 PDF”。

以下问题会阻止正式导出：

- 文书引用了 RAG 上下文中不存在的引用 ID；
- 引用在分析日期尚未生效或已经失效；
- 申请号不属于事实快照中的候选；
- 申请人不属于事实快照中的候选；
- 关键风险或法律依据段落缺少引用。

“打印 PDF”使用浏览器打印样式。选择浏览器的“另存为 PDF”即可，不需要安装额外的 PDF 渲染程序。

### 8.7 法律咨询页

法律咨询适合询问：

- 商标近似判断通常考虑哪些因素；
- 商品或服务类别如何影响冲突判断；
- 组合商标的文字和图形如何比较；
- 风险报告中的法律引用如何理解；
- 不同法律版本如何按分析日期适用。

不适合用来：

- 代替律师给出正式法律意见；
- 决定诉讼或行政程序策略；
- 生成未经核验的案号和案例；
- 提交商标注册、异议、复审或无效申请；
- 处理包含大量个人敏感信息或商业秘密的问题。

咨询结果包含：

- 回答正文；
- 逐条引用；
- 不确定性；
- 生成模式；
- 免责声明。

没有相关证据时，系统会明确拒绝给出确定性结论。

### 8.8 数据源管理页

数据源页面展示：

- `source_key`；
- 适配器类型；
- 来源许可；
- 当前健康状态；
- 记录数量；
- 最后同步时间；
- 同步按钮。

点击“同步数据”后，系统执行分页获取、规范化、哈希比较、幂等新增或更新，并保存失败记录。

同步结果页展示：

- 读取数量；
- 新增数量；
- 更新数量；
- 未变化数量；
- 失败数量；
- 失败记录和错误原因。

系统不允许用户传入任意 URL。所有数据源必须在服务端代码中显式注册。

## 9. 你自己演示时的推荐流程

为了避免现场输入过多，可以按以下顺序演示。

### 9.1 演示前准备

```bash
make db-migrate
make seed
make check
```

确认 `.env` 已填写可用的 `DEEPSEEK_API_KEY`，提前执行一次 `make models-download`，避免现场下载模型。

### 9.2 演示输入

```text
商标名称：MarkLens
业务描述：用于商标检索、图像识别、风险分析和软件即服务
国际分类：9, 42
```

可以上传一张项目生成的演示图样，也可以只演示文字检索。

### 9.3 演示顺序

1. 首页展示依赖状态和数据版本；
2. 新建分析，说明 OCR 确认和原图不发送给 DeepSeek；
3. 展示异步任务进度；
4. 在检索结果页切换候选，查看雷达图和来源；
5. 生成风险分析，强调分数由确定性引擎产生；
6. 打开法律引用，说明生效日期过滤；
7. 生成报告并修改一个段落；
8. 点击校验并打印 PDF；
9. 在法律咨询页询问组合商标近似问题；
10. 在数据源页面演示幂等同步统计。

### 9.4 展示时必须说明

- 60 条商标是合成演示数据；
- 当前没有连接真实官方商标数据库；
- 分数和阈值是教学启发式规则；
- 法律回答和文书是可编辑初稿；
- 最终结果需要官方检索和人工复核。

## 10. API 使用说明

### 10.1 统一错误结构

所有业务错误使用以下格式：

```json
{
  "error": {
    "code": "MODEL_NOT_CONFIGURED",
    "message": "未配置 DEEPSEEK_API_KEY",
    "request_id": "req_demo",
    "details": null
  }
}
```

排查问题时应记录 `request_id`。日志只记录请求编号、路径、状态、模型、数据集和配置版本，不记录 API Key、完整原图或完整提示词。

### 10.2 上传图样

```bash
curl -X POST http://localhost:8000/api/v1/assets \
  -F "file=@./logo.png"
```

响应中的 `asset_id` 用于创建案件。

### 10.3 创建案件

```bash
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Content-Type: application/json" \
  -d '{
    "trademark_name": "MarkLens",
    "business_description": "商标检索与风险分析软件服务",
    "nice_classes": [9, 42],
    "image_asset_id": null,
    "confirmed_ocr_text": null
  }'
```

保存返回的 `case_id`。

### 10.4 创建检索任务

```bash
curl -X POST http://localhost:8000/api/v1/searches \
  -H "Content-Type: application/json" \
  -d '{
    "case_id": "替换为 case_id",
    "top_k": 10
  }'
```

耗时操作返回 HTTP 202 和 `run_id`。

### 10.5 轮询任务

```bash
curl http://localhost:8000/api/v1/agent-runs/替换为_run_id
```

任务完成时响应包含：

```json
{
  "status": "completed",
  "resource_type": "search",
  "resource_id": "search_id"
}
```

然后读取产物：

```bash
curl http://localhost:8000/api/v1/searches/替换为_search_id
```

### 10.6 创建风险分析

```bash
curl -X POST http://localhost:8000/api/v1/risk-analyses \
  -H "Content-Type: application/json" \
  -d '{
    "search_id": "替换为 search_id",
    "analysis_date": "2026-07-14"
  }'
```

轮询 `run_id`，完成后读取：

```bash
curl http://localhost:8000/api/v1/risk-analyses/替换为_analysis_id
```

### 10.7 创建文书

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{
    "analysis_id": "替换为 analysis_id",
    "document_type": "trademark_registration_risk_report"
  }'
```

读取和校验文书：

```bash
curl http://localhost:8000/api/v1/documents/替换为_document_id

curl -X POST \
  http://localhost:8000/api/v1/documents/替换为_document_id/validate
```

### 10.8 法律咨询

```bash
curl -X POST http://localhost:8000/api/v1/consultations \
  -H "Content-Type: application/json" \
  -d '{
    "question": "组合商标的文字和图形都有差异时，仍可能构成近似吗？",
    "case_id": null,
    "analysis_date": "2026-07-14"
  }'
```

任务完成后读取：

```bash
curl http://localhost:8000/api/v1/consultations/替换为_consultation_id
```

### 10.9 查看和同步数据源

```bash
curl http://localhost:8000/api/v1/sources

curl -X POST http://localhost:8000/api/v1/sources/demo-json/sync \
  -H "Content-Type: application/json" \
  -d '{
    "cursor": null,
    "page_size": 100,
    "max_pages": 100
  }'
```

任务完成后读取导入统计：

```bash
curl http://localhost:8000/api/v1/ingestion-runs/替换为_ingestion_run_id
```

完整请求和响应模型可在 `http://localhost:8000/docs` 查看。

## 11. 演示数据管理

### 11.1 数据存放位置

| 数据 | 位置 |
|---|---|
| JSON、CSV 演示源 | `data/sources` |
| 上传和演示图片 | `data/uploads` |
| 模型缓存 | `.model-cache` |
| 数据库文件 | Docker volume 或本机 MySQL 数据目录 |

上传文件、模型缓存和原始抓取数据都已排除 Git。

### 11.2 重新执行种子

```bash
make seed
```

无需先清空数据库。种子程序会比较来源记录哈希，对没有变化的记录执行幂等跳过。

### 11.3 完全重建 Docker 数据库

以下操作会永久删除 Docker 中的 MarkLens 数据，只能在确认不需要保留案件和文书时执行：

```bash
docker compose -f infra/compose.yaml down -v
make db-up
make db-migrate
make seed
```

不要在共享数据库或包含真实测试资料的环境中执行该操作。

## 12. 接入新的数据源

### 12.1 适配器接口

所有商标数据源实现以下能力：

```text
source_key
license_info()
health_check()
fetch_page(cursor, limit) -> SourcePage
normalize(raw_record) -> TrademarkIngestRecord
```

实现位置：

```text
apps/api/app/sources.py
```

### 12.2 JSON 记录格式

```json
{
  "source_record_id": "SOURCE-0001",
  "name": "示例商标",
  "application_number": "202600000001",
  "applicant": "示例申请人",
  "nice_classes": [9, 42],
  "goods_services": ["可下载的软件", "软件即服务"],
  "status": "申请中",
  "status_date": "2026-07-14",
  "application_date": "2026-06-01",
  "source_url": "https://经过许可的数据源.example/record/1",
  "image_path": null,
  "is_demo": false
}
```

必填字段：

- `source_record_id`；
- `name`；
- `application_number`；
- `applicant`；
- `source_url`。

### 12.3 HTTP 数据源要求

真实 HTTP 适配器必须：

1. 继承 `RegisteredHttpSourceAdapter`；
2. 在服务端声明固定 `allowed_domains`；
3. 声明 `rate_limit_per_minute`；
4. 写明数据许可和使用范围；
5. 显式实现字段映射；
6. 为每条记录保留来源链接；
7. 在 `build_registry()` 中注册；
8. 添加分页、更新、失败恢复和限速测试。

不要增加“用户输入 URL 后抓取”的接口。这样会引入 SSRF、许可和审计风险。

## 13. 测试和质量检查

### 13.1 一键检查

```bash
make check
```

包括：

- contract-v0.1 和 contract-v0.2 示例校验；
- Python Ruff 检查；
- 后端 Pytest；
- 前端 Vitest；
- TypeScript 检查；
- Vite 生产构建。

### 13.2 分项执行

```bash
make validate
make lint-api
make test-api
make test-web
make build-web
```

### 13.3 不下载模型运行测试

```bash
MODEL_RUNTIME_ENABLED=false make check
```

### 13.4 MySQL 集成测试

MySQL 集成测试默认在本地跳过，避免误连未知数据库。准备好独立测试数据库后可以执行：

```bash
RUN_MYSQL_TESTS=true \
MODEL_RUNTIME_ENABLED=false \
make test-api
```

运行前必须确认 `DATABASE_URL` 指向专用测试库。GitHub Actions 会自动启动 MySQL 8.4，执行迁移、种子幂等和检索集成测试。

## 14. 常见问题

### 14.1 `python3.12: command not found`

项目固定使用 Python 3.12。macOS 可以直接安装：

```bash
brew install python@3.12
```

安装后确认命令名为 `python3.12`。如果本机命令路径不同，可以临时指定：

```bash
make setup PYTHON=/你的路径/python3.12
```

不要直接使用 Python 3.14 作为团队统一运行版本，本地模型依赖可能出现轮子兼容问题。

### 14.2 MySQL 连接失败

先检查：

```bash
make db-status
tail -n 100 data/mysql84-instance/marklens.err
```

然后检查 `.env`：

- 主机是否正确；
- 端口是否正确；
- 数据库是否存在；
- 用户是否有权限；
- 密码中的特殊字符是否 URL 编码；
- URL 是否以 `mysql+pymysql://` 开头。

MarkLens 不提供 SQLite 回退。

### 14.3 端口 3307 已被占用

项目特意使用 3307，避免与常见的本机 3306 实例冲突。如果 3307 仍被占用，可以指定新端口启动：

```bash
MYSQL_PORT=3308 make db-up
```

同时修改 `.env`：

```text
DATABASE_URL=mysql+pymysql://marklens:marklens@127.0.0.1:3308/marklens?charset=utf8mb4
```

### 14.4 首页显示 DeepSeek 降级

确认 `.env` 已填写：

```text
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

修改 `.env` 后重启 API。

### 14.5 任务提示 `MODEL_NOT_CONFIGURED`

这是预期的安全降级，不会自动伪造模型结果。填写 DeepSeek API Key，重启 API，然后重新创建风险、咨询或文书任务。

### 14.6 首次检索很慢

通常是首次下载或加载本地模型。建议提前执行：

```bash
make models-download
```

检查 `.model-cache` 是否可写，并确认网络可以访问模型下载源。

### 14.7 OCR 没有结果

检查：

- 图片是否清晰；
- 文字是否过小；
- 图片是否只有图形元素；
- `MODEL_RUNTIME_ENABLED` 是否为 `true`；
- RapidOCR 模型是否下载成功。

纯图形商标没有 OCR 文字是正常情况，系统仍会使用图像向量和 pHash。

### 14.8 页面一直停留在任务运行中

检查 API 终端日志和任务接口：

```bash
curl http://localhost:8000/api/v1/agent-runs/对应的_run_id
```

开发版使用进程内 BackgroundTasks。创建任务后不要立即重启 API，否则未完成的后台任务不会由独立队列自动接管。任务状态保存在 MySQL，可以查看失败原因后重新提交。

### 14.9 前端能打开但没有数据

依次确认：

```bash
curl http://localhost:8000/health
make db-migrate
make seed
```

然后刷新浏览器。

### 14.10 浏览器出现跨域错误

检查 `.env` 中：

```text
CORS_ORIGINS=http://localhost:5173
```

如果前端使用其他端口，需要把实际来源加入列表并重启 API。多个来源使用逗号分隔。

### 14.11 文书不能导出

先查看页面顶部校验提示，常见原因包括：

- 引用被删除；
- 手工填写了事实快照中不存在的申请号；
- 修改了申请人名称；
- 使用了分析日期不适用的法律版本；
- 风险分析或法律依据段落没有引用。

修正后点击“保存”和“校验”。

## 15. 安全和合规边界

### 15.1 不应提交的内容

- `.env`；
- DeepSeek API Key；
- 数据库真实密码；
- 用户上传原图；
- 模型缓存；
- 许可不明确的抓取数据；
- 包含个人敏感信息的咨询记录；
- 未核验的法律案例或案号。

### 15.2 模型数据边界

DeepSeek 只接收：

- 用户确认后的事实；
- 结构化近似候选；
- OCR 确认文字；
- 经过日期和法域过滤的法律片段。

DeepSeek 不接收用户原图，也不能修改确定性风险分数。

### 15.3 数据源边界

- 数据源由服务端注册；
- 不开放任意 URL 抓取；
- 真实数据源必须记录许可说明；
- 每条记录保留来源链接和原始记录哈希；
- 导入过程保存新增、更新、跳过和失败统计。

### 15.4 法律输出边界

- 无证据时不得生成确定性结论；
- 引用必须来自当前 RAG 上下文；
- 未知事实显示“待补充”；
- 文书是可编辑初稿；
- 所有结果都需要人工复核。

## 16. 主要目录

```text
apps/api/
  app/main.py              API 路由和错误处理
  app/models.py            MySQL 数据模型
  app/schemas.py           contract-v0.2 运行时类型
  app/retrieval.py         图片处理、本地模型和多模态检索
  app/rag.py               LangChain、法律混合检索和 DeepSeek 链
  app/sources.py           SourceAdapter 与幂等同步
  app/services.py          智能体任务和业务服务
  app/seed.py              60 条样本、12 张图样和法律资料
  alembic/                 数据库迁移

apps/web/
  src/App.tsx              页面、路由和业务流程
  src/api.ts               API 客户端
  src/contracts.ts         前端类型
  src/styles.css           明暗主题和响应式样式

contracts/v0.2/            当前公共契约
docs/                      架构、分工、契约和使用文档
infra/compose.yaml         MySQL 8.4 本地编排
```

## 17. 你排查或向别人求助时应整理的信息

出现问题时，请提供：

1. 操作系统；
2. Python、Node.js、pnpm 和 MySQL 版本；
3. 执行的命令；
4. 完整错误码；
5. `request_id`；
6. `/health` 响应中各依赖状态；
7. 是否使用 Docker；
8. 是否启用真实本地模型；
9. 问题发生在上传、检索、风险、咨询、文书还是数据同步阶段。

不要在求助信息中粘贴 API Key、数据库密码、完整用户原图或包含敏感事实的完整提示词。
