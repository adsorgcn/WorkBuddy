# 微信 HTML 规则（脚本已内置，这里是给人看的对照表）

微信编辑器和草稿接口只认内联样式。规则来自自有账号 2026-08 到 10 推了几十篇的实战记录，脚本 `scripts/wechat_draft.py` 的 render 子命令照这套转。

## Markdown 怎么转

| Markdown | 转成 |
|---|---|
| 第一行 `# 标题` | 当文章标题，不进正文 |
| `## 小标题` | 17px 加粗段落 |
| 普通段落 | 15px、行高 1.8、字距 0.5px 的 p |
| 段落之间 | `<p><br/></p>` |
| `**粗体**` | strong |
| `- 列表` | 每条一个 p，前面是 • |
| `1. 列表` | 每条一个 p，保留编号 |
| `> 引用` | 橙色左边条信息卡（section） |
| `> [!NOTE] 标题` 开头的引用（GFM 提示块，认 NOTE / TIP / IMPORTANT / WARNING / CAUTION，标题可不写） | 带加粗标题的信息卡，颜色按类型：NOTE、IMPORTANT 蓝；TIP 绿；WARNING 橙；CAUTION 红。不写标题就用默认名：说明、重点、推荐、注意、避坑 |
| 表格 | 一行一张蓝色左边条信息卡：第一列加粗，其他列写成「列名：值」。微信不渲染 table |
| ``` 代码块 | 深色 section，每行一个等宽 p |
| `![说明](本地路径.jpg)` 单独成行 | 图片 100% 宽，说明变 12px 灰色图注；推送时自动上传换成微信图床地址 |
| `[文字](网址)` | 正文只留文字加 [n] 角标，网址收进文末「参考链接」一节（公众号正文不放外链）；加 --no-cite 就只留文字；mp.weixin.qq.com 的链接保留为可点链接 |
| `---` | 一行灰色横线 |
| 长破折号 | 换成逗号 |

## 推之前必须为零的

- `[📝 …]` `[💬 …]` `[🖼 …]` `[📊 …]` 这四种标记：是专家留给作者填的位置，推之前作者要么填掉要么删掉
- 长破折号
- table、div、style、script、class、id、position:fixed/absolute
- 非微信图床的图片地址

## 排版常量

```html
<p style="font-size:15px;color:#333;line-height:1.8;letter-spacing:0.5px;margin:0;">正文</p>
<p style="font-size:17px;font-weight:bold;color:#111;line-height:1.8;letter-spacing:0.5px;margin:0;">小标题</p>
<p><br/></p>
<p style="margin:0;"><img src="https://mmbiz.qpic.cn/..." style="width:100%;"/></p>
<p style="font-size:12px;color:#999;text-align:center;letter-spacing:0.5px;margin:0;">图注</p>
<section style="padding:12px 15px;background-color:#f0f7ff;border-left:4px solid #1a73e8;margin:0;">信息卡</section>
<p style="text-align:center;color:#ccc;margin:0;">────────</p>
```

颜色系统：蓝 #1a73e8 底 #f0f7ff 正常信息；绿 #2e7d32 底 #f1f8f2 推荐；橙 #ff8f00 底 #fff8e1 提醒；红 #c62828 底 #fef2f2 避坑。

## 图片

- 正文图 jpg/png，1MB 以内，900×500 到 900×620 看着最舒服；大于 20KB 才算有效图
- 封面 2.35:1，主体居中，jpg/png，10MB 以内
- 装了 Pillow 时正文图超 1MB 会自动压；没装就报错让你自己压

## 预览页

`render` 除了写 `*.wechat.html`（纯片段，推的就是它），还写一个 `*.preview.html`：把片段套进 390 宽的手机壳，浏览器打开就能看排版，图片用本地路径。它只是看，不是微信的真实渲染，哪里跟草稿箱里不一样以草稿箱为准。

## 贴图（图片消息）的卡片

不走这套 HTML。`scripts/newspic_cards.py` 按【第N页】切页，填 `scripts/cards.html` 模板，用本机 Edge/Chrome 无头截成 1080×1440 的 PNG。封面卡的字全落在中央正方形里（信息流裁 1:1），要点卡是标题加正文，结尾卡同要点卡。放不下顶部出红条，脚本报「第 k 张放不下了，删字」，不缩字号。字段和推法见 api-notes.md「图片消息」。

## 手动贴编辑器那条路

不走接口的人：MD 粘到 ilang.cn/md 预览微信样式，一键复制进公众号编辑器。表格在那条路上正常渲染。
