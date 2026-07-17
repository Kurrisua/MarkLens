# contract-v0.2

本目录冻结 MarkLens 完整 MVP 的公共接口。`apps/api/app/schemas.py` 是运行时类型源，FastAPI 的 `/openapi.json` 是可执行规范；这里的 OpenAPI、JSON Schema 与示例用于团队评审和跨模块联调。v0.1 保留为历史 Mock，不再扩展。

耗时操作统一返回 `202 AgentRun`，客户端轮询 `GET /api/v1/agent-runs/{id}`，完成后根据 `resource_type/resource_id` 读取检索、风险、咨询、文书或导入产物。
