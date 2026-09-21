# WorkBuddy wb2api

<div align="center">

**Tencent CodeBuddy account-pool management console and multi-protocol API gateway**

[![Go](https://img.shields.io/badge/Go-1.22%2B-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Deploy](https://img.shields.io/badge/deploy-Docker%20%7C%20Windows-2496ED?logo=docker&logoColor=white)](DEPLOY.md)
[![License](https://img.shields.io/badge/license-MIT-22c55e.svg)](LICENSE)

[Chinese](README.md) | English

</div>

---

## Contents

- [Overview](#overview)
- [Core capabilities](#core-capabilities)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [API integration](#api-integration)
- [Configuration](#configuration)
- [Data and backups](#data-and-backups)
- [Project layout](#project-layout)
- [Development and testing](#development-and-testing)
- [Operations](#operations)
- [Security boundaries](#security-boundaries)
- [Known limitations](#known-limitations)
- [Documentation](#documentation)
- [License](#license)

## Overview

WorkBuddy wb2api is a self-hosted multi-account gateway for CodeBuddy. It places multiple authorized Tencent CodeBuddy accounts into an account pool, exposes an OpenAI-compatible API, and provides a web console for account management, key distribution, access control, request auditing and usage reporting.

The current version merges workbuddy2api and workbuddy-manager into one project. The Go gateway, FastAPI management service and Next.js frontend share one repository root, one entrypoint, one data layout and one container image.

The Go and Python components remain separate processes because they use different runtimes. From an installation and operations perspective, however, there is one application:

~~~text
Client / SDK
      |
      | OpenAI / Anthropic / Responses API
      v
FastAPI manager :7864  <- only public entrypoint
      |
      | accounts, keys, IP rules, quotas, logs, statistics, protocol translation
      v
Embedded Go gateway 127.0.0.1:7863
      |
      | account rotation, session affinity, cooldowns, circuit breaking
      v
Tencent CodeBuddy
~~~

The core data flow is:

~~~text
Authorized accounts -> auths/*.json -> account pool -> request routing -> CodeBuddy -> SSE / JSON
~~~

> This is not an official Tencent product. Use only accounts that you own or are explicitly authorized to use, and follow the applicable CodeBuddy terms, laws and organizational policies.

## Core capabilities

### 1. Unified deployment

- One Git repository, one Docker image and one Compose service.
- FastAPI owns the management UI, public APIs, protocol translation and the Go child-process lifecycle.
- The unified Docker deployment does not publish port 7863; the manager reaches the embedded gateway through 127.0.0.1:7863 and publishes port 7864.
- Configuration, credentials, gateway state, the management database and logs use one data layout.
- Saving upstream settings or adding an account from the manager can reload the embedded Go gateway automatically.

### 2. Multi-protocol API compatibility

| Protocol | Main endpoints | Typical clients |
|----------|----------------|-----------------|
| OpenAI Chat Completions | GET /v1/models, POST /v1/chat/completions | OpenAI SDK, Cherry Studio, LobeChat and similar clients |
| OpenAI Chat Completions v2 | POST /v2/chat/completions | Clients that require the v2 path |
| Anthropic Messages | POST /v1/messages, POST /v1/messages/count_tokens | Claude Code, Cline, Cursor, Zed and similar clients |
| OpenAI Responses | POST /v1/responses, POST /responses | Codex, Responses SDK, DeepSeek Harness and similar clients |

The gateway supports streaming SSE and non-streaming responses. Anthropic Messages and OpenAI Responses are translated to the upstream Chat Completions protocol. Authentication, realm selection, IP rules, quotas, rate limits, logs and usage accounting still use the same authorization path.

### 3. Account-pool governance

- Add accounts through web-based QR authorization, persist credentials and reload the upstream gateway automatically.
- Refresh tokens, inspect account health, query credits and track expiration.
- Support both the China (CN) and Global realms, with realm-aware models, logs, tasks and statistics.
- Keep a conversation on the same account when possible, preserving multi-turn context and upstream cache locality.
- Distribute traffic using account balance, soon-to-expire credits and idle time.
- Use per-account concurrency leases, soft-rate cooldowns, failure circuit breakers and model-level cooldowns.
- Persist pool state in data/gateway/state.json so cooldowns, balances and counters survive restarts.

### 4. Management console

- Dashboard for account health, available models, keys, requests and usage.
- Account management: QR onboarding, temporary disable/restore, token refresh, check-in, credit refresh, connectivity tests and deletion.
- Task history and scheduling for check-in, activity reporting, cat travel, keepalive and other upstream jobs.
- API key management with independent expiration, realm, IP allowlist, maximum IP count, model allowlist and token/credit quotas.
- Request logs with model, status code, source IP, time to first token, total latency, tokens and actual credit cost.
- Usage reports by date, model, key and realm.
- Model center with display name, context length, maximum output, reasoning levels and credit multipliers.
- Admin-only playground for testing real models through the same account pool.
- Security settings for global IP allow/deny rules, CIDR entries and blocked-request auditing.
- Settings for upstream configuration, prompts, schedules, concurrency, breakers, model aliases and updates.
- Chinese, English, Japanese and Korean UI translations, plus light/dark themes and mobile layouts.

### 5. Access control and auditing

- The manager uses username/password authentication and signed cookies. API keys cannot log into the admin console.
- Admin and read-only roles are separated; changing a user, password or role revokes existing sessions.
- API keys are stored as hashes and shown in plaintext only when created.
- Each key can have its own realm, model, IP, expiration, token quota and credit quota.
- FastAPI interactive documentation at /docs, /redoc and /openapi.json is disabled by default.
- Management request bodies, gateway request bodies and per-key request rates are bounded by default.

## Architecture

### Runtime topology

~~~text
                         ┌──────────────────────────────┐
                         │          wb2api image         │
                         │                              │
Client / SDK ───────────>│ FastAPI manager :7864        │
  OpenAI                 │  - management API            │
  Anthropic              │  - protocol translation      │
  Responses              │  - keys / IP / quotas / audit│
                         │  - static frontend           │
                         │           │                  │
                         │           v                  │
                         │ Embedded Go :7863            │
                         │  - account pool and routing  │
                         │  - cooldowns / breakers      │
                         │  - session affinity          │
                         └───────────┼──────────────────┘
                                     v
                         Tencent CodeBuddy
~~~

### Request flow

~~~text
Request
  -> parse protocol and model
  -> validate key / realm / IP / expiration / quota / rate limit
  -> apply model aliases and session-affinity routing
  -> select an account from the Go pool
  -> call CodeBuddy using streaming transport
  -> translate the response protocol
  -> record request, tokens, latency and credit cost
~~~

### Relationship to the old split projects

The old deployment required separate workbuddy2api and workbuddy-manager projects. The merged repository now shares the runtime and data paths, so a new deployment does not need:

- A second Compose service.
- docker.sock.
- A separate upstream container.
- Two sets of exposed ports.
- Two configuration files and two independent service lifecycles.

Historical migration material is kept in [docs/legacy/](docs/legacy/). For current deployments, follow this README and [DEPLOY.md](DEPLOY.md).

## Quick start

### Requirements

| Deployment | Requirements |
|------------|--------------|
| Docker | Docker 24+ and Docker Compose v2 |
| Windows native | Windows 10/11, Python 3.11+, Go 1.22+; Node.js 20+ for frontend builds |
| Linux native | Python 3.11+, Go 1.22+ and Node.js 20+; systemd is recommended |
| Runtime | Network access to CodeBuddy and at least one authorized account |

### Docker Compose (recommended)

Run these commands from the wb2api project root:

~~~bash
cp .env.example .env
cp config.example.json config.json
mkdir -p auths data/gateway data/manager
~~~

Edit config.json and replace api_key with a strong random secret. The test_key value in the example is only a placeholder and must not be used for a public deployment.

On Linux, give the container user 10001 ownership of runtime directories:

~~~bash
sudo chown -R 10001:10001 auths data
~~~

Start the service and inspect its logs:

~~~bash
docker compose up -d --build
docker compose ps
docker compose logs -f wb2api
~~~

Open the management console at <http://127.0.0.1:7864>.

If WB_ADMIN_PASSWORD is not set on the first start, a random administrator password is printed once in the container logs:

~~~bash
docker compose logs wb2api
~~~

Set it explicitly in .env for predictable deployments:

~~~dotenv
WB_ADMIN_PASSWORD=replace-with-a-long-random-password
~~~

### Windows native

Open PowerShell in the wb2api project root:

~~~powershell
Copy-Item config.example.json config.json
Copy-Item .env.example .env

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server\requirements.txt

cd web
npm ci
npm run build:export
cd ..

.\start-all.cmd
~~~

start.ps1 builds wb2api.exe if it is missing, starts FastAPI and lets FastAPI supervise the embedded Go gateway. Open <http://127.0.0.1:7864>.

Stop the service or use the background service helper:

~~~powershell
.\stop-all.cmd
powershell -ExecutionPolicy Bypass -File .\service-tools.ps1 status
powershell -ExecutionPolicy Bypass -File .\service-tools.ps1 start
powershell -ExecutionPolicy Bypass -File .\service-tools.ps1 stop
~~~

FastAPI can start without web/out/, but the management homepage returns 404 until the static frontend has been exported.

## API integration

Log into the management console and create a downstream key in the API Keys page. The api_key in config.json is the internal gateway credential and should not be reused as a shared downstream key.

### OpenAI Chat Completions

~~~bash
BASE_URL=http://127.0.0.1:7864
WB_KEY=key-created-in-the-management-console

curl "$BASE_URL/v1/models" \
  -H "Authorization: Bearer $WB_KEY"

curl "$BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $WB_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "use-a-model-returned-by-v1-models",
    "messages": [{"role": "user", "content": "Hello, please introduce yourself."}],
    "stream": true
  }'
~~~

For the OpenAI SDK, set base_url to http://127.0.0.1:7864/v1. Use a model returned by /v1/models. Global models use the global: prefix shown by the manager.

### Anthropic Messages

Set the Anthropic SDK base_url to http://127.0.0.1:7864 and use a key created by the manager. The service accepts x-api-key, x-anthropic-api-key and Authorization: Bearer authentication.

### OpenAI Responses

Responses SDK clients can use http://127.0.0.1:7864/v1 as base_url, which maps to /v1/responses. The root /responses endpoint is also supported. Requests are translated to Chat Completions internally and streaming or non-streaming results are translated back to the Responses format.

### Health check

~~~bash
curl -s http://127.0.0.1:7864/api/healthz
~~~

This endpoint confirms that the FastAPI manager is alive. Inspect embedded gateway state in the management console. Do not publish port 7863 to the Internet.

## Configuration

### config.json: gateway and pool settings

Copy config.example.json and adjust the values as needed:

| Setting | Purpose |
|---------|---------|
| listen | Embedded Go gateway listener; Docker does not publish 7863, while native deployments should prefer 127.0.0.1:7863 |
| api_key | Go gateway inbound credential; set it for any non-isolated deployment |
| auth_dir | Account credential directory, normally ./auths |
| state_file | Account-pool state file, normally under data |
| schedule | Check-in, travel, activity, keepalive and event-task schedules |
| pool | Concurrency, cooldown, breaker, expiring-credit and exploration settings |
| session_sticky | Session affinity, rolling TTL and cleanup interval |
| prompt | Upstream system-prompt mode and custom prompt file |
| global | Global realm switch and related upstream settings |

The manager validates settings before saving them. Avoid editing the file manually at the same time as saving from the UI.

### .env: manager and deployment settings

Common variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| WB_MANAGER_HOST | 127.0.0.1 | Manager bind address; put it behind HTTPS in production |
| WB_MANAGER_PORT | 7864 | Manager and public API port |
| WB_ADMIN_PASSWORD | empty | Initial admin password; empty means generate and print once |
| WB2API_MODE | integrated | Recommended for the merged project; native and docker support external gateway setups |
| WB2API_BASE | http://127.0.0.1:7863 | Manager URL for the Go gateway |
| WB_UPSTREAM_DIR | project root | Root directory for account, upstream config and gateway data |
| WB_AUTH_DIR | $WB_UPSTREAM_DIR/auths | Account credential directory |
| WB_DATA_DIR | data/manager | Manager database, users and manager state |
| WB_TRUST_PROXY | 1 | Trust forwarding headers only from configured proxies |
| WB_TRUSTED_PROXY_HOPS | 1 | Proxy/CDN depth used to parse X-Forwarded-For |
| WB_TRUSTED_PROXY_CIDRS | local/private networks | Networks allowed to act as trusted proxies |
| WB_ENABLE_DOCS | 0 | Enable /docs, /redoc and /openapi.json |
| WB_GATEWAY_RATE_PER_MIN | 120 | Per-key requests per minute; 0 disables this limit |
| WB_HTTP_PROXY | empty | Explicit CodeBuddy egress proxy |

Restart the manager after changing .env. Upstream config changes can be saved from the Settings page or applied by restarting the service.

## Data and backups

Important runtime files:

~~~text
config.json                     # Go gateway configuration, including api_key
auths/workbuddy-*.json          # CodeBuddy account credentials
data/gateway/state.json         # Account-pool state
data/gateway/server.log         # Go gateway log
data/manager/manager.db         # Manager database, keys, logs and statistics
data/manager/users.json         # Manager users and session-signing material
web/out/                        # Generated static frontend; can be rebuilt
~~~

Keep at least these items for migration or backup:

~~~text
.env
config.json
auths/
data/
~~~

auths/, config.json, .env and data/manager/users.json contain sensitive material. Encrypt backups and do not upload them to public repositories or public file-sharing services. Code updates must not replace runtime data.

## Project layout

~~~text
wb2api/
├── cmd/                     # Go gateway, login, check-in, credit and stats CLIs
├── internal/                # Go pool, upstream client, scheduler and protocol core
├── server/                  # FastAPI manager, protocol translation, audit and updates
│   ├── routers/             # Account, key, gateway, log, stats and system APIs
│   ├── services/            # Embedded Go process, tasks, updates and models
│   └── tests/               # Manager tests
├── web/                     # Next.js management frontend
├── scripts/                 # Task and operations helpers
├── auths/                   # Runtime account credentials; do not commit
├── data/                    # Runtime state, database and logs; do not commit
├── config.example.json      # Gateway configuration template
├── .env.example             # Manager environment template
├── Dockerfile               # Single-image build
├── docker-compose.yml       # Single-service orchestration
├── start-all.cmd            # Windows one-command start
├── stop-all.cmd             # Windows one-command stop
├── DEPLOY.md                # Deployment notes
└── docs/                    # Security, release, i18n and legacy documents
~~~

## Development and testing

### Build the backend

~~~bash
go build ./...
go vet ./...
go test ./...
~~~

Install manager dependencies and build the static frontend:

~~~bash
python -m pip install -r server/requirements.txt
cd web
npm ci
npm run build:export
cd ..
~~~

### Run the manager

~~~bash
go build -o wb2api ./cmd/server
python -m uvicorn server.main:app --host 127.0.0.1 --port 7864 --env-file .env
~~~

FastAPI starts the wb2api binary from the project root. If the binary is missing, build it first or use start.ps1 on Windows, which builds it automatically.

### Run tests

~~~bash
go test ./...
python -m unittest discover -s server/tests -p "test_*.py"
~~~

If pytest is installed, the Python suite can also be run with:

~~~bash
python -m pytest server/tests -q
~~~

Changes to APIs, authentication, data contracts or frontend behavior should include corresponding test and documentation updates. Do not commit auths/, config.json, .env, data/, web/out/ or build artifacts.

## Operations

### Production recommendations

1. Put port 7864 behind Nginx, Caddy or another HTTPS reverse proxy.
2. Do not expose port 7863; in the unified Docker deployment it is internal to the container.
3. Set strong random values for api_key and WB_ADMIN_PASSWORD.
4. Disable proxy buffering for SSE and use sufficiently long read/write timeouts.
5. Set WB_MANAGER_HOST=0.0.0.0 only when necessary, and configure trusted proxy networks and hop count correctly.
6. Back up auths/, config.json and data/ regularly, with restricted backup permissions.

Minimal Nginx proxy example:

~~~nginx
location / {
    proxy_pass http://127.0.0.1:7864;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
~~~

### Updates

Update the unified repository from its root:

~~~bash
git pull
docker compose up -d --build
~~~

The web updater is intended for deployments with a configured release source and signature verification. Manual updates are suitable for development machines and installations that do not use the updater. Back up auths/, config.json and data/ first.

### Routine checks

~~~bash
docker compose ps
docker compose logs --tail=100 wb2api
curl -s http://127.0.0.1:7864/api/healthz
~~~

Common issues:

| Symptom | Action |
|---------|--------|
| The console shows zero accounts | Check auths/, ownership for uid 10001 and data/gateway/server.log |
| The container cannot write data | Run sudo chown -R 10001:10001 auths data and restart |
| The page returns 404 | Ensure web/out/index.html exists and rerun npm run build:export |
| The API returns 401 | Check that the downstream key exists, is enabled and has not expired |
| Streaming stalls | Disable proxy buffering and increase the reverse-proxy read timeout |
| A configuration change has no effect | Verify the loaded .env and config.json paths, then restart |
| The gateway repeatedly exits | Check the Go binary, config.json, data/gateway/server.log and port 7863 |

## Security boundaries

- Manager sessions and downstream API keys are separate identity systems. Revoke a leaked downstream key immediately, even though it should not grant admin access.
- Account credential files contain renewable access credentials and should be readable and writable only by the service user.
- An empty api_key disables inbound gateway authentication. Use that only in a fully isolated local test environment.
- WB_TRUST_PROXY=1 is for a trusted reverse proxy. Do not blindly trust client-supplied forwarding headers when the service is directly exposed.
- The admin playground sends real upstream requests and consumes account credits; it is not an offline simulator.
- /docs, /redoc and /openapi.json are disabled by default and should be re-disabled after temporary debugging.
- Do not paste account files, cookies, keys or complete logs into public issues when reporting a security problem.

See [docs/SECURITY-AUDIT.md](docs/SECURITY-AUDIT.md) for the security audit and fixed issues.

## Known limitations

- This is a compatibility gateway for CodeBuddy, not an official CodeBuddy client. Upstream changes to APIs, models, credits or account policies may require updates.
- Voice, image generation and realtime audio are outside the core scope; availability depends on the upstream model and the translation layer.
- The Global realm does not expose every China-realm task, including check-in, cat travel and some events. The manager shows the actual capabilities by realm.
- Default rate limits, login-failure counters and some runtime state are process-local. Multi-instance deployments need shared storage or a Redis-based design.
- The manager is a single-instance console and does not currently provide a multi-node database cluster or automatic failover.
- Users must authorize and maintain their own upstream accounts. The project does not obtain, sell or share third-party accounts.
- Custom prompts, model aliases and protocol translation may not preserve every advanced client-specific field.

## Documentation

| Document | Description |
|----------|-------------|
| [Deployment notes](DEPLOY.md) | Docker, Windows native and Linux deployment details |
| [Release process](docs/release-process.md) | Build, release and version workflow |
| [Release signing](docs/release-signing.md) | Update-package signing and verification |
| [Security audit](docs/SECURITY-AUDIT.md) | Authentication, gateway, file-access and deployment security |
| [Internationalization](docs/i18n.md) | Frontend translation and validation workflow |
| [Legacy split-project docs](docs/legacy/) | Documentation and Compose files from before the merge |
| [Changelog](CHANGELOG.md) | Version history |

## License

This project is licensed under the MIT License; see [LICENSE](LICENSE). Copies of the original licenses from the two merged projects are kept in [licenses/](licenses/).
