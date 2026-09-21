# WorkBuddy wb2api

`workbuddy2api` and `workbuddy-manager` are merged into one project. The Go gateway, FastAPI management API and Next.js frontend share the repository root, one configuration, one data layout and one container image.

[中文版](README.md)

```text
client -> FastAPI :7864 -> embedded Go gateway 127.0.0.1:7863 -> CodeBuddy
                     \\-> management API, keys, audit, accounts and frontend
```

The Go gateway and FastAPI remain separate processes because they use different runtimes. FastAPI owns the Go process lifecycle, logs, crash recovery and configuration reloads. There is one public service, one compose service and one startup command.

## Quick start

### Docker

```bash
cp .env.example .env
cp config.example.json config.json
docker compose up -d --build
```

Open `http://127.0.0.1:7864`. If `WB_ADMIN_PASSWORD` is empty, the generated first-login password is printed by `docker compose logs wb2api`.

```bash
docker compose logs wb2api
```

Persistent data is stored in `auths/`, `data/gateway/` and `data/manager/`. The container uses uid `10001`; fix bind-mount ownership with `sudo chown -R 10001:10001 auths data` when needed.

```bash
sudo chown -R 10001:10001 auths data
```

### Windows native

```cmd
copy config.example.json config.json
python -m venv .venv
.venv\Scripts\python -m pip install -r server\requirements.txt
start-all.cmd
```

The startup script builds `wb2api.exe` when it is missing and starts the single FastAPI entrypoint. Stop it with `stop-all.cmd` or `Ctrl+C`.

### Manual development

```bash
go build -o wb2api ./cmd/server
python -m pip install -r server/requirements.txt
cd web && npm ci && NEXT_OUTPUT_EXPORT=1 npm run build
cd .. && python -m uvicorn server.main:app --host 127.0.0.1 --port 7864
```

## Project layout

```text
wb2api/
├── cmd/ internal/       Go gateway and account pool
├── server/              FastAPI management API
├── web/                 Next.js management frontend
├── scripts/             account task scripts
├── auths/               credentials (runtime)
├── data/gateway/        Go state and logs (runtime)
├── data/manager/        management database (runtime)
├── config.json          shared Go and management configuration
├── Dockerfile            single image build
└── docker-compose.yml    single service orchestration
```

`cmd/` and `internal/` contain the Go gateway, `server/` contains the FastAPI application, `web/` contains the frontend, and `scripts/` contains account tasks. `config.json` is shared by both runtimes. Build artifacts and runtime credentials are ignored by Git.

## Configuration and updates

Saving gateway settings in the management UI restarts the embedded Go process. For a code deployment, update the repository root and rebuild the single service:

```bash
git pull
docker compose up -d --build
```

Compatibility templates for older native layouts remain under `deploy/windows-native/`; the unified entrypoint does not depend on them.
