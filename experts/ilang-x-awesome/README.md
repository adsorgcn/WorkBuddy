# X运营专家 · X-Awesome v2.3.44

`[GET:@SRC]=>[CHEK]=>[SEND:@DST]=>[CHEK]=>[Ω]`
`#iml/0.5/7e29fae7f5ea GT@SR CK SN@DS CK $`

你说清定位，它替你跑 X 账号里所有能跑的执行：找题、写帖、发帖、巡查评论、回复。你只定方向和拍板。

## 一句话说清楚

把执行交给 AI，人只做判断。选题先读 X榜单 的公开榜（免费，脚本直接解析），再读仓库每天自动更新的免费内容清单，X榜单 MCP 可选；写帖按 X 的写法：钩子开头、短句、一条一个点、结尾一个具体问题；发帖二选一：走官方接口花你自己的积分，或者脚本把文案送进浏览器编辑框你点发；评论巡查走官方接口，只回你自己帖子下的评论，回不回由专家判，你在 WorkBuddy 里点头再发。

## 输入 → 输出

```
你的定位 + 你的素材（可选）
         ↓
     X运营专家
         ↓
  1. 选题清单：1 到 3 条候选，带来源、角度、争议点、禁区判定
  2. 帖子：单帖 / 串帖 / 长文，去 AI 味后交稿
  3. 发：接口（check → post --dry-run → post）或手动（intent 开编辑框）
  4. 巡查：拉你帖下的新评论 → 专家拟回复 → 你点头 → 接口发出
  5. 日志：发帖和回复全文落在你自己电脑的 ~/.x-ops/<handle>/
```

## 花多少钱

- 走接口才花钱，按量计费无月费：普通帖 0.015 美元一条，正文带链接 0.20 一条，回复自己帖下的评论 0.010 一条，读自己的提及 0.001 一条。新号充 5 美元送 5 美元，一共 10 美元；一天十条评论约 3 美元一个月，发帖走手动的话这 10 美元能用三个月左右。
- 走手动不花钱。
- 选题不花钱：X榜单 的公开榜和仓库清单都免费。要在它 30 天的库里按赛道、粉丝数细筛才用得上 X榜单 MCP（年卡，每天 300 次查询），可选。

## 不做什么

不用脚本碰 X 网站，不点赞、不关注、不引用、不私信，不给陌生人的帖评论，不发热搜话题，不碰时政和地缘，一天不超过两条。半年前一台每十分钟追热点、主线地缘的无头 bot 被封号，这个专家就是照着那次的教训反着做的。

## 包里有什么

```
ilang-x-awesome/
├── .codebuddy-plugin/plugin.json      专家配置（市场与 CLI 用）
├── agents/ilang-x-awesome.md          专家正文，可整段粘进「创建专家」
├── skills/x-topic-hunter/             选题：X榜单 公开榜（x_rank.py）、仓库清单（x_feed.py），过滤与禁区，MCP 可选
│   ├── SKILL.md
│   ├── scripts/x_rank.py              标准库 Python：读 X榜单 公开榜（最火推文、话题榜、长文榜、海外榜）
│   ├── scripts/x_feed.py              标准库 Python：读仓库每日清单并按 X 口径过滤
│   └── references/                    算法权重与出处、数据源、过滤规则
├── skills/x-post/                     发帖：接口或手动
│   ├── SKILL.md
│   ├── scripts/x_api.py               标准库 Python：check / post / thread / reply / mentions / intent
│   └── references/                    写作规则、三种格式、接口笔记
├── skills/x-comment-patrol/           评论巡查：拉新评论、发回复、推水位线
│   ├── SKILL.md
│   ├── scripts/x_patrol.py            标准库 Python：fetch / send / status
│   └── references/                    回复规则、Actions 定时模板
└── avatars/expert.png
```

## 推荐阅读

- X 新手攻略：https://x.com/ai_chuhai/status/2112640526176358616
- X 算法公式：https://x.com/ai_chuhai/status/2113358982391750858

## 怎么装

见仓库首页 README。没有运行环境的，需要一个能读 SKILL.md 的 Agent，WorkBuddy 海外版、Claude Code、Codex、Muse 都行；教程关注 X 上的 @ai_chuhai。

## 许可

MIT · © 2026 静水流深 / iLang Inc.
