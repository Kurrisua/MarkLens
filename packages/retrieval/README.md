# 多模态检索智能体

负责商标数据导入、文字/拼音/语义/OCR/图像召回、候选合并与可解释重排。

输入：`CaseContext`。输出：`EvidenceBundle`。当前实现位于 `apps/api/app/retrieval.py` 与 `sources.py`，公共字段遵循 `contract-v0.2`。
