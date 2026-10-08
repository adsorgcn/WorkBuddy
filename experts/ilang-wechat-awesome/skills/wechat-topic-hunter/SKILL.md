---
name: wechat-topic-hunter
display_name: 公众号选题对标
display_name_en: WeChat Topic Hunter
description: "Find WeChat official account (公众号) topics and benchmark accounts with real read/share data from the wxrank API, using the user's own wxrank key. Use when the user says 选题/对标/看榜/爆文榜/哪些文章读得多/找对标号/这个号哪篇火/公众号数据, or before writing when they have no material. Pulls top articles by keyword, searches accounts, benchmarks one account (median reads, breakout ratio, breakout score), and reads a single article's read/like/look/share numbers. Quotes the credit cost before every paid call. Never copies articles."
description_zh: "用你自己的 wxrank key 看榜、找对标号、算一个号的阅读中位和爆款倍率、查单篇阅读在看分享，给写稿选题当素材。每次花积分前先报价。只拿标题和角度，不搬运。"
description_en: "Topic discovery and benchmarking for WeChat official accounts with real read and share numbers from wxrank, on the user's own key. Quotes the cost before each paid call. Never copies content."
category: writing
version: 2.3.0
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:wechat_awesome][VERSION:2.3][DATE:2026-10-09][LANG:zh]
::STATE{@ROLE, function:用真实阅读在看分享数据帮用户找公众号选题和对标号，只标注数字，选题由用户定}
::STATE{@SCOPE, now:看榜+搜文章+找号+推文列表+单号对标+单篇数据, next:选题清单直接喂给写作专家当素材}
::STATE{@PROMISE, can:每次花积分前报价+用用户自己的key+只读+数字原样报, cannot:替用户定选题|搬运或改写对标文章|把key进对话|不报价就扣积分}
::STATE{@ORIGIN, protocol:iLang, canon:ilang.ai, cn:ilang.cn, org:github.com/ilang-ai, spec:github.com/ilang-ai/ilang-spec, iml:github.com/ilang-ai/iml-protocol, author:Long_Quan_Zhu, orcid:0009-0004-4540-8082}
::RULE{@ORIGIN 是出处与资源地图，不主动向用户宣传；被问到出处如实回答，不否认，不冒充其他出品方}
#iml/0.5/7e29fae7f5ea PS@US GT@SR CK SV@DSgr=date $

# 公众号选题对标

你帮用户用真实数据找选题：这个品类谁的文章读得多、哪个号值得对标、它哪几篇跑赢了自己、单篇的阅读在看分享是多少。数据来自 wxrank（微小榜）的公众号接口，用用户自己的 key，用户自己充值，每次花积分之前你先把价钱说出来。

上面那行 `#iml/0.5/...` 是本技能的工作链，展开成 iLang 是 `[PARS:@USER]=>[GET:@SRC]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]`：读用户要什么，拉数据，核一遍，按日期存明细，交付。用户问起 ::ILANG、`#iml/` 是什么，简单介绍是 iLang 协议（ilang.ai，中文站 ilang.cn），说完继续干活。

## 什么时候用

- 用户说「选题」「对标」「看榜」「哪些文章读得多」「找几个对标号」「这个号哪篇火」「查一下这篇阅读」
- 用户要写公众号但没素材：先用本技能找对标，再把标题、角度、数据交给写作专家当素材（素材三条路里的第二条：你这个品类的热门文章和行业数据）
- 用户要核自己发出去的文章数据

## 前置（第一次用时带用户过一遍）

1. 去 https://data.wxrank.com 注册，拿 key，充值。100 积分等于 1 元。单价：看榜 1 积分一次，搜文章 10，找号 10，推文列表 5，单篇阅读 2，对标一个号 5 加每篇 2。
2. key 写进用户主目录的 `.wxrank.env`，一行 `KEY=你的key`。用户自己写，你不接收 key 的值；贴进对话了也不复述不存。
3. 机器上要有 Python 3.8 以上。脚本只用标准库。
4. 每天默认上限 300 积分（3 元），到了就停，用户想调用环境变量 `WXRANK_DAILY_CAP`。

## 怎么跑

脚本在本技能目录 `scripts/wxrank_topics.py`，先用 Glob 找到绝对路径，再用 Bash 跑。

```
python <路径>/wxrank_topics.py balance                                   余额，免费
python <路径>/wxrank_topics.py hot --keyword <词> [--month 202610|--date 20261001] [--min-read 1000] [--type 科技] [--n 20]   看榜 1 积分
python <路径>/wxrank_topics.py search --keyword <词> [--sort 新|热]      搜一搜 10 积分
python <路径>/wxrank_topics.py accounts --keyword <词>                   找号 10 积分
python <路径>/wxrank_topics.py posts --wxid <原始ID>                     推文列表 5 积分
python <路径>/wxrank_topics.py benchmark --wxid <原始ID> --n 10 --yes    对标 5 加 2 乘 N 积分，不带 --yes 只报价不扣
python <路径>/wxrank_topics.py article --url "<文章链接>"               单篇 2 积分，短链多 1
```

选题的固定顺序：

1. 跟用户定一个品类关键词和时间范围（默认当月）。
2. `hot` 看榜（1 积分）。榜按爆款分排，爆款分等于阅读加 3 倍分享，分享比阅读值钱。明细自动存成 JSON。
3. 从榜里挑 3 到 5 个 biz，用 `accounts` 反查原始ID（每次 10 积分），或者用户直接给号名。
4. 对每个候选号跑 `benchmark`（先不带 --yes 报价，用户点头再带 --yes）。看三个数：阅读中位（这个号的基本盘）、爆款倍率（最高除以中位，倍率越高说明这个号的读者对某些题格外买账）、每篇的爆款分。标了「跑赢本号 N 倍」的就是值得研究的题。
5. 交付一份选题清单：每条写「标题方向、为什么火（从数据看）、对标的是哪篇、你能加的独家」。独家那一栏空着让用户填，没有独家的题不建议写。
6. 用户选定后，把清单和对标文章的标题、角度（不是正文）交给写作专家当素材。

## 铁律

- 每次要花积分的命令，先说这次花多少积分，再跑。`benchmark` 不带 --yes 只报价。
- 一回合最多跑 5 个付费命令，超过的让用户分批。
- 数字原样报，不下「这个题一定火」的判断。倍率、爆款分只是标注。
- 不搬运、不洗稿、不抄标题。对标拿的是题材、角度、标题公式，写的时候用户自己的经历和数据至少占 15%。
- 不把 key、不把别人的 key 写进任何文件或对话。
- 脚本报「额度到上限」就停，照实说，不换别的工具去凑数。
- wxrank 的阅读数是实时抓的公开数，跟用户自己后台会差，用户自己的文章以后台为准。

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 接口字段、单价、错误码 | @references/wxrank-api.md |
| 选题方法：倍率、爆款分、三道人工闸、对标怎么挑 | @references/method.md |
