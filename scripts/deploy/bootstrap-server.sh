#!/usr/bin/env bash
set -euo pipefail

# Run once as root on the target host after cloning MarkLens.
# The only supplied value is the local MySQL root password. All application
# secrets are generated on the server and never printed or committed.
APP_ROOT=/opt/marklens
DB_NAME=marklens
DB_USER=marklens

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

: "${MARKLENS_MYSQL_ROOT_PASSWORD:?Set MARKLENS_MYSQL_ROOT_PASSWORD in the server shell.}"
: "${MARKLENS_ADMIN_EMAIL:?Set MARKLENS_ADMIN_EMAIL in the server shell.}"
: "${MARKLENS_ADMIN_PASSWORD:?Set MARKLENS_ADMIN_PASSWORD in the server shell.}"

command -v mysql >/dev/null || { echo "MySQL client is required" >&2; exit 1; }
command -v openssl >/dev/null || { echo "openssl is required" >&2; exit 1; }

db_password="$(openssl rand -hex 24)"
auth_secret="$(openssl rand -hex 48)"
health_secret="$(openssl rand -hex 24)"

mysql --protocol=socket -uroot -p"${MARKLENS_MYSQL_ROOT_PASSWORD}" <<SQL
CREATE DATABASE IF NOT EXISTS ${DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${db_password}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${db_password}';
GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

install -d -m 0750 "$APP_ROOT"
umask 077
{
  printf '%s\n' 'APP_ENV=production'
  printf '%s\n' 'APP_LOG_LEVEL=INFO'
  printf 'DATABASE_URL=%s\n' "mysql+pymysql://${DB_USER}:${db_password}@127.0.0.1:3306/${DB_NAME}?charset=utf8mb4"
  printf 'AUTH_SECRET=%s\n' "$auth_secret"
  printf '%s\n' 'COOKIE_SECURE=false'
  printf '%s\n' 'CORS_ORIGINS=http://152.136.27.117'
  # Start with deterministic CPU-safe retrieval. Enable only after model
  # weights have been intentionally downloaded and verified on the server.
  printf '%s\n' 'MODEL_RUNTIME_ENABLED=false'
  printf '%s\n' 'MODEL_CACHE_DIR=.model-cache'
  printf '%s\n' 'UPLOAD_DIR=data/uploads'
  printf '%s\n' 'SOURCE_DATA_DIR=data/sources'
  printf 'DEMO_ADMIN_EMAIL=%s\n' "$MARKLENS_ADMIN_EMAIL"
  printf 'DEMO_ADMIN_PASSWORD=%s\n' "$MARKLENS_ADMIN_PASSWORD"
  printf 'HEALTH_CHECK_SECRET=%s\n' "$health_secret"
} > "$APP_ROOT/.env"
chown root:marklens "$APP_ROOT/.env"
chmod 640 "$APP_ROOT/.env"

echo "Server-private MarkLens environment and least-privilege MySQL account created."
