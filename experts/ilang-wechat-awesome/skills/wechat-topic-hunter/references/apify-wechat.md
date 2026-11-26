# Apify 这条数据路（脚本已内置，这里是给人看的对照表）

`scripts/apify_wechat.py` 调的是 Apify 上的一个采集器：`zen-studio/wechat-official-account-scraper`。用用户自己的 Apify 令牌，花的是用户自己 Apify 账号里的额度。下面的数字是 2026-11-25 核的，以 Apify 页面和账单为准。

## 前置

1. 没有 Apify 账号先注册：https://www.apify.com?fpr=tqio9f 。这是我们的推广链接。免费套餐每月有 5 美元额度。
2. 在 https://console.apify.com/settings/integrations 的 Personal API tokens 里建一个令牌。令牌只在建的那一刻显示一次。
3. 写进用户主目录的 `.apify.env`，一行 `TOKEN=你的令牌`。用户自己写，令牌不进对话。也认环境变量 `APIFY_TOKEN`。
4. 跑 `python apify_wechat.py me`，能看到账号名、套餐、本期已用和月上限，就通了。

## 脚本命令对采集器的哪个操作

| 脚本命令 | 采集器操作 | 拿到什么 | 单价（美元） |
|---|---|---|---|
| `viral` | viralArticles | 低粉爆文日榜：小号里阅读远超平时的文章，一页 50 条，带这个号近 90 天的阅读基线和倍率 | 每条 0.012 |
| `search` | articleSearch | 按词搜公众号文章：标题、发文号、时间、链接 | 每篇 0.006 |
| `metrics` | articleMetrics | 单篇的阅读、点赞、在看、分享、收藏、评论数 | 每篇 0.03 |
| `history` | accountHistoryArticles | 一个号的历史发文：标题、时间、链接、微信给的约数阅读 | 每篇 0.006 |
| `detail` | articleDetail | 正文、作者、是否原创、发文地区 | 每篇 0.03 |
| `comments` | articleComments | 精选留言：昵称、地区、内容、点赞数 | 每条 0.003 |
| `index` | wechatIndexSearch | 微信指数：一个词近 30 天每天的热度 | 每词 0.30 |
| `run --op` | 其余九个 | 原样跑，结果存文件 | 见下 |

每次运行另收一次启动费 0.05 美元。其余九个操作：accountSearch 搜号（每个 0.008）、searchSuggestions 联想词（每组 0.30）、miniProgramSearch 搜小程序（每个 0.015）、articleCommentReplies 留言的回复（每条 0.025）、convertArticleLink 短链还原（每条 0.025）、accountBasicInfo 公众号资料、accountPrincipalInfo 认证主体、accountOriginalCount 原创篇数（这三个每个号 0.03）、accountTodayArticles 今日发文。

套餐档位高的单价更低，这张表是免费档和最低付费档的数。

## 实测一次拿回多少（2026-11-25）

| 命令 | 拿回 | 花费 |
|---|---|---|
| `viral --pages 1` | 50 条 | 约 0.65 |
| `search --keyword 一个词 --pages 1` | 36 篇 | 约 0.27 |
| `history --account 一个号 --pages 1` | 10 篇 | 约 0.11 |
| `metrics --url 一篇` | 1 行 | 约 0.08 |
| `detail --url 一篇` | 1 行 | 约 0.08 |
| `comments --url 一篇` | 7 条 | 约 0.07 |
| `index --keyword 一个词` | 30 天 | 约 0.33 |

`--max-usd` 是这次运行的封顶，实测管用：`search` 封顶 0.10 时采集器拿到 8 篇就停了。默认封顶 1 美元，想一次多拿就调高。

## 几个要知道的口径

- 低粉爆文榜不能按词或分类去取，只能整页拿回来筛。脚本的 `--category`、`--keyword`、`--min-boost` 都是拿回来之后在本机筛的。一页 50 条里各分类都有，想要的分类少就加 `--pages`。
- 阅读显示 100001 的是 10 万加。
- `metrics` 里点赞取的是 `old_like_count`，在看取的是 `like_count`，这是微信接口的老叫法。
- 时间一律按北京时间显示，机器在哪个时区都一样。
- 数字是采集器当场从微信拿的公开数，跟公众号后台会差，用户自己的文章以后台为准。
- 一次运行只跑一个操作；一次最多带 50 个词、链接或账号；每个最多 50 页。

## 没数据时会看到什么

采集器跑完状态照样是成功，数据里只有一行通知，脚本会把它的原话打出来。没拿到数据的运行只扣启动费。

| 通知 | 意思 | 怎么办 |
|---|---|---|
| limitReached | 这个账号在这个采集器上的免费次数用完了 | 在 Apify 后台升级套餐后继续 |
| temporarilyUnavailable | 采集器对免费套餐的临时限制 | 过一会再试，或升级套餐 |
| entriesSkipped | 有条目被跳过，原因在 message 里 | 按 message 说的改输入 |

运行状态是 FAILED、说 temporarily unavailable 的，是采集器或微信那头临时出问题，过一会原样再跑一次。

## Apify 账号这头

照 Apify 自己的页面：免费套餐每月 5 美元额度；微信指数、联想词、小程序搜索这三个操作采集器只对付费套餐开放；最低的付费套餐是 Starter，19 美元一个月，含 19 美元额度。额度用到月上限就停，付费套餐可以在后台 Billing 的 Limits 里把上限调高。套餐和上限都在 https://console.apify.com/billing 。

## 想直接调接口的

三步，令牌放请求头 `Authorization: Bearer 你的令牌`：

1. `POST https://api.apify.com/v2/acts/zen-studio~wechat-official-account-scraper/runs?waitForFinish=60&maxTotalChargeUsd=1`，请求体是输入 JSON，比如 `{"operation":"viralArticles","rankingWindow":"7d","maxPages":1}`。
2. 没跑完就 `GET https://api.apify.com/v2/actor-runs/<运行号>?waitForFinish=60` 接着等，直到 status 是 SUCCEEDED。
3. `GET https://api.apify.com/v2/datasets/<defaultDatasetId>/items?clean=true&format=json` 取结果。

输入字段：`operation` 必填；`keywords` 给搜索类和指数；`articleUrls` 给文章类；`accounts` 给账号类，认原始 ID、微信号、号名、这个号任意一篇文章链接；`maxPages` 1 到 50；`sortBy` 取 relevance、latest、hot；`publishTime` 取 all、day、week、halfYear；`rankingDates` 和 `rankingWindow`（3d、7d、30d）只给低粉爆文榜。

采集器输入里有个 `feedback` 字段，是给它作者留言用的。脚本不填，直接调接口时也不用填。

## 脚本不做的

- 不搬运、不改写拿回来的正文。`detail` 只当素材看题材、角度、结构。
- 不存令牌，不把令牌写进输出。
- 不替用户升级套餐、不替用户调上限，这些在 Apify 后台由用户自己点。
