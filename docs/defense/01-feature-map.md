# 功能到代码的答辩索引

> `现状` 只描述已实现内容；`下一步` 指向路线图中的规划，不应在答辩中表述为已完成。

## 用户端核心闭环（已实现）

| 功能 | 页面与演示动作 | Web 入口 | API 入口 | 数据/服务 | 验证 |
|---|---|---|---|---|---|
| 账号与角色 | 注册普通用户；运营账户进入后台 | `apps/web/src/App.tsx`：`AuthPage`、`RequireUser` | `apps/api/app/main.py`：`/api/v1/auth/*` | `auth.py`、`User`、`UserRole` | `test_product_auth.py` |
| 私有品牌项目 | 新建项目，添加方案 | `App.tsx`：`Projects`、`ProjectDetail`、`NewMark` | `/api/v1/app/projects*` | `Project`、`CaseRecord` | `test_product_auth.py` |
| 图样/OCR 输入 | 上传图样、确认识别文字 | `App.tsx`：`NewMark` | `/api/v1/app/assets` | `retrieval.py`、`ImageAsset` | `test_api.py` |
| 多路初筛 | 点击“开始初筛”，打开候选线索 | `App.tsx`：`MarkRow`、`TaskPage`、`SearchPage` | `/api/v1/app/searches*` | `services.py`、`retrieval.py`、`SearchRecord` | `test_retrieval.py`、`result-pages.test.tsx` |
| 风险解读 | 从候选页生成风险解读 | `App.tsx`：`RiskPage` | `/api/v1/app/risk-analyses*` | `rag.py`、`RiskAnalysis` | `test_rag.py` |
| 报告保存与复用 | 生成报告后再次打开风险页 | `App.tsx`：`RiskPage`、`DocumentPage` | `/api/v1/app/documents*`、`.../risk-analyses/{id}/document` | `DocumentDraft`、`services.py` | `test_product_auth.py` |
| PDF 导出 | 报告页点击“导出 PDF” | `App.tsx`：`DocumentPage`；`api.ts`：`exportDocument` | `.../documents/{id}/export.pdf` | `pdf_export.py` | `test_pdf_export.py` |
| 学习与实训 | 查看专题，完成一题 | `App.tsx`：`Learn`、`Topic`、`Practice` | `/api/v1/app/learn/*`、`/practice/*` | `LearningTopic`、`PracticeQuestion` | `test_learning_library.py` |

## 运营与安全（已实现）

| 功能 | 演示动作 | Web 入口 | API 入口 | 核心说明 |
|---|---|---|---|---|
| 运营工作台 | 使用演示运营账户进入 `/ops` | `App.tsx`：`Ops` | `/api/v1/ops/overview`、`/ops/runs` | 普通用户没有该入口，后端仍执行角色校验 |
| 内容/题库编辑 | 发布学习主题或案例题 | `App.tsx`：`OpsTopicForm`、`OpsQuestionForm` | `/ops/learning/topics`、`/ops/practice/questions` | 支持草稿/发布状态 |
| 数据源同步 | 在数据中心发起同步 | `App.tsx`：`Ops` data tab | `/ops/sources*` | 来源许可、同步任务与状态由服务端管理 |
| 用户与角色 | 管理员调整角色 | `App.tsx`：`RoleControl` | `/api/v1/admin/users*` | `operator` 不可调整角色 |
| 资源隔离与审计 | 用第二个普通账户访问第一个项目 | 无需特定页面 | `auth.py`、`main.py` 中 `require_owned_*` | 前端隐藏不是权限；所有资源在 API 校验归属 |

## 技术能力与边界（已实现）

| 追问主题 | 代码位置 | 可直接回答 |
|---|---|---|
| 图像与文字如何检索 | `apps/api/app/retrieval.py` | 使用 OCR、pHash、图像特征、文字/拼音/语义召回，再汇总重排。 |
| 风险分数是否由大模型决定 | `apps/api/app/retrieval.py`、`services.py` | 不是；分数与风险映射由确定性规则负责，模型只生成受证据约束的解释。 |
| 如何防止幻觉 | `apps/api/app/rag.py` | 生成只接收事实和法律证据包，并执行事实、引用、生效日期校验。 |
| 报告是否持久化 | `apps/api/app/models.py`：`DocumentDraft` | 报告正文、引用、校验结果和事实快照写入数据库，可再次打开和导出。 |
| 数据边界 | `docs/10-real-data.md`、`apps/api/data/sources/` | 默认演示数据不等同于官方穷尽检索，所有结论带人工复核边界。 |

## 下一步展示（尚未实现，见路线图）

| 规划功能 | 答辩价值 | 路线图章节 |
|---|---|---|
| 项目级品牌顾问 | 将 RAG 问答变为可行动的项目决策能力 | 5 |
| 候选方案对比板 | 可解释地比较多个名称和类别选择 | 4.2 |
| 品牌 DNA 卡 | 汇总图样、文字、业务与证据的多模态画像 | 4.1 |
| 证据地图与类别关系图 | 将复杂相似线索可视化 | 4.3、7 |
| 决策日志与协作 | 将一次性分析变为可追溯项目过程 | 6 |

## 快速检索命令

```bash
# 前端页面与组件
rg -n "function (RiskPage|DocumentPage|Ops|Practice)" apps/web/src/App.tsx

# 用户侧受保护接口
rg -n '"/api/v1/app' apps/api/app/main.py

# 运营、管理员接口
rg -n '"/api/v1/(ops|admin)' apps/api/app/main.py

# 权限校验和审计
rg -n "require_owned|require_roles|audit\(" apps/api/app
```
