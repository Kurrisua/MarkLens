# 案件咨询与编排智能体

负责案件信息收集、缺失字段提示、任务路由、运行状态和智能体结果汇总。当前通过持久化 `AgentRun` 和 FastAPI BackgroundTasks 编排，耗时端点遵循 `contract-v0.2` 的 202 轮询协议。

输入：`CaseContext`。输出：结构化的下一步动作或已完成产物引用。
