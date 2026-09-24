# One image for the complete WorkBuddy application.
# FastAPI owns the embedded Go gateway process and both runtimes share this root.

FROM golang:1.22-bookworm AS go-builder
WORKDIR /src
COPY gateway/go.mod gateway/go.sum ./gateway/
WORKDIR /src/gateway
RUN go mod download
COPY gateway/cmd ./cmd
COPY gateway/internal ./internal
COPY scripts /src/scripts
RUN mkdir -p /out && CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o /out/wb2api ./cmd/server

FROM node:20-slim AS web-builder
WORKDIR /src
COPY web/ /src/
ARG NPM_REGISTRY=""
RUN set -eu; \
    if [ -f /src/out/index.html ]; then \
        echo "frontend: using prebuilt output"; \
        cp -r /src/out /dist; \
    else \
        echo "frontend: building output"; \
        npm_ci() { npm ci --no-audit --no-fund ${1:+--registry="$1"}; }; \
        if [ -n "${NPM_REGISTRY}" ]; then npm_ci "${NPM_REGISTRY}"; \
        elif npm_ci ""; then :; \
        else rm -rf node_modules; npm_ci https://registry.npmmirror.com; fi; \
        NEXT_OUTPUT_EXPORT=1 npx --no-install next build; \
        test -f out/index.html; cp -r out /dist; \
    fi; \
    test -f /dist/index.html

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WB_RUN_MODE=integrated \
    WB2API_MODE=integrated \
    WB_MANAGER_HOST=0.0.0.0 \
    WB_MANAGER_PORT=7864 \
    WB_UPSTREAM_DIR=/app \
    WB_AUTH_DIR=/app/data/auths \
    WB_UPSTREAM_CONFIG=/app/config.json \
    WB_DATA_DIR=/app/data/manager \
    WB_STATIC_DIR=/app/web/out \
    WB2API_BASE=http://127.0.0.1:7863 \
    WB2API_BINARY=/usr/local/bin/wb2api \
    WB2API_LOG_FILE=/app/data/gateway/server.log

WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r /app/server/requirements.txt
COPY server /app/server
COPY --from=go-builder /out/wb2api /usr/local/bin/wb2api
COPY --from=web-builder /dist /app/web/out
COPY config.example.json /app/config.example.json
COPY scripts /app/scripts
COPY deploy /app/deploy
COPY CHANGELOG.md README.md /app/
RUN useradd -u 10001 -m -s /bin/bash app \
    && mkdir -p /app/data/auths /app/data/gateway /app/data/manager \
    && chown -R 10001:10001 /app /usr/local/bin/wb2api
USER app
EXPOSE 7864
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7864/api/healthz', timeout=3)"
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "7864"]
