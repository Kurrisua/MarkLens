#!/usr/bin/env bash
set -euo pipefail

GROUP_ROOT=/root/code/group26/MarkLens
DATABASE_NAME=marklens_g26

: "${MARKLENS_MYSQL_ROOT_PASSWORD:?Set this only in the current server shell.}"

mkdir -p "$GROUP_ROOT/backups"
stamp="$(date +%Y%m%d-%H%M%S)"
mysqldump --single-transaction --routines --triggers --no-tablespaces \
  -uroot -p"$MARKLENS_MYSQL_ROOT_PASSWORD" "$DATABASE_NAME" \
  | gzip > "$GROUP_ROOT/backups/${DATABASE_NAME}-${stamp}.sql.gz"
echo "$GROUP_ROOT/backups/${DATABASE_NAME}-${stamp}.sql.gz"
