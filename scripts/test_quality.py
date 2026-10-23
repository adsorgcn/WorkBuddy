#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归用例（门禁 build_packages.py 会跑；本地 python scripts/test_quality.py）。只用标准库，不碰网络，不花积分。
覆盖 2026-10-10 两份外部检测报告指出的点：聚类误合并、时间归一与时区、排序、日程步长、排版、版本号同步、派活流中断、坏源不拖死整轮。"""
import datetime, email.utils, io, os, socket, struct, sys, tempfile, zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "experts", "ilang-wechat-awesome", "skills")
for d in ("wechat-topic-hunter", "wechat-draft-push", "remote-dispatch"):
    sys.path.insert(0, os.path.join(SK, d, "scripts"))
XSK = os.path.join(ROOT, "experts", "ilang-x-awesome", "skills")
for d in ("x-post", "x-topic-hunter", "x-comment-patrol"):
    sys.path.insert(0, os.path.join(XSK, d, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import hot_sources as hs          # noqa: E402
import wxrank_topics as wx        # noqa: E402
import wechat_draft as wd         # noqa: E402
import newspic_cards as nc        # noqa: E402
import x_api as xa                # noqa: E402
import x_feed as xf               # noqa: E402
import x_patrol as xp             # noqa: E402
import dispatch as dp             # noqa: E402
import update_hot_list as uhl     # noqa: E402
import release as rl              # noqa: E402

fails = []
def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else "  " + str(detail)[:200]))
    if not cond:
        fails.append(name)

# ---- 聚类 ----
def same(a, b):
    return hs.same_event(a, b, hs.grams(a), hs.grams(b), 0.42)
check("相反说法不合并 跌破/突破", not same("美光科技总市值跌破万亿美元", "美光科技总市值突破 1 万亿美元"))
check("短名不并进长题 美光科技", not same("美光科技总市值跌破万亿美元", "美光科技"))
check("短名不并进长题 英雄联盟", not same("英雄联盟", "访问移除,英雄联盟将取消OB"))
check("连字符版本不合并 GPT-4/GPT-5", not same("GPT-4 is out", "GPT-5 is out"))
check("数字版本不合并 iPhone 16/17", not same("iPhone 16 发布", "iPhone 17 发布"))
check("点版本不合并 2.0/3.0", not same("产品 X 2.0 发布", "产品 X 3.0 发布"))
check("完全相同必合并 英文", same("Anthropic releases Claude Opus 5.5", "Anthropic releases Claude Opus 5.5"))
check("近似中文题合并", same("马化腾姚顺雨罕见同框", "马化腾姚顺雨同框"))
check("同版本不同写法合并 GPT-5/GPT 5", same("OpenAI launches GPT-5 today", "OpenAI launches GPT 5 today"))
check("英文单词题不并 Apple", not same("Apple", "Apple event today"))
check("不相干的中文不合并", not same("Anthropic 发布报告称 AI 代理成主流", "派早报：苹果发布新品等"))
check("涨跌互现不算相反", not hs.opposite("A股涨跌互现 沪指微涨", "沪指微涨 两市涨跌互现"))

# ---- 时间归一 ----
now = datetime.datetime(2026, 10, 10, 7, 45)
check("22分钟前", hs.norm_time("22分钟前", now) == "10-10 07:23", hs.norm_time("22分钟前", now))
check("16小时前", hs.norm_time("16小时前", now) == "10-09 15:45", hs.norm_time("16小时前", now))
check("只有日期 2026-10-09", hs.norm_time("2026-10-09", now) == "10-09 00:00", hs.norm_time("2026-10-09", now))
check("只有日期 2026-10-9", hs.norm_time("2026-10-9", now) == "10-09 00:00", hs.norm_time("2026-10-9", now))
check("昨天 12:30", hs.norm_time("昨天 12:30", now) == "10-09 12:30", hs.norm_time("昨天 12:30", now))
rfc = "Fri, 09 Oct 2026 23:43:27 GMT"
exp_rfc = email.utils.parsedate_to_datetime(rfc).astimezone().replace(tzinfo=None).strftime("%m-%d %H:%M")
check("RFC2822 换算到本地钟", hs.norm_time(rfc, now) == exp_rfc, (hs.norm_time(rfc, now), exp_rfc))
check("ISO Z 与 RFC2822 同一时刻结果一致", hs.norm_time("2026-10-09T23:43:27Z", now) == exp_rfc, hs.norm_time("2026-10-09T23:43:27Z", now))
exp8 = datetime.datetime(2026, 10, 9, 23, 43, tzinfo=datetime.timezone(datetime.timedelta(hours=8))).astimezone().replace(tzinfo=None).strftime("%m-%d %H:%M")
check("ISO +08:00 换算到本地钟", hs.norm_time("2026-10-09T23:43:27+08:00", now) == exp8, hs.norm_time("2026-10-09T23:43:27+08:00", now))
ts = 1760000000
check("10 位时间戳", hs.norm_time(str(ts), now) == datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M"))
check("认不出的原样截 16 位", hs.norm_time("某天下午", now) == "某天下午")
jan = datetime.datetime(2027, 1, 5, 12, 0)
check("跨年：12-30 是去年", abs(hs.age_hours("12-30 08:00", jan) - 148.0) < 0.01, hs.age_hours("12-30 08:00", jan))
check("newest 不按字符串比", hs.newest(["01-05 12:00", "12-30 08:00"], jan) == "01-05 12:00")
check("age_hours 认不出返回 None", hs.age_hours("2026-9-24") is None)

# ---- 排序 ----
rows = [{"title": "旧的多平台", "platforms": 2, "published": "07-27 14:40"},
        {"title": "新的单平台", "platforms": 1, "published": "10-10 00:00"},
        {"title": "新的多平台", "platforms": 2, "published": "10-09 20:00"},
        {"title": "没时间的", "platforms": 1, "published": ""}]
def age(r):
    a = hs.age_hours(r["published"], now)
    return uhl.FRESH_HOURS if a is None else a
order = [r["title"] for r in sorted(rows, key=lambda r: uhl.sort_key(r, age(r)))]
check("72 小时内的在前、多平台优先、过期垫底", order == ["新的多平台", "新的单平台", "没时间的", "旧的多平台"], order)

# ---- 备用源 ----
res = [({"name": "百度热搜"}, [("a", "", "")], "ok"), ({"name": "百度热搜直连", "fallback_for": "百度热搜"}, [("a", "", "")], "ok"),
       ({"name": "知乎"}, [], "打不开"), ({"name": "知乎直连", "fallback_for": "知乎"}, [("b", "", "")], "ok")]
kept = [s["name"] for s, _, _ in hs.drop_fallbacks(res)]
check("主源有数据时备用源不出现", kept == ["百度热搜", "知乎", "知乎直连"], kept)

# ---- 坏源不拖死整轮 ----
_fetch = hs.fetch
hs.fetch = lambda url, timeout=8: "<html><a href='/x'>标题标题标题</a></html>".encode("utf-8")
try:
    src, items, note = hs.pull({"name": "bad", "url": "https://example.com/", "type": "html", "pattern": "("}, 5)
    check("坏 pattern 只返回解析失败", items == [] and note.startswith("解析失败"), note)
    src, items, note = hs.pull({"name": "nourl", "type": "json"}, 5)
    check("缺 url 只返回配置坏了", items == [] and note.startswith("配置坏了"), note)
finally:
    hs.fetch = _fetch

# ---- 日程 ----
d0 = datetime.date(2026, 10, 14)
gaps = lambda ds: [(b - a).days for a, b in zip(ds, ds[1:])]
check("每周 2 篇＝隔 4 天 3 天", gaps(wx.plan_dates(d0, 2, 5)) == [4, 3, 4, 3], gaps(wx.plan_dates(d0, 2, 5)))
check("每周 5 篇 5 篇都在 7 天内", (wx.plan_dates(d0, 5, 5)[-1] - d0).days < 7)
check("每周 7 篇＝每天", gaps(wx.plan_dates(d0, 7, 4)) == [1, 1, 1])
check("每周 1 篇＝隔 7 天", gaps(wx.plan_dates(d0, 1, 3)) == [7, 7])
check("idx_of", wx.idx_of({"art_url": "https://mp.weixin.qq.com/s?__biz=x&mid=1&idx=2&sn=y"}) == 2 and wx.idx_of({"art_url": "https://mp.weixin.qq.com/s/abc"}) is None)
feed = {"groups": {"AI": [{"title": "t", "published": "10-09 22:51", "time": "", "platforms": 2}]}}
check("feed 没 time 用 published", wx.feed_rows(feed, None, None, False, 5)[0]["time"] == "10-09 22:51")

# ---- 排版 ----
md = """# 标题

## 小节带图 ![alt](https://example.com/x.png)

这里有 `**not bold**` 代码和 **真加粗**。
English paragraph wrapped on
purpose. Second line here
中文接着
写不加空格

| 文档 | 说明 |
|---|---|
| [文档](https://example.com/a) | 第一行 |
| 第二 | 第二行 |
"""
blocks, images, title, warnings = wd.md_to_html(md)
html = "\n".join(blocks)
check("行内代码里的 ** 不排版", "**not bold**" in html and "<strong>not bold</strong>" not in html)
check("代码外的加粗照常", "<strong>真加粗</strong>" in html)
check("标题里的行内图片只留说明", "小节带图 alt" in html and "!alt" not in html and "x.png" not in html)
check("行内图片有提醒", any("行内图片请单独成行" in w for w in warnings), warnings)
check("图片地址不进参考链接", all("x.png" not in u for _, u in wd.CITATIONS), wd.CITATIONS)
check("表头链接只引一次", sum(1 for _, u in wd.CITATIONS if u == "https://example.com/a") == 1, wd.CITATIONS)
check("英文软换行补空格", "wrapped on purpose. Second line here" in html, html[:400])
check("中文软换行不加空格", "中文接着写不加空格" in html)

# ---- 提示块与预览页 ----
blocks, _, _, _ = wd.md_to_html("> [!TIP] 推荐这么做\n> 第一条\n\n> [!CAUTION]\n> 别带 HTML\n\n> 普通引用\n")
check("提示块按类型配色 TIP 绿 带标题", "#2e7d32" in blocks[0] and "#f1f8f2" in blocks[0] and ">推荐这么做</p>" in blocks[0], blocks[0])
check("提示块没写标题用默认名 CAUTION 避坑", "#c62828" in blocks[1] and ">避坑</p>" in blocks[1] and "别带 HTML" in blocks[1], blocks[1])
check("普通引用还是橙色卡 没有标题行", "#ff8f00" in blocks[2] and "普通引用" in blocks[2] and "font-weight:bold" not in blocks[2], blocks[2])
shell = wd.preview_shell("标题<b>", "<p>正文</p>")
check("预览页标题转义 片段原样 390 宽", "标题&lt;b&gt;" in shell and "<p>正文</p>" in shell and "width:390px" in shell)

# ---- 贴图：切页、门、合成 PNG 校验（不开浏览器） ----
pages = nc.split_pages("---\nx: 1\n---\n【第1页】\n封面\n副标题\n\n【第 2 页】\n要点\n- 一\n- 二\n【第三页】\n结尾\n")
check("按【第N页】切页 认空格和中文数字 跳过 YAML 头", [p[0] for p in pages] == ["1", "2", "三"], [p[0] for p in pages])
check("每页第一行是标题 后面是正文行", nc.page_parts(pages[1][1]) == ("要点", ["- 一", "- 二"]), nc.page_parts(pages[1][1]))
check("切页校验过", nc.validate_pages(pages) == [], nc.validate_pages(pages))
check("标记前有内容算错", any("前面有内容" in e for e in nc.validate_pages(nc.split_pages("多出来的\n【第1页】\n封面\n【第2页】\n结尾\n"))))
check("残留标记和长破折号拦住", len(nc.validate_pages(nc.split_pages("【第1页】\n封面 [📝 填]\n【第2页】\n结尾——\n"))) == 2)
check("超过 20 页拦住", any("多于 20" in e for e in nc.validate_pages([("1", ["t"])] * 21)))
txt, w = wd.newspic_text("第一行——\r\n\r\n\r\n\r\n第二行  \n")
check("配文归一 破折号换逗号 空行压缩 去尾空格", txt == "第一行，\n\n第二行" and len(w) == 1, (txt, w))
errs = wd.newspic_gate("标题", "纯文本配文", [__file__])
check("贴图门：非图片文件拦住 其他都过", errs == ["只收 jpg/png：" + __file__], errs)
errs = wd.newspic_gate("", "<b>x</b> [📝 待填]", [])
check("贴图门：空标题 HTML 标记 没图 四条都报", len(errs) == 4, errs)
check("没收到回复才算 UNKNOWN 微信自己的 -1 不算", wd.no_reply({"errcode": -1, "errmsg": "网络请求失败：timeout"}) and not wd.no_reply({"errcode": -1, "errmsg": "system error"}))
def png_bytes(w, h, rows_red):
    raw = b"".join(b"\x00" + (bytes([200, 16, 46] if y < rows_red else [255, 255, 255]) * w) for y in range(h))
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
tmpd = tempfile.mkdtemp(prefix="tq-png-")
io.open(os.path.join(tmpd, "01.png"), "wb").write(png_bytes(nc.W, nc.H, 6))
io.open(os.path.join(tmpd, "02.png"), "wb").write(png_bytes(nc.W, nc.H, 0))
io.open(os.path.join(tmpd, "03.png"), "wb").write(png_bytes(100, 100, 0))
check("PNG 头解析", nc.png_info(os.path.join(tmpd, "02.png")) == (nc.W, nc.H, 8, 2), nc.png_info(os.path.join(tmpd, "02.png")))
check("顶部红条＝放不下 没红条＝放得下", nc.has_overflow_bar(os.path.join(tmpd, "01.png")) and not nc.has_overflow_bar(os.path.join(tmpd, "02.png")))
errs, _ = nc.validate_pngs(tmpd, 4)
check("出图校验：尺寸不对和缺图都报", any("尺寸 100x100" in e for e in errs) and any("第 4 张没出图" in e for e in errs), errs)

# ---- X：加权长度、门、串帖、签名、提及分类、日志、清单过滤（不碰网络） ----
check("加权长度：中文算 2 英文算 1", xa.weighted_len("你好") == 4 and xa.weighted_len("ab") == 2)
check("加权长度：链接按 23", xa.weighted_len("看 https://example.com/a/very/long/path/that/goes/on") == 2 + 1 + 23)
check("加权长度：emoji 算 2", xa.weighted_len("🚀") == 2)
check("链接识别：裸域名算 小数不算", xa.has_url("去 github.com/adsorgcn 看") and xa.has_url("ilang.ai") and not xa.has_url("今天 3.5 版本上线 v2.3.30"))
errs = xa.gate("带标记 [📝 填] 和链接 https://a.co 和破折号——", [])
check("门：标记 链接 破折号 三条都报", len(errs) == 3, errs)
check("门：回复里不放链接", any("回复里不放链接" in e for e in xa.gate("看 https://a.co", [], is_reply=True)))
check("门：相似拒发", any("相似" in e for e in xa.gate("这条帖子讲的是加权长度怎么算的问题", ["这条帖子讲的是加权长度怎么算的问题。"])))
check("门：不相似放行", xa.gate("完全不同的另一条内容，说的是巡查", ["这条帖子讲的是加权长度怎么算的问题"]) == [])
check("门：超 280 拦", any("加权长度" in e for e in xa.gate("字" * 141, [])))
check("串帖按单独一行的 --- 切", xa.split_thread("a\n---\nb\n\n---\n\nc") == ["a", "b", "c"])
t, w = xa.normalize("第一行——\r\n第二行  ")
check("归一：破折号换逗号 去尾空格", t == "第一行，\n第二行" and len(w) == 1, (t, w))
oc = {"API_KEY": "xvz1evFS4wEEPTGEFPHBog", "API_SECRET": "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
      "ACCESS_TOKEN": "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb", "ACCESS_SECRET": "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE"}
hdr = xa.oauth_header("POST", "https://api.twitter.com/1.1/statuses/update.json",
                      {"include_entities": "true", "status": "Hello Ladies + Gentlemen, a signed OAuth request!"}, oc,
                      nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", ts="1318622958")
check("OAuth 1.0a 签名对上官方示例", 'oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"' in hdr, hdr)
_xcall = xa.call
xa.call = lambda method, path, creds, query=None, body=None, timeout=60, fatal=True: (200, {
    "data": [{"id": "2", "text": "回你", "author_id": "u2", "in_reply_to_user_id": "me", "referenced_tweets": [{"type": "replied_to", "id": "1"}]},
             {"id": "3", "text": "引用", "author_id": "u3", "referenced_tweets": [{"type": "quoted", "id": "1"}]},
             {"id": "4", "text": "@me 提一下", "author_id": "u4"}],
    "includes": {"users": [{"id": "u2", "username": "two"}]}, "meta": {"newest_id": "4"}})
try:
    rows, meta = xa.get_mentions(oc, "me")
    check("提及分类 reply_to_me quote mention 带 username 和原帖 id", [r["kind"] for r in rows] == ["reply_to_me", "quote", "mention"] and rows[0]["username"] == "two" and rows[0]["parent_id"] == "1" and meta["newest_id"] == "4", rows)
finally:
    xa.call = _xcall
_pages = [
    (200, {"data": [{"id": "20", "text": "第一页 很长的一条评论说了很多", "author_id": "a", "in_reply_to_user_id": "me"}, {"id": "19", "text": "看 https://x.co/1", "author_id": "b", "in_reply_to_user_id": "me"}],
           "includes": {"users": [{"id": "a", "username": "aa", "public_metrics": {"followers_count": 50}}, {"id": "b", "username": "bb", "public_metrics": {"followers_count": 9000}}]}, "meta": {"newest_id": "20", "next_token": "p2"}}),
    (200, {"data": [{"id": "18", "text": "第二页 另一条评论", "author_id": "c", "in_reply_to_user_id": "me"}, {"id": "17", "text": "赞", "author_id": "d"}],
           "includes": {"users": [{"id": "c", "username": "cc", "public_metrics": {"followers_count": 120000}}]}, "meta": {"newest_id": "18"}}),
]
_calls = []
def _paged(method, path, creds, query=None, body=None, timeout=60, fatal=True):
    _calls.append(dict(query or {}))
    return _pages[1] if (query or {}).get("pagination_token") == "p2" else _pages[0]
xa.call = _paged
try:
    rows, newest, pages = xa.get_mentions_all(oc, "me", None, 300)
    check("提及按 next_token 翻页拉全 newest 取第一页", len(rows) == 4 and pages == 2 and newest == "20" and _calls[1].get("pagination_token") == "p2", (len(rows), pages, newest, _calls))
    ranked = xa.rank_mentions([dict(r) for r in rows])
    check("排序：帖下评论先按粉丝多的 带链接和几个字的垫底", [r["id"] for r in ranked] == ["18", "20", "19", "17"] and ranked[0]["rank"] == 1 and ranked[0]["followers"] == 120000, [(r["id"], r.get("followers")) for r in ranked])
finally:
    xa.call = _xcall
os.environ["X_OPS_DIR"] = tempfile.mkdtemp(prefix="tq-xops-")
xd = xa.ops_dir()
xa.append_log(xd, "replies.jsonl", {"to": "11", "status": "ok", "text": "回过"})
xa.append_log(xd, "replies.jsonl", {"to": "12", "status": "FAIL", "text": "失败"})
check("回过的 id 只算成功的", xp.replied_ids(xd) == {"11"}, xp.replied_ids(xd))
xa.append_log(xd, "posts.jsonl", {"kind": "post", "status": "ok", "text": "a", "via": "api"})
xa.append_log(xd, "posts.jsonl", {"kind": "thread", "status": "ok", "text": "b", "via": "api"})
xa.append_log(xd, "posts.jsonl", {"kind": "reply", "status": "ok", "text": "c", "via": "api"})
check("今天发帖计数只算帖和串帖", xa.today_count(xd) == 2, xa.today_count(xd))
check("禁区：英文整词 BioWare 不拦 Iran 拦", xf.banned_reason("EA closes BioWare") is None and xf.banned_reason("Iran strike plan") == "Iran", (xf.banned_reason("EA closes BioWare"), xf.banned_reason("Iran strike plan")))
check("禁区：中文子串", xf.banned_reason("泽连斯基表示愿意") == "泽连斯基")
check("禁区：英文复数和缩写也拦", xf.banned_reason("tribute to 2 late presidents") is not None and xf.banned_reason("ties with N. Korea") is not None and xf.banned_reason("Kim Jong-un's letter") is not None)
check("禁区：冲突只拦政治语境", xf.banned_reason("今天碰到的一个公共场合的小冲突") is None and xf.banned_reason("巴以冲突升级") == "巴以冲突")
ny = datetime.timezone(datetime.timedelta(hours=-4))
check("清单时间按北京时间算 纽约机器不少算", abs(xf.age_hours("10-22 08:00", datetime.datetime(2026, 10, 22, 0, 0, tzinfo=ny)) - 4) < 0.01, xf.age_hours("10-22 08:00", datetime.datetime(2026, 10, 22, 0, 0, tzinfo=ny)))
xnow = datetime.datetime(2026, 10, 22, 12, 0)
check("清单时间按小时算 跨年往前推", abs(xf.age_hours("10-22 08:00", xnow) - 4) < 0.01 and xf.age_hours("12-30 08:00", datetime.datetime(2027, 1, 2, 8, 0)) == 72.0)
xfeed = {"groups": {"AI": [{"title": "Iran drone AI", "published": "10-22 11:00", "lang": "en", "platforms": 3},
                           {"title": "OpenAI 发新模型", "published": "10-22 10:00", "lang": "zh", "platforms": 2},
                           {"title": "旧闻", "published": "10-18 10:00", "lang": "zh", "platforms": 5},
                           {"title": "我发过的 OpenAI 新模型", "published": "10-22 09:00", "lang": "zh", "platforms": 1}]}}
kept, dropped, total = xf.pick(xfeed, hours=48, n=10, posted=["我发过的 OpenAI 新模型 真不错"], now=xnow)
check("清单过滤：禁区 时效 去重 都拦 剩一条", [r["title"] for r in kept] == ["OpenAI 发新模型"] and len(dropped) == 3 and total == 1, ([r["title"] for r in kept], [w for _, w in dropped], total))

# ---- 版本号同步 ----
txt = "version: 2.3.12\n[VERSION:2.3.10]\n| 2.3.1 |\nv2.3.1 and v2.3.12 and \"version\": \"2.3.1\""
out = rl.vsub(txt, "2.3.1", "2.3.2", ["version: %s", "| %s |", "v%s", '"version": "%s"'])
check("不误伤更长的版本号", "version: 2.3.12" in out and "v2.3.12" in out and "[VERSION:2.3.10]" in out, out)
check("完整匹配的都换", "| 2.3.2 |" in out and "v2.3.2 and" in out and '"version": "2.3.2"' in out, out)
check("正文标签不管旧值都对齐", rl.retag("[VERSION:2.0] x [VERSION:2.3]", "2.3.14") == "[VERSION:2.3.14] x [VERSION:2.3.14]")

# ---- 派活流中断 ----
class FakeResp:
    headers = {"Content-Type": "text/event-stream"}
    def __iter__(self):
        yield b"event: message\n"
        yield b'data: {"content": {"markdown": "part1"}}\n'
        yield b"\n"
        raise socket.timeout("timed out")
_open = dp.urllib.request.urlopen
dp.urllib.request.urlopen = lambda req, timeout=0: FakeResp()
try:
    mds, status, err = dp.read_stream("http://127.0.0.1:1", "pw", 1, "run", 5)
    check("流卡住不抛栈 保留已收到的", mds == ["part1"] and status == "timeout" and "超时" in (err or ""), (mds, status, err))
finally:
    dp.urllib.request.urlopen = _open

total = len([l for l in io.open(__file__, encoding="utf-8") if l.lstrip().startswith("check(")])
if fails:
    print("FAIL %d/%d：%s" % (len(fails), total, "；".join(fails))); sys.exit(1)
print("quality tests passed %d/%d" % (total, total))
