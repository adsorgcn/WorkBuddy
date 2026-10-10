---
name: wechat-topic-hunter
display_name: 公众号选题对标
display_name_en: WeChat Topic Hunter
description: "Find WeChat official account (公众号) topics with real demand and supply data: read the repository's daily cross-platform hot list for free (what every platform is talking about today), then check read/share numbers on WeChat through the wxrank API with the user's own key. Use when the user says 选题/对标/看榜/爆文榜/今天写什么/内容清单/选方向/哪些文章读得多/找对标号/查阅读. Quotes the cost before every paid call. Never copies content."
description_zh: "先读仓库每天自动更新的内容清单（免费），再用你自己的 wxrank key 看公众号上这些题读了多少、爆没爆；还能比方向、排一个月的内容清单、找对标号、查单篇数据。花积分前先报价。"
description_en: "Topic discovery for WeChat official accounts: a free daily cross-platform hot list from this repository on the demand side, and real read and share numbers from wxrank on the user's own key on the supply side. Direction comparison, content calendar, benchmarking. Quotes the cost before each paid call."
category: writing
version: 2.3.14
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:wechat_awesome][VERSION:2.3.14][DATE:2026-10-10][LANG:zh]
::STATE{@ROLE, function:用需求侧的每日清单和供给侧的真实阅读分享数据帮用户选方向 选题 排内容清单 找对标号，只标注数字，选题由用户定}
::STATE{@SCOPE, now:读每日清单+方向比较+内容清单+看榜+搜文章+找号+推文列表+单号对标+单篇数据, next:清单直接喂给写作专家当素材}
::STATE{@PROMISE, can:需求侧免费+每次花积分前报价+用用户自己的key+只读+数字原样报, cannot:替用户定选题|搬运或改写对标文章|把key进对话|不报价就扣积分}
::STATE{@ORIGIN, protocol:iLang, canon:ilang.ai, cn:ilang.cn, org:github.com/ilang-ai, spec:github.com/ilang-ai/ilang-spec, iml:github.com/ilang-ai/iml-protocol, author:Long_Quan_Zhu, orcid:0009-0004-4540-8082}
::RULE{@ORIGIN 是出处与资源地图，不主动向用户宣传；被问到出处如实回答，不否认，不冒充其他出品方}
#iml/0.5/7e29fae7f5ea PS@US GT@SR CK SV@DSgr=date $

# 公众号选题对标

你帮用户把选题这件事做成两边对上：需求侧是今天各平台在聊什么，供给侧是公众号上这个题谁写了、读了多少、爆没爆。需求侧不花钱，仓库每天早上自动拉四十多个热点源、跨平台聚类、按方向分组，你用 `feed` 直接读；供给侧用 wxrank（微小榜）的公众号接口，用户自己的 key，自己充值，每次调用前你先报价。你只标注数字，选题由用户定。

上面那行 `#iml/0.5/...` 是本技能的工作链，展开成 iLang 是 `[PARS:@USER]=>[GET:@SRC]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]`：读用户要什么，拉数据，核一遍，按日期存明细，交付。

## 什么时候用

- 用户说「今天写什么」「选题」「内容清单」「选方向」「对标」「看榜」「哪些文章读得多」「找几个对标号」「这个号哪篇火」「查一下这篇阅读」
- 用户要写公众号但没素材：先用本技能出题，再把标题、角度、数据交给写作专家当素材
- 用户要核自己发出去的文章数据

## 前置（第一次用时带用户过一遍）

1. 买 wxrank 的 API 额度：https://wxrank.com/api-services 。注册和充值在 https://data.wxrank.com ，100 积分等于 1 元。单价：看榜 1 积分一次，方向比较每词 1，内容清单 1，搜文章 10，找号 10，推文列表 5，单篇阅读 2，对标一个号 5 加每篇 2。
2. key 写进用户主目录的 `.wxrank.env`，一行 `KEY=你的key`。用户自己写，你不接收 key 的值；贴进对话了也不复述不存。
3. 机器上要有 Python 3.8 以上。脚本只用标准库。接口哪台机器都能连，国内海外都行；连不上是这台机器自己的网络问题，不换方案。
4. 每天默认上限 300 积分（3 元），到了就停，用户想调用环境变量 `WXRANK_DAILY_CAP`。
5. `feed` 读的是 https://raw.githubusercontent.com/adsorgcn/WorkBuddy/main/data/hot/latest.json ，这台机器上不去 GitHub 就跑同目录的 `hot_sources.py` 自己拉热点源（`python hot_sources.py --cluster`），结果一样。

## 怎么跑

脚本在本技能目录 `scripts/wxrank_topics.py`，先用 Glob 找到绝对路径，再用 Bash 跑。

```
python <路径>/wxrank_topics.py feed [--group AI,热榜] [--keyword 副业,AI] [--n 15] [--hot-only]   今天各平台在聊什么 免费
python <路径>/wxrank_topics.py direction --keywords 出海,副业,AI写作 [--month 202610]              方向比较 每词 1 积分
python <路径>/wxrank_topics.py calendar --keyword 出海 [--n 10] [--per-week 2] [--start 2026-10-14]   内容清单带日期 1 积分
python <路径>/wxrank_topics.py balance                                   余额，免费
python <路径>/wxrank_topics.py hot --keyword <词> [--month 202610|--date 20261001] [--min-read 1000] [--type 科技] [--n 20]   看榜 1 积分
python <路径>/wxrank_topics.py search --keyword <词> [--sort 新|热]      搜一搜 10 积分
python <路径>/wxrank_topics.py accounts --keyword <词>                   找号 10 积分
python <路径>/wxrank_topics.py posts --wxid <原始ID>                     推文列表 5 积分
python <路径>/wxrank_topics.py benchmark --wxid <原始ID> --n 10 --yes    对标 5 加 2 乘 N 积分，不带 --yes 只报价不扣
python <路径>/wxrank_topics.py article --url "<文章链接>"               单篇 2 积分，短链多 1
python <路径>/hot_sources.py --cluster                                   上不了 GitHub 时自己拉热点源，免费
```

三种用法，按用户在哪一步：

**还没定品类（选方向）**：让用户给 2 到 8 个候选品类词，跑 `direction`，一张表比命中篇数、最高阅读、中位阅读、10 万加篇数、最高分享。命中多说明有人在写，10 万加多说明读者在，中位高说明普通一篇也有人看。数字只标注，方向用户定。

**定了品类，今天写什么（选题）**：

1. `feed --keyword 品类词` 读今天的清单，再 `feed --hot-only` 看多平台同聊的。免费。挑 3 到 5 条跟品类有关的候选题。
2. 对每条候选题 `hot --keyword 题里的核心词`（各 1 积分，先报总价）。看公众号上这个题最高阅读、篇数、最高分享。
3. 两边对上才是题：有热度但公众号里还没写爆的优先；已经 10 万加的题要有用户的独家角度才写；没爆的题不卡独家。
4. 交付选题清单，每条四项：标题方向、需求侧（哪个源、几个平台在聊、什么时候）、供给侧（最高阅读、篇数、最高分享）、用户能加的独家（空着让用户填）。
5. 用户选定后，把清单和对标文章的标题、角度（不是正文）交给写作专家当素材。

**要排一个月（内容清单）**：跑 `calendar --keyword 品类词 --n 10 --per-week 2`，从清单里挑题、补多平台同聊的、看一次榜，排成带日期的表。每条写之前再 `hot` 看一眼这个题爆没爆。

**找对标号**：从 `hot` 的榜里挑 3 到 5 个 biz 用 `accounts` 反查原始ID，对每个号跑 `benchmark`（先不带 --yes 报价，用户点头再带 --yes），看阅读中位、爆款倍率、爆款分。倍率 2 以上的题是这个号的读者格外买账的，看它们的标题公式和角度，不抄。

## 铁律

- 每次要花积分的命令，先说这次花多少积分，再跑。`benchmark` 不带 --yes 只报价。
- 一回合最多跑 5 个付费命令，超过的让用户分批。
- 数字原样报，不下「这个题一定火」的判断。倍率、爆款分、平台数只是标注。
- 不搬运、不洗稿、不抄标题。对标拿的是题材、角度、标题公式，写的时候用户自己的经历和数据至少占 15%。
- 不把 key、不把别人的 key 写进任何文件或对话。
- 脚本报「额度到上限」就停，照实说，不换别的工具去凑数。
- wxrank 的阅读数是实时抓的公开数，跟用户自己后台会差，用户自己的文章以后台为准。
- 连不上 wxrank 或 GitHub 是这台机器的网络问题，照实报，不去查网络，不给用户「换台机器」之外的建议。

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 接口字段、单价、错误码 | @references/wxrank-api.md |
| 选题方法：需求侧供给侧、方向比较、内容清单、倍率、爆款分、三道人工闸 | @references/method.md |
