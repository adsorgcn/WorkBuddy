# 公众号接口笔记（推草稿这条路用到的全部）

数据口径：微信公众平台开发文档「新建草稿」「发布能力」页，腾讯客服接口权限表，2026-10-08 核；踩坑来自自有账号 2026-08 到 10 的实战记录。

## 谁能用

| 账号 | 草稿箱接口（draft/add、draft/get） | 发布接口（freepublish） |
|---|---|---|
| 个人主体订阅号 | 能用（官方 2025-07 回收名单里没有草稿箱；社区实测稿子能进草稿箱） | 不能，2025 年 7 月起回收 |
| 企业主体未认证 | 同上 | 不能 |
| 微信认证企业号 | 能用 | 能用，但本技能不做 |

官方原文：「2025年7月起，个人主体账号、企业主体未认证账号及不支持认证的账号将被回收以上接口的调用权限」，「以上接口」指发布能力的 5 个接口。

## 前置

- 公众号后台「设置与开发 → 基本配置」：AppID、AppSecret（重置生成，只存配置文件）。
- 「IP 白名单」：填调接口那台机器的公网 IP。报 40164 时 errmsg 里带着当前 IP，照抄进白名单。
- 凭据存 `~/.wechat-mp.env`（两行 APPID= 与 SECRET=）或环境变量，永远不贴进对话。

## 端点

| 动作 | 端点 | 要点 |
|---|---|---|
| 拿 token | GET /cgi-bin/token?grant_type=client_credential&appid&secret | 2 小时有效，每次跑现取 |
| 正文图 | POST /cgi-bin/media/uploadimg | multipart 字段 media；只收 jpg/png，1MB 以内；返回 url，http 换 https |
| 封面 | POST /cgi-bin/material/add_material?type=image | 永久素材，10MB 以内；返回 media_id 当 thumb_media_id |
| 推草稿 | POST /cgi-bin/draft/add | articles[]；请求体 json.dumps(ensure_ascii=False).encode("utf-8")，头 Content-Type: application/json; charset=utf-8 |
| 回读 | POST /cgi-bin/draft/get | body {"media_id"}；响应是 text/plain 不带 charset，必须拿原始字节按 UTF-8 解 |

## 字段限制（新建草稿）

| 字段 | 限制 |
|---|---|
| title | 32 字内，必填 |
| author | 16 字内，可空 |
| digest | 120 字内，单图文有效；不填取正文前 54 字 |
| content | HTML，2 万字符内、1MB 内；JS 被剥；图片必须是 uploadimg 返回的地址，外链图被过滤 |
| thumb_media_id | news 类型必填，永久素材 |
| need_open_comment / only_fans_can_comment | 0 或 1 |

## 错误码速查

| errcode | 意思 | 怎么办 |
|---|---|---|
| 40164 | IP 不在白名单 | errmsg 里的 IP 加进后台白名单 |
| 40013 | AppID 不对 | 重新复制 |
| 40125 | AppSecret 不对或被重置 | 重置后更新配置文件 |
| 40001 | token 失效 | 重跑 |
| 40007 | media_id 不合法 | 多半是封面没传成永久素材 |
| 45110 | author 太长 | 16 字内；中文如果被转成 \uXXXX 也会超，脚本已按 UTF-8 直传 |
| 45009 | 接口次数到顶 | 明天 |
| 48001 | 没权限 | 看上面「谁能用」 |

## 接口做不了的三件事（人去后台点）

标原创、赞赏、评论区置顶。还有：视频塞不进正文，只能后台手动插。

## 回读核对标准

标题一致；正文中文无损（UTF-8 解码后正常）；mmbiz 图片数等于上传数；没有长破折号。回读显示乱码不等于存储坏了，别重推，重推会多一篇重复草稿。

## 本技能没有的命令

freepublish/submit（发布）、draft/delete（删草稿）、draft/update（改草稿）。发布永远是人在后台点。
