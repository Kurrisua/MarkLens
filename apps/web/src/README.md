# Web 源码导航（答辩定位版）

当前前端以单一产品入口 `App.tsx` 维持稳定运行。为了避免答辩时在长文件中盲找，请按以下“功能锚点”定位；后续新功能应优先放入 `features/<feature-name>/`，并在本表登记。

| 关注功能 | 首先打开 | 搜索锚点 |
|---|---|---|
| 登录、角色菜单、路由守卫 | `App.tsx` | `ProductHeader`、`RequireUser`、`RouteBoundary` |
| 项目与方案创建 | `App.tsx` | `Projects`、`ProjectDetail`、`NewMark` |
| 初筛、候选、风险 | `App.tsx` | `MarkRow`、`TaskPage`、`SearchPage`、`RiskPage` |
| 报告保存、PDF 导出 | `App.tsx`、`api.ts` | `DocumentPage`、`exportDocument` |
| 学习与练习 | `App.tsx` | `Learn`、`Topic`、`Practice` |
| 运营台、内容和题库表单 | `App.tsx` | `Ops`、`OpsTopicForm`、`OpsQuestionForm` |
| 产品 API 客户端 | `api.ts` | `export const api` |
| 请求/响应类型 | `contracts.ts` | 接口名，例如 `DocumentDraft` |
| 产品样式 | `product.css` | `.ops-composer`、`.report-actions` |
| 基础布局样式 | `styles.css` | 页面类名，例如 `.risk-layout` |
| 结果页回归测试 | `result-pages.test.tsx` | `result page loading transitions` |

完整演示索引见 [`docs/defense/01-feature-map.md`](../../../docs/defense/01-feature-map.md)。
