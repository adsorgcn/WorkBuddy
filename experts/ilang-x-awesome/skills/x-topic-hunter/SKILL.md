---
name: x-topic-hunter
display_name: X 选题
display_name_en: X Topic Hunter
description: "Find what to post on X (Twitter) with data instead of guessing: query X榜单 (xbangdan.com) through its MCP on the user's own yearly key for viral posts, benchmark accounts and today's Chinese-zone hot topics, or fall back to this repository's free daily cross-platform hot list filtered for X (recency, language, no politics or geopolitics, no repeats of what the user already posted). Use when the user says 选题 / 今天发什么 / 看榜 / 对标 / 热点 / what should I post. Outputs 1 to 3 candidates with source, summary, suggested angle, controversy hook and a banned-topic verdict. Read-only, never posts."
description_zh: "用数据定 X 上发什么：装了 X榜单 MCP 就用它查爆款、查对标号、看今日热点（用户自己的年卡）；没装就读仓库每天自动更新的免费内容清单，按 X 口径过滤（时效、语言、禁区、去重）。每次给 1 到 3 条候选，带来源、角度、争议点、禁区判定。只读，不发帖。"
description_en: "Data-driven topic picking for X: X榜单 MCP on the user's own key, or this repository's free daily hot list filtered for X. One to three candidates per run with source, angle, controversy hook and banned-topic verdict. Read-only."
category: writing
version: 2.3.43
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:x_awesome][VERSION:2.3.43][DATE:2026-10-22][LANG:zh]
::STATE{@ROLE, function:先看 X榜单 今天什么在热，再到中国大陆自媒体里找对标文，挑出 1 到 3 条候选交给 x-post 改写，每条带对标文链接 可用的图和视频 角度 争议点 禁区判定，选哪条由用户定}
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
- 写帖技能 x-post 开工前没有素材，先来这里拿候选和对标文

## 三个数据源，按这个顺序用

**第一源：X榜单 公开榜**（xbangdan.com，免费，不用账号不用 MCP）。页面是服务端渲染的，本技能的脚本直接解析：

```
python <路径>/x_rank.py --board all --n 10 [--show-banned] [--posted ~/.x-ops/<handle>/posts.jsonl]
python <路径>/x_rank.py --board posts|words|articles|global --n 20 [--zone cn|global] [--json]
```

| 榜 | 页面 | 拿到什么 |
|---|---|---|
| posts | /posts/ | 24 小时最火推文：每小时曝光、作者、赞数、发了几小时、链接 |
| words | /words/ | 话题榜：今天中文区在聊什么，每个话题的帖数、人数、首发时间、曝光、升温还是退烧 |
| articles | /articles/ | 长文榜：近 7 天收藏最多的长文，中文区或海外区，带分类、收藏数、曝光 |
| global | /global/ | 海外榜：海外热门推文，点赞、曝光、转发、收藏 |

对标账号直接打开 `https://xbangdan.com/account/<handle>/` 看，或让 Agent 自己打开任何一个榜单页读；脚本只是把页面读成表，Agent 自己开页面也一样。页面结构变了脚本会报，那就直接开页面。

**第二源：X榜单 MCP**（可选，xbangdan.com/mcp，用户自己买年卡，每天 300 次查询）。公开榜已经够选题；只有要按天数、赛道、内容类型、作者粉丝数在近 30 天的库里筛，或要拿爆款全文和配图，或查没上榜的账号时才值得买。装好后对 AI 说人话就能用：「用 X榜单 查最近 3 天 AI 赛道收藏最多的 10 条」「查 @某某 最近 30 天」「看今天的热点」。用户没装不劝他买。

**第三源：仓库每日清单**（免费，兜底）。仓库每天早上自动拉四十多个源跨平台聚类，脚本按 X 口径过滤后给你：

```
python <路径>/x_feed.py --n 10 --hours 48 [--group AI,科技,海外] [--lang en|zh] [--keyword 关键词] [--hot-only] [--posted ~/.x-ops/<handle>/posts.jsonl] [--show-banned]
```

两个脚本都在本技能目录 `scripts/` 下，先用 Glob 找到绝对路径再用 Bash 跑（Mac 和 Linux 上 `python` 多半要写成 `python3`）。`x_feed.py` 在仓库克隆里跑读本地清单，不在就从 GitHub raw 拉；打印的「通过 M 条，显示前 N 条」两个数口径不同：M 是整份清单过了禁区和时效的，N 是 `--n` 截断后给你看的。清单里的时间是北京时间，脚本按北京时间算时效，机器在哪个时区都一样。`--posted` 指向他本机的发帖日志，发过相近的自动去掉。`--show-banned` 把被禁区初筛拦下的也列出来带理由，你再判一遍。

## 固定顺序

这条链和公众号专家的「找对标」是同一个逻辑，只是方向反过来：公众号是看榜找公众号里的对标文；X 是先看 X榜单 今天什么在热，再回中国大陆的自媒体里找对标文，把它改成 X 上的帖子。大陆自媒体的东西 X 中文区大多没见过，这就是信息差。

1. 问清赛道和语言。他说过就不再问。
2. 看什么热：跑 `x_rank.py --board all`。话题榜看今天中文区在聊什么，最火推文看什么形态在爆（截图、长文、图），长文榜看他赛道谁的收藏多。装了 MCP 的可以再细筛。这一步只回答「今天该蹭哪个方向、用什么形态」。
3. 找对标文：拿第 2 步的方向回大陆自媒体里搜，找写得最透、数据最硬、图最好的那一篇。顺序：公众号（装了公众号选题技能 wechat-topic-hunter 的，用它的 `search` 按关键词搜文章并看阅读数；没装的用搜狗微信搜索 weixin.sogou.com 搜标题关键词）、知乎、B 站、头条、抖音和小红书（Agent 自己打开搜）、仓库清单里每条的 members 链接。对标文要存下来：标题、链接、正文要点、图片地址、视频地址。
4. 过滤：禁区（时政、地缘、选举、战争、宗教、民族，话题榜里有也跳）→ 时效 → 身份匹配（不是他赛道的再热也不留）→ 去重（本机日志里发过的主题和角度不再出）。
5. 出候选：1 到 3 条，每条六样：X 上热的方向（来自哪个榜）、对标文（标题和链接）、一句话摘要、可用的图和视频（地址）、建议角度（他能加的判断）、禁区判定。
6. 他选一条，连对标文一起交给 x-post 改写：文字按 X 的写法重切，图和视频直接拿。他一条都不要，再找一轮，不硬推。

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
- X 上别人的帖只拿角度和数据当参考，不原样复述。大陆自媒体的对标文可以拿来改：文字按 X 的写法重切，图和视频直接用。
- 数字原样报，来源说得出口；算法权重的数字见 @references/algorithm-notes.md，写明出处和哪些没核。
- 装了 MCP 的，年卡密钥在他自己的 MCP 配置里，不进对话。公开榜不需要任何密钥。

## Muse 快速启动

用 Muse 这类带定时器的 Agent，把下面这段贴给它：

```
每天 [时间] 帮我选 X 选题。我的赛道是 [赛道]，语言 [中文/英文]。
先跑 x_rank.py --board all 看 X榜单 的话题榜、最火推文和我赛道的长文榜（公开页，免费），再读 https://raw.githubusercontent.com/adsorgcn/WorkBuddy/main/data/hot/latest.json 的清单补海外源。
过滤：时政、地缘、选举、战争、宗教、民族一律跳过；超过 72 小时的不要；我发过的主题不要（我的发帖日志在 [路径]）。
给我 1 到 3 条候选，每条写：来源、一句话摘要、我能加的角度、结尾的争议点、禁区判定。只给候选，不发帖，选哪条我定。
```

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 算法权重是多少、出处在哪、哪些没核 | @references/algorithm-notes.md |
| 公开榜四个页面各有什么、MCP 什么时候才值得买、免费清单的字段 | @references/sources.md |
| 过滤规则细则、禁区词表怎么用 | @references/topic-filter.md |
