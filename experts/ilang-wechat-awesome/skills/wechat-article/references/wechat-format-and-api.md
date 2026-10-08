# 转微信格式与接口推草稿

## 两条路

| 路 | 适合谁 | 怎么做 |
|---|---|---|
| 手动贴编辑器 | 所有人 | MD 正文粘到 ilang.cn/md 预览微信样式，一键复制到公众号编辑器。纯前端页面，内容只在你的浏览器里处理，不上传服务器。表格在这条路上正常渲染 |
| 接口推草稿箱 | 有开发者接口权限的账号 | AI 把 MD 转成带内联样式的 HTML，上传图片拿微信图床地址，调草稿箱接口。注意：2025 年 7 月起，个人主体账号和企业主体未认证账号的草稿箱与发布接口权限被微信回收，这条路只对认证企业主体账号开放，发前先确认自己账号有没有接口权限 |

## 转微信格式的 HTML 规则（用户要"转微信格式"时照这个出）

正文段落：
```html
<p style="font-size:15px;color:#333;line-height:1.8;">正文</p>
```

加粗小标题：
```html
<p style="font-size:17px;font-weight:bold;color:#111;">标题</p>
```

图片（必须用微信图床，接口路径里外部图片地址会被过滤）：
```html
<p><img src="https://mmbiz.qpic.cn/..." style="width:100%;"/></p>
```

信息卡片（接口路径里代替表格）：
```html
<section style="padding:15px;background-color:#f8f9fa;border-left:4px solid #1a73e8;margin-bottom:12px;">
<p style="font-size:15px;color:#333;line-height:2;margin:0;">内容</p>
</section>
```

段落间距：`<p><br/></p>`

接口路径绝对禁止：`<table>` 标签（微信渲染不稳定，改成卡片或带完整内联样式的表格）、CSS class、外部样式表、非微信图床的图片地址、长破折号。所有样式写在标签的 style 属性里。

## 接口推草稿的步骤（只对有权限的账号）

1. 拿钥匙：公众号后台「设置与开发」→「基本配置」，复制 AppID，重置生成 AppSecret。钥匙只放配置文件或环境变量，不写进对话。
2. 配 IP 白名单：查服务器公网 IP，填进「基本配置」→「IP 白名单」。家庭宽带 IP 会变，发布报错多半是这个。
3. 取令牌：`GET https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=...&secret=...`，有效期 2 小时。
4. 传图：正文配图走 `cgi-bin/media/uploadimg` 拿 mmbiz 地址（http 换成 https）；封面走 `cgi-bin/material/add_material?type=image` 拿 thumb_media_id。
5. 推草稿：`POST cgi-bin/draft/add`，articles 里带 title、content（转好的 HTML）、digest（一句话说清文章价值）、thumb_media_id、need_open_comment。请求体必须 `json.dumps(..., ensure_ascii=False).encode('utf-8')`，否则中文全变乱码。
6. 人工审核：去后台草稿箱点进编辑器预览（列表页只显示文字，看不到图和排版），没问题再发布。发布可以手动点，也可以 `POST cgi-bin/freepublish/submit`。

## 踩坑清单（实战记录）

| 现象 | 原因 | 解决 |
|---|---|---|
| 中文全变 \uXXXX 乱码 | json 参数默认 ascii 编码 | data=json.dumps(ensure_ascii=False).encode('utf-8') |
| 图片不显示 | 用了外部图片地址 | 先 uploadimg 传到微信拿 mmbiz 地址 |
| 表格不渲染 | 微信对 table 兼容差 | section 加内联样式模拟卡片 |
| 排版全丢失 | 用了 class 或外部样式 | 所有样式写在 style 属性里 |
| 报错 ip not in whitelist | IP 没加白名单或 IP 变了 | 重新查 IP 加到后台 |
| 标题报错 | author 字段超长 | author 留空 |
| 推了但看不到效果 | 在草稿列表看的 | 点进编辑器预览 |

## 配图规则

搜跟内容直接相关的图，不搜装饰风景图。文章讲某个 App 就搜它的截图，讲数据对比就用产品官方对比图。来源优先级：产品官方截图或营销图，再搜索引擎图片，最后免费图库。文中截图位在 MD 里用 [🖼 建议截图：说明] 标出，由作者自己补。
