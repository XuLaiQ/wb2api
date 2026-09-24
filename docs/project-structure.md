# 项目目录与文件约定

仓库由 Next.js 前端、FastAPI 管理服务和 Go 网关组成。源码按组件边界放置；根目录仅保留跨组件集成、部署入口和仓库级配置。Docker 部署仍组装为一个应用，源码分层不代表要拆成多个部署项目。

## 目录职责

| 路径 | 职责 | 放置规则 |
| --- | --- | --- |
| `web/` | Next.js 前端 | 路由页面放 `app/`，可复用 UI 放 `components/`，浏览器端逻辑放 `lib/`、`hooks/`。依赖和构建缓存不提交。 |
| `server/` | FastAPI 管理后端 | HTTP 端点放 `routers/`，业务用例与集成放 `services/`，Python 测试放 `tests/`。 |
| `gateway/` | 独立 Go module | Go 模块文件放本目录；命令入口放 `cmd/<name>/`，内部实现放 `internal/<package>/`。Go 代码内引用保持 module-relative。 |
| `scripts/` | 应用运行或运维流程实际调用的脚本 | 仅放运行时需要的脚本；一次性校验、截图和调试脚本放 `dev/`。 |
| `deploy/` | 安装、升级和平台部署资源 | 保持部署入口与平台专用配置集中；部署脚本不得依赖开发机私有路径。 |
| `dev/` | 开发者工具、诊断与回归辅助 | 不作为运行时依赖，也不打入生产镜像。新增脚本应有明确用途，优先复用测试框架，避免为一次性操作长期堆积。 |
| `docs/` | 当前仍有效的接口、开发、发布和安全文档 | 只保留被当前代码、流程或用户文档引用的专题资料；过期的拆分项目前端截图、配置及旧部署模板不留在这里。 |

## 根目录约定

根目录只放跨组件文件，例如 `Dockerfile`、`docker-compose.yml`、`.env.example`、`config.example.json`、README、许可证和部署入口。组件专属源码不要放在根目录；新增文件前先确认它属于哪个组件及其调用方。

`gateway/` 是 Go module 根目录。从仓库根目录构建/测试可使用 `go -C gateway build ./...`、`go -C gateway test ./...`；Go 包导入仍沿用 `workbuddy2api/...` module 路径。跨组件脚本应显式指定该模块目录，不要依赖调用者当前工作目录。

## 运行数据、凭据与生成物

- `data/auths/`、`data/`、根目录 `.env` 和 `config.json` 是本地凭据或运行数据；不提交、不放进源码文档附件，备份应限制访问并加密。
- `web/node_modules/`、`web/.next/`、`web/tsconfig.tsbuildinfo`、`web/out/`、Python `__pycache__/` 和本地虚拟环境均为可再生成或机器相关内容，不应当作源码维护。
- 不确定文件是否可删时，先检查 Dockerfile、Compose、CI 工作流、发布包清单及代码调用方；有运行依赖的文件应补充测试或打包检查后再清理。
