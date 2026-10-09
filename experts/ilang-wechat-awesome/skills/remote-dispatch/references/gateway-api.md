# CodeBuddy Code 网关怎么调（2026-10-09 实测）

远程机：`codebuddy --serve --host 0.0.0.0 --port 8080 --session-id <名字> --permission-mode bypassPermissions`。口令首次启动随机生成，写在远程机 `~/.codebuddy/settings.json` 的 gateway.password，想换就改这个字段再重启服务。绑定非回环地址时鉴权强制开，关不掉。

## 请求头三样，缺一个都不行

| 头 | 值 | 缺了会怎样 |
|---|---|---|
| X-CodeBuddy-Request | 1 | 403 Missing required header |
| Authorization | Bearer 口令 | 401 AUTH_REQUIRED |
| Host | localhost:端口 | 400 Invalid Host header（它只认 localhost、127.0.0.1 和 Cloudflare 隧道的公网地址，直连公网 IP 得改写 Host） |

正文 `Content-Type: application/json; charset=utf-8`，中文一定按 UTF-8 发，Windows 终端直接拼中文会乱码，脚本用文件发。

## 派活

`POST /api/v1/runs`

```
{"id":"调用方自己生成的唯一id","type":"message","version":"1.0",
 "source":{"platform":"generic","sender":{"id":"dispatch","name":"dispatch"},"conversation":{"id":"同id","type":"direct"}},
 "payload":{"text":"命令块全文"},
 "timeoutMs":900000}
```

回 `{"data":{"runId":"uuid","status":"accepted"}}`。

## 收结果

`GET /api/v1/runs/{runId}/stream`，SSE。只能在跑的时候挂，跑完再挂回 `RUN_NOT_FOUND`。事件：

```
event: message
data: {"version":"1.0","replyTo":"id","status":"completed","content":{"markdown":"…"},"agent":{"sessionId":"…","toolCalls":[]}}

event: done
data: {}
```

跑得太快没挂上：`GET /api/v1/sessions?limit=5` 找到 name 等于命令开头那句的会话，再 `GET /api/v1/sessions/{id}/history` 读。

`GET /api/v1/runs/{runId}` 只回 `{"data":{"runId":"…","active":true|false}}`，没有内容。

## 其他有用的路由

`/api/v1/health`（探活，也要口令）、`/api/v1/runs/{id}/cancel`、`/api/v1/sessions`、`/api/v1/sessions/{id}/history`、`/api/v1/scheduled-tasks`、`/api/v1/channels/wechat`（扫码绑微信，手机发消息派活）、`/api/v1/channels/wecom`、`/api/openapi.json`（全部路由）。

## 权限

网关默认 permission-mode 是 default，远程机跑 Bash 会停下等审批，派活就挂住。专机干活用 `--permission-mode bypassPermissions` 起（HIGH/CRITICAL 还会问）。审批由人在远程机那边点，派活脚本不代点。
