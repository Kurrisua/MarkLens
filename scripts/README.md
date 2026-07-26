# 脚本说明

- `build_sample_trademark_attachments.py`：生成可用于演示附件识别的 DOCX、PDF 与图样；
- `deploy/prepare-server.sh`：在已准备好 MySQL 的 Linux 服务器上构建前后端、运行迁移并安装 Nginx/systemd 配置。

脚本不读取或打印仓库外的密钥。部署时通过服务器上的 `/opt/marklens/.env` 注入配置。
