# 生产部署文件

- `nginx/marklens.conf`：提供前端静态文件、SPA 回退和 `/api` 反向代理；
- `systemd/marklens-api.service`：以专用 `marklens` 用户运行 API，监听本机 `127.0.0.1:8001`。

服务器配置不进仓库。请从根目录 `.env.production.example` 复制为服务器 `/opt/marklens/.env`，填入实际数据库和密钥后再执行 `scripts/deploy/prepare-server.sh`。
