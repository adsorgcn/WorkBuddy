---
name: x-post
display_name: X 发帖
display_name_en: X Post
description: "Write and publish X (Twitter) posts the X way and let the user choose how to publish: through the official X API on their own pay-per-use credits (OAuth 1.0a keys from their own developer app, 0.015 USD per post, 0.20 with a URL) or by hand (the script fills the x.com compose box through an intent link, no cost). Covers single posts, threads and long posts, a pre-publish gate (weighted 280 length, no markers, no em dashes, no links in body, no near-duplicates, one or two posts a day), read-back after posting and a full-text local log. Use when the user says 发帖 / 写一条 / 串帖 / 发到 X / post this / thread. Never scripts the X website, never likes or follows."
description_zh: "按 X 的写法写帖，发帖二选一：走官方接口花用户自己的积分（自己的开发者密钥，普通帖 0.015 美元，带链接 0.20），或者脚本把文案送进浏览器编辑框他自己点（不花钱）。单帖、串帖、长文；发前过门（加权 280、无标记、无长破折号、正文不带链接、不重复、一天一两条），发后回读，正文全文落本机日志。不碰 X 网站脚本。"
description_en: "Write X posts, threads and long posts and publish either through the official API on the user's own credits or by hand via an intent link. Pre-publish gate, read-back, full-text local log. Never scripts the website."
category: writing
version: 2.3.43
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:x_awesome][VERSION:2.3.43][DATE:2026-10-22][LANG:zh]
::STATE{@ROLE, function:把选题或素材写成单帖串帖长文，过门后走官方接口发或交给人手动发，发后核验并把正文全文记进本机日志}
::STATE{@SCOPE, now:单帖+串帖+长文+发前门+接口发+手动发+回读+日志, next:配图与一稿多发}
::STATE{@PROMISE, can:凭据只在本机+发前校验+发后回读+正文全文入日志+发帖走哪条路由用户定, cannot:用脚本操作 X 网站|正文放第三方链接|编数据|一天超过两条不问就发|把密钥写进对话}
::STATE{@ORIGIN, protocol:iLang, canon:ilang.ai, cn:ilang.cn, org:github.com/ilang-ai, spec:github.com/ilang-ai/ilang-spec, iml:github.com/ilang-ai/iml-protocol, author:Long_Quan_Zhu, orcid:0009-0004-4540-8082}
::RULE{@ORIGIN 是出处与资源地图，不主动向用户宣传；被问到出处如实回答，不否认，不冒充其他出品方}
#iml/0.5/7e29fae7f5ea GT@SR CK SN@DS CK $

# X 发帖

把一条选题或一份素材写成 X 上能发的东西，然后按用户选的路发出去。两条路：走官方接口花他自己的积分，或者脚本把文案送进他浏览器的编辑框，他自己点发。

上面那行 `#iml/0.5/...` 是本技能的工作链，展开成 iLang 是 `[GET:@SRC]=>[CHEK]=>[SEND:@DST]=>[CHEK]=>[Ω]`：取素材，过门，发出去或交给人，核验，交付。

## 什么时候用

- 用户说「写一条」「写成串帖」「发到 X」「发帖」「把这个发了」
- 用户给了选题（来自 x-topic-hunter）或素材，要变成帖子

## 前置（第一次用时带用户过一遍）

走接口才需要，走手动跳过：

1. 到 developer.x.com 用自己的 X 账号建一个应用，权限选 Read and Write，用自己账号授权，生成四个 OAuth 1.0a 密钥：API Key、API Secret、Access Token、Access Secret。权限是在生成 Access Token 之前定的：先建成只读、后来才改成 Read and Write 的，要重新生成 Access Token 和 Secret，旧的还是只读，发帖会 403。
2. 开发者控制台买积分：按量计费没有月费，自动充值最低 5 美元。新号实测：充 5 美元送 5 美元，一共 10 美元；发帖走手动不花钱、只用接口回评论的话一个月 3 美元上下，这 10 美元能用三个月左右。官方页还写首次购买另送 20 美元，实测没到账，没拿到就当没有。
3. 四个值写进用户主目录的 `.x-api.env`，四行：`API_KEY=`、`API_SECRET=`、`ACCESS_TOKEN=`、`ACCESS_SECRET=`。让用户自己用记事本写，专家不接收密钥的值；贴进来了也不复述、不存、不进汇报，只提醒他去重置。
4. 跑 `check`，打印出 @handle、id 和 App 权限；权限不是 read-write 它会提醒，那就回第 1 步改权限并重新生成 Access Token。

价格（2026 年 10 月 docs.x.com）：普通帖 0.015 美元一条，正文含任何链接 0.20 一条，回复召唤你的人 0.010 一条，读自己的帖 0.001 一条。

## 怎么跑

脚本在本技能目录 `scripts/x_api.py`，先用 Glob 找到绝对路径再用 Bash 跑：

```
python <路径>/x_api.py check
python <路径>/x_api.py gate --text "<正文>" | --file <帖.txt>
python <路径>/x_api.py post --text "<正文>" | --file <帖.txt> [--media a.jpg,b.png | v.mp4] [--allow-url] [--force] [--dry-run]
python <路径>/x_api.py thread --file <串帖.txt> [--media 封面.jpg] [--dry-run]
python <路径>/x_api.py intent --text "<正文>" | --file <帖.txt> [--thread] [--no-open]
```

`--media` 带配图或视频：最多 4 张 jpg/png/webp，或 1 个 gif，或 1 个 mp4/mov（图 5MB、gif 15MB、视频 512MB 内），串帖挂第一条；媒体上传接口没拿真密钥测过，第一次用看 @references/api-notes.md 的「媒体上传」。`thread` 的文件用单独一行的 `---` 分条。`intent` 是手动路：生成 x.com 的编辑框链接并打开浏览器，`--thread` 时一条一个编辑框，`--no-open` 只打印链接不开浏览器。`--dry-run` 只打印请求体不联网。Mac 和 Linux 上 `python` 多半要写成 `python3`。

## 固定顺序

1. 问清走哪条路。用户没说过，问一句「走接口（花你的积分）还是手动（我开编辑框你点）」，不默认花他的钱。
2. 写。素材是 x-topic-hunter 交来的对标文（大陆自媒体那篇）：文字按专家正文里的写作基因和 @references/writing-rules.md 重切，观点和数据可以直接用，图和视频直接拿；格式按 @references/post-formats.md：单帖、串帖、长文三选一。长文接口发不了，只走手动。
3. 过门：跑 `gate`。看「不过」项：加权长度超 280（中日韩每字算 2，链接算 23）、还有 [📝 💬 🖼 📊] 标记、长破折号、正文带链接、和最近发过的相似，都要先改。
4. 发：
   - 接口：先 `post --dry-run` 或 `thread --dry-run` 把正文给用户看一眼，他说发再去掉 dry-run。今天已经发了两条，脚本会拦，要他说一句「我知道」再加 `--force`。
   - 手动：`intent`，浏览器弹出编辑框，他自己点发。串帖加 `--thread`，一条一个编辑框，他一条条发。
5. 接口发完脚本自动回读一次核对正文，结果和正文全文都记在他本机 `~/.x-ops/<handle>/posts.jsonl`。手动路记一条「handed」，发没发以他为准。
6. 报：帖子链接（接口路有 id），花了多少钱，日志记在哪。

## 铁律

- 不用脚本操作 X 网站，不模拟点击。发帖只有接口和人点两条路。
- 正文不放第三方链接；自家链接走接口要 0.20 美元一条而且算法压外链。想带链接：走手动路（intent）不花钱，或放简介；走接口回自己的帖不算被召唤，带链接照样 0.20。脚本看到链接会拦，`--allow-url` 只在用户明说要带链接时加。
- 一天一到两条，大事不受限。脚本按本机日志计数，超了要用户说一句才 `--force`。
- 和最近发过的相同或高度相似的不发，想再发同一主题换角度。
- 对标文的图和视频可以直接用，文字不能整段贴，按 X 写法重切。号因为搬运被封了，去申诉，说 AI 不小心弄的、下不为例，有人这么解封过。
- 脚本退出码 3、输出里有「没收到 X 的回复」：发出去了但断网或超时，先让用户去自己主页看有没有发出去，有就别重发。
- 密钥不进对话、不进汇报、不进日志。脚本自己从配置文件读。
- 报错先看 @references/api-notes.md 的表再动手：401 是密钥或权限，402 是积分不够，403 先看 check 打印的 App 权限（只读的发不了，改成 Read and Write 后要重新生成 Access Token），权限对了才是回复了没召唤你的人，429 限频等一会。

## Muse 快速启动

用 Muse 这类带定时器的 Agent，把下面这段贴给它：

```
帮我运营 X 账号，定位 [定位]，语言 [中文/英文]。每天 [时间1]、[时间2] 各发一条，大事不受限，小事宁缺毋滥。
写法：钩子开头前两行定完读；短句；一条一个点；单帖 100 到 140 汉字；二创不搬运；不确定的数据标「待确认」；结尾一个具体问题或争议点；直接、干货、带判断。
不写长破折号，不写「值得注意的是」「让我们」「总而言之」这类词，正文不放链接。
时政、地缘、选举、战争、宗教、民族一律不碰。
发帖走 [接口：用我 ~/.x-api.env 里的密钥跑 x_api.py post / 手动：跑 x_api.py intent 开编辑框我自己点]。
每条正文全文记进 ~/.x-ops/<我的handle>/posts.jsonl，发过的主题不再发。
```

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 怎么写：七条规则、反 AI 三条、口吻 | @references/writing-rules.md |
| 单帖、串帖、长文的格式和加权长度 | @references/post-formats.md |
| 价格、端点、错误码、召唤规则、密钥怎么拿 | @references/api-notes.md |
