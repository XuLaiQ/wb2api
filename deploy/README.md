# wb2api deployment helpers

The deployment scripts target the unified repository root. They do not clone or start a separate `workbuddy2api` project.

For a Docker host:

```bash
APP_DIR=/opt/wb2api REPO_URL=https://example.com/your/wb2api.git sudo -E bash deploy/install.sh
```

The installer creates `config.json`, prepares `data/auths/`, gateway state and manager data, and runs the root `docker-compose.yml`. The resulting service listens on `127.0.0.1:7864`; the embedded Go gateway listens only on the container or host loopback at `7863`.

For an existing installation, run `python3 deploy/migrate_auths.py --root /opt/wb2api` before restarting to safely move the legacy `auths/` directory and update default path settings. Conflicting files stop the migration without overwriting credentials.

For a host without Docker, the installer creates `.venv`, builds the Go binary, builds the static frontend, and prints the single uvicorn command. `deploy/workbuddy-web.service` is the systemd template for that command.

Runtime data is never replaced during a code update:

```text
config.json
data/
```
