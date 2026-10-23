# X 接口笔记（发帖和巡查两条路用到的全部，2026-10-22 从 docs.x.com 和 help.x.com 抄的）

## 计费

- 按量计费，无订阅无最低消费。开发者控制台先买积分，用一次扣一次。自动充值最低 5 美元，每 5 分钟最多充一次，余额为零或负时不自动充；可以设每个周期的花费上限，到了上限接口会被拒直到下个周期。
- 新号激励：实测充 5 美元送 5 美元（首次自动充值按金额匹配，官方页写最多匹配 50 美元），一共 10 美元起步。官方页另写首次购买送 20 美元（只加卡不算、预付卡不算、一张卡只送一次），2026-10-23 实测没到账，没拿到就当没有。赠送的三个月过期。
- 老的 Basic、Pro 订阅档现行定价页已经不列，2026-02-06 的 changelog 写「Basic and Pro plans remain available」，只给老订户，具体月费以控制台为准。

| 项 | 价 |
|---|---|
| 读自己的数据（Owned Reads：自己的提及、自己的帖等 12 个端点，条件是认证用户就是应用所有者） | 0.001 美元一条 |
| 读别人的帖 | 0.005 美元一条 |
| 读用户资料 | 0.010 美元一条 |
| 发帖 POST /2/tweets | 0.015 美元一条 |
| 发帖且正文含任何 URL | 0.20 美元一条 |
| 回复召唤你的人 | 0.010 美元一条 |
| 月上限 | 300 万条帖读 |

## 端点（本技能用到的）

| 动作 | 端点 | 要点 |
|---|---|---|
| 验密钥 | GET /2/users/me | 回 id 和 username；check 子命令用 |
| 发帖 | POST /2/tweets | body {"text"}；回复带 {"reply": {"in_reply_to_tweet_id"}}；串帖就是一条条回复上一条 |
| 回读 | GET /2/tweets/{id} | 发完核一次正文 |
| 自己的提及 | GET /2/users/{id}/mentions | since_id 只拿新的；expansions=author_id 拿到 username；巡查用 |

鉴权：OAuth 1.0a 用户上下文，四个密钥在自己的开发者应用里生成（权限 Read and Write）。脚本用标准库做 HMAC-SHA1 签名，JSON 请求体不参与签名，查询参数参与。

## 规矩（官方原文的意思）

- 2026-02-23 起，程序化回复只准回「召唤」你的人：对方 @ 了你，或引用了你的帖。回自己帖子下的评论算。回别人的热帖不算，接口会拒。
- 2026-04-16 公告、4 月 20 日生效：点赞、关注、引用从所有自助档移除。本技能做不了这三样。
- 对方互动一次只回一条，脚本的「同一条评论只回一次」就是这个意思。
- 自动化规则（2026 年 4 月更新）允许「自动广播有用信息」和「对跟你内容互动的用户自动回复」；不允许「用脚本操作 X 网站」「自动发热搜话题」「重复内容」「多账号重复用途」「误导链接」。违反会被降权或封号。

## 媒体上传（按 2025 年起的 v2 媒体接口写，没拿真密钥测过）

- 图和 gif：POST /2/media/upload，multipart 字段 media 加 media_category=tweet_image 或 tweet_gif，一次传完，返回 data.id 当 media_id。
- 视频：POST /2/media/upload/initialize（JSON：media_type、total_bytes、media_category=tweet_video）拿 id → POST /2/media/upload/{id}/append 按 4MB 分块传（multipart，segment_index 从 0 起）→ POST /2/media/upload/{id}/finalize → GET /2/media/upload?command=STATUS&media_id= 轮询到 processing_info.state 是 succeeded。
- 发帖时 body 加 {"media": {"media_ids": [...]}}。一条最多 4 张图，或 1 个视频，或 1 个 gif。
- 上限：图 5MB、gif 15MB、视频 512MB。媒体上传本身价目表没单列，按发帖那条计。
- 第一次用真密钥跑，哪一步返回和这里写的不一样，以实际返回为准改脚本。

## 搬运被封怎么办

- 图和视频搬问题不大，文字整段贴像搬运号。
- 真被封了去申诉：说是 AI 不小心弄的、下不为例。2026 年 10 月有人这么申诉解封了。

## 错误码

| HTTP | 意思 | 怎么办 |
|---|---|---|
| 401 | 密钥不对、过期，或应用权限不是 Read and Write | 重新生成四个密钥写进配置文件 |
| 402 | 积分不够 | 去控制台充值 |
| 403 | 被拒 | 先看 check 打印的 App 权限：不是 Read and write 就是它（去 developer.x.com 改权限，重新生成 Access Token 和 Secret）；权限对的话，回复多半是对方没有召唤你；发帖看 detail |
| 429 | 限频 | 等一会再发 |
| 503 | X 那边暂时不可用 | 稍后再试 |

脚本退出码：0 成功；1 参数或门没过；2 接口报错；3 发出去了没收到回复（UNKNOWN，先去主页看，有就别重发）。

## 本机数据

`~/.x-ops/<handle>/`：`state.json`（me_id、since_id、上次巡查时间）、`posts.jsonl`（发过的每条，正文全文，接口路和手动路都记）、`replies.jsonl`（回过的每条）。`X_OPS_DIR` 可以换目录。这些文件不进仓库。
