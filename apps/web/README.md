# MarkLens Web

React 工作台覆盖首页、新建分析、异步任务、Top-K 检索、风险分析、文书编辑、法律咨询和数据源管理。界面使用 Radix Themes，支持系统中文字体、明暗主题、响应式布局、低强度动效和 reduced-motion。

```bash
make setup-web
make dev-web
make test-web
make build-web
```

Vite 将 `/api` 和 `/health` 代理到 `http://localhost:8000`。页面包含加载、空、错误、降级和成功状态，不直接展示原始 JSON。
