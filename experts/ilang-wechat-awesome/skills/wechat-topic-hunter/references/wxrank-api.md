# wxrank 公众号接口（本技能用到的）

来源：wxrank（微小榜）showdoc 原文，2026-10-09 抄录并实测。注册、充值、拿 key 都在 https://data.wxrank.com ，100 积分 = 1 元。本技能的脚本只调下面这些端点，只读，key 从用户主目录 .wxrank.env 读。

## 本技能各命令用哪个端点、花多少

| 命令 | 端点 | 积分 |
|---|---|---|
| balance | score | 0 |
| hot | artlist | 1 |
| search | getso | 10 |
| accounts | getsu | 10 |
| posts | getps | 5 |
| benchmark | getps 一次 + getrk 每篇一次 | 5 + 2 × N |
| article | getrk（短链先 artinfo 转长链） | 2（短链 3） |

## artlist 实测返回的字段（2026-10-09）

sn、wx_biz、wx_type、pub_time、title、read_num、like_num、look_num、share_num、word_num、video_num、image_num、qmusic_num、ip_region、copyright、content_type、art_url、pic_url、content（正文片段）、data_update_time。所以看榜一次就能拿到阅读、在看、分享、字数和链接，不用再逐篇查。


通用：域名 `http://data.wxrank.com`（文档全部写 http），key 放请求参数/JSON 体里的 `key` 字段；GET 或 POST（POST 用 `Content-Type: application/json`，推荐 POST，避免 URL 编码问题）；返回 `{"code":0,"msg":"剩余N积分","data":...}`；`code=0` 即扣积分（含返回空列表）；100 积分 = 1 元。通用错误码：1000 积分不足；1002/1003 请求失败或超时请重试；1008 请求频繁；9999 QPS 超上限（搜索类每秒 3 个，getrk 每秒 10 个）。

## score 获取当前剩余积分（免费）
GET `http://data.wxrank.com/weixin/score?key=xxx` → `{"code":0,"msg":"剩余9810积分"}`

## getrk 实时获取公众号文章阅读（0.02 元/次）
POST `/weixin/getrk` body `{"key","url","comment_id"(可选)}`；url 仅支持长链 `https://mp.weixin.qq.com/s?__biz=xxx==&mid=xxx&idx=1&sn=xxx`（短链先用 artinfo 转长链）。
返回 data：read_num 阅读、like_num 点赞、look_num 在看、share_num 分享、collect_num 收藏、reward_count 赞赏、comment_count 留言（传 comment_id 才有）。
错误：1001 链接为空/不是公众号文章链接；1002 文章验证失败；1003 获取失败重试；1004 服务异常；9999 QPS（每秒 10）。

## artdata 实时获取文章数据含阅读（0.05 元/次）
POST `/weixin/artdata` body `{"key","url"}`，url 仅长链。返回 data：biz、mid、idx、sn、article_url、name 公众号名、user_name 原始ID、pub_time、signature、short_link、title、digest、author、province_name、comment_id、copyright_stat、appmsg_bar_data{read_num, like_num, look_num, share_num, collect_num, reward_count, comment_count, original_content_num}。

## artinfo 实时获取公众号文章内容（0.01 元/次）
POST `/weixin/artinfo` body `{"key","url"}`，长链短链都行。返回 data：biz、mid、idx、sn、article_url（长链）、name、user_name（原始ID gh_）、pub_time、signature、title、digest、author、province_name、comment_id、copyright_stat、picture_url_list、正文等。用途之一：短链转长链、拿 comment_id。

## getso 实时获取搜一搜文章列表（0.10 元/次）
POST `/weixin/getso` body `{"key","keyword"(必),"sort_type"(0 不限/2 最新/4 最热),"page"(默认 1)}`。
返回 data 数组：wx_name 公众号名、pub_time、title（含 `<em class="highlight">` 高亮标签）、desc 摘要、art_url 文章链接、pic_url 封面。无总条数，data 为 [] 即最后一页。错误：1001 关键词为空；9999 QPS 每秒 3。

## getsu 实时获取公众号搜索列表（0.10 元/次）
POST `/weixin/getsu` body `{"key","keyword"(必),"page"}`。返回 data 数组：wx_id 微信号、wx_biz、wx_user 原始ID（gh_ 或 wxid_）、wx_name、signature 简介、headImgUrl。data 为 [] 即最后一页。

## getps 实时获取公众号推文列表（0.05 元/次）
POST `/weixin/getps` body `{"key","wxid"(必，微信号或原始ID，建议原始ID gh_ 开头),"cursor"(翻页，24 小时有效)}`。每页 10 次推文，每次推文最多 8 篇（art_url 的 idx 是第几篇）。
返回 data：list[{pub_time, title, sn, art_url, pic_url}]、wxid、cursor。list 为 [] 即最后一页。

## artlist 获取公众号文章列表（离线库，0.01 元/次）
GET/POST `/weixin/artlist` 参数：key；date（yyyymmdd，20230101 至昨日）；month（yyyymm，不传 date 时用，默认当月）；wx_biz；wx_type（24 大类：时事 文化 健康 职场 学术 美食 民生 科技 情感 楼市 汽车 幽默 政务 财富 旅行 企业 时尚 美体 教育 体娱 百科 乐活 创业 文摘）；keyword（搜标题和内容）；min_read_num / max_read_num（含边界，0 不限）；content_type（article 文章 / book 贴图 / note 笔记 / all）；has_image / has_video / has_audio（1/0）；cursor（上一页返回的游标，5 分钟有效，续页只传 key+cursor）。
每页最多 50 条，按阅读数从高到低排。返回 data：cursor、total（匹配总数）、list[{sn, wx_biz, wx_type, pub_time, title, read_num, ...（示例被截断，至少含 read_num、title、wx_biz、pub_time）}]。空列表也计费。同一游标顺序用不要并发。
