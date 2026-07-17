# MarkLens 真实商标数据说明

## 当前已导入样本

当前本机数据库已导入捷克工业产权局（IPO CZ）发布的国家商标 ST.96 增量数据：

- 发布日期：2026-06-20；
- 记录数量：26；
- 带图样记录：11；
- 数据格式：WIPO ST.96 XML + 商标图样；
- 数据集元数据：[Trademarks (ST96) - increment 2026-06-20](https://isdv.upv.gov.cz/webapp/webapp.opendata.datovasada?ptyp=tm96&pid=20260620diff)；
- 字段文档：[IPO CZ trademark documentation](https://isdv.upv.gov.cz/doc/opendata/doc/tm-dokumentace.html)；
- 使用条款：[IPO CZ open-data terms](https://isdv.upv.gov.cz/doc/opendata/doc/podminky_uziti.html)。

官方条款说明该数据集及其组成部分不受数据库著作权或特殊数据库权利限制，可以自由提取和使用，并声明分发包不包含个人数据。MarkLens 仍保留数据来源、发布批次和 ZIP 内原始成员路径，方便审计。

下载包的 SHA-256 为：

```text
d6e4f635d30515f4b7e7fc7451d50a3a19d702d10b00cabff35301312713465f
```

## 重新下载和导入

在项目根目录执行：

```bash
make download-real-sample
make import-real-sample
```

第二条命令可以重复执行。数据源以 `source_key + source_record_id` 幂等更新，不会重复创建同一条商标。

导入过程包括：

1. 解析 ST.96 XML；
2. 规范化申请号、商标文字、申请人、状态、申请日、Nice 分类和商品服务；
3. 将 GIF 图样安全转换为 PNG；
4. 生成 pHash、OCR、ResNet 图像向量；
5. 生成 BGE 中文文本向量；
6. 写入来源许可、导入统计和原始记录审计信息。

原始 ZIP 位于 `data/raw/ipo-cz-20260620/source.zip`，该目录已被 Git 忽略，不会意外提交大体积原始数据。

## 法域边界

这批数据的法域是捷克共和国（`CZ`），用途是验证真实字段解析、文字检索、图像检索、来源追溯和幂等同步。

它不能证明某标志在中国构成在先权利，也不能直接支撑中国商标注册风险结论。MarkLens 会在检索结果中显示“CZ 参考”，境外记录可以参与相似度对比，但确定性中国法风险分析会排除它们。

## 中国商标数据下一步

中国法风险分析的正式主数据源应使用国家知识产权局商标数据开放系统。国家知识产权局说明，该系统提供全量和增量批量下载，包含注册商标基本信息、商品/服务、代理人、注册人、图样、共有人、国际注册和优先权等 8 张表、60 个数据项。

入口：

- [中国商标网](https://sbj.cnipa.gov.cn/)；
- [国家知识产权公共服务平台](https://ggfw.cnipa.gov.cn/)；
- [知识产权数据使用手册及开放目录](https://www.cnipa.gov.cn/module/download/downfile.jsp?classid=0&filename=ac2074de2761499d85c09041a6513d87.pdf)。

自 2025-12-19 起，商标数据开放系统接入统一身份认证，未通过实名核验的账号不能访问。因此下载动作需要项目成员本人登录完成，不能由代码绕过。拿到一个官方 ZIP、CSV、XML 或字段样例后，可以在现有 `TrademarkSourceAdapter` 基础上增加 CNIPA 专用映射。

WIPO Global Brand Database 不作为自动数据源。其使用条款明确禁止自动查询、批量下载、批量存储和网页抓取。
