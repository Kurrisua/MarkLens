# 脚本说明

- `build_sample_trademark_attachments.py`：生成可用于演示附件识别的 DOCX、PDF 与图样；
- `deploy/bootstrap-server.sh`：仅在服务器本地创建最小权限 MySQL 账号和私有 `.env`，所有应用密钥在服务器生成；
- `deploy/prepare-server.sh`：在已准备好 MySQL 的 Linux 服务器上构建前后端、运行迁移并安装 Nginx/systemd 配置。

脚本不读取或打印仓库外的密钥。部署时通过服务器上的 `/opt/marklens/.env` 注入配置。
