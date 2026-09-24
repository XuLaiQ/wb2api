# wb2api 部署说明

本项目是一个统一服务。`docker compose` 只启动 `wb2api` 一个容器，容器内的 FastAPI 进程负责管理页面、对外协议和内置 Go 网关。

## Docker

```bash
cp .env.example .env
cp config.example.json config.json
mkdir -p data/auths data/gateway data/manager
sudo chown -R 10001:10001 data
docker compose up -d --build
docker compose logs -f wb2api
```

只发布 `7864`。Go 网关的 `7863` 只绑定容器回环地址，管理端通过 `http://127.0.0.1:7863` 调用，因此不需要第二个容器、Docker 网络、Docker socket 或第二组卷。

## 原生 Windows

```cmd
copy config.example.json config.json
python -m venv .venv
.venv\Scripts\python -m pip install -r server\requirements.txt
start-all.cmd
```

`start.ps1` 会构建缺失的 Go 二进制并启动 FastAPI；FastAPI 在 lifespan 中启动 Go 网关。`stop-all.cmd` 使用进程树终止两个运行时，避免留下占用 7863 的孤儿进程。

## 数据和备份

备份以下内容即可迁移部署：

```text
.env
config.json
data/
```

`data/auths/` 保存账号授权凭据。Go 配置中的 `auth_dir` 默认是 `./data/auths`。旧部署升级可执行 `python3 deploy/migrate_auths.py --root .`：脚本会先检查冲突，再迁移文件并更新仍指向旧目录的 `config.json`/`.env`；检测到内容冲突会中止且保留源文件。确认账号正常后，再手动清理其他安装路径中的旧副本。

`config.json` 中的 `api_key` 是 Go 网关入站鉴权密钥；管理端会自动读取它向内置网关发请求。管理端自己的密钥、审计记录和登录用户保存在 `data/manager/manager.db` 与 `data/manager/users.json`。

## 更新

所有代码都在同一个 Git 仓库，必须从项目根目录更新：

```bash
git pull
docker compose up -d --build
```

管理页面的配置保存会只重启内置 Go 子进程，完整代码更新仍需重建统一容器或重启原生服务。
