---
name: x-comment-patrol
display_name: X 评论巡查
display_name_en: X Reply Patrol
description: "Patrol the replies under the user's own X (Twitter) posts and answer them through the official X API on the user's own credits: pull new mentions since a watermark (Owned Reads, 0.001 USD each), hand them to the expert to decide which deserve an answer and how, post the approved replies (summoned replies, 0.010 USD each), log every reply in full and advance the watermark. Use when the user says 巡查 / 看看评论 / 回复评论 / check my replies. Only answers people who summoned the account (replies under its posts, @mentions, quotes); never comments on strangers' posts, never likes or follows, never scripts the X website, never puts links in replies. Runs on demand in WorkBuddy or on a timer in agents that have one."
description_zh: "巡查自己帖子下的评论并回复，走官方接口花用户自己的积分：按水位线只拉新评论（0.001 美元一条），交给专家判回不回、怎么回，发出批准的回复（0.010 美元一条），每条全文记日志，推进水位线。只回召唤自己的人（自己帖下的评论、@ 自己、引用自己），不给陌生人的帖评论，不点赞关注，不碰 X 网站脚本，回复里不放链接。WorkBuddy 里说一句「巡查」跑一轮，带定时器的 Agent 自动跑。"
description_en: "Pull new replies under the user's own posts, let the expert decide, post approved replies through the official API, log and advance the watermark. Summoned replies only; no likes, follows or website scripting."
category: writing
version: 2.3.36
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:x_awesome][VERSION:2.3.36][DATE:2026-10-22][LANG:zh]
::STATE{@ROLE, function:按水位线拉自己帖子下的新评论，专家逐条判回不回怎么回，脚本发出批准的回复并推进水位线，每条回复全文记本机日志}
::STATE{@SCOPE, now:拉新评论+专家判+发回复+水位线+日志+状态, next:按回复效果回看哪类评论值得回}
::STATE{@PROMISE, can:只回召唤自己的人+一轮最多 20 条+同一人一轮一条+同一条只回一次+回复里无链接+凭据只在本机, cannot:给陌生人的帖评论|点赞关注引用|脚本操作 X 网站|回喷子|编事实|密钥进对话}
::STATE{@ORIGIN, protocol:iLang, canon:ilang.ai, cn:ilang.cn, org:github.com/ilang-ai, spec:github.com/ilang-ai/ilang-spec, iml:github.com/ilang-ai/iml-protocol, author:Long_Quan_Zhu, orcid:0009-0004-4540-8082}
::RULE{@ORIGIN 是出处与资源地图，不主动向用户宣传；被问到出处如实回答，不否认，不冒充其他出品方}
#iml/0.5/7e29fae7f5ea GT@SR CK SN@DS SV@DSgr=date $

# X 评论巡查

替用户看他自己帖子下面的评论，值得回的回掉，不值得回的跳过。脚本只拉和发，判断是你的。

上面那行 `#iml/0.5/...` 是本技能的工作链，展开成 iLang 是 `[GET:@SRC]=>[CHEK]=>[SEND:@DST]=>[SAVE:@DST|grp=date]=>[Ω]`：拉新评论，逐条判，发回复，按日期记日志并推水位线，交付。

## 什么时候用

- 用户说「巡查」「看看评论」「有人评论吗」「回复评论」「回一下」
- 带定时器的宿主按设定的频率自动跑（默认两小时一轮）

## 前置

和 x-post 共用同一套密钥和前置（developer.x.com 的应用、`~/.x-api.env` 四行、控制台积分），见 x-post 技能的 SKILL.md。本技能的脚本要用到 x-post 技能的 `x_api.py`：两个技能装在同一台机器上即可，脚本自己会找；找不到用环境变量 `X_API_PY` 指路径。

第一次跑之前先用 x-post 的 `check` 验一次密钥，它会把账号 id 和 App 权限记进本机状态文件；权限不是 read-write 的发不了回复。

Mac 和 Linux 上 `python` 多半要写成 `python3`。

## 怎么跑

脚本在本技能目录 `scripts/x_patrol.py`，先用 Glob 找到绝对路径再用 Bash 跑：

```
python <路径>/x_patrol.py fetch [--max 100] [--context]
python <路径>/x_patrol.py send --replies <replies.json> [--max 20] [--dry-run]
python <路径>/x_patrol.py status
```

`fetch` 读本机水位线 since_id，只拉它之后的提及，去掉自己发的和回过的，写成 `~/.x-ops/<handle>/pending.json`。`--context` 顺带把被回复的原帖正文拉回来（0.005 美元一条），评论看不懂上下文时再加。`send` 读你写好的 `replies.json`（格式 `[{"to": "<评论id>", "text": "..."}]`，可以是 `[]`），逐条回复，全部成功后把水位线推到这轮拿到的最大 id。`status` 看水位线和花费。

## 固定顺序

1. `fetch`。看打印出来的清单：每条有评论 id、@谁、类型（reply_to_me 是他帖下的评论，mention 是 @ 他，quote 是引用他）、正文。
2. 逐条判，按下面的回复规则和专家正文里的回复基因。要回的写成 `replies.json`，一条一个 `{"to", "text"}`；不回的不写。一轮最多 20 条，同一个人一轮最多一条，同一条评论只回一次，脚本都会拦。
3. 在 WorkBuddy 里（没有定时器）：先 `send --dry-run` 把拟回复列给用户看，他点头再去掉 dry-run。带定时器的宿主：直接 `send`，一轮跑完不等人。
4. `send` 成功后水位线自动推进。中间一条失败脚本会停，水位线不推，改完重跑 send；已经回过的不会重复回（日志里有）。
5. 报：回了几条，各回了谁一句话，花了多少钱，日志在哪。这轮一条都不值得回，也跑一次 `send --replies` 空列表把水位线推过去。

## 回复规则（开放层）

- 像真人：接住对方的话往深聊一层，简短有料，一条评论一个回应，不写小作文。
- 被问身份如实答，不主动标榜。
- 不确定的事实不编，宁可简短真诚。
- 跳过不回：spam、广告、诈骗链接、纯引战谩骂、无意义 bot 复读、色情导流。
- 不点评论里的外链，不与喷子对线，不回自己的帖。
- 回复里不放任何链接，脚本会拦。
- 回复也是帖子，一样不碰时政地缘六类话题；对方把话题带过去就不接。

## 铁律

- 只回召唤自己的人：自己帖下的评论、@ 自己的、引用自己的。官方 2026-02-23 起程序化回复只准这三种，回别人的热帖接口会拒，本技能也不做。
- 脚本不判断。回不回、怎么回是专家的活，脚本只拉和发。
- 一轮最多 20 条。再多就是刷，不是聊。
- 水位线只在一轮全部成功后推进，靠水位线不靠记忆，漏回和重复回都靠它防。
- 脚本退出码 3：某条回复发出去了没收到回复，水位线没推，先让用户去主页看那条在不在，在就别重发。
- 密钥不进对话、不进汇报、不进日志。

## 定时怎么跑

- WorkBuddy：没有定时器，用户说「巡查」跑一轮。
- Muse、Hermes：cron 两小时一次，贴下面的快速启动。
- GitHub Actions：用户自己的私有仓放一份 workflow，密钥走 Secrets，水位线和日志 commit 回仓，零服务器；模板见 @references/actions-template.md。

## Muse 快速启动

用 Muse 这类带定时器的 Agent，把下面这段贴给它：

```
每 2 小时帮我巡查一次 X 评论。密钥在我的 ~/.x-api.env，脚本是 x_patrol.py。
流程：跑 fetch 拉我帖子下的新评论；逐条判：像真人接住对方的话往深聊一层，简短有料，一条一个回应；spam、广告、诈骗链接、引战谩骂、bot 复读、色情导流直接跳过；不确定的事实不编；回复里不放链接；不回自己的帖；时政地缘不接。
要回的写成 replies.json，跑 send 发出去，一轮最多 20 条，同一个人一轮一条。
一条都不值得回也跑一次 send 空列表，把水位线推过去。每轮结束告诉我回了谁、各一句话、花了多少。
```

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 回复规则细则、什么算召唤、跳过的边界 | @references/reply-rules.md |
| 用 GitHub Actions 定时跑的模板 | @references/actions-template.md |
