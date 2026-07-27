#!/usr/bin/env bash
set -euo pipefail

GROUP_ROOT=/root/code/group26/MarkLens
LEGACY_ROOT=/opt/marklens
STATIC_ROOT=/usr/share/nginx/html/marklens

test -f "$GROUP_ROOT/apps/api/app/main.py"
test -d "$LEGACY_ROOT/apps/api/.venv"
test -d "$STATIC_ROOT"

install -d -m 0750 \
  "$GROUP_ROOT/runtime/uploads" \
  "$GROUP_ROOT/runtime/sources" \
  "$GROUP_ROOT/runtime/model-cache" \
  "$GROUP_ROOT/runtime/nginx" \
  "$GROUP_ROOT/web"

# Reuse already installed dependencies and assets. No package manager is called.
rsync -a --delete "$LEGACY_ROOT/apps/api/.venv/" "$GROUP_ROOT/apps/api/.venv/"
rsync -a "$LEGACY_ROOT/apps/api/data/uploads/" "$GROUP_ROOT/runtime/uploads/"
rsync -a "$LEGACY_ROOT/apps/api/data/sources/" "$GROUP_ROOT/runtime/sources/"
rsync -a "$LEGACY_ROOT/apps/api/.model-cache/" "$GROUP_ROOT/runtime/model-cache/"
rsync -a --delete "$STATIC_ROOT/" "$GROUP_ROOT/web/"

export PYTHONPATH="$GROUP_ROOT/apps/api:$GROUP_ROOT/apps/api/.venv/lib/python3.12/site-packages"
/usr/bin/python3.12 -c 'import fastapi, sqlalchemy, fastembed, rapidocr, uvicorn'
/usr/sbin/nginx -t -p "$GROUP_ROOT" -c infra/group26/nginx.conf

echo "Group 26 runtime preparation passed without installing dependencies."
