#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回归用例（门禁 build_packages.py 会跑；本地 python scripts/test_quality.py）。只用标准库，不碰网络，不花积分。
覆盖 2026-10-10 两份外部检测报告指出的点：聚类误合并、时间归一与时区、排序、日程步长、排版、版本号同步、派活流中断、坏源不拖死整轮。"""
import datetime, email.utils, io, os, socket, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SK = os.path.join(ROOT, "experts", "ilang-wechat-awesome", "skills")
for d in ("wechat-topic-hunter", "wechat-draft-push", "remote-dispatch"):
    sys.path.insert(0, os.path.join(SK, d, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
import hot_sources as hs          # noqa: E402
import wxrank_topics as wx        # noqa: E402
import wechat_draft as wd         # noqa: E402
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
