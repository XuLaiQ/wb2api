# WorkBuddy wb2api

<div align="center">

**腾讯 CodeBuddy 账号池管理控制台 · 多协议兼容 API 网关**

[![Go](https://img.shields.io/badge/Go-1.22%2B-00ADD8?logo=go&logoColor=white)](https://go.dev/)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![Deploy](https://img.shields.io/badge/deploy-Docker%20%7C%20Windows-2496ED?logo=docker&logoColor=white)](DEPLOY.md)
[![License](https://img.shields.io/badge/license-MIT-22c55e.svg)](LICENSE)

[English](README.en.md) | 简体中文

</div>

---

## 目录

- [项目简介](#项目简介)
- [核心能力](#核心能力)
- [架构总览](#架构总览)
- [快速开始](#快速开始)
- [API 接入](#api-接入)
- [配置说明](#配置说明)
- [数据与备份](#数据与备份)
- [项目结构](#项目结构)
- [开发与测试](#开发与测试)
- [部署与运维](#部署与运维)
- [安全边界](#安全边界)
- [已知限制](#已知限制)
- [相关文档](#相关文档)
- [许可证](#许可证)

## 项目简介

WorkBuddy wb2api 是一个自托管的 CodeBuddy 多账号网关。它把多个经过授权的腾讯 CodeBuddy 账号纳入账号池，对外提供 OpenAI 兼容接口，并在同一个 Web 控制台中完成账号管理、密钥分发、访问控制、调用审计和用量统计。

当前版本是 workbuddy2api 与 workbuddy-manager 的合并版：Go 网关、FastAPI 管理端和 Next.js 前端位于同一个项目根目录，由一个入口和一个容器统一启动、停止、更新和备份。

运行时仍然是两个进程，这是 Go 与 Python 两种运行时的自然边界；部署和运维层面只有一个应用：

~~~text
客户端 / SDK
      |
      | OpenAI / Anthropic / Responses API
      v
FastAPI 管理端 :7864  <- 唯一对外入口
      |
      | 账号、密钥、IP、配额、日志、统计、协议转换
      v
内置 Go 网关 127.0.0.1:7863
      |
      | 账号池轮转、会话粘性、冷却、熔断、上游请求
      v
腾讯 CodeBuddy
~~~

核心数据流可以概括为：

~~~text
授权账号 -> data/auths/*.json -> 账号池 -> 请求鉴权与路由 -> CodeBuddy -> SSE / JSON 响应
~~~

> 本项目不是腾讯官方软件。请只使用本人拥有或明确获准使用的账号，并自行遵守 CodeBuddy 的服务条款、当地法律及组织内部合规要求。

## 核心能力

### 1. 一体化部署

- 一个 Git 仓库、一个 Docker 镜像、一个 Compose 服务。
- FastAPI 负责管理页面、对外 API、协议转换和 Go 子进程生命周期。
- 统一 Docker 部署不发布 7863，管理端通过 127.0.0.1:7863 访问内置网关，默认只发布 7864。
- 配置、账号凭据、网关状态、管理数据库和日志采用统一数据布局。
- 管理端保存上游配置或新增账号后，可以自动重载内置 Go 网关。

### 2. 多协议 API 兼容

| 协议 | 主要端点 | 适用客户端 |
|------|----------|------------|
| OpenAI Chat Completions | GET /v1/models、POST /v1/chat/completions | OpenAI SDK、Cherry Studio、LobeChat 等 |
| OpenAI Chat Completions v2 | POST /v2/chat/completions | 需要 v2 路径的兼容客户端 |
| Anthropic Messages | POST /v1/messages、POST /v1/messages/count_tokens | Claude Code、Cline、Cursor、Zed 等 |
| OpenAI Responses | POST /v1/responses、POST /responses | Codex、Responses SDK、DeepSeek Harness 等 |

支持流式 SSE 与非流式响应。Anthropic Messages 和 OpenAI Responses 由管理端转换为上游的 Chat Completions 请求，鉴权、模型版本、IP、配额、限流、日志和用量统计仍复用同一套规则。

### 3. 账号池治理

- Web 扫码授权纳管账号，保存凭据并自动触发上游重载。
- 自动刷新 token、检查账号状态、查询积分和有效期。
- 支持国内版（CN）与国际版（Global）账号，并按版本隔离模型、日志、任务和统计。
- 会话粘性：同一对话尽量固定到同一账号，减少多轮上下文和上游缓存被打散。
- 加权选号：综合积分、即将过期积分和闲置时间分配流量。
- 单账号并发租约、软限流冷却、失败熔断和模型级冷却，避免故障账号拖垮账号池。
- 状态持久化到 data/gateway/state.json，重启后保留冷却、积分和计数信息。

### 4. 管理控制台

- 仪表盘：账号健康度、可用模型、密钥、请求和用量概览。
- 账号：扫码添加、临时禁用/恢复、刷新 token、签到、积分刷新、连通性测试和删除。
- 任务：签到、活跃上报、猫猫旅行、保活及其他上游任务的记录与调度。
- API 密钥：独立有效期、版本、IP 白名单、最大 IP 数、模型白名单和 Token / 积分配额。
- 请求日志：记录模型、状态码、来源 IP、首字延迟、总耗时、Token 和实际扣费。
- 用量统计：按日期、模型、密钥和版本查看调用量与消耗。
- 模型中心：查看模型显示名、上下文、最大输出、推理档位和积分倍率。
- 聊天测试台：管理员登录后直接测试真实模型；测试会消耗账号池积分。
- 安全设置：全局 IP 白名单/黑名单、CIDR 规则和拦截审计。
- 系统设置：上游配置、提示词、定时任务、并发、熔断、模型映射和更新。
- 国际化与主题：支持中文、英文、日文、韩文，支持浅色/深色主题和移动端布局。

### 5. 访问控制与审计

- 管理端使用用户名、密码和签名 Cookie，API 密钥不能登录后台。
- 管理员与只读用户分离，修改用户、密码和角色会吊销旧会话。
- API 密钥只保存哈希，明文只在创建时展示。
- 每把密钥可单独配置版本、模型、IP、有效期、Token 配额和积分额度。
- 默认关闭 FastAPI /docs、/redoc 和 /openapi.json，需要时通过环境变量显式开启。
- 默认限制管理 API 请求体、网关请求体和单密钥调用速率。

## 架构总览

### 运行时拓扑

~~~text
                         ┌──────────────────────────────┐
                         │        wb2api 单容器           │
                         │                              │
客户端 / SDK ───────────>│ FastAPI :7864               │
  OpenAI                 │  · 登录与管理 API            │
  Anthropic              │  · 多协议转换                │
  Responses              │  · 密钥 / IP / 配额 / 审计    │
                         │  · 静态前端                  │
                         │          │                   │
                         │          v                   │
                         │ Go 网关 127.0.0.1:7863      │
                         │  · 账号池与模型路由          │
                         │  · 冷却 / 熔断 / 会话粘性     │
                         └──────────┼───────────────────┘
                                    v
                         腾讯 CodeBuddy 服务
~~~

### 请求处理流程

~~~text
请求
  -> 解析协议与模型
  -> 校验 API Key / 版本 / IP / 有效期 / 配额 / 限流
  -> 模型别名映射与会话粘性路由
  -> Go 账号池选号
  -> CodeBuddy 流式请求
  -> 协议响应转换
  -> 记录请求、Token、耗时和扣费
~~~

### 与旧版拆分项目的关系

旧版需要分别运行 workbuddy2api 和 workbuddy-manager 两个项目。合并版已经把两者的运行时和数据路径统一到本仓库，新的部署不需要：

- 第二个 Compose 服务；
- docker.sock；
- 独立的上游容器；
- 两套端口暴露；
- 两份配置和两套启停脚本。

当前部署与开发说明以本 README、[DEPLOY.md](DEPLOY.md) 和下方列出的专题文档为准。

## 快速开始

### 系统要求

| 方式 | 要求 |
|------|------|
| Docker | Docker 24+，Docker Compose v2 |
| Windows 原生 | Windows 10/11、Python 3.11+、Go 1.22+；构建前端需要 Node.js 20+ |
| Linux 原生 | Python 3.11+、Go 1.22+、Node.js 20+，推荐使用 systemd |
| 运行环境 | 能访问 CodeBuddy 接口；账号必须已授权 |

### Docker Compose 部署（推荐）

在本项目根目录执行：

~~~bash
cp .env.example .env
cp config.example.json config.json
mkdir -p auths data/gateway data/manager
~~~

编辑 config.json，至少将 api_key 换成随机生成的强密钥。示例文件里的 test_key 只是占位值，公网部署不能直接使用。

Linux 宿主机需要让容器用户 10001 读写运行时目录：

~~~bash
sudo chown -R 10001:10001 auths data
~~~

启动并查看日志：

~~~bash
docker compose up -d --build
docker compose ps
docker compose logs -f wb2api
~~~

打开管理页面：<http://127.0.0.1:7864>

首次启动未设置 WB_ADMIN_PASSWORD 时，随机管理员密码只会在日志中打印一次：

~~~bash
docker compose logs wb2api
~~~

推荐在 .env 中显式设置：

~~~dotenv
WB_ADMIN_PASSWORD=请替换为足够长的随机密码
~~~

### Windows 原生运行

在 wb2api 根目录打开 PowerShell：

~~~powershell
Copy-Item config.example.json config.json
Copy-Item .env.example .env

py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server\requirements.txt

cd web
npm ci
npm run build:export
cd ..

.\scripts\windows\start-all.cmd
~~~

`scripts/windows/start.ps1` 会在缺少 wb2api.exe 时自动执行 Go 构建，然后启动 FastAPI；FastAPI 会在同一进程树中拉起 Go 网关。管理页面地址为 <http://127.0.0.1:7864>。

停止、查看状态或后台启停：

~~~powershell
.\scripts\windows\stop-all.cmd
powershell -ExecutionPolicy Bypass -File .\scripts\windows\service-tools.ps1 status
powershell -ExecutionPolicy Bypass -File .\scripts\windows\service-tools.ps1 start
powershell -ExecutionPolicy Bypass -File .\scripts\windows\service-tools.ps1 stop
~~~

如果只需要启动后端 API 而暂时没有 web/out/，FastAPI 仍可以启动，但管理首页会返回 404；完成前端静态导出后再访问页面即可。

## API 接入

登录管理页面后，在“API 密钥”中创建一把下游密钥。上游 config.json 中的 api_key 是内部网关鉴权配置，不应直接当作多人共享的下游密钥。

### OpenAI Chat Completions

~~~bash
BASE_URL=http://127.0.0.1:7864
WB_KEY=在管理页面创建的密钥

curl "$BASE_URL/v1/models" \
  -H "Authorization: Bearer $WB_KEY"

curl "$BASE_URL/v1/chat/completions" \
  -H "Authorization: Bearer $WB_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "从 /v1/models 返回的模型名",
    "messages": [{"role": "user", "content": "你好，请介绍一下自己。"}],
    "stream": true
  }'
~~~

OpenAI SDK 的 base_url 通常设置为 http://127.0.0.1:7864/v1。模型名应以 /v1/models 的实际返回为准；国际版模型使用管理页面展示的 global: 前缀。

### Anthropic Messages

将 Anthropic SDK 的 base_url 指向 http://127.0.0.1:7864，并使用管理页面创建的密钥。服务支持 x-api-key、x-anthropic-api-key 和 Authorization: Bearer 形式的鉴权。

### OpenAI Responses

Responses SDK 可以使用 http://127.0.0.1:7864/v1 作为 base_url，对应 /v1/responses；也兼容直接以根地址调用 /responses。Responses 请求会在网关内部转换为 Chat Completions，再把流式或非流式结果转换回 Responses 结构。

### 健康检查

~~~bash
curl -s http://127.0.0.1:7864/api/healthz
~~~

健康检查只用于确认 FastAPI 管理端存活。Go 网关的内部状态可在管理页面查看；部署时不要把 7863 直接发布到公网。

## 配置说明

### config.json：网关和账号池配置

从 config.example.json 复制后按需修改：

| 配置 | 作用 |
|------|------|
| listen | 内置 Go 网关监听地址；统一 Docker 部署不发布 7863，原生部署建议设置为 127.0.0.1:7863 |
| api_key | Go 网关入站鉴权密钥；公网或管理端启用上游管理能力时必须设置 |
| auth_dir | 账号凭据目录，默认 ./data/auths |
| state_file | 账号池状态文件，默认位于 data 目录 |
| schedule | 签到、旅行、活跃、保活及活动任务的开关与执行时间 |
| pool | 并发、熔断、冷却、过期积分优先级和探索策略 |
| session_sticky | 会话粘性开关、滚动有效期和清理周期 |
| prompt | 上游系统提示词模式与自定义提示词文件 |
| global | 国际版能力开关与相关上游地址 |

管理页面中的设置会校验输入，并通过统一配置路径保存；不要同时手工修改文件和点击保存，以免产生覆盖竞态。

### .env：管理端和部署配置

常用变量如下：

| 变量 | 默认值 | 说明 |
|------|----------|------|
| WB_MANAGER_HOST | 127.0.0.1 | 管理端监听地址；生产环境应放在 HTTPS 反向代理后 |
| WB_MANAGER_PORT | 7864 | 管理端和对外 API 端口 |
| WB_ADMIN_PASSWORD | 空 | 首次管理员密码；为空则随机生成并打印一次 |
| WB2API_MODE | integrated | 合并版推荐值；native 用于外部原生网关场景，docker 用于兼容外部容器场景 |
| WB2API_BASE | http://127.0.0.1:7863 | 管理端访问 Go 网关的地址 |
| WB_UPSTREAM_DIR | 项目根目录 | 上游 config.json 所在目录 |
| WB_AUTH_DIR | 项目根目录下的 data/auths | 账号凭据目录 |
| WB_DATA_DIR | data/manager | 管理数据库、用户和管理端状态目录 |
| WB_TRUST_PROXY | 1 | 是否采信可信反向代理转发的来源 IP |
| WB_TRUSTED_PROXY_HOPS | 1 | 反向代理/CDN 层数，用于解析 X-Forwarded-For |
| WB_TRUSTED_PROXY_CIDRS | 常见本机/私网网段 | 允许被信任为反向代理的来源网段 |
| WB_ENABLE_DOCS | 0 | 是否启用 /docs、/redoc 和 /openapi.json |
| WB_GATEWAY_RATE_PER_MIN | 120 | 单把下游密钥每分钟调用上限，0 表示不限 |
| WB_HTTP_PROXY | 空 | 显式设置 CodeBuddy 出口代理；留空时不使用系统代理 |

修改 .env 后需要重启管理端。修改上游 config.json 后可在设置页保存，或重启服务使完整配置重新加载。

## 数据与备份

运行时重要文件：

~~~text
config.json                     # Go 网关配置，含 api_key
data/auths/workbuddy-*.json          # CodeBuddy 账号凭据
data/gateway/state.json         # 账号池状态
data/gateway/server.log         # Go 网关日志
data/manager/manager.db         # 管理端数据库、密钥、日志和统计
data/manager/users.json         # 管理端用户和会话签名材料
web/out/                        # 前端静态构建产物，可重新生成
~~~

迁移或备份至少保留：

~~~text
.env
config.json
data/
~~~

data/auths/、config.json、.env 和 data/manager/users.json 都含有敏感信息。备份应加密保存，不要上传到公开仓库或公开网盘。升级代码时不要覆盖这些运行时数据。

## 项目结构

~~~text
wb2api/
├── gateway/                 # 独立 Go 网关模块
│   ├── cmd/                  # 网关、登录、签到、积分和统计 CLI
│   ├── internal/             # 账号池、上游客户端、调度器和协议核心
│   ├── go.mod
│   └── go.sum
├── server/                  # FastAPI 管理端、协议转换、审计和更新服务
│   ├── routers/             # 账号、密钥、网关、日志、统计和系统 API
│   ├── services/            # 内置 Go 进程、任务、更新和模型服务
│   └── tests/               # 管理端测试
├── web/                     # Next.js 管理前端
├── scripts/                 # 任务和运维辅助脚本
├── data/                    # 运行时数据（不应提交）
│   ├── auths/                # 账号凭据
│   ├── gateway/              # 网关状态与日志
│   └── manager/              # 管理数据库与用户状态
├── config.example.json      # Go 网关配置模板
├── .env.example             # 管理端环境变量模板
├── Dockerfile               # 单镜像构建
├── docker-compose.yml       # 单服务编排
├── scripts/                 # 辅助脚本与 Windows 启停脚本
│   └── windows/              # Windows 启停与服务管理脚本
├── DEPLOY.md                # 部署补充说明
└── docs/                    # 当前维护的开发、接口与安全专题文档
~~~

## 开发与测试

### 构建后端

~~~bash
go -C gateway build ./...
go -C gateway vet ./...
go -C gateway test ./...
~~~

构建管理端依赖并生成静态前端：

~~~bash
python -m pip install -r server/requirements.txt
cd web
npm ci
npm run build:export
cd ..
~~~

### 运行管理端

~~~bash
go -C gateway build -o wb2api ./cmd/server
python -m uvicorn server.main:app --host 127.0.0.1 --port 7864 --env-file .env
~~~

FastAPI 启动时会自动拉起项目根目录下的 wb2api 二进制。若二进制不存在，先运行上面的构建命令，或在 Windows 上使用 scripts/windows/start.ps1 自动构建。

### 运行测试

~~~bash
go -C gateway test ./...
python -m unittest discover -s server/tests -p "test_*.py"
~~~

如果本机已安装 pytest，也可以使用：

~~~bash
python -m pytest server/tests -q
~~~

旧版部署可运行 `python deploy/migrate_auths.py` 安全迁移根目录 `auths/` 并更新默认配置；发现同名但内容不同的凭据时会中止，不覆盖文件。

涉及接口、鉴权、数据结构或前端行为的改动，应同时更新相关测试和文档。不要把 config.json、.env、data/、web/out/ 或构建产物提交到仓库。

## 部署与运维

### 生产环境建议

1. 只把 7864 放到 Nginx、Caddy 或其他 HTTPS 反向代理之后。
2. 不要开放 7863；在统一 Docker 部署中它只供容器内部使用。
3. 设置强随机的 api_key 和 WB_ADMIN_PASSWORD。
4. 反向代理必须关闭 SSE 缓冲，并设置足够长的读写超时。
5. 只有在确实需要时才设置 WB_MANAGER_HOST=0.0.0.0；同时正确配置可信代理网段和跳数。
6. 定期备份 config.json 和 data/，并保护备份文件权限。

Nginx 最小反代示例：

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

### 更新

统一仓库必须从项目根目录更新：

~~~bash
git pull
docker compose up -d --build
~~~

网页“系统更新”适合已经配置好发布源和签名校验的部署；手动更新适合开发机和没有启用自动更新的环境。更新前建议先备份 config.json 和 data/。

### 日常检查

~~~bash
docker compose ps
docker compose logs --tail=100 wb2api
curl -s http://127.0.0.1:7864/api/healthz
~~~

常见问题：

| 现象 | 处理 |
|------|------|
| 页面显示账号数为 0 | 检查 data/auths/ 是否有凭据、目录是否属于 uid 10001，并查看 data/gateway/server.log |
| 容器无法读写数据 | 执行 sudo chown -R 10001:10001 auths data 后重启 |
| 页面 404 | 确认 web/out/index.html 存在；重新执行 npm run build:export |
| API 返回 401 | 检查下游密钥是否在管理页面创建、是否已过期或被禁用 |
| 流式输出卡住 | 检查反向代理是否设置 proxy_buffering off，并确认读超时足够长 |
| 改配置未生效 | 检查实际加载的 .env 和 config.json 路径，然后重启服务 |
| 上游网关反复退出 | 检查 Go 二进制、config.json 和 data/gateway/server.log，确认 7863 未被其他进程占用 |

## 安全边界

- 管理端会话与下游 API 密钥是两套身份体系；泄露一把下游密钥不应直接获得管理权限，但仍应立即在面板中禁用或删除。
- 账号授权文件包含可续期的访问凭据，权限应限制为服务运行用户可读写。
- api_key 为空意味着 Go 网关不做入站鉴权。仅在完全隔离的本机测试环境使用，公网部署必须设置。
- WB_TRUST_PROXY=1 只适用于可信反向代理；服务直接暴露公网时不要无条件信任客户端提交的转发头。
- 管理员聊天测试台是真实上游请求，会消耗账号积分，不是离线模拟器。
- /docs、/redoc 和 /openapi.json 默认关闭；临时开启后不要忘记恢复。
- 发现凭据泄露或可利用安全问题时，不要在公开 Issue 中粘贴账号文件、Cookie、密钥或完整日志。

最新安全审计和已修复问题见 [docs/SECURITY-AUDIT-2026-09-15.md](docs/SECURITY-AUDIT-2026-09-15.md)。

## 已知限制

- 这是对 CodeBuddy 接口的兼容网关，不是 CodeBuddy 官方客户端；上游接口、模型、积分和账号策略变化可能需要同步适配。
- 语音、图片生成、实时音频等不属于本项目的核心能力，是否可用取决于上游模型和协议转换范围。
- 国际版不提供国内版的全部任务能力，例如签到、猫猫旅行和部分活动任务；面板会按版本显示实际可用能力。
- 默认的限流、登录失败计数和部分状态保存在单进程内；多实例部署需要额外的共享存储或 Redis 设计。
- 管理端是单实例管理控制台，当前不提供多节点数据库集群和高可用故障转移。
- 上游账号凭据必须由用户自行授权和维护；项目不会替用户获取、出售或共享第三方账号。
- 启用自定义提示词、模型映射或协议转换时，个别客户端的高级字段可能无法一一映射到上游协议。

## 相关文档

| 文档 | 内容 |
|------|------|
| [部署说明](DEPLOY.md) | Docker、Windows 原生和 Linux 部署 |
| [项目目录约定](docs/project-structure.md) | 源码分层、文件归属与清理边界 |
| [API Token 说明](docs/api-tokens.md) | 管理端访问令牌与权限范围 |
| [命名空间兼容](docs/namespace-compat.md) | API 命名空间兼容约定 |
| [Anthropic 上游配置](docs/sub2api-anthropic.md) | 在 Sub2API 中配置 Anthropic 上游 |
| [国际化说明](docs/i18n.md) | 前端翻译与校验流程 |
| [发布流程](docs/release-process.md) | 发布、构建和版本流程 |
| [发布签名](docs/release-signing.md) | 更新包签名与验签 |
| [安全审计](docs/SECURITY-AUDIT-2026-09-15.md) | 2026-09-15 安全审计结论 |
| [历史安全审计](docs/SECURITY-AUDIT.md) | v1.0.0 阶段安全审计记录 |
| [更新日志](CHANGELOG.md) | 版本变更记录 |

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。合并前两个项目的原始许可证副本保存在 [licenses/](licenses/) 目录中。
