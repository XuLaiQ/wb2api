# WorkBuddy wb2api

这是 `workbuddy2api` 和 `workbuddy-manager` 的真正合并版。Go 网关、FastAPI 管理端和 Next.js 前端都在同一个项目根目录，由一个入口和一个容器统一构建、启动、停止与更新。

[English](README.en.md)

运行时只有一个对外服务：

```text
客户端 -> FastAPI :7864 -> 内置 Go 网关 127.0.0.1:7863 -> CodeBuddy
                  └-> 管理 API、密钥、审计、账号和前端
```

Go 和 Python 仍然是两个进程，这是两种语言运行时的必要边界；FastAPI 会负责 Go 子进程的启动、日志、崩溃拉起和配置重载，用户不再需要第二个项目、第二个 compose 服务、容器名或独立重启脚本。

## 快速开始

### Docker

```bash
cp .env.example .env
cp config.example.json config.json
docker compose up -d --build
```

打开 `http://127.0.0.1:7864`。首次没有设置 `WB_ADMIN_PASSWORD` 时，管理员随机密码在容器日志中：

```bash
docker compose logs wb2api
```

账号凭据在 `auths/`，网关状态在 `data/gateway/`，管理数据库和日志在 `data/manager/` 与 `data/gateway/`。容器使用 uid `10001`，宿主机 bind mount 首次创建后若出现权限错误，执行：

```bash
sudo chown -R 10001:10001 auths data
```

### Windows 原生

```cmd
copy config.example.json config.json
python -m venv .venv
.venv\Scripts\python -m pip install -r server\requirements.txt
start-all.cmd
```

`start.ps1` 会在根目录构建缺失的 `wb2api.exe`，然后启动统一的 FastAPI 入口；FastAPI 会自动拉起 Go 网关。停止使用 `stop-all.cmd`，或在服务窗口按 `Ctrl+C`。

### 手动开发

```bash
go build -o wb2api ./cmd/server
python -m pip install -r server/requirements.txt
cd web && npm ci && NEXT_OUTPUT_EXPORT=1 npm run build
cd .. && python -m uvicorn server.main:app --host 127.0.0.1 --port 7864
```

前端构建产物是 `web/out/`。没有它时 API 仍可启动，但管理页面会返回 404。

## 项目结构

```text
wb2api/
├── cmd/ internal/       Go 网关与账号池
├── server/              FastAPI 管理端、协议转换和审计
├── web/                 Next.js 管理前端
├── scripts/              账号任务脚本
├── auths/               账号凭据（运行时）
├── data/gateway/        Go 状态与网关日志（运行时）
├── data/manager/        管理数据库、用户和更新状态（运行时）
├── config.json          Go 与管理端共用配置（运行时）
├── Dockerfile           单镜像构建
└── docker-compose.yml    单服务编排
```

默认路径都从项目根目录推导。只有需要外置数据目录时才设置 `WB_UPSTREAM_DIR`、`WB_AUTH_DIR`、`WB_UPSTREAM_CONFIG` 或 `WB_DATA_DIR`。

## 配置重载和更新

管理端保存 Go 配置后会重启内置 Go 子进程，新的账号和配置立即生效。无需 `docker restart workbuddy2api`，也无需在两个目录之间同步配置。

仓库更新应在根目录执行：

```bash
git pull
docker compose up -d --build
```

生产部署建议只把 `7864` 放在 HTTPS 反向代理后面；Go 的 `7863` 只在容器内部监听，不对宿主机发布。

原两个项目的许可证保存在 `licenses/`，历史设计文档保存在 `docs/`。统一入口不再依赖旧的独立上游启停脚本。
