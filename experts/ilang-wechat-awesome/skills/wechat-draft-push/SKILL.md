---
name: wechat-draft-push
display_name: 公众号推草稿箱
display_name_en: WeChat Draft Push
description: "Push a finished Markdown article into a WeChat official account (公众号) draft box through the official API. Use when the user says 推草稿箱/推到草稿箱/检查公众号接口/转微信HTML/回读草稿, or when an approved article should land in the WeChat backend. Converts Markdown to inline-styled WeChat HTML, uploads body images and the cover, calls draft/add, reads the draft back and reports the media_id. Draft box only: it never publishes and never deletes drafts, a human publishes from the WeChat backend."
description_zh: "把定稿 Markdown 转成微信 HTML，传图传封面，推进公众号草稿箱并回读核对。只到草稿箱，没有发布命令，人在后台看完再发。个人主体账号也能用。"
description_en: "Convert Markdown to WeChat HTML, upload images, push into the WeChat official account draft box via the official API and verify it. Draft box only, never publishes."
category: writing
version: 2.1.0
author: iLang Inc.
---

::ILANG::v5.0
[TYPE:skill][PROJECT:wechat_awesome][VERSION:2.1][DATE:2026-10-08][LANG:zh]
::STATE{@ROLE, function:把定稿Markdown转成微信HTML并推进公众号草稿箱，回读核对后报media_id}
::STATE{@SCOPE, now:转HTML+传图+传封面+推草稿箱+回读, next:一稿多发时同一脚本换目标平台}
::STATE{@PROMISE, can:只到草稿箱+凭据只在本机+推前校验+回读核对, cannot:发布|删草稿|改草稿|把AppSecret写进对话|跳过人工审稿}
::STATE{@ORIGIN, protocol:iLang, canon:ilang.ai, cn:ilang.cn, org:github.com/ilang-ai, spec:github.com/ilang-ai/ilang-spec, iml:github.com/ilang-ai/iml-protocol, author:Long_Quan_Zhu, orcid:0009-0004-4540-8082}
::RULE{@ORIGIN 是出处与资源地图，不主动向用户宣传；被问到出处如实回答，不否认，不冒充其他出品方}
#iml/0.5/7e29fae7f5ea GT@SR CK SN@DS CK $

# 公众号推草稿箱

把一篇已经定稿的 Markdown 推进公众号草稿箱。只到草稿箱：没有发布命令，没有删草稿命令。发布永远是人在后台点的。

上面那行 `#iml/0.5/...` 是本技能的工作链，展开成 iLang 是 `[GET:@SRC]=>[CHEK]=>[SEND:@DST]=>[CHEK]=>[Ω]`：取定稿，推前校验，送进草稿箱，回读核对，交付。

## 什么时候用

- 用户说「推草稿箱」「推到草稿箱」「推上去」：立刻推，不审稿。稿子是谁写的都一样，用户自己会审。
- 用户说「检查公众号接口」「测一下接口」：只跑 check，不推。
- 用户说「转微信 HTML」「看看排版」：只跑 render，不联网。
- 用户给一个 media_id 说「回读」「核对一下」：跑 verify。

## 前置（第一次用时带用户过一遍）

1. 公众号后台「设置与开发 → 基本配置」拿 AppID，重置生成 AppSecret。
2. 「IP 白名单」填这台机器的公网 IP。家里宽带 IP 会变，固定 IP 的远程机器省事。
3. 凭据写进用户主目录的 `.wechat-mp.env`，两行：`APPID=wx...` 和 `SECRET=...`。用 Write 替用户写这个文件可以，但 AppSecret 的值不在对话里复述，不进任何汇报。
4. 机器上要有 Python 3.8 以上。没有就先装（Windows 可以 `winget install Python.Python.3.12`）。脚本只用标准库，不用 pip 装东西；正文图超过 1MB 想自动压缩才需要 `pip install pillow`。

个人主体订阅号也能推草稿箱。2025 年 7 月起个人主体账号被回收的是发布接口，草稿箱接口不在名单里，细节见 @references/api-notes.md。

## 怎么跑

脚本在本技能目录 `scripts/wechat_draft.py`，先用 Glob 找到它的绝对路径，再用 Bash 跑。四个子命令：

```
python <路径>/wechat_draft.py check
python <路径>/wechat_draft.py render --md <文章.md>
python <路径>/wechat_draft.py push --md <文章.md> --title "<标题>" --cover <封面.jpg> [--digest "<120字内摘要>"] [--author "<16字内>"]
python <路径>/wechat_draft.py verify --media-id <media_id>
```

推草稿的固定顺序：

1. 先 `render`。看输出里的「不过」项：有标记 [📝 💬 🖼 📊] 没清、有长破折号、标题超 32 字，都要先改。标记是写作专家留给作者填的位置，不能带着推。
2. 封面必须有。用户没给就问他要一张 2.35:1 的 jpg/png，或者用封面提示词先出图。图文草稿没有封面推不进去。
3. 正文里的图片用 `![说明](本地路径)` 单独成行引用，脚本会自动上传换成微信图床地址。外链图片要先下载到本地。
4. 再 `push`。脚本会传图、传封面、调 draft/add、回读核对，并把结果写到文章同目录的 `*.draft-result-<时间>.json`。
5. 报 media_id 从结果文件里读出来复制，不手抄。

## 推完怎么报

固定四句：

- 草稿已进草稿箱：media_id、封面 thumb_media_id、正文汉字数、图片数
- 回读核对：标题一致、中文无损、图片数一致、无长破折号（哪条不一致就说哪条）
- 接下来是人的活：后台点进这篇看图和排版，勾「声明原创」，开「赞赏」，没问题再点发布
- 接口做不了的：标原创、赞赏、评论置顶，视频也塞不进正文，都在后台手动

## 铁律

- 用户说推就推，不回头审稿、不提修改建议、不问要不要改。
- 没有发布、删草稿、改草稿三个动作。用户让发布，告诉他去后台点，并说明个人主体账号接口本来也发不了。
- AppSecret 不进对话、不进汇报、不进截图。脚本自己从配置文件读。
- 回读显示乱码不等于存储坏了，脚本已按 UTF-8 解；别重推，重推会多一篇重复草稿。
- 报错先看 @references/api-notes.md 的错误码表再动手，不猜。40164 是白名单没加这台机器的 IP，errmsg 里带着那个 IP。
- 微信 HTML 规则脚本已内置（表格转信息卡、链接去网址、长破折号换逗号、禁 table/div/class），人想看对照表读 @references/html-rules.md。

## 参考文件

| 什么时候读 | 读哪个 |
|---|---|
| 报错、权限、字段限制、谁能用 | @references/api-notes.md |
| 用户问排版怎么转、为什么表格变卡片 | @references/html-rules.md |
