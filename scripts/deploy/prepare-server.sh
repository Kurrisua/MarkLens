#!/usr/bin/env bash
set -euo pipefail

# Run on the target host after the repository has been cloned to /opt/marklens.
# Secrets must already exist in /opt/marklens/.env and are never copied by this script.
APP_ROOT=/opt/marklens
WEB_ROOT=/usr/share/nginx/html/marklens

command -v python3.12 >/dev/null || { echo "Python 3.12 is required" >&2; exit 1; }
command -v pnpm >/dev/null || { echo "pnpm is required" >&2; exit 1; }
command -v nginx >/dev/null || { echo "nginx is required" >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync is required" >&2; exit 1; }

id marklens >/dev/null 2>&1 || useradd --system --create-home --shell /usr/sbin/nologin marklens
install -d -o marklens -g marklens "$APP_ROOT/apps/api/data/uploads" "$APP_ROOT/apps/api/data/sources"

cd "$APP_ROOT"
python3.12 -m venv apps/api/.venv
apps/api/.venv/bin/python -m pip install --upgrade pip
apps/api/.venv/bin/python -m pip install -e 'apps/api[dev]'
pnpm install --frozen-lockfile
pnpm --filter @marklens/web build

install -d -m 0755 "$WEB_ROOT"
rsync -a --delete apps/web/dist/ "$WEB_ROOT/"
install -m 0644 infra/nginx/marklens.conf /etc/nginx/conf.d/marklens.conf
install -m 0644 infra/systemd/marklens-api.service /etc/systemd/system/marklens-api.service

cd "$APP_ROOT/apps/api"
.venv/bin/alembic upgrade head
PYTHONPATH="$APP_ROOT/apps/api" .venv/bin/python -m app.seed
cd "$APP_ROOT"
chown -R marklens:marklens "$APP_ROOT/apps/api/data" "$APP_ROOT/apps/api/.model-cache" 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now marklens-api
nginx -t
systemctl reload nginx
