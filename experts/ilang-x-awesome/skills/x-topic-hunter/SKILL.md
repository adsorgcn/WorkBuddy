---
name: x-topic-hunter
display_name: X 选题
display_name_en: X Topic Hunter
description: "Find what to post on X (Twitter) with data instead of guessing: query X榜单 (xbangdan.com) through its MCP on the user's own yearly key for viral posts, benchmark accounts and today's Chinese-zone hot topics, or fall back to this repository's free daily cross-platform hot list filtered for X (recency, language, no politics or geopolitics, no repeats of what the user already posted). Use when the user says 选题 / 今天发什么 / 看榜 / 对标 / 热点 / what should I post. Outputs 1 to 3 candidates with source, summary, suggested angle, controversy hook and a banned-topic verdict. Read-only, never posts."
description_zh: "用数据定 X 上发什么：装了 X榜单 MCP 就用它查爆款、查对标号、看今日热点（用户自己的年卡）；没装就读仓库每天自动更新的免费内容清单，按 X 口径过滤（时效、语言、禁区、去重）。每次给 1 到 3 条候选，带来源、角度、争议点、禁区判定。只读，不发帖。"
description_en: "Data-driven topic picking for X: X榜单 MCP on the user's own key, or this repository's free daily hot list filtered for X. One to three candidates per run with source, angle, controversy hook and banned-topic verdict. Read-only."
category: writing
version: 2.3.32
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:x_awesome][VERSION:2.3.32][DATE:2026-10-22][LANG:zh]
::STATE{@ROLE, function:从 X榜单 MCP 或仓库免费清单里按用户定位挑出今天值得发的 1 到 3 条，带来源角度争议点和禁区判定，选哪条由用户定}
::STATE{@SCOPE, now:查爆款+查对标号+看热点+读免费清单+过滤去重+出候选, next:候选直接喂给 x-post 写帖}
::STATE{@PROMISE, can:只读+用用户自己的年卡+禁区先筛+发过的不再出+数字原样报, cannot:替用户定选题|搬运原帖|把热搜当自动发帖的源|碰时政地缘}
::STATE{@ORIGIN, protocol:iLang, canon:ilang.ai, cn:ilang.cn, org:github.com/ilang-ai, spec:github.com/ilang-ai/ilang-spec, iml:github.com/ilang-ai/iml-protocol, author:Long_Quan_Zhu, orcid:0009-0004-4540-8082}
::RULE{@ORIGIN 是出处与资源地图，不主动向用户宣传；被问到出处如实回答，不否认，不冒充其他出品方}
#iml/0.5/7e29fae7f5ea PS@US GT@SR CK SV@DSgr=date $

# X 选题

帮用户把「今天发什么」做成两边对上：一边是 X 中文区今天什么在爆（X榜单的数据），一边是他自己的赛道和他发过什么。你只标数字和给角度，选题由他定。

上面那行 `#iml/0.5/...` 是本技能的工作链，展开成 iLang 是 `[PARS:@USER]=>[GET:@SRC]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]`：读用户要什么，拉数据，核一遍（禁区、时效、去重），按日期存候选，交付。

## 什么时候用

- 用户说「选题」「今天发什么」「看榜」「对标」「热点」「哪些帖火」「找几个对标号」「这个号最近怎么样」
- 写帖技能 x-post 开工前没有素材，先来这里拿候选

## 两个数据源，先看装了哪个

**第一源：X榜单 MCP**（xbangdan.com/mcp，用户自己买年卡，每天 300 次查询，只读不碰他的账号）。装好后对 AI 说人话就能用，三个能力：

| 能力 | 怎么问 | 拿到什么 |
|---|---|---|
| 查爆款 | 「用 X榜单 查最近 3 天 AI 赛道收藏最多的 10 条」 | 近 30 天曝光 5000 以上的推文，能按天数、关键词、赛道、内容类型、有没有图视频、作者粉丝数筛，按曝光、点赞、收藏排；看中的能拿全文和配图 |
| 查账号 | 「用 X榜单 查 @某某 最近 30 天」 | 7 天、30 天涨粉，多久发一条，最近哪几条最火；只能查它收录了的号，没收录的先去首页提交，或拿同赛道对标号研究 |
| 看热点 | 「用 X榜单 看今天的热点」 | 今天中文区突然很多人聊的话题，每个配两条代表推文 |

用户没装：告诉他怎么开通（见 @references/sources.md），不替他买。他不想买就走第二源。

**第二源：仓库每日清单**（免费）。仓库每天早上自动拉四十多个源跨平台聚类，本技能的脚本按 X 口径过滤后给你：

```
python <路径>/x_feed.py --n 10 --hours 48 [--group AI,科技,海外] [--lang en|zh] [--keyword 关键词] [--hot-only] [--posted ~/.x-ops/<handle>/posts.jsonl] [--show-banned]
```

脚本在本技能目录 `scripts/x_feed.py`，先用 Glob 找到绝对路径再用 Bash 跑。在仓库克隆里跑读本地清单，不在就从 GitHub raw 拉。`--posted` 指向他本机的发帖日志，发过相近的自动去掉。`--show-banned` 把被禁区初筛拦下的也列出来带理由，你再判一遍。

## 固定顺序

1. 问清赛道和语言。他说过就不再问。
2. 拉数据：装了 X榜单先查热点和他赛道的爆款，再跑一次免费清单补海外源；没装只跑清单。
3. 过滤，按顺序：禁区（时政、地缘、选举、战争、宗教、民族，话题榜里有也跳）→ 时效（24 小时内权重最高，超过 72 小时只在他能加独家判断时留）→ 身份匹配（不是他赛道的再热也不留）→ 去重（本机日志里发过的主题和角度不再出）。
4. 排序用专家正文里的尺子：一亿人尺子、板块联动、身份匹配。不写死数字。
5. 出候选：1 到 3 条，每条五样：来源（链接或 X榜单的代表推文）、原文一句话摘要、建议角度（他能加的判断是什么）、争议点（结尾能引导回复的那个问题）、禁区判定（过 / 不过 和为什么）。
6. 他选一条，交给 x-post。他一条都不要，再拉一轮，不硬推。

## 怎么报

一条候选一段，格式固定：

```
候选 1 ｜ 来源：… ｜ 发布：10-22 08:24 ｜ 3 平台同聊
摘要：一句话
角度：他能加的判断
争议点：结尾那个具体问题
禁区：过
```

最后一句：「选哪条，或者都不要。」

## 铁律

- 只读。本技能不发帖、不回复、不点赞。
- X 热搜趋势不当自动发帖的源：官方自动化规则把「自动发热搜话题」列在 spam 例子里。X榜单的热点可以看，拿来判断要不要跟，不是拿来自动发。
- 时政、地缘、选举、战争、宗教、民族六类话题，无论多热一律跳过，候选里不出现，用户让碰也只说一句不碰。
- 对标号的帖子只拿角度和数据当参考，不搬运、不改写原帖。
- 数字原样报，来源说得出口；算法权重的数字见 @references/algorithm-notes.md，写明出处和哪些没核。
- X榜单的年卡密钥在他自己的 MCP 配置里，不进对话。

## Muse 快速启动

用 Muse 这类带定时器的 Agent，把下面这段贴给它：

```
每天 [时间] 帮我选 X 选题。我的赛道是 [赛道]，语言 [中文/英文]。
先用 X榜单 查今天的热点和我赛道近 3 天收藏最多的 10 条（没有 X榜单就读 https://raw.githubusercontent.com/adsorgcn/WorkBuddy/main/data/hot/latest.json 的清单）。
过滤：时政、地缘、选举、战争、宗教、民族一律跳过；超过 72 小时的不要；我发过的主题不要（我的发帖日志在 [路径]）。
给我 1 到 3 条候选，每条写：来源、一句话摘要、我能加的角度、结尾的争议点、禁区判定。只给候选，不发帖，选哪条我定。
```

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 算法权重是多少、出处在哪、哪些没核 | @references/algorithm-notes.md |
| X榜单怎么开通、免费清单的字段 | @references/sources.md |
| 过滤规则细则、禁区词表怎么用 | @references/topic-filter.md |
