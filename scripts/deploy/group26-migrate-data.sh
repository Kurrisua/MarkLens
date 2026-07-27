#!/usr/bin/env bash
set -euo pipefail

GROUP_ROOT=/root/code/group26/MarkLens
LEGACY_ROOT=/opt/marklens
LEGACY_DATABASE=marklens
GROUP_DATABASE=marklens_g26
GROUP_DATABASE_USER=marklens_g26

: "${MARKLENS_MYSQL_ROOT_PASSWORD:?Set this only in the current server shell.}"

install -d -m 0750 "$GROUP_ROOT/backups"
stamp="$(date +%Y%m%d-%H%M%S)"
legacy_dump="$GROUP_ROOT/backups/${LEGACY_DATABASE}-legacy-${stamp}.sql.gz"
database_password="$(openssl rand -hex 24)"

mysqldump --single-transaction --routines --triggers --no-tablespaces \
  -uroot -p"$MARKLENS_MYSQL_ROOT_PASSWORD" "$LEGACY_DATABASE" | gzip > "$legacy_dump"

mysql -uroot -p"$MARKLENS_MYSQL_ROOT_PASSWORD" <<SQL
CREATE DATABASE IF NOT EXISTS ${GROUP_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER IF NOT EXISTS '${GROUP_DATABASE_USER}'@'localhost' IDENTIFIED BY '${database_password}';
ALTER USER '${GROUP_DATABASE_USER}'@'localhost' IDENTIFIED BY '${database_password}';
GRANT ALL PRIVILEGES ON ${GROUP_DATABASE}.* TO '${GROUP_DATABASE_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

gunzip -c "$legacy_dump" | mysql -uroot -p"$MARKLENS_MYSQL_ROOT_PASSWORD" "$GROUP_DATABASE"

grep -vE '^(DATABASE_URL|CORS_ORIGINS|UPLOAD_DIR|SOURCE_DATA_DIR|MODEL_CACHE_DIR|DEEPSEEK_)=' \
  "$LEGACY_ROOT/.env" > "$GROUP_ROOT/.env"
{
  printf '%s\n' "DATABASE_URL=mysql+pymysql://${GROUP_DATABASE_USER}:${database_password}@127.0.0.1:3306/${GROUP_DATABASE}?charset=utf8mb4"
  printf '%s\n' 'CORS_ORIGINS=http://152.136.27.117:3026'
  printf '%s\n' 'UPLOAD_DIR=/root/code/group26/MarkLens/runtime/uploads'
  printf '%s\n' 'SOURCE_DATA_DIR=/root/code/group26/MarkLens/runtime/sources'
  printf '%s\n' 'MODEL_CACHE_DIR=/root/code/group26/MarkLens/runtime/model-cache'
  printf '%s\n' 'MODEL_RUNTIME_ENABLED=false'
} >> "$GROUP_ROOT/.env"
chmod 600 "$GROUP_ROOT/.env"

export PYTHONPATH="$GROUP_ROOT/apps/api:$GROUP_ROOT/apps/api/.venv/lib/python3.12/site-packages"
(
  cd "$GROUP_ROOT/apps/api"
  /usr/bin/python3.12 -m alembic upgrade head
)

echo "Migrated data into ${GROUP_DATABASE}; legacy dump: ${legacy_dump}"
