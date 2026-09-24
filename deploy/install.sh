#!/usr/bin/env bash
set -euo pipefail

# Install the unified wb2api service. The Go gateway and FastAPI management
# application are built and deployed together from one repository root.

APP_DIR="${APP_DIR:-/opt/wb2api}"
REPO_URL="${REPO_URL:-}"

if [[ ! -d "$APP_DIR/.git" ]]; then
  if [[ -z "$REPO_URL" ]]; then
    echo "APP_DIR is not a git checkout. Set REPO_URL or clone the repository first." >&2
    exit 1
  fi
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"
test -f README.en.md
python3 deploy/migrate_auths.py --root "$APP_DIR"
mkdir -p data/auths data/gateway data/manager
if [[ ! -f config.json ]]; then
  cp config.example.json config.json
  echo "Created $APP_DIR/config.json. Set api_key before serving traffic."
fi

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  chown -R 10001:10001 data 2>/dev/null || true
  docker compose up -d --build
  echo "wb2api is running at http://127.0.0.1:7864"
  exit 0
fi

python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements.txt
go -C gateway build -o wb2api ./cmd/server
NEXT_OUTPUT_EXPORT=1 npm --prefix web ci
NEXT_OUTPUT_EXPORT=1 npm --prefix web run build
echo "Dependencies and binaries are ready. Start with:"
echo "  .venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 7864"
