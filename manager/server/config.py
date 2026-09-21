"""运行期配置：全部通过环境变量覆盖，默认值适配 1Panel 单机部署。"""
from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # manager 项目根目录
# 合并仓库的根。本仓库布局是 <root>/{upstream, manager}，所以它等于 manager/ 的
# 上一级。单独把 manager/ 拆出去部署时它同样等于 manager 的上一级，只是那个位置
# 没有 upstream/ —— 此时 _default_upstream_dir() 会回退到历史默认值，
# 行为与拆分部署完全一致（下面有详细说明）。
PROJECT_ROOT = ROOT.parent


def _env(name: str, default: str) -> str:
    v = os.environ.get(name, '').strip()
    return v or default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, '').strip() or default)
    except ValueError:
        return default


PORT = _env_int('WB_MANAGER_PORT', 7864)
HOST = _env('WB_MANAGER_HOST', '0.0.0.0')

def _default_upstream_dir() -> Path:
    """上游目录的默认位置。

    **这是合并成一个仓库后最大的收益**：上游固定是 manager 的兄弟目录
    `upstream/`，位置可推导，于是不再需要用户手填绝对路径。

    为什么值得单独写一个函数：手填路径是原管理端**唯一**的部署坑 —— 两个仓库
    分处不同目录（`/opt/workbuddy2api` 与 `/opt/workbuddy-manager`）时无法互相
    推导，只能让用户写绝对路径；而写错的表现是面板显示「0 个账号」，报错信息里
    既没有路径也没有原因，排查成本很高（本机部署时也踩过：见仓库根 README）。

    探测顺序（「存在即用」，不存在的直接跳过）：

      1. `<manager>/../upstream` —— 源码 / 原生进程部署，本仓库的标准布局；
      2. `<manager>/upstream`    —— 容器内 manager 装在 /app，
                                    上游挂在 /app/upstream 时命中；
      3. `/opt/workbuddy2api`    —— 历史默认值，兼容「只部署 manager、
                                    上游在别处」的既有部署与旧文档。

    三者都不存在时返回第 3 项而不是抛错：让后续的「文件不存在」错误指向一个
    用户能认出来的路径，比抛一个「推导失败」更容易定位。
    """
    for candidate in (PROJECT_ROOT / 'upstream', ROOT / 'upstream'):
        if candidate.is_dir():
            return candidate
    return Path('/opt/workbuddy2api')


# 上游 workbuddy2api（Go）
WB2API_BASE = _env('WB2API_BASE', 'http://127.0.0.1:7863').rstrip('/')
WB2API_KEY = _env('WB2API_KEY', '')
WB2API_CONTAINER = _env('WB2API_CONTAINER', 'workbuddy2api')
WB2API_MODE = _env('WB2API_MODE', 'docker').lower()  # docker | native

# 上游数据文件（与 upstream/ 共享）
#
# 顺序很关键：先定 UPSTREAM_DIR，其余三项**由它派生**。反过来（先 UPSTREAM_CONFIG
# 再取 .parent）是原实现的写法，在合并结构下会指错——用户只改 WB_AUTH_DIR 一项时，
# 上游目录就跟着变了，而 native 启停脚本仍按 config 那份找，结果一半功能落在 A
# 目录、另一半落在 B 目录且不报错。现在全项目只有 UPSTREAM_DIR 一处口径。
UPSTREAM_DIR = Path(_env('WB_UPSTREAM_DIR', str(_default_upstream_dir())))
AUTH_DIR = Path(_env('WB_AUTH_DIR', str(UPSTREAM_DIR / 'auths')))
UPSTREAM_CONFIG = Path(_env('WB_UPSTREAM_CONFIG', str(UPSTREAM_DIR / 'config.json')))
WB2API_START_SCRIPT = Path(_env(
    'WB2API_START_SCRIPT', str(UPSTREAM_DIR / 'start-workbuddy2api.cmd'),
))
WB2API_STOP_SCRIPT = Path(_env(
    'WB2API_STOP_SCRIPT', str(UPSTREAM_DIR / 'stop-workbuddy2api.cmd'),
))
WB2API_LOG_FILE = Path(_env(
    'WB2API_LOG_FILE', str(UPSTREAM_DIR / 'data' / 'server.err.log'),
))

# 本管理端数据
DATA_DIR = Path(_env('WB_DATA_DIR', str(ROOT / 'data')))
DB_PATH = Path(_env('WB_DB', str(DATA_DIR / 'manager.db')))
USERS_FILE = Path(_env('WB_USERS_FILE', str(DATA_DIR / 'users.json')))
STATIC_DIR = Path(_env('WB_STATIC_DIR', str(ROOT / 'web' / 'out')))

# 网络
UPSTREAM_TIMEOUT = _env_int('WB_UPSTREAM_TIMEOUT', 120)
TENCENT_TIMEOUT = _env_int('WB_TENCENT_TIMEOUT', 15)
# 「全部签到」的并发上限：太低会拖到前端超时（几十个账号时），
# 太高又容易触发腾讯风控。5 是保守且够快的取值。
CHECKIN_CONCURRENCY = max(1, _env_int('WB_CHECKIN_CONCURRENCY', 5))
TRUST_PROXY = _env('WB_TRUST_PROXY', '1') == '1'
# 可信反向代理跳数：用于从 X-Forwarded-For 右侧取真实客户端 IP。
# 前面直接是 1Panel/OpenResty 时保持 1；若还挂了 CDN 则设为 CDN+反代的层数。
TRUSTED_PROXY_HOPS = _env_int('WB_TRUSTED_PROXY_HOPS', 1)
# 可信代理的**来源网段**（逗号分隔，支持 CIDR）。
#
# 为什么需要它：仅凭「配置里开了 TRUST_PROXY」就无条件采信 X-Real-IP 是错的——
# 服务直接暴露（systemd 默认 0.0.0.0）时，X-Real-IP 只是普通客户端头，
# 任何人加一个 `X-Real-IP: 9.9.9.9` 就能冒充任意来源 IP，从而绕过
# 全局 IP 白/黑名单、密钥 IP 白名单与 max_ips、以及登录失败按 IP 锁定。
# 现在只在**TCP 对端确实来自这些网段**时才采信转发头，否则一律用对端地址。
#
# 默认含回环 + 常见私网：标准部署（反代与本体同机）开箱即用；
# 若反代在另一台机器，把它所在的网段加进来即可。
TRUSTED_PROXY_CIDRS = [
    c.strip() for c in _env(
        'WB_TRUSTED_PROXY_CIDRS',
        '127.0.0.0/8,::1/128,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,fc00::/7',
    ).split(',') if c.strip()
]
# 是否暴露 /docs、/openapi.json、/redoc。生产环境建议关闭（默认关闭）。
ENABLE_DOCS = _env('WB_ENABLE_DOCS', '0') == '1'
# 入站访问日志（安全页的「IP 访问日志」）是否记录**放行**的请求。
#
# 默认关闭：那张表的用途是安全审计（谁在扫我、谁被挡了），记全量会把信号淹没。
# 实测线上 7877 行里只有 17 行是拦截记录（0.2%），而表有 2 万行滚动上限，
# 被正常流量占满后保留窗口从数月压到约 17 天——真出事时记录可能已被挤掉。
# 放行的明细在「请求日志」页有完整记录，这里不重复记不丢信息。
#
# 需要核对「某个 IP 到底来过什么」时临时设 1 恢复全量记录。
AUDIT_ALL_ACCESS = _env('WB_AUDIT_ALL_ACCESS', '0') == '1'
# 显式出口代理（可选，如 http://127.0.0.1:7890）。
# 留空时所有请求都不使用任何代理：httpx 默认 trust_env=True 会读取系统/环境代理，
# 会把内网请求（如 127.0.0.1:7863）也交给系统代理，导致连接被劫持或长时间超时。
HTTP_PROXY = _env('WB_HTTP_PROXY', '')
# 会话**总时长**上限（天）：登录后最多维持这么久，到点必须重新登录。
#
# 下限钳到 1 天：0（或负数）会让 cookie 的 exp 等于签发时刻，即「登录成功但
# 立刻过期」——用户被锁在门外，而报错只会说「未登录」，看不出是配置写错了。
# 想「几乎不过期」就把值调大（如 30），而不是写 0。
SESSION_DAYS = max(1, _env_int('WB_SESSION_DAYS', 1))
# 会话**空闲**上限（小时）：距上次活动超过它就失效（滑动续期的窗口）。
# **0 = 关闭空闲判定**，只按总时长失效（`security.idle_expired` 显式处理）。
#
# 为什么要有这个、而不只是把总时长调短：只减总时长会惩罚**天天用**的人
# （每天都要重登一次），却对「登录一次就再也不碰」的会话没有额外约束。
# 滑动续期把两件事分开——常用的人不断续、不被打扰；放着不用的会话自己过期。
SESSION_IDLE_HOURS = _env_int('WB_SESSION_IDLE_HOURS', 12)
COOKIE_NAME = 'wb_session'
SECURE_COOKIE = _env('WB_SECURE_COOKIE', 'auto')  # auto | true | false

# 允许的 CORS 来源（同源部署时留空即可）
CORS_ORIGINS = [o for o in _env('WB_CORS_ORIGINS', '').split(',') if o]

TENCENT_BASE = 'https://copilot.tencent.com'
TENCENT_BILLING_BASE = 'https://www.codebuddy.cn'  # 国内版 billing 基址
TENCENT_CHECKIN = 'https://www.codebuddy.cn/v2/billing/meter/daily-checkin'
# 积分余额查询（与上游 BillingBaseCN 一致）
TENCENT_BILLING = 'https://www.codebuddy.cn/v2/billing/meter/get-user-resource'
# 国内版通用请求头。国际版用 realm.headers('global') 取（Origin/UA 都不同）——
# 这里的常量保留为 CN 默认值，供既有调用点与不区分版本处使用。
#
# 当前所有腾讯出站都走 realm.headers()（含风控头 X-CodeBuddy-Request /
# Accept-Language，见 realm.py 注释），本常量暂无调用点。保留但它也必须与
# 那边口径一致：否则将来有人照着这里取值，就会发出「形态不像官方客户端」
# 的请求（Accept 的宽松值与 D6 收紧后的口径相矛盾）。
TENCENT_HEADERS = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'Accept-Language': 'zh-CN',
    'X-Requested-With': 'XMLHttpRequest',
    'X-CodeBuddy-Request': '1',
    'User-Agent': 'CLI/2.63.2 CodeBuddy/2.63.2',
    'Origin': 'https://www.codebuddy.cn',
    'Referer': 'https://www.codebuddy.cn/',
}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)


def upstream_api_key() -> str:
    """优先环境变量，其次读取 workbuddy2api 的 config.json。"""
    if WB2API_KEY:
        return WB2API_KEY
    try:
        cfg = json.loads(UPSTREAM_CONFIG.read_text(encoding='utf-8'))
        return str(cfg.get('api_key') or '')
    except Exception:
        return ''


def new_secret() -> str:
    return secrets.token_urlsafe(48)


def http_client(timeout, *, connect: float | None = None):
    """统一的 httpx 客户端：默认忽略系统/环境代理，避免内网请求被代理劫持。

    需要走代理时显式设置 WB_HTTP_PROXY。

    timeout 可以传数字，也可以传已构造好的 httpx.Timeout。
    注意：httpx 不允许「Timeout 实例 + connect 关键字」同时传，
    因此传入实例时忽略 connect，避免 AssertionError。
    """
    import httpx

    if isinstance(timeout, httpx.Timeout):
        tmo = timeout
    elif connect is not None:
        tmo = httpx.Timeout(timeout, connect=connect)
    else:
        tmo = httpx.Timeout(timeout)
    kwargs = {'timeout': tmo, 'trust_env': False}
    if HTTP_PROXY:
        kwargs['proxy'] = HTTP_PROXY
    return httpx.AsyncClient(**kwargs)
