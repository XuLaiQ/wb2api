<div align="center">

# WorkBuddy 一体化部署

**上游网关 + 管理面板，合成一个仓库，一条命令起全部**

把 [`workbuddy2api`](https://github.com/Sliverkiss/workbuddy2api)（Go 网关）与
[`workbuddy-manager`](https://github.com/ithtelab/workbuddy-manager)（Web 面板）
装进同一个仓库：**一次 clone、一次部署、一个 compose 文件**。

</div>

---

## 这是什么

| 目录 | 角色 | 技术栈 | 端口 |
|---|---|---|---|
| `upstream/` | **上游网关**：把 CodeBuddy 账号池包装成 OpenAI 兼容 API | Go 1.22+ | `7863` |
| `manager/` | **管理面板 + 对外网关**：扫码纳管、密钥分发、IP 管控、调用审计、协议转换 | FastAPI + Next.js 15 | `7864` |

两者是**上下游关系**，不是二选一：

```
客户端 ──► manager :7864 ──► upstream :7863 ──► 腾讯 CodeBuddy
            │                  │
      密钥/IP/审计        账号池/轮转/熔断
      Anthropic 协议        （只有 OpenAI 协议）
      Responses 协议
```

**对外一律接 `:7864`**（manager）。它才有密钥分发、IP 管控和调用日志；
直连 `:7863` 会绕过全部这些能力。仅本机自用、不需要这些时，直连 `:7863` 也能跑。

---

## 快速开始（Docker，推荐）

```bash
git clone <你的仓库地址> wb2api
cd wb2api

cp .env.example .env          # 通常只需改 WB_ADMIN_PASSWORD
docker compose up -d --build

# 首次启动若未设密码，管理员密码会打印在日志里：
docker compose logs workbuddy-manager | grep -A2 密码
```

然后：

1. 浏览器打开 <http://127.0.0.1:7864>，用 `admin` + 上面的密码登录；
2. 进「账号」页扫码添加 CodeBuddy 账号（**别用上游的 `login.sh`**，见下方说明）；
3. 进「密钥」页签发一个 API Key；
4. 用它调用：`http://127.0.0.1:7864/v1/chat/completions`。

> **两个端口都只绑 `127.0.0.1`**。要对外提供服务，请在前面挂 Nginx/Caddy 并配 HTTPS，
> 而不是把端口改成 `0.0.0.0` —— manager 持有全部账号凭据，直接暴露到公网是被打穿的常见原因。

### 首次部署的两个权限坑

bind mount 的目录属主由宿主机决定，容器内的 `chown` 不起作用。容器以 uid `10001` 运行，
所以仓库根执行一次即可：

```bash
mkdir -p upstream/auths upstream/data manager/data
sudo chown -R 10001:10001 upstream/auths upstream/data manager/data
```

不做的症状：管理端报 `sqlite3.OperationalError: unable to open database file`
（那个报错既不说路径也不说原因），或者明明有账号却显示「0 个账号」。

---

## 快速开始（Windows 原生，不用 Docker）

```cmd
:: 一次性准备
cd upstream && go build -o wb2api.exe ./cmd/server && cd ..
copy upstream\config.example.json upstream\config.json
::   编辑 upstream\config.json，设好 api_key 与 admin.enabled
cd manager && python -m venv .venv && .venv\Scripts\python -m pip install -r server\requirements.txt && cd ..

:: 以后每次启动
start-all.cmd
```

`start-all.cmd` 会依次拉起上游（后台、写 PID 文件）和面板（独立窗口）。
停止用 `stop-all.cmd`。

> 面板配置在 `manager/.env`，**路径项全部留空**——上游就在 `../upstream`，代码会自己推导。
> 这是合并带来的最大便利，详见下面的「合并后改了什么」。

---

## 目录结构

```
wb2api/
├── docker-compose.yml        # 统一编排：两个服务、同一网络、端口只绑本机
├── .env.example              # 统一配置模板（多数项留空即可）
├── start-all.cmd             # Windows 一键启动（原生模式）
├── stop-all.cmd
│
├── upstream/                 # 上游 workbuddy2api（原样保留，见「来源与许可」）
│   ├── cmd/ internal/ scripts/
│   ├── config.example.json   # 配置模板 → 复制为 config.json
│   ├── auths/                # 账号凭证（git 忽略）
│   ├── data/                 # 运行状态与日志（git 忽略）
│   └── docker-compose.yml    # 上游自带的编排，单独部署时用
│
└── manager/                  # 管理面板 workbuddy-manager
    ├── server/               # FastAPI 后端（含协议转换网关）
    ├── web/                  # Next.js 前端（out/ 为构建产物，git 忽略）
    ├── deploy/               # 安装 / 更新 / 签名校验脚本
    ├── data/                 # 数据库、日志、更新状态（git 忽略）
    ├── .env                  # 本机配置（git 忽略）
    └── docker-compose.yml    # manager 自带的编排，单独部署时用
```

---

## 配置

**Docker 部署**：`docker-compose.yml` 的 `environment` 段已经设好了关键项，
`.env` 通常只需要 `WB_ADMIN_PASSWORD`。

**原生部署**：改 `manager/.env`（模板见 `.env.example`）。

需要改的通常只有这些：

| 变量 | 说明 |
|---|---|
| `WB_ADMIN_PASSWORD` | 首次启动的管理员密码；留空则随机生成并打印到日志 |
| `WB_MANAGER_PORT` | 面板端口，默认 `7864` |
| `WB2API_BASE` | 上游地址。Docker 用 `http://workbuddy2api:7863`；原生用 `http://127.0.0.1:7863` |
| `WB_TRUST_PROXY` | 前面有反向代理时设 `1`（默认已是） |

**上游自己的配置**在 `upstream/config.json`，其中 `api_key` 是上游的入站密钥。
它由 manager 自动读取，一般不需要手动同步到 `.env`。

---

## 更新

合并成一个仓库后，**更新就是更新整个仓库**：

```bash
cd wb2api
git pull
docker compose up -d --build
```

`auths/`、`config.json`、`data/`、`.env` 都在 `.gitignore` 里，`git pull` **不会**碰到
你的账号和配置。

面板里的「系统更新」页面：

- **宿主机部署**（systemd / 直接跑）：可以全自动——拉取整个仓库并重建容器；
- **容器部署**：compose 只把 `upstream/` 子目录挂进容器，仓库根的 `.git` 不在容器里，
  无法在容器内执行 git。此时面板会**明确提示你在宿主机执行上面那两条命令**，
  而不是静默跳过。

---

## 合并后改了什么

`upstream/` 与 `manager/` 的源码**来自各自上游的发布版本，未做功能删改**。
为让两者在单一仓库里协同工作，只动了四处，全部在 `manager/` 内：

| 文件 | 改动 | 为什么 |
|---|---|---|
| `manager/server/config.py` | 上游路径改为**自动推导**（`<仓库>/upstream`），环境变量仍可覆盖 | 原实现要求手填绝对路径。这是原管理端唯一的部署坑——两个仓库分处不同目录时无法互相推导，路径一写错就表现为「0 个账号」，而报错里既没有路径也没有原因 |
| `manager/deploy/update.py` | 新增合并布局识别：上游没有独立 `.git` 时，「更新上游」提升为**更新整个仓库** | 合并后 `upstream/` 只是子目录，没有自己的 git 历史，按原逻辑会因「不是 git 仓库」而静默跳过 |
| `manager/server/services/updater.py` | 版本检测指向**本仓库**（从 `git remote` 自动推导，跟随你的 fork） | 否则会拿本仓库的 commit 去和原上游仓库比对，compare API 必然 404，界面永远显示「已是最新」 |
| `manager/server/tests/test_taskrun.py` | 两处 `setUp` 显式把上游目录指向空目录 | 这些测试测的是「宿主没有脚本 → 从容器提取」。原默认值 `/opt/workbuddy2api` 在开发机上恰好不存在，合并后推导命中了真实的 `upstream/scripts/`，前提不再自动成立 |

新增的只有根目录的编排与文档：`docker-compose.yml`、`.env.example`、`start-all.cmd`、
`stop-all.cmd`、`README.md`、`.gitignore`。

改造后 `manager/` 的测试套件与原仓库基线**完全一致**（1066 项，2 项失败均为本机环境所致：
一项需要 `wsl.exe`、一项是事件循环计时，两者在原仓库同样失败）。

### 已知的取舍

- **不再能单独跟随两个上游仓库更新**。合并前 `workbuddy-manager` 可以独立拉取
  `workbuddy2api` 的新版本；现在两者同版本。想单独跟进上游，需要手动把某个子目录
  的改动同步过来。
- **`upstream/docker-compose.yml` 保持原样**（端口是 `7863:7863`，公网可达）。
  单独用它起上游时请自行改成 `127.0.0.1:7863:7863`。根目录的 compose 已经绑好了本机。
- **`manager/` 的「一键更新」只替换 `server/` 与 `web/out/`**，不会动 `upstream/`。
  要连上游一起更新，用「更新上游」或直接 `git pull`。

---

## 来源与许可

本仓库是**聚合项目**，由两个 MIT 许可的独立项目组成：

| 目录 | 来源 | 许可证 |
|---|---|---|
| `upstream/` | [Sliverkiss/workbuddy2api](https://github.com/Sliverkiss/workbuddy2api) | MIT © 2026 Sliverkiss |
| `manager/` | [ithtelab/workbuddy-manager](https://github.com/ithtelab/workbuddy-manager) | MIT © 2026 WorkBuddy Manager contributors |

两个子目录各自保留原始 `LICENSE` 与 `README`。本仓库根目录的 `LICENSE` 覆盖新增的
编排、脚本与文档部分。上游项目的功能与用法请以各自的 README 为准。

---

## 排障

| 症状 | 原因与处理 |
|---|---|
| 面板显示「0 个账号」，但 `upstream/auths/` 里明明有文件 | bind mount 的属主问题。`sudo chown -R 10001:10001 upstream/auths` |
| `sqlite3.OperationalError: unable to open database file` | 同上，对 `manager/data` 做一次 chown |
| 面板打不开、容器起来了但页面 404 | `web/out` 没构建。容器会自动构建；原生模式需在 `manager/web` 执行 `npm ci && NEXT_OUTPUT_EXPORT=1 npm run build` |
| 上游容器重启失败 | 检查是否挂了 `/var/run/docker.sock`；没挂时面板会如实提示「请到宿主机操作」 |
| 「系统更新」说未配置仓库地址 | 本仓库还没有 git remote。`git remote add origin <你的仓库地址>`，或设 `WB_MANAGER_REPO` |
| 本机开着 Clash 等 TUN 代理时连不上上游 | `.env` 的 `WB_HTTP_PROXY` 保持留空 |
| 添加账号报错 / 扫码无反应 | 用面板的扫码功能，别用上游 `login.sh`（后者在 Git Bash 下有 python3 缺失等问题） |

**服务器部署**（Nginx 反代、HTTPS、安全组、接入 sub2api、备份与迁移、排障表）
见 **[`DEPLOY.md`](DEPLOY.md)**。

更细的说明见 `manager/README.md` 与 `manager/deploy/README.md`；
上游的账号池、熔断、签到等机制见 `upstream/README.md`。
