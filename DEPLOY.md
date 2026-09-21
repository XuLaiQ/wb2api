# WorkBuddy 服务器部署指南

把这一整个仓库（上游账号池网关 + Web 面板 + 对外网关）部署到 Linux 服务器。

以 AWS EC2（Amazon Linux 2023）为参照环境；其他发行版同理，差异只在包管理与防火墙。

> 合并成一个仓库后，**部署只有一步**：clone、配 `.env`、`docker compose up -d --build`。
> 上游与面板的目录关系（原本要求"必须相邻"）现在是天然的——`upstream/` 就是仓库的子目录。

---

## 0. 速览

| 项 | 值 |
|---|---|
| 上游端口 | `7863`（仅本机） |
| 面板端口 | `7864`（仅本机） |
| 对外入口 | Nginx 反代 `127.0.0.1:7864` |
| 部署方式 | 单个 Docker Compose |
| 服务器目录 | `/home/ec2-user/wb2api` |
| 最低配置 | 2 核 2 GB，磁盘 10 GB |

---

## 1. 架构

```
Internet / Cloudflare
        |
        |  TCP 80 / 443
        v
      Nginx
        |
        |  127.0.0.1:7864
        v
  workbuddy-manager          ← Web 面板 + 密钥分发 + IP 管控 + 调用日志
        |
        |  http://workbuddy2api:7863   （同一 compose 网络，走服务名）
        v
  workbuddy2api              ← 账号池 + 轮转 + 熔断 + 定时签到
        |
        |  HTTPS / SSE
        v
  腾讯 CodeBuddy
```

两个容器在同一自定义网络 `wb2api` 里，共享宿主机的 `upstream/` 目录
（`config.json`、`auths/`），manager 通过挂载的 `docker.sock` 重启上游容器。

---

## 2. 前置准备

### 2.1 服务器要求

- Linux（本文用 Amazon Linux 2023）
- Docker 24+ 与 Docker Compose v2
- 能访问 `github.com`（拉代码）与腾讯接口（`copilot.tencent.com`）

```bash
docker --version && docker compose version
```

若未安装：

```bash
# Amazon Linux 2023
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# 重新登录使 docker 组生效
```

### 2.2 磁盘

镜像构建需要约 2 GB 空间（Go 编译阶段 + Node 构建阶段）。**首次构建时内存峰值约 1.5 GB**，
2 GB 的机器若同时跑别的服务可能 OOM；届时可改在本机构建好 `manager/web/out` 再上传，
容器会直接复用（见 `manager/Dockerfile` 的说明）。

---

## 3. 部署

### 3.1 拉代码

```bash
mkdir -p ~/wb2api && cd ~/wb2api
git clone <你的仓库地址> .
```

最终结构：

```
~/wb2api/
├── docker-compose.yml        ← 唯一需要操作的编排文件
├── .env.example
├── upstream/                 ← 上游（含 config.json、auths/）
└── manager/                  ← 面板（含 data/）
```

### 3.2 生成配置

```bash
cp .env.example .env
vi .env        # 只需设 WB_ADMIN_PASSWORD；其余项留空即可
```

`.env` 里的**路径项全部留空**——上游就在 `upstream/`，代码会自己推导。
这是合并带来的便利：原管理端要求手填绝对路径，一旦写错就表现为"面板显示 0 个账号"，
而报错里既没有路径也没有原因。

上游自己的配置：

```bash
cp upstream/config.example.json upstream/config.json
vi upstream/config.json
```

至少要改：

```json
{
  "api_key": "<生成一个强随机串>",
  "admin": { "enabled": true }
}
```

生成强随机串：

```bash
openssl rand -base64 32 | tr -d '/+=' | head -c 40; echo
```

### 3.3 建目录并修权限（最容易踩的坑）

```bash
mkdir -p upstream/auths upstream/data manager/data
sudo chown -R 10001:10001 upstream/auths upstream/data manager/data
```

**为什么必须做**：bind mount 的目录属主由宿主机决定，容器内的 `chown` 不起作用，
而容器以 uid `10001` 运行。不做的症状有两个，且都不报权限错：

- 面板显示「0 个账号」，而 `upstream/auths/` 里明明有文件；
- `sqlite3.OperationalError: unable to open database file`（既不说路径也不说原因）。

### 3.4 启动

```bash
docker compose up -d --build
```

首次构建需数分钟（要编译 Go 二进制与前端）。看进度：

```bash
docker compose logs -f
```

### 3.5 取初始管理员密码

```bash
docker compose logs workbuddy-manager | grep -A2 密码
```

若已在 `.env` 里设了 `WB_ADMIN_PASSWORD`，直接用那个。

### 3.6 验证

```bash
curl -s http://127.0.0.1:7863/healthz
# {"healthy":0,"realm_servable":{...},"service":"workbuddy2api","total":0}   ← 还没加账号
curl -s http://127.0.0.1:7864/api/healthz
# {"ok":true,"service":"workbuddy-manager"}
docker compose ps          # 两个服务都应是 Up
```

---

## 4. 对外暴露（Nginx）

### 4.1 站点配置

```bash
sudo vi /etc/nginx/conf.d/workbuddy.conf
```

```nginx
server {
    listen 80;
    server_name wb.example.com;   # 改成你的域名

    location / {
        proxy_pass http://127.0.0.1:7864;
        proxy_http_version 1.1;

        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 流式输出必须关缓冲，否则对话会卡住不吐字
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        chunked_transfer_encoding on;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### 4.2 HTTPS

走 Cloudflare 回源，或 certbot：

```bash
sudo dnf install -y certbot python3-certbot-nginx
sudo certbot --nginx -d wb.example.com
```

用 certbot 签完，把 `.env` 里的 `WB_SECURE_COOKIE` 设为 `true`（比依赖反代透传
`X-Forwarded-Proto` 更确定）。

### 4.3 安全组

| 协议 | 端口 | 来源 | 用途 |
|---|---|---|---|
| TCP | `22` | 管理员 IP `/32` | SSH |
| TCP | `80` | `0.0.0.0/0` | Nginx / Cloudflare 回源 |
| TCP | `443` | `0.0.0.0/0` | HTTPS（若直连） |

> **不要开放 `7863` 和 `7864`。** 面板持有你全部 CodeBuddy 账号的明文凭据；
> 上游的 `api_key` 是全局密钥，泄漏即失守。两个端口只在宿主机与 Docker 网络内可达
> （compose 里已绑死 `127.0.0.1`）。

---

## 5. 添加 CodeBuddy 账号

浏览器打开面板 → 用 `admin` 登录 → **账号** → **添加账号** → 用微信/QQ 扫码。

扫码成功后 manager 会自动完成三件事：

1. 凭证落盘到 `upstream/auths/workbuddy-<uid>.json`
2. 调 `docker restart workbuddy2api` 重启上游容器加载新账号
3. 面板刷新出该账号

验证：

```bash
curl -s http://127.0.0.1:7863/healthz
# {"healthy":1,"realm_servable":{...},"service":"workbuddy2api","total":1}
```

> **不要用 `login.sh` 在服务器上加号。** 它需要交互式 `read`、依赖 `python3`、
> 还会因 `login.exe` 后缀问题反复重编译。面板的扫码功能是同一套协议的 Python 实现，
> 走 Web 界面，更可靠。

---

## 6. 接入 sub2api（可选）

如果同一台服务器上还跑着 sub2api，可以把它接进来当上游渠道。

### 6.1 在 sub2api 里添加账号

| 字段 | 填什么 |
|---|---|
| 平台 | **OpenAI** |
| 账号类型 | **API Key** |
| Base URL | 见 6.3 |
| API Key | 面板「密钥」页创建的，或上游 `config.json` 的 `api_key` |

### 6.2 两个必踩的坑

**Base URL 不要带 `/v1`。** sub2api 出站拼的是 `{base_url}/v1/chat/completions`，
填了 `/v1` 会变成 `/v1/v1/chat/completions`。

**不要选 `upstream`（上游透传）类型。** 它看着最像，但实际是 antigravity 平台专用的中继类型。
通用入口是各平台的 `apikey` 类型。

### 6.3 网络可达性

sub2api 是独立 compose，与 workbuddy 不在同一 Docker 网络。两种接法：

**方式 A：共享 Docker 网络（推荐）**

```bash
docker network connect wb2api <sub2api 容器名>
```

Base URL 填 `http://workbuddy-manager:7864`。

若希望重启后自动保持，在 sub2api 的 compose 里声明外部网络：

```yaml
services:
  sub2api:
    networks:
      - default
      - wb2api

networks:
  wb2api:
    external: true
    name: wb2api          # 即 workbuddy 的 compose 项目名_网络名，用 docker network ls 确认
```

**方式 B：宿主机网关**

sub2api 的 compose 里加：

```yaml
services:
  sub2api:
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

Base URL 填 `http://host.docker.internal:7864`。

> **前提**：manager 的端口映射不能只绑 `127.0.0.1`。把根 compose 里改成 `"7864:7864"`，
> 再用安全组兜住（不开放 7864）。这也是为什么**方式 A 更干净**——不用放宽端口绑定。

### 6.4 验证

在 sub2api 里对该渠道做一次连通性测试。失败时按顺序查：

```bash
docker network ls | grep wb2api                    # 网络存在？
docker exec <sub2api> ping -c1 workbuddy-manager   # 能解析服务名？
curl -s http://127.0.0.1:7864/api/healthz          # 面板本身活着？
```

---

## 7. 运维

### 7.1 更新

合并成一个仓库后，**更新就是更新整个仓库**：

```bash
cd ~/wb2api
git pull
docker compose up -d --build
```

`upstream/auths/`、`upstream/config.json`、`upstream/data/`、`manager/data/`、`.env`
都在 `.gitignore` 里，`git pull` **不会**碰到账号与配置。

面板「系统更新」页面在**宿主机部署**下可以全自动做这件事；**容器部署**下
容器里看不到仓库根的 `.git`，面板会明确提示你在宿主机执行上面两条命令，而不是静默跳过。

### 7.2 备份

要备份的只有这些（都在 git 之外）：

```bash
cd ~/wb2api
tar czf ~/wb2api-backup-$(date +%F).tar.gz \
  .env upstream/config.json upstream/auths upstream/data manager/data
```

`upstream/auths/` 是账号凭证、`manager/data/` 是数据库（密钥、IP 规则、调用日志）——
**丢了就要重新扫码加号**，务必定期备份。

### 7.3 查看日志

```bash
docker compose logs -f workbuddy2api        # 上游：选号、熔断、定时任务
docker compose logs -f workbuddy-manager    # 面板：请求、鉴权、错误
tail -f upstream/data/server.err.log        # 上游的持久化错误日志
```

### 7.4 重启单个服务

```bash
docker compose restart workbuddy2api        # 只重启上游（改 config.json 后用）
docker compose restart workbuddy-manager    # 只重启面板
```

---

## 8. 排障

| 症状 | 原因与处理 |
|---|---|
| 面板显示「0 个账号」，但 `upstream/auths/` 里有文件 | 属主问题。`sudo chown -R 10001:10001 upstream/auths` |
| `sqlite3.OperationalError: unable to open database file` | 同上，对 `manager/data` 做一次 chown |
| 容器起来了但页面 404 | `web/out` 没构建。容器会自动构建；看 `docker compose logs workbuddy-manager` 的构建阶段 |
| 上游容器重启失败 | 检查 `/var/run/docker.sock` 是否挂上；没挂时面板会如实提示"请到宿主机操作" |
| SSE 流式对话卡住不吐字 | Nginx 少了 `proxy_buffering off` |
| 面板登录后立刻掉线 | `WB_SECURE_COOKIE` 与实际协议不匹配（HTTP 下设了 `true`） |
| 面板提示"未配置仓库地址" | 服务器上的仓库没有 remote。`git remote add origin <url>`，或设 `WB_MANAGER_REPO` |
| 构建时 OOM | 本机构建 `manager/web/out` 后上传，跳过容器内前端构建 |
| 上游容器起不来、日志无输出 | `docker compose logs workbuddy2api`；再看 `upstream/data/server.err.log` |

---

## 9. 从本机迁移到服务器

本机（Windows）已经加好号的话，不必重新扫码：

```bash
# 本机执行
cd F:/token-p/WorkBuddy/wb2api
tar czf /tmp/wb2api-state.tar.gz .env upstream/config.json upstream/auths

# 上传
scp /tmp/wb2api-state.tar.gz ec2-user@<server>:~/

# 服务器执行
cd ~/wb2api && tar xzf ~/wb2api-state.tar.gz
sudo chown -R 10001:10001 upstream/auths
docker compose up -d --build
```

> `manager/data/`（面板数据库：密钥、IP 规则、调用日志）也可一并带上；
> 不带的话面板会重新初始化，需要重新建密钥——但账号仍然可用。

---

## 10. 与本机部署的差异

| 项 | 本机（Windows 原生） | 服务器（Docker） |
|---|---|---|
| 启动 | `start-all.cmd` | `docker compose up -d --build` |
| 上游 | `upstream/wb2api.exe` 进程 | `workbuddy2api` 容器 |
| 面板 | `uvicorn` 前台窗口 | `workbuddy-manager` 容器 |
| 上游地址 | `http://127.0.0.1:7863` | `http://workbuddy2api:7863`（服务名） |
| 更新 | `git pull` + 重跑 `start-all.cmd` | `git pull` + `docker compose up -d --build` |
| 需要 `.venv` | 是 | 否（依赖在镜像里） |

两种形态共用同一份代码与同一套路径推导，**不需要改任何配置文件**。
