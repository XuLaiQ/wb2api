# 在 Sub2API 中配置 workbuddy2Api 的 Anthropic 上游

workbuddy2Api 的 API 密钥可作为 Sub2API 的 **Anthropic API Key 上游凭据**使用。服务已提供 Anthropic Messages 协议 `POST /v1/messages`，并支持 `x-api-key` 和 `Authorization: Bearer ...` 两种密钥头。

## Sub2API 上游配置

- **平台 / 协议：** Anthropic / API Key
- **Base URL：** `https://<workbuddy2Api 域名>`（如反向代理使用子路径，需保留子路径；不要在末尾加 `/v1`）
- **API Key：** 在 workbuddy2Api「API 密钥」页面创建的 `wbk_...` 密钥
- **Model：** 使用 workbuddy2Api `GET /v1/models` 返回、并且该密钥允许访问的模型 ID；国际版密钥可选 `global:...` 模型

Sub2API 提供给下游客户端的 API Key 与这里填入的 `wbk_...` 上游密钥是两种不同凭据，请分别保存在对应的字段中。

## Base URL 不要重复包含 `/v1`

workbuddy2Api 的页面会显示供 Anthropic SDK 等客户端使用的 Base URL（以 `/v1` 结尾）。**Sub2API 的上游 Base URL 字段用途不同**：Anthropic Messages 请求路径是 `/v1/messages`，因此这里填域名根地址（或代理子路径），不要再附加 `/v1`。否则代理若继续拼接 `/v1/messages`，可能请求到 `/v1/v1/messages` 等错误路径。

截图中的 `405 Method Not Allowed` 本身不能证明 API Key 错误。请先确认 Sub2API 配置指向正确的 `POST /v1/messages` 路径、Base URL 没有重复 `/v1`，并且模型 ID 存在于 workbuddy2Api 的 `/v1/models`。随后查看 workbuddy2Api 请求日志，确认请求是否到达网关。

## 用 curl 快速验证

```sh
curl -i https://<workbuddy2Api 域名>/v1/messages \
  -H 'content-type: application/json' \
  -H 'anthropic-version: 2023-06-01' \
  -H 'x-api-key: wbk_REPLACE_WITH_YOUR_KEY' \
  -d '{"model":"global:YOUR_ENABLED_MODEL","max_tokens":32,"messages":[{"role":"user","content":"Reply with ok"}]}'
```

请替换成 `/v1/models` 实际返回的模型 ID。不要把真实 API Key 提交到代码仓库。
