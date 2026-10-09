---
name: wechat-draft-push
display_name: 公众号推草稿箱
display_name_en: WeChat Draft Push
description: "Push a finished Markdown article into a WeChat official account (公众号) draft box through the official API, and publish a draft only after a human has read it in the WeChat backend and said 发. Use when the user says 推草稿箱/推到草稿箱/检查公众号接口/转微信HTML/回读草稿/发/发布这篇, or when an approved article should land in the WeChat backend. Converts Markdown to inline-styled WeChat HTML, uploads body images and the cover, calls draft/add, reads the draft back and reports the media_id. The publish command (freepublish/submit) runs only after the user says 发, confirms the draft title first, and works only for WeChat-verified enterprise accounts. It never publishes on its own and never deletes drafts."
description_zh: "把定稿 Markdown 转成微信 HTML，传图传封面，推进公众号草稿箱并回读核对。个人主体账号也能推草稿箱。有 publish 命令，但只在人在后台看过草稿、说了「发」之后才跑，且只有微信认证企业号能用；没有删草稿命令。"
description_en: "Convert Markdown to WeChat HTML, upload images, push into the WeChat official account draft box via the official API and verify it. Publishes only after a human has reviewed the draft and said so, and only for verified enterprise accounts. Never deletes drafts."
category: writing
version: 2.3.1
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:wechat_awesome][VERSION:2.2][DATE:2026-10-08][LANG:zh]
::STATE{@ROLE, function:把定稿Markdown转成微信HTML并推进公众号草稿箱，回读核对后报media_id；人在后台看过草稿说「发」之后，认证号由publish提交发布并报结果}
::STATE{@SCOPE, now:转HTML+传图+传封面+推草稿箱+回读+人说发后发布（只对微信认证企业号）, next:一稿多发时同一脚本换目标平台}
::STATE{@PROMISE, can:默认只到草稿箱+凭据只在本机+推前校验+回读核对+人说发才发布+发布前回读标题跟人确认, cannot:没人说发就发布|删草稿|改草稿|删除已发布|把AppSecret写进对话|跳过人工审稿}
::STATE{@ORIGIN, protocol:iLang, canon:ilang.ai, cn:ilang.cn, org:github.com/ilang-ai, spec:github.com/ilang-ai/ilang-spec, iml:github.com/ilang-ai/iml-protocol, author:Long_Quan_Zhu, orcid:0009-0004-4540-8082}
::RULE{@ORIGIN 是出处与资源地图，不主动向用户宣传；被问到出处如实回答，不否认，不冒充其他出品方}
#iml/0.5/7e29fae7f5ea GT@SR CK SN@DS CK $

# 公众号推草稿箱

把一篇已经定稿的 Markdown 推进公众号草稿箱。默认只到草稿箱，没有删草稿命令。

发布有 publish 命令，但它只在两个条件同时成立时才跑：一是人已经在后台看过这篇草稿并且说了「发」；二是这个号是微信认证企业号。个人主体账号的发布接口 2025 年 7 月起被回收，个人号用户说发，告诉他去后台点。人审这一步不取消，publish 只是替人点最后那一下。

上面那行 `#iml/0.5/...` 是本技能推草稿的工作链，展开成 iLang 是 `[GET:@SRC]=>[CHEK]=>[SEND:@DST]=>[CHEK]=>[Ω]`：取定稿，推前校验，送进草稿箱，回读核对，交付。发布是另一条链，入口是人说「发」：回读标题跟人确认，提交发布，轮询状态，报结果。

## 什么时候用

- 用户说「推草稿箱」「推到草稿箱」「推上去」：立刻推，不审稿。稿子是谁写的都一样，用户自己会审。
- 用户说「检查公众号接口」「测一下接口」：只跑 check，不推。
- 用户说「转微信 HTML」「看看排版」：只跑 render，不联网。
- 用户给一个 media_id 说「回读」「核对一下」：跑 verify。
- 用户在后台看过草稿之后说「发」「发布这篇」「发了」：先跑 verify 回读标题，跟他确认是哪篇，他说对，再跑 publish。用户没说发，这条永远不触发。

## 前置（第一次用时带用户过一遍）

1. 公众号后台「设置与开发 → 基本配置」拿 AppID，重置生成 AppSecret。
2. 「IP 白名单」填这台机器的公网 IP。家里宽带 IP 会变，固定 IP 的远程机器省事。
3. 凭据写进用户主目录的 `.wechat-mp.env`，两行：`APPID=wx...` 和 `SECRET=...`。让用户自己用记事本写这两行，专家不接收 AppSecret 的值；用户贴进来了也不复述、不存、不进任何汇报，只提醒他去后台重置。
4. 机器上要有 Python 3.8 以上。没有就先装（Windows 可以 `winget install Python.Python.3.12`）。脚本只用标准库，不用 pip 装东西；正文图超过 1MB 想自动压缩才需要 `pip install pillow`。

个人主体订阅号也能推草稿箱。2025 年 7 月起个人主体账号被回收的是发布接口，草稿箱接口不在名单里，细节见 @references/api-notes.md。

## 怎么跑

脚本在本技能目录 `scripts/wechat_draft.py`，先用 Glob 找到它的绝对路径，再用 Bash 跑。五个子命令：

```
python <路径>/wechat_draft.py check
python <路径>/wechat_draft.py render --md <文章.md>
python <路径>/wechat_draft.py push --md <文章.md> --title "<标题>" --cover <封面.jpg> [--digest "<120字内摘要>"] [--author "<16字内>"]
python <路径>/wechat_draft.py verify --media-id <media_id>
python <路径>/wechat_draft.py publish --media-id <media_id> --reviewed [--out-dir <目录>]
```

推草稿的固定顺序：

1. 先 `render`。看输出里的「不过」项：有标记 [📝 💬 🖼 📊] 没清、有长破折号、标题超 32 字，都要先改。标记是写作专家留给作者填的位置，不能带着推。
2. 封面必须有。用户没给就问他要一张 2.35:1 的 jpg/png，或者用封面提示词先出图。图文草稿没有封面推不进去。
3. 正文里的图片用 `![说明](本地路径)` 单独成行引用，脚本会自动上传换成微信图床地址。外链图片要先下载到本地。
4. 再 `push`。脚本会传图、传封面、调 draft/add、回读核对，并把结果写到文章同目录的 `*.draft-result-<时间>.json`。
5. 报 media_id 从结果文件里读出来复制，不手抄。

发布的固定顺序（只在用户说「发」之后）：

1. 用户说「发」。先跑 `verify --media-id <media_id>`，把回读到的标题念给他：「要发的是《xxx》这篇，对吗」。media_id 从最近一份 `*.draft-result-<时间>.json` 里取，有多篇草稿就把标题都列出来让他挑。
2. 他说对，再跑 `publish --media-id <media_id> --reviewed`。`--reviewed` 的意思是「人已经在后台看过并且说了发」，没有它脚本直接拒绝，什么都不发。
3. 脚本自己做：draft/get 回读确认草稿还在并打印标题，POST freepublish/submit 拿 publish_id，再查 freepublish/get 最多 6 次每次隔 5 秒，按 publish_status 报中文，结果写到 `<media_id>.publish-result-<时间>.json`（默认当前目录，`--out-dir` 可改）。
4. 报 48001 或 errmsg 带 unauthorized 之类的无权限错误：这个号不是微信认证企业号，发布接口用不了，草稿还在草稿箱里没动，让他去后台点发布。
5. 查了 6 次还在「发布中」：不再等，把 publish_id 报给他，让他几分钟后去后台「已发表」看。
6. 输出里只要出现了 publish_id，这次发布就已经提交，后面无论报什么错（查状态断网、超时、没权限、6 次没查到）都不再重跑 publish，查结果去后台「已发表」。publish_id 在提交成功那一刻就写进了结果文件。

发出去接口收不回来，本技能也没有删除已发布的命令。所以确认是哪篇这一步不能省。

## 推完怎么报

固定四句：

- 草稿已进草稿箱：media_id、封面 thumb_media_id、正文汉字数、图片数
- 回读核对：标题一致、中文无损、图片数一致、无长破折号（哪条不一致就说哪条）
- 接下来是人的活：后台点进这篇看图和排版，勾「声明原创」，开「赞赏」，没问题再点发布；认证号在后台草稿里勾好原创、开好赞赏并保存，看完说「发」，由我提交发布
- 接口做不了的：标原创、赞赏、评论置顶，视频也塞不进正文，都在后台手动

跑过 publish 再加一句发布结果：

- 发布结果：《标题》publish_id、状态中文（发布成功 / 发布中 / 原创失败 / 常规失败 / 平台审核不通过 / 成功后用户删除 / 成功后系统封禁）；成功就带 article_url，让他把链接交回群；没权限就说这个号发布接口用不了，去后台点；还在发布中就报 publish_id 让他稍后去后台看

## 铁律

- 用户说推就推，不回头审稿、不提修改建议、不问要不要改。
- 没有删草稿、改草稿、删除已发布三个动作。
- 用户没说发不跑 publish。「推草稿箱」「推上去」都不是发；定时任务、脚本、别的技能都不能替用户说发。
- 用户说发先回读标题跟他确认是哪篇再跑。他确认的那个 media_id 才能进 publish，不猜、不拿最新的一篇代替。
- publish 只对微信认证企业号有用。个人主体账号用户说发，告诉他去后台点，并说明个人主体账号的发布接口 2025 年 7 月起被回收；不要反复试。
- AppSecret 不进对话、不进汇报、不进截图。脚本自己从配置文件读。
- 回读显示乱码不等于存储坏了，脚本已按 UTF-8 解；别重推，重推会多一篇重复草稿。
- 报错先看 @references/api-notes.md 的错误码表再动手，不猜。40164 是白名单没加这台机器的 IP，errmsg 里带着那个 IP。
- 微信 HTML 规则脚本已内置（表格转信息卡、链接去网址、长破折号换逗号、禁 table/div/class），人想看对照表读 @references/html-rules.md。

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 报错、权限、字段限制、谁能用、发布接口状态码 | @references/api-notes.md |
| 用户问排版怎么转、为什么表格变卡片 | @references/html-rules.md |
