# wb2api deployment helpers

The deployment scripts target the unified repository root. They do not clone or start a separate `workbuddy2api` project.

For a Docker host:

```bash
APP_DIR=/opt/wb2api REPO_URL=https://example.com/your/wb2api.git sudo -E bash deploy/install.sh
```

The installer creates `config.json`, prepares `auths/` and `data/`, and runs the root `docker-compose.yml`. The resulting service listens on `127.0.0.1:7864`; the embedded Go gateway listens only on the container or host loopback at `7863`.

For a host without Docker, the installer creates `.venv`, builds the Go binary, builds the static frontend, and prints the single uvicorn command. `deploy/workbuddy-web.service` is the systemd template for that command.

Runtime data is never replaced during a code update:

```text
config.json
auths/
data/gateway/
data/manager/
```
