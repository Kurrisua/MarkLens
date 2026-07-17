# MarkLens 环境配置与启动手册

这份文档专门解决“换一台电脑后，怎样从零把 MarkLens 跑起来”的问题。它面向项目开发成员，不要求预先了解 Python 虚拟环境、pnpm、MySQL 或本地模型。

本文默认使用 macOS。Windows 或 Linux 用户可以沿用相同的软件版本和项目命令，但 MySQL 的安装、服务管理和 PATH 配置需要按各自系统调整。

## 1. 最短安装路径

已经安装 Homebrew 的 Apple Silicon Mac，可以先执行：

```bash
brew install python@3.12 node@22 pnpm mysql@8.4 git
```

进入项目根目录：

```bash
cd /Users/zhangzuhao/Documents/Code/01_school/2025-2026-2/anthropic-langchain-lab
```

然后执行：

```bash
cp .env.example .env
chmod 600 .env
make setup
make db-up
make db-migrate
make seed
make models-download
```

在本机的 `.env` 中填写自己的 DeepSeek Key。不要把 Key 写进 `.env.example`、README、聊天截图或任何准备提交到 Git 的文件。

最后分别打开两个终端：

```bash
make dev-api
```

```bash
make dev-web
```

浏览器访问 `http://localhost:5173`。

如果最短路径执行成功，可以跳到第 11 节查看日常启动命令。

## 2. 项目运行结构

MarkLens 本地开发时有三个长期运行的部分：

```text
浏览器 http://localhost:5173
            │
            ▼
React / Vite Web
            │  /api 与 /health 代理
            ▼
FastAPI http://localhost:8000
            │
            ├── MySQL 127.0.0.1:3307
            ├── DeepSeek HTTPS API
            └── 本地 Embedding、图像与 OCR 模型
```

因此，“网页可以打开”不代表整个系统已经就绪。至少需要分别检查 Web、API、MySQL、DeepSeek 配置和本地模型状态。

## 3. 推荐版本

| 软件 | 推荐版本 | 是否必需 | 用途 |
|---|---:|---|---|
| macOS | 13 或更高 | 是 | 当前主要开发平台 |
| Git | 较新稳定版 | 是 | 获取代码与团队协作 |
| Python | 3.12 | 是 | API、RAG、本地模型和测试 |
| Node.js | 22 | 是 | React 和 Vite |
| pnpm | 10 或更高 | 是 | JavaScript 依赖管理 |
| MySQL | 8.0 或更高 | 是 | 唯一业务数据库 |
| Homebrew | 较新稳定版 | 推荐 | macOS 软件安装 |
| Docker Desktop | 较新稳定版 | 可选 | 使用容器运行 MySQL |

项目不建议使用系统自带 Python，也不要使用 Python 3.14 代替 3.12。本地 OCR、ONNX 和向量模型依赖对 Python 小版本较敏感。

## 4. 安装 Homebrew 和基础工具

### 4.1 检查 Homebrew

```bash
brew --version
```

如果提示 `command not found: brew`，先从 [Homebrew 官方网站](https://brew.sh/)安装。安装结束后，按 Homebrew 在终端中给出的提示，把 `brew shellenv` 加入 `~/.zprofile`。

Apple Silicon Mac 常见配置为：

```bash
eval "$(/opt/homebrew/bin/brew shellenv)"
```

Intel Mac 的 Homebrew 通常位于 `/usr/local`。不要直接照抄 Apple Silicon 的路径，应使用安装程序给出的实际命令。

### 4.2 安装开发工具

```bash
brew install git python@3.12 node@22 pnpm mysql@8.4
```

检查版本：

```bash
git --version
python3.12 --version
node --version
pnpm --version
/opt/homebrew/opt/mysql@8.4/bin/mysql --version
```

预期至少满足：

```text
Python 3.12.x
Node.js v22.x
pnpm 10.x 或更高
MySQL 8.x
```

如果 `node` 找不到，但 Homebrew 已经安装 `node@22`，执行：

```bash
echo 'export PATH="/opt/homebrew/opt/node@22/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

如果 `python3.12` 找不到，可以执行：

```bash
echo 'export PATH="/opt/homebrew/opt/python@3.12/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

Intel Mac 请用 `brew --prefix node@22` 和 `brew --prefix python@3.12` 确认真实路径。

## 5. 获取项目代码

首次从 GitHub 获取项目时：

```bash
git clone <MARKLENS_GITHUB_REPOSITORY_URL>
cd anthropic-langchain-lab
```

当前作者电脑上的项目目录是：

```text
/Users/zhangzuhao/Documents/Code/01_school/2025-2026-2/anthropic-langchain-lab
```

其他成员不需要使用相同绝对路径。项目脚本会根据仓库根目录定位 `.env`、模型缓存、上传目录和数据目录。

确认当前目录正确：

```bash
pwd
test -f Makefile && echo "已经位于 MarkLens 项目根目录"
```

## 6. 配置 `.env`

### 6.1 创建本地配置

在项目根目录执行：

```bash
cp .env.example .env
chmod 600 .env
```

`.env.example` 只保存安全的变量名和开发默认值，可以提交到 Git。`.env` 保存本机密码和 API Key，已经被 `.gitignore` 排除，不得提交。

### 6.2 推荐开发配置

```dotenv
APP_ENV=development
APP_LOG_LEVEL=INFO
DATABASE_URL=mysql+pymysql://marklens:marklens@127.0.0.1:3307/marklens?charset=utf8mb4
DEEPSEEK_API_KEY=
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=disabled
TEXT_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
IMAGE_EMBEDDING_MODEL=Qdrant/resnet50-onnx
OCR_PROVIDER=rapidocr
MODEL_CACHE_DIR=.model-cache
UPLOAD_DIR=data/uploads
SOURCE_DATA_DIR=data/sources
CORS_ORIGINS=http://localhost:5173
MODEL_RUNTIME_ENABLED=true
AGENT_EAGER=false
```

把 DeepSeek Key 只写在等号右边：

```dotenv
DEEPSEEK_API_KEY=在这里填写你自己的密钥
```

注意：

- 不要把示例文字原样保留；
- 不要在等号两侧加入多余空格；
- 修改 `.env` 后需要重启 API；
- 不要在排错截图中完整显示 `.env`；
- 不要把 Key 作为前端 `VITE_` 环境变量；
- 浏览器端永远不应直接持有 DeepSeek Key。

### 6.3 环境变量说明

| 变量 | 说明 |
|---|---|
| `APP_ENV` | 应用环境标识，本地使用 `development` |
| `APP_LOG_LEVEL` | API 日志等级，通常使用 `INFO` |
| `DATABASE_URL` | SQLAlchemy MySQL 连接地址，项目不支持 SQLite |
| `DEEPSEEK_API_KEY` | DeepSeek 私密密钥，只能保存在本机 `.env` |
| `DEEPSEEK_BASE_URL` | DeepSeek OpenAI 兼容接口根地址 |
| `DEEPSEEK_MODEL` | 请求使用的模型名，需要与当前账号可用模型一致 |
| `DEEPSEEK_THINKING` | Thinking 模式开关 |
| `TEXT_EMBEDDING_MODEL` | 中文文本向量模型 |
| `IMAGE_EMBEDDING_MODEL` | 图像向量模型 |
| `OCR_PROVIDER` | OCR 提供方，当前为 RapidOCR |
| `MODEL_CACHE_DIR` | 本地模型缓存目录 |
| `UPLOAD_DIR` | 清理后的上传图片目录 |
| `SOURCE_DATA_DIR` | 内置 JSON、CSV 数据目录 |
| `CORS_ORIGINS` | 可以访问 API 的前端来源，多个来源用逗号分隔 |
| `MODEL_RUNTIME_ENABLED` | 是否启用真实本地模型；测试时可设为 `false` |
| `AGENT_EAGER` | 是否在请求线程立即执行任务，日常开发保持 `false` |

### 6.4 密码包含特殊字符

如果使用自建 MySQL 密码，并且密码包含 `@`、`:`、`/`、`#` 或 `%`，需要对密码部分进行 URL 编码，否则 `DATABASE_URL` 会被错误解析。

可以在本机临时执行：

```bash
python3.12 -c "from urllib.parse import quote; print(quote(input('Password: '), safe=''))"
```

输出只用于填入本机 `.env`，不要保存到仓库文件或聊天记录。

## 7. 安装项目依赖

### 7.1 一键安装

```bash
make setup
```

它等价于先后执行：

```bash
make setup-api
make setup-web
```

后端依赖安装到：

```text
apps/api/.venv
```

前端依赖安装到 pnpm 工作区的 `node_modules`。这两个目录都不会提交到 Git。

### 7.2 检查后端虚拟环境

```bash
apps/api/.venv/bin/python --version
apps/api/.venv/bin/python -c "import fastapi, sqlalchemy, langchain_core; print('API dependencies ready')"
```

### 7.3 检查前端依赖

```bash
pnpm --filter @marklens/web exec vite --version
```

如果出现 `make: pnpm: No such file or directory`，说明 pnpm 没有安装或当前终端还没有刷新 PATH。执行：

```bash
brew install pnpm
exec zsh
pnpm --version
make setup-web
```

## 8. 配置 MySQL

三种方案只选择一种。推荐 macOS 使用方案 A，团队成员已经使用 Docker 时选择方案 B。

### 8.1 方案 A：项目独立的本机 MySQL

安装：

```bash
brew install mysql@8.4
```

启动：

```bash
make db-up
make db-status
```

脚本会创建与系统其他数据库隔离的实例：

| 项目 | 默认值 |
|---|---|
| 地址 | `127.0.0.1` |
| 端口 | `3307` |
| 数据库 | `marklens` |
| 用户 | `marklens` |
| 开发密码 | `marklens` |
| 字符集 | `utf8mb4` |
| 数据目录 | `data/mysql84-instance` |

停止实例：

```bash
make db-down
```

停止不会删除数据库数据。

### 8.2 方案 B：Docker MySQL

确认 Docker Desktop 已经启动，然后执行：

```bash
make db-up-docker
docker compose -f infra/compose.yaml ps
```

等待健康状态变为 `healthy`。默认 `.env` 不需要修改，因为容器同样映射到本机 3307 端口。

停止容器：

```bash
make db-down-docker
```

### 8.3 方案 C：已有 MySQL 服务

使用管理员账号执行：

```sql
CREATE DATABASE marklens
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;

CREATE USER 'marklens'@'localhost' IDENTIFIED BY '替换为你自己的密码';
GRANT ALL PRIVILEGES ON marklens.* TO 'marklens'@'localhost';
FLUSH PRIVILEGES;
```

然后把 `.env` 中的主机、端口、用户名和密码改成实际值。

### 8.4 测试数据库连接

项目独立实例可以执行：

```bash
MYSQL_PWD=marklens /opt/homebrew/opt/mysql@8.4/bin/mysql \
  -h 127.0.0.1 -P 3307 -u marklens \
  -e "SELECT VERSION(), DATABASE(), NOW();" marklens
```

也可以直接使用项目命令：

```bash
make db-status
```

## 9. 数据库迁移和初始化

### 9.1 创建表结构

```bash
make db-migrate
```

查看迁移版本：

```bash
cd apps/api
.venv/bin/alembic current
cd ../..
```

### 9.2 写入演示和法律资料

```bash
make seed
```

`make seed` 是幂等命令，可以重复执行。它会补齐合成商标、演示图样、数据源定义和法律资料，不会为同一来源记录创建无限重复数据。

如果需要导入仓库支持的真实开放样本：

```bash
make import-real-sample
```

真实样本的来源、许可和法域限制见 [《MarkLens 真实商标数据说明》](10-real-data.md)。

## 10. 下载本地模型

提前下载：

```bash
make models-download
```

主要包括：

- `BAAI/bge-small-zh-v1.5` 中文文本向量模型；
- `Qdrant/resnet50-onnx` 图像向量模型；
- RapidOCR 所需 OCR 模型。

模型默认写入 `.model-cache`，不会提交到 Git。首次下载需要稳定网络，并可能占用数百 MB 磁盘空间。

只运行测试、不想下载模型时：

```bash
MODEL_RUNTIME_ENABLED=false make check
```

这只是测试模式，不建议用于正式演示效果评估。

## 11. 启动与关闭

### 11.1 每天启动

终端一：

```bash
cd /Users/zhangzuhao/Documents/Code/01_school/2025-2026-2/anthropic-langchain-lab
make db-up
make dev-api
```

终端二：

```bash
cd /Users/zhangzuhao/Documents/Code/01_school/2025-2026-2/anthropic-langchain-lab
make dev-web
```

打开：

- Web：`http://localhost:5173`
- API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

### 11.2 正常关闭

API 和 Web 终端分别按 `Ctrl+C`。

如果还要停止项目独立 MySQL：

```bash
make db-down
```

Docker 方案使用：

```bash
make db-down-docker
```

## 12. 验证环境

### 12.1 健康检查

```bash
curl http://localhost:8000/health
```

重点检查 MySQL、DeepSeek、本地模型和数据版本。DeepSeek 未配置时，基础检索仍可运行，但风险解释、法律咨询和报告措辞生成会降级或返回明确错误。

### 12.2 全部质量检查

```bash
make check
```

该命令执行：

1. API 契约和 OpenAPI 引用校验；
2. Python Ruff 检查；
3. API 单元测试；
4. 前端测试；
5. 前端 TypeScript 检查和生产构建。

### 12.3 最小功能验收

1. 打开工作台，确认 MySQL 为就绪状态；
2. 创建只包含文字的商标分析；
3. 确认检索任务完成并返回候选；
4. 生成风险分析；
5. 生成报告并检查引用；
6. 打开法律咨询，确认回答包含可回溯来源；
7. 上传一张小于 5 MB 的 PNG，验证 OCR 和图像通道。

## 13. DeepSeek 配置排错

### 13.1 已填写 Key，但系统仍显示未配置

按顺序检查：

1. `.env` 是否位于仓库根目录，而不是 `apps/api`；
2. 变量名是否严格为 `DEEPSEEK_API_KEY`；
3. 等号右侧是否确实有值；
4. 修改 `.env` 后是否重启了 `make dev-api`；
5. 当前启动命令是否在正确的仓库中执行；
6. `curl http://localhost:8000/health` 是否仍报告未配置。

检查程序是否读取到 Key，但不打印 Key 本身：

```bash
PYTHONPATH=apps/api apps/api/.venv/bin/python -c \
  "from app.config import get_settings; print('configured' if bool(get_settings().deepseek_api_key.strip()) else 'missing')"
```

这条命令只输出 `configured` 或 `missing`。

### 13.2 返回 401 或 403

通常表示 Key 无效、过期、账号权限不足或服务端拒绝请求。不要把 Key 发给其他成员排查。应在 DeepSeek 控制台重新创建或确认 Key，然后替换本机 `.env` 并重启 API。

### 13.3 返回模型不存在

确认 `DEEPSEEK_MODEL` 与当前账号和 API 地址实际支持的模型名一致。修改后重启 API。不要通过前端传入任意模型名，也不要把模型名写死到用户输入中。

### 13.4 风险分析可运行，但报告显示“专业模板生成”

这不一定是 API 故障。报告生成会校验固定章节顺序、最低篇幅、事实一致性和引用有效性。如果模型输出未通过约束，系统会自动改用专业确定性模板，保证报告可读且不编造引用。

## 14. 常见故障

### 14.1 `make: pnpm: No such file or directory`

```bash
brew install pnpm
exec zsh
pnpm --version
make setup-web
```

### 14.2 `python3.12: command not found`

```bash
brew install python@3.12
echo 'export PATH="/opt/homebrew/opt/python@3.12/bin:$PATH"' >> ~/.zshrc
exec zsh
python3.12 --version
```

### 14.3 MySQL `Connection refused`

```bash
make db-status
make db-up
lsof -nP -iTCP:3307 -sTCP:LISTEN
```

同时确认 `.env` 使用端口 `3307`，而不是配置类中的兜底端口 `3306`。

### 14.4 3307 端口被占用

先确认占用进程：

```bash
lsof -nP -iTCP:3307 -sTCP:LISTEN
```

不要直接终止不认识的系统进程。可以停止另一套 MySQL 或 Docker 容器，也可以为 MarkLens 选择新端口，并同步修改 `.env` 和 MySQL 启动配置。

### 14.5 Alembic 连接失败

```bash
make db-status
test -f .env && echo ".env exists"
make db-migrate
```

如果仍失败，检查 `DATABASE_URL` 的用户名、密码、主机、端口和数据库名称。

### 14.6 模型下载失败或首次请求很慢

```bash
make models-download
```

确认网络可以访问模型托管服务，并检查 `.model-cache` 所在磁盘是否有足够空间。首次加载 OCR 和图像模型比后续请求慢属于正常现象。

### 14.7 前端能打开但 API 请求失败

分别检查：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/openapi.json
```

如果 8000 端口没有响应，重新运行 `make dev-api`。如果 API 正常但前端失败，检查 Vite 终端报错、浏览器控制台和 `CORS_ORIGINS`。

### 14.8 端口 5173 或 8000 被占用

```bash
lsof -nP -iTCP:5173 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

先停止旧的 MarkLens 开发进程，再重新启动。不要随意结束不属于本项目的服务。

### 14.9 GitHub 已登录，但 `git push` 连接超时

`gh auth status` 正常而 `git push` 报 `Operation timed out` 时，常见原因是 macOS 已启用代理，但 Git 命令行没有自动继承系统代理。

查看系统代理：

```bash
scutil --proxy
```

如果输出显示代理地址为 `127.0.0.1`、端口为 `7897`，先确认代理端口正在监听：

```bash
lsof -nP -iTCP:7897 -sTCP:LISTEN
```

再测试代理能否访问 GitHub：

```bash
curl --proxy http://127.0.0.1:7897 -I --max-time 15 https://github.com
```

测试成功后，只给当前 MarkLens 仓库配置 GitHub 专用代理：

```bash
git config --local http.https://github.com.proxy http://127.0.0.1:7897
git push
```

使用 `--local` 可以避免影响电脑上的其他 Git 仓库。代理端口可能随软件配置变化，应以 `scutil --proxy` 的实际输出为准，不要固定照抄 7897。

关闭代理软件或切换为可以直接访问 GitHub 的网络后，可以移除当前仓库的代理配置：

```bash
git config --local --unset-all http.https://github.com.proxy
```

查看当前仓库是否仍配置代理：

```bash
git config --local --get http.https://github.com.proxy
```

## 15. API Key 和提交安全

### 15.1 永远不提交的内容

- `.env` 和任何真实环境配置；
- DeepSeek API Key；
- 数据库真实密码；
- `data/raw` 原始下载包；
- `data/uploads` 用户上传文件；
- `.model-cache` 模型文件；
- MySQL 本地数据目录；
- 日志、构建目录和虚拟环境。

### 15.2 提交前检查

确认 `.env` 已被忽略：

```bash
git check-ignore -v .env
```

查看准备提交的文件：

```bash
git status --short
git diff --cached --name-only
git diff --cached
```

如果 `.env` 出现在 `git status` 的待提交列表中，立即停止提交并检查 `.gitignore`。

可以只检查候选文件中是否出现常见密钥变量名，而不输出具体值：

```bash
git grep -l 'DEEPSEEK_API_KEY' -- ':!*.example' ':!docs/**'
```

文档和 `.env.example` 可以出现变量名，但等号右侧必须保持为空或使用明显占位符。

### 15.3 Key 曾经误提交怎么办

即使随后删除文件，Key 仍可能存在于 Git 历史中。应立即：

1. 在 DeepSeek 控制台撤销旧 Key；
2. 创建新 Key；
3. 更新本机 `.env`；
4. 通知仓库维护者清理 Git 历史；
5. 检查 GitHub Actions 日志、Issue 和聊天记录是否也暴露过 Key。

不要继续使用已经公开过的 Key。

## 16. 团队成员配置规则

- 每个人从 `.env.example` 创建自己的 `.env`；
- 不在群聊中共享 DeepSeek Key；
- 不要求其他成员复制你的数据库目录；
- 数据库结构通过 Alembic 同步；
- 演示数据通过 `make seed` 同步；
- JavaScript 依赖以 `pnpm-lock.yaml` 为准；
- Python 依赖以 `apps/api/pyproject.toml` 为准；
- 拉取新代码后优先执行 `make setup`、`make db-migrate` 和 `make seed`；
- 提交前执行 `make check`。

## 17. 日常命令速查

| 目标 | 命令 |
|---|---|
| 安装全部依赖 | `make setup` |
| 启动本机 MySQL | `make db-up` |
| 查看 MySQL 状态 | `make db-status` |
| 停止本机 MySQL | `make db-down` |
| 执行迁移 | `make db-migrate` |
| 补齐种子数据 | `make seed` |
| 下载本地模型 | `make models-download` |
| 启动 API | `make dev-api` |
| 启动 Web | `make dev-web` |
| 导入真实开放样本 | `make import-real-sample` |
| 运行完整检查 | `make check` |

## 18. 完整重装顺序

在新电脑上推荐严格按以下顺序执行：

```text
1. 安装 Homebrew
2. 安装 Git、Python 3.12、Node 22、pnpm、MySQL 8.4
3. 克隆仓库并进入项目根目录
4. 从 .env.example 创建本机 .env
5. 填写本机数据库配置和 DeepSeek Key
6. make setup
7. make db-up
8. make db-migrate
9. make seed
10. make models-download
11. make check
12. 分别运行 make dev-api 和 make dev-web
13. 打开 http://localhost:5173
```

完成以上步骤后，MarkLens 的前端、API、MySQL、RAG、DeepSeek 和本地多模态模型环境即配置完毕。
