# 第 26 组部署约束

- 源码、运行数据、日志和备份均位于 `/root/code/group26/MarkLens`。
- 前端仅监听 `3026`，后端仅监听 `127.0.0.1:18226`；不使用系统 Nginx 的 80 端口。
- 后端从 group26 下复制的既有虚拟环境读取依赖；本方案不执行 `pip install` 或 `pnpm install`。
- 数据库使用宿主机 MySQL 的独立 `marklens_g26` 库。备份使用 `scripts/deploy/group26-backup-db.sh`。
- 只有复制后的依赖验证失败时，才允许讨论新增依赖或下载。
