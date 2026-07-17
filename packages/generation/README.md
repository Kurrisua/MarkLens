# 可信文书智能体

负责事实确认、模板选择、分段生成、引用检查和事实一致性校验。

输入：`RiskAssessment` 与用户确认事实。输出：`DocumentDraft`。MVP 只支持商标注册风险评估报告。

当前 LangChain LCEL、DeepSeek 结构化输出、MySQL 法律向量检索和模板降级实现位于 `apps/api/app/rag.py`。
