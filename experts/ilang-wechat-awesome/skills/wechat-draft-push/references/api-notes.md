# 公众号接口笔记（推草稿加发布这两条路用到的全部）

数据口径：微信公众平台开发文档「新建草稿」「发布能力」页，发布接口字段与错误码取自开发文档 api_freepublish_submit 与 api_freepublish_get 页，腾讯客服接口权限表，2026-10-08 核；踩坑来自自有账号 2026-08 到 10 的实战记录。发布接口本技能 2.2 才加，自有账号是个人主体没法实测，状态码走的是官方页面。

## 谁能用

| 账号 | 草稿箱接口（draft/add、draft/get） | 发布接口（freepublish/submit、freepublish/get） |
|---|---|---|
| 个人主体订阅号 | 能用（官方 2025-07 回收名单里没有草稿箱；社区实测稿子能进草稿箱） | 不能，2025 年 7 月起回收，调了报 48001 或 unauthorized |
| 企业主体未认证 | 同上 | 不能 |
| 微信认证企业号 | 能用 | 能用。本技能 2.2 起有 publish 命令，只在人说「发」之后跑 |

官方原文：「2025年7月起，个人主体账号、企业主体未认证账号及不支持认证的账号将被回收以上接口的调用权限」，「以上接口」指发布能力的 5 个接口：发布草稿 freepublish/submit、发布状态 freepublish/get、删除发布 freepublish/delete、获取已发布图文 freepublish/getarticle、获取已发布列表 freepublish/batchget。腾讯客服权限表：发布接口普通公众号不支持、微信认证公众号支持。

## 前置

- 公众号后台「设置与开发 → 基本配置」：AppID、AppSecret（重置生成，只存配置文件）。
- 「IP 白名单」：填调接口那台机器的公网 IP。报 40164 时 errmsg 里带着当前 IP，照抄进白名单。
- 本机没有固定 IP：白名单填远程机的 IP，本机走 ssh 隧道出去，见下面「本机没有固定 IP」一节。
- 凭据存 `~/.wechat-mp.env`（两行 APPID= 与 SECRET=）或环境变量，永远不贴进对话。

## 端点

| 动作 | 端点 | 要点 |
|---|---|---|
| 拿 token | GET /cgi-bin/token?grant_type=client_credential&appid&secret | 2 小时有效，每次跑现取 |
| 正文图 | POST /cgi-bin/media/uploadimg | multipart 字段 media；只收 jpg/png，1MB 以内；返回 url，http 换 https |
| 封面 | POST /cgi-bin/material/add_material?type=image | 永久素材，10MB 以内；返回 media_id 当 thumb_media_id |
| 推草稿 | POST /cgi-bin/draft/add | articles[]；请求体 json.dumps(ensure_ascii=False).encode("utf-8")，头 Content-Type: application/json; charset=utf-8 |
| 回读 | POST /cgi-bin/draft/get | body {"media_id"}；响应是 text/plain 不带 charset，必须拿原始字节按 UTF-8 解 |
| 提交发布 | POST /cgi-bin/freepublish/submit | body {"media_id"}；返回 publish_id、msg_data_id；只有认证号能调 |
| 查发布状态 | POST /cgi-bin/freepublish/get | body {"publish_id"}；返回 publish_status、article_id、article_detail、fail_idx |

## 字段限制（新建草稿）

| 字段 | 限制 |
|---|---|
| title | 32 字内，必填 |
| author | 16 字内，可空 |
| digest | 120 字内，单图文有效；不填取正文前 54 字 |
| content | HTML，2 万字符内、1MB 内；JS 被剥；图片必须是 uploadimg 返回的地址，外链图被过滤 |
| thumb_media_id | news 类型必填，永久素材 |
| need_open_comment / only_fans_can_comment | 0 或 1；脚本 --comment open（1/0，默认）、fans（1/1）、off（0/0） |
| content_source_url | 「阅读原文」跳转地址，可空；脚本 --source-url，要 http(s) 开头 |

## 发布接口（微信认证企业号，2.2 起有 publish 命令）

### 谁能用

只有微信认证企业号。个人主体、企业主体未认证、不支持认证的账号 2025 年 7 月起被回收，调了报 48001（api unauthorized）或 errmsg 带 unauthorized。个人号用户要发，去后台点，不要反复试。

### 什么时候能跑

人在后台看过这篇草稿、说了「发」之后。脚本层面用 `--reviewed` 把这个条件钉死，没有它直接拒绝。跑之前先 draft/get 回读标题跟人确认是哪篇。

### 发出去收不回来

发出去接口收不回来。本技能没有 freepublish/delete，发错了去后台处理。

### 提交发布 freepublish/submit

| 项 | 内容 |
|---|---|
| 请求 | POST https://api.weixin.qq.com/cgi-bin/freepublish/submit?access_token=TOKEN |
| body | {"media_id": "草稿的 media_id"} |
| 返回 | errcode、errmsg、publish_id（发布任务 id）、msg_data_id（消息数据 id） |
| 注意 | 返回成功只代表任务提交了，之后还可能在原创校验、平台审核上失败，要查状态 |

### 查发布状态 freepublish/get

| 项 | 内容 |
|---|---|
| 请求 | POST https://api.weixin.qq.com/cgi-bin/freepublish/get?access_token=TOKEN |
| body | {"publish_id": "提交发布拿到的 publish_id"} |
| 返回 | publish_id、publish_status、article_id（成功时）、article_detail{count, item[{idx, article_url}]}（成功时）、fail_idx[]（失败的文章序号） |

publish_status 对照（脚本按这张表报中文）：

| publish_status | 意思 | 脚本怎么办 |
|---|---|---|
| 0 | 发布成功 | 打印 article_detail.item[].article_url，让人把链接交回群 |
| 1 | 发布中 | 隔 5 秒再查，最多 6 次；还没好就报 publish_id 让人去后台「已发表」看 |
| 2 | 原创失败 | 报错退出，去后台看原创状态，改完重推草稿再发 |
| 3 | 常规失败 | 报错退出，带 fail_idx，去后台看草稿 |
| 4 | 平台审核不通过 | 报错退出，去后台看通知里的原因 |
| 5 | 成功后用户删除 | 报错退出，发出去过，之后被用户在后台删了 |
| 6 | 成功后系统封禁 | 报错退出，发出去过，之后被系统封了 |

### 发布接口错误码（官方页面列的）

| errcode | 意思 | 怎么办 |
|---|---|---|
| 48001 | api unauthorized，没这个接口的权限 | 不是认证号。草稿没动，去后台点发布 |
| 40002 | invalid argument，参数不合法 | media_id 或 publish_id 抄错了 |
| 40001 | invalid credential，token 失效 | 重跑 |
| 53503 | 草稿未通过发布检查 | 去后台看草稿内容 |
| 53504 | 需前往公众平台官网使用草稿 | 这篇接口发不了，去后台 |
| 53505 | 请手动保存成功后再发表 | 去后台把这篇手动保存一次再发 |

### 结果文件

`<media_id>.publish-result-<时间>.json`，默认写在当前目录，`--out-dir` 可改。里面有 media_id、标题、publish_id、msg_data_id、publish_status 和中文、article_id、article_urls、fail_idx、每次轮询的记录、提交时间。报结果从这里复制，不手抄。

## 错误码速查

| errcode | 意思 | 怎么办 |
|---|---|---|
| 40164 | IP 不在白名单 | errmsg 里的 IP 加进后台白名单 |
| 40013 | AppID 不对 | 重新复制 |
| 40125 | AppSecret 不对或被重置 | 重置后更新配置文件 |
| 40001 | token 失效 | 重跑 |
| 40002 | 参数不合法 | media_id 或 publish_id 写错 |
| 40007 | media_id 不合法 | 推草稿时：先看封面是不是走 material/add_material 传成的永久素材（结果文件里有 thumb_media_id），不是就重传封面再推，是的话就是 media_id 抄错了；发布时：草稿 media_id 抄错了，从最近一份 draft-result 文件重新复制 |
| 45110 | author 太长 | 16 字内；中文如果被转成 \uXXXX 也会超，脚本已按 UTF-8 直传 |
| 45003 | 标题太长 | 32 字内 |
| 45004 | digest 太长 | 120 字内 |
| 45166 | content 不合法 | 正文里有微信不认的标签或属性（script、iframe、外站图片地址、没转义的尖括号），或小绿书 newspic 的正文传了 HTML。先 render 看 HTML，去掉可疑标签再推 |
| 53404 / 53405 | 内容涉嫌违规 / 含敏感内容 | 去后台看具体提示，改稿再推；脚本不改 |
| 45009 | 接口次数到顶 | 明天 |
| 48001 | 没权限 | 看上面「谁能用」；发布接口只有认证号能用 |
| 53503 / 53504 / 53505 | 发布检查没过 / 要去官网用 / 要先手动保存 | 看上面「发布接口错误码」 |

## 本机没有固定 IP（隧道借远程机的 IP）

家里宽带、手机热点的 IP 会变，白名单填不住。办法：白名单只填一台固定 IP 的远程机，本机开一条 ssh 隧道，微信接口的流量从远程机出去，AppSecret 和稿子都不离开本机。

1. 本机开隧道，开着别关：`ssh -N -L 127.0.0.1:8443:api.weixin.qq.com:443 root@远程机IP`
2. `~/.wechat-mp.env` 加一行 `TUNNEL=127.0.0.1:8443`（或环境变量 WECHAT_MP_TUNNEL）
3. 之后 check / push / publish 照常跑。脚本连的是本机 8443，TLS 的 SNI 和证书校验仍按 api.weixin.qq.com，证书对得上，不用关校验。
4. `python wechat_draft.py tunnel --vps root@远程机IP` 打印这三步；配了 TUNNEL 会顺带发一个测试请求，微信回 40013（测试 appid 无效）就说明隧道通了。

2026-10-09 用一台加拿大机实测：隧道开着时 tunnel 子命令回「ok：隧道通」，check 用假凭据回 40013，请求确实从远程机到了微信。走隧道时 40164 的 errmsg 里带的是远程机 IP，白名单填那个。

## 接口做不了的三件事（人去后台点）

标原创、赞赏、评论区置顶。还有：视频塞不进正文，只能后台手动插。

原创和赞赏要在后台草稿里勾好并保存，再说发；发布接口本身没有这两个字段。

## 回读核对标准

标题一致；正文中文无损（UTF-8 解码后正常）；mmbiz 图片数等于上传数；没有长破折号。回读显示乱码不等于存储坏了，别重推，重推会多一篇重复草稿。

## 本技能没有的命令

draft/delete（删草稿）、draft/update（改草稿）、freepublish/delete（删除已发布）、freepublish/batchget（已发布列表）、freepublish/getarticle（已发布图文）。发布只有 publish 一个入口，只在人说「发」之后跑。
