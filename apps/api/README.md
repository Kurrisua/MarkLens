# MarkLens API

FastAPI 服务实现 contract-v0.2、MySQL 数据层、多模态检索、数据源导入、LangChain RAG、DeepSeek 结构化生成和引用校验。

```bash
make setup-api
make db-migrate
make seed
make dev-api
make test-api
```

生产与 CI 的业务数据库均为 MySQL。模型在首次请求时延迟加载；测试使用 `MODEL_RUNTIME_ENABLED=false` 避免下载权重。运行时配置只来自根目录 `.env`。
