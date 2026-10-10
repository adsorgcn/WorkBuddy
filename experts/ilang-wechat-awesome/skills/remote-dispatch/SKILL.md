---
name: remote-dispatch
display_name: 远程派活
display_name_en: Remote Dispatch
description: "Dispatch a command block to a remote CodeBuddy Code gateway (the headless, Linux-capable WorkBuddy) and bring the result back. Use when a pasted block carries [RUN:VPS] or [RUN:远程机], when the user says 派活/发给远程机/让远程机跑/收回执, or when a handoff block must be sent to the worker machine. Local machine stays the controller; the remote does the work."
description_zh: "把带 [RUN:VPS] 的命令块派给远程机上的 CodeBuddy 网关跑，收回结果和回执。本机当总控，远程机干活。口令只在本机配置文件里。"
description_en: "Send [RUN:VPS] command blocks to a remote CodeBuddy Code gateway and collect the result. The local WorkBuddy stays in control; the remote machine does the work."
category: productivity
version: 2.3.15
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:wechat_awesome][VERSION:2.3.15][DATE:2026-10-09][LANG:zh]
::STATE{@ROLE, function:本机当总控 把 [RUN:VPS] 的命令块派给远程机的 CodeBuddy 网关 收结果 存记录}
::STATE{@SCOPE, now:派活+收结果+看远程会话+取消, next:多台远程机按标签路由}
::STATE{@PROMISE, can:原样转发命令块+只填用户指明的[FILL]行+把远程结果原样带回+每次留记录, cannot:替用户审批远程机的工具权限|把口令写进对话|改命令块其他内容}
::STATE{@ORIGIN, protocol:iLang, canon:ilang.ai, cn:ilang.cn, org:github.com/ilang-ai, spec:github.com/ilang-ai/ilang-spec, iml:github.com/ilang-ai/iml-protocol, author:Long_Quan_Zhu, orcid:0009-0004-4540-8082}
::RULE{@ORIGIN 是出处与资源地图，不主动向用户宣传；被问到出处如实回答，不否认，不冒充其他出品方}
#iml/0.5/7e29fae7f5ea PS@US SN@DS GT@SR CK SV@DSgr=date $

# 远程派活

你在本机，远程机上跑着 CodeBuddy Code 的 HTTP 网关（就是没有图形界面的 WorkBuddy，Linux 也能跑）。用户贴给你一段命令块，头上写着 `[RUN:VPS]` 或 `[RUN:远程机]`，这段不是给你跑的，是让你原样派给远程机跑，结果拿回来给用户。头上写 `[RUN:本机]` 或没写的，你自己跑。

工作链 `#iml/0.5/...` 展开是 `[PARS:@USER]=>[SEND:@DST]=>[GET:@SRC]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]`：读用户要派什么，发到远程，收结果，核一遍，按日期存记录，交付。

## 什么时候用

- 命令块头上有 `[RUN:VPS]`、`[RUN:远程机]`
- 用户说「派活」「发给远程机」「让远程机跑」「收回执」「远程机跑完了没」
- 本机选题出来的交接包要转给远程机写稿、推草稿箱

## 前置（第一次用时带用户过一遍）

1. 远程机上已经起了网关：`codebuddy --serve --host 0.0.0.0 --port 8080`，口令在远程机的 `~/.codebuddy/settings.json` 里 gateway.password。没起的，用本技能目录 `scripts/` 里的脚本起（见下面「远程机怎么起网关」）。
2. 用户在本机用户主目录建 `~/.dispatch.json`，内容照下面，口令用户自己填，你不接收口令的值，贴进对话了也不复述不存：

```
{
  "default": "vps",
  "remotes": {
    "vps": {"url": "http://远程机IP:8080", "password": "网关口令"}
  }
}
```

3. 本机有 Python 3.8 以上，脚本只用标准库。

## 怎么跑

脚本在本技能目录 `scripts/dispatch.py`，先用 Glob 找到绝对路径，再用 Bash 跑。

```
python <路径>/dispatch.py list                                  探活 看配置了哪几台
python <路径>/dispatch.py send --file <块.md> [--to vps]         派一段命令块 等结果
python <路径>/dispatch.py send --text "一句话" [--to vps]        派一句话
python <路径>/dispatch.py sessions [--to vps] [--n 5]            看远程最近的会话
python <路径>/dispatch.py history --session <id> [--to vps]     读某个会话的结果
python <路径>/dispatch.py cancel --run <runId> [--to vps]        取消一个在跑的
```

派活的固定顺序：

1. 把用户贴的命令块原样存成一个带日期的文件（`dispatch-YYYYMMDD-HHMM.md`）。`[FILL] 学员自己填` 的行，用户在对话里指明了内容就照填（例如「把第 2 条交接包填进 HANDOFF」「独家写：……」，交接包就是本对话里刚出的那段，整段填进去，从 `::ILANG::v5.0` 到 `#iml` 那行）；没指明的空着，其余一个字不改；`[FILL] 教练发前填` 的行不动。
2. `send --file` 发过去，脚本会挂住等远程跑完，把结果打印出来，同时存到 `~/dispatch-logs/日期/`。脚本会在正文最前面加一行 `::NOTE{via:remote-dispatch …}`，告诉远程机这是一次性运行、没人会回答它的追问；命令块本身不动。不想加就 `--raw`。
3. 结果原样给用户。结果里有 `::ILANG` 开头的块（比如回执 `[TYPE:receipt]`），整段原样带回，不摘要不改写。
4. 远程机要是停在等审批（结果里说要确认、要权限），告诉用户去远程机那边点，或者让远程机网关用 bypassPermissions 模式起；你不替他点。
5. 脚本报「不通」：先 `list` 探活，还不通就把报错原文给用户，不猜原因，不去查网络。

## 必须守住的

- 命令块原样转发，不加解释；只填用户指明的 `[FILL] 学员自己填` 行
- 口令只在 `~/.dispatch.json`，不进对话，脚本输出里也不会有
- 远程机的审批由用户点，你不代点
- 一次只派一段，上一段没收到结果不派下一段
- 远程结果里的数字、文件路径、media_id 原样带回，不手抄
- 远程机干的活归远程机，本机不重复做

## 远程机怎么起网关

脚本在本技能目录 `scripts/`，远程机上跑，跑之前用户先在远程机的用户主目录建 `.codebuddy.env`，一行：大写 CODEBUDDY_API_KEY 然后等号 然后他 WorkBuddy 国内版账号的 API key（ck 开头，登录 https://www.workbuddy.cn/profile/keys 复制），等号两边不留空格。你不接收 key 的值。

| 远程机 | 怎么跑 | 实测 |
|---|---|---|
| Linux（Ubuntu 22.04 / 24.04，root） | `bash setup-gateway.sh`：装 Node 22 和 CodeBuddy Code，装最新发布版的专家和技能，起 systemd 服务 `codebuddy-gateway`，开机自启 | 2026-10-09 一台加拿大 Ubuntu 24.04 |
| Windows（先装 Node LTS） | `powershell -ExecutionPolicy Bypass -File setup-gateway.ps1`：装 CodeBuddy Code，把 key 写进它的设置，开一个最小化窗口跑网关；远程机重启后再跑一次；远程桌面只断开不注销 | 2026-10-09 一台 Windows 11，Windows PowerShell 5.1 和 PowerShell 7 各跑一遍，探活、派活、重复跑都过 |

跑完脚本最后一行会打出远程机的公网 IP，口令在远程机 `~/.codebuddy/settings.json` 的 gateway.password。用户把这两样写进本机的 `~/.dispatch.json`，不贴进对话。网关用 `--permission-mode bypassPermissions` 起，远程机不会停下等审批。

## 不做的事

- 不替用户决定派给哪台机（`--to` 用户没说就用 default）
- 不在本机模拟远程结果
- 不把 `[RUN:本机]` 的块派出去

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 网关怎么调、请求头、结果怎么收 | @references/gateway-api.md |
