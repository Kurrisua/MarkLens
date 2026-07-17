# 参与 MarkLens 开发

## 开始之前

```bash
make setup
make validate
```

阅读：

1. `docs/06-team-parallel-development.md`；
2. `docs/07-contract-governance.md`；
3. 自己负责模块的 `packages/*/README.md`；
4. `contracts/v0.2/openapi.yaml`、JSON Schema 和示例。

## 日常开发

1. 从 `main` 创建所属功能分支；
2. 只修改自己模块及明确约定的公共文件；
3. 通过 contract-v0.2 和服务接口开发，不跨模块读取私有表；
4. 提交前执行 `make validate` 和所属模块测试；
5. 通过 Pull Request 合并，说明契约是否发生变化。

推荐提交前缀：

- `feat(retrieval): ...`
- `feat(risk): ...`
- `feat(document): ...`
- `feat(orchestration): ...`
- `contract: ...`
- `docs: ...`

## 禁止提交

- `.env` 和任何真实密钥；
- 真实用户上传文件；
- 许可不明确的数据集；
- 无法核验的法律资料或案例；
- 模型生成但未标记来源的“演示事实”。
