# 完整 MVP 实现索引

本文记录计划与代码的对应关系，便于四位成员按功能继续并行迭代。

| 能力 | 主要代码 | 验收入口 |
|---|---|---|
| MySQL 与迁移 | `apps/api/app/models.py`、`db.py`、`alembic/` | `make db-migrate` |
| 合成样本与法律资料 | `apps/api/app/seed.py` | `make seed` |
| 数据源适配与同步 | `apps/api/app/sources.py` | 数据源管理页 |
| 图片安全、OCR 与向量 | `apps/api/app/retrieval.py` | 新建分析页 |
| 多通道检索与评分 | `apps/api/app/retrieval.py`、`services.py` | 检索结果页 |
| 法律混合 RAG | `apps/api/app/rag.py` | 法律咨询页 |
| 风险解释 | `rag.py`、`services.py` | 风险分析页 |
| 文书生成与校验 | `rag.py`、`main.py` | 文书编辑页 |
| 异步任务 | `models.py`、`services.py` | `/api/v1/agent-runs/{id}` |
| React 工作台 | `apps/web/src/App.tsx`、`styles.css` | `make dev-web` |
| 公共接口 | `apps/api/app/schemas.py`、`contracts/v0.2/` | `/docs`、`make validate` |

本地模型和 DeepSeek 均延迟加载。`MODEL_RUNTIME_ENABLED=false` 只用于 CI 的固定测试向量；生产演示应保持 `true`。风险分数、等级和文书校验始终由确定性代码负责。
