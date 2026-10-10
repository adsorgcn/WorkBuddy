#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号选题对标（wxrank 微小榜数据）。你自己的 wxrank key，你自己充值，每次调用都先告诉你要花多少积分。

用法：
  python wxrank_topics.py balance                                   余额（免费）
  python wxrank_topics.py hot --keyword 出海 [--date 20261001 | --month 202610] [--min-read 1000] [--type 科技] [--n 20]
                                                                    离线库里这个词阅读最高的文章（1 积分）
  python wxrank_topics.py search --keyword 出海 [--sort 新|热] [--page 1]   搜一搜文章列表（10 积分）
  python wxrank_topics.py accounts --keyword 出海                   找公众号，拿原始ID 和 biz（10 积分）
  python wxrank_topics.py posts --wxid gh_xxx                       某个号最近一页推文（5 积分）
  python wxrank_topics.py benchmark --wxid gh_xxx [--n 10] [--yes]  对标一个号：最近 N 篇各拉一次阅读在看分享，算阅读中位、爆款倍率、爆款分（5 + 2N 积分，先报价，加 --yes 才扣）
  python wxrank_topics.py article --url "https://mp.weixin.qq.com/s?__biz=..."   一篇文章的阅读 点赞 在看 分享 收藏 赞赏（2 积分，短链多 1 积分）
  python wxrank_topics.py feed [--group AI,热榜] [--keyword 副业,AI] [--n 15] [--hot-only]   读仓库每天自动更新的内容清单（免费 不花积分）
  python wxrank_topics.py direction --keywords 出海,副业,AI写作 [--month 202610]   方向比较：每个词看一次榜 出一张表（每词 1 积分）
  python wxrank_topics.py calendar --keyword 出海 [--n 10] [--per-week 2] [--start 2026-10-14] [--month 202610]   内容清单：清单里挑题 对照榜 排日期（1 积分）

凭据：~/.wxrank.env 一行 KEY=你的key（或环境变量 WXRANK_KEY）。注册和充值 https://data.wxrank.com ，100 积分 = 1 元。
纪律：只读；每天上限 WXRANK_DAILY_CAP 积分（默认 300）；用量记 ~/.wxrank-usage.log；输出不含 key；只用标准库。
口径：wxrank 的数是实时抓的公开数，跟后台会差；爆款倍率 = 单篇阅读 ÷ 该号阅读中位；爆款分 = 阅读 + 3 × 分享（分享比阅读值钱）。只标注数字，选题是你定。
"""
import argparse, datetime, io, json, os, re, statistics, sys, time, urllib.request, urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://data.wxrank.com/weixin/"
FEED_URL = os.environ.get("WECHAT_FEED_URL", "https://raw.githubusercontent.com/adsorgcn/WorkBuddy/main/data/hot/latest.json")
FEED_LOCAL = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))), "data", "hot", "latest.json")
ENV = os.path.join(os.path.expanduser("~"), ".wxrank.env")
LOG = os.path.join(os.path.expanduser("~"), ".wxrank-usage.log")
DAILY_CAP = int(os.environ.get("WXRANK_DAILY_CAP", "300"))
ERR = {1000: "积分不足 或 key 不对（key 错时 wxrank 也回 1000）先核 ~/.wxrank.env 再去 data.wxrank.com 充值",
       1001: "参数为空 或不是公众号文章链接", 1002: "请求失败或文章验证失败 可以重试一次", 1003: "获取失败 可以重试一次",
       1004: "wxrank 服务异常 稍后再试", 1008: "请求太频繁 歇一会再查", 9999: "超过 QPS 上限 歇一秒再查"}
TYPES = "时事 文化 健康 职场 学术 美食 民生 科技 情感 楼市 汽车 幽默 政务 财富 旅行 企业 时尚 美体 教育 体娱 百科 乐活 创业 文摘".split()


def die(msg, code=1):
    print("错误：" + msg); sys.exit(code)


def load_key():
    k = os.environ.get("WXRANK_KEY", "").strip()
    if not k and os.path.exists(ENV):
        for line in io.open(ENV, encoding="utf-8"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                a, b = line.split("=", 1)
                if a.strip().upper() in ("KEY", "WXRANK_KEY"):
                    k = b.strip().strip('"').strip("'")
    if not k:
        die("没找到 wxrank key。注册 https://data.wxrank.com 拿 key，写进 %s 一行 KEY=你的key" % ENV)
    if re.search(r"[\s\"'\\]", k):
        die("key 里有空白或引号，不合法")
    return k


def today():
    return datetime.date.today().isoformat()


def spent_today():
    if not os.path.exists(LOG):
        return 0
    s = 0
    for line in io.open(LOG, encoding="utf-8"):
        parts = line.split()
        if parts and parts[0] == today():
            for p in parts:
                if p.startswith("units="):
                    try: s += int(p[6:])
                    except ValueError: pass
    return s


def logit(cmd, arg, rows, units):
    arg = re.sub(r"\s+", "_", arg)[:80] or "-"
    io.open(LOG, "a", encoding="utf-8").write("%s %s %s %s lines=%d units=%d\n" % (today(), datetime.datetime.now().strftime("%H:%M:%S"), cmd, arg, rows, units))


def gate(units):
    s = spent_today()
    if s + units > DAILY_CAP:
        die("今天的 wxrank 额度到上限了（已用 %d 积分 上限 %d）明天再查，或者设环境变量 WXRANK_DAILY_CAP 调高" % (s, DAILY_CAP), 4)


_last_call = [0.0]


def call(endpoint, body, key):
    # QPS：搜索类每秒 3 个，阅读每秒 10 个；统一隔 0.4 秒
    wait = 0.4 - (time.time() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.time()
    body = dict(body); body["key"] = key
    req = urllib.request.Request(BASE + endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "wechat-topic-hunter/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
    except Exception as e:
        die("连不上 wxrank（%s）稍后再试" % type(e).__name__)
    raw = raw.replace(key, "[key]")
    try:
        j = json.loads(raw)
    except Exception:
        die("wxrank 返回的不是 JSON：" + re.sub(r"\s+", " ", raw)[:120])
    code = j.get("code")
    if code != 0:
        die("wxrank 报错 code %s：%s" % (code, ERR.get(code, "未知错误码")))
    m = re.search(r"(\d+)", str(j.get("msg", "")))
    return j.get("data"), (int(m.group(1)) if m else None)


def clean(s, n=0):
    s = re.sub(r"<[^>]*>", "", str(s if s is not None else ""))
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n] if n else s


def num(v):
    try: return int(float(v))
    except Exception: return 0


def fmt_time(v):
    v = str(v or "")
    if v.isdigit() and len(v) >= 10:
        try: return datetime.datetime.fromtimestamp(int(v[:10])).strftime("%Y-%m-%d %H:%M")
        except Exception: return v
    return v[:16]


def clean_url(u):
    u = u.strip().replace("&amp;", "&")
    if re.search(r"[\s\"'`$\\@]", u):
        die("链接里有空白、引号或特殊字符")
    u = u.split("#")[0]
    u = re.sub(r"^http://", "https://", u)
    if not u.startswith("https://mp.weixin.qq.com/"):
        die("只认 mp.weixin.qq.com 的文章链接")
    return u


def tail(units, bal):
    print("本次 %d 积分｜余额 %s｜今天已用 %d 积分 上限 %d" % (units, ("%d 积分 约 %.2f 元" % (bal, bal / 100)) if bal is not None else "未知", spent_today(), DAILY_CAP))


# ---------- commands ----------
def cmd_balance(a, key):
    _, bal = call("score", {}, key)
    logit("balance", "-", 1, 0)
    print("wxrank 余额 %s 积分 约 %.2f 元｜今天已用 %d 积分 上限 %d" % (bal, (bal or 0) / 100, spent_today(), DAILY_CAP))
    if bal == 0:
        print("余额为 0 也可能是 key 不对，先核 %s" % ENV)


def cmd_hot(a, key):
    body = {"keyword": a.keyword, "content_type": "article"}
    if a.date: body["date"] = a.date
    elif a.month: body["month"] = a.month
    if a.min_read: body["min_read_num"] = a.min_read
    if a.type:
        if a.type not in TYPES: die("分类只认：" + " ".join(TYPES))
        body["wx_type"] = a.type
    gate(1)
    data, bal = call("artlist", body, key)
    lst = (data or {}).get("list") or []
    total = (data or {}).get("total")
    logit("hot", a.keyword, len(lst), 1)
    print("离线库「%s」%s：命中 %s 篇，取阅读最高的 %d 篇，按爆款分（阅读 + 3 × 分享）重排" % (a.keyword, a.date or a.month or "当月", total if total is not None else "?", min(len(lst), a.n)))
    rows = []
    for it in lst[: a.n]:
        rows.append({"read": num(it.get("read_num")), "look": num(it.get("look_num")), "share": num(it.get("share_num")), "words": num(it.get("word_num")),
                     "type": clean(it.get("wx_type")), "biz": clean(it.get("wx_biz")), "time": fmt_time(it.get("pub_time")),
                     "title": clean(it.get("title"), 60), "url": re.sub(r"\s+", "", str(it.get("art_url") or "")), "copyright": clean(it.get("copyright"))})
    for i, r in enumerate(sorted(rows, key=lambda x: x["read"] + 3 * x["share"], reverse=True), 1):
        print("%2d. 爆款分 %6d  阅读 %6d  在看 %4d  分享 %4d  %4d 字  %s  %s  %s" % (i, r["read"] + 3 * r["share"], r["read"], r["look"], r["share"], r["words"], r["type"] or "-", r["time"], r["title"]))
        print("    biz %s  %s" % (r["biz"], r["url"]))
    if not lst:
        print("没命中。换个更宽的词，或者去掉日期用当月（空列表也扣 1 积分）")
    else:
        out = os.path.join(os.getcwd(), "hot-%s-%s.json" % (re.sub(r"[^0-9A-Za-z一-鿿_-]", "", a.keyword)[:20], datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
        io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(rows, ensure_ascii=False, indent=1))
        print("明细已存：" + out + "（biz 可以拿去 accounts 反查原始ID，再用 benchmark 对标）")
    tail(1, bal)


def cmd_search(a, key):
    st = {"新": 2, "热": 4}.get(a.sort, 0)
    gate(10)
    data, bal = call("getso", {"keyword": a.keyword, "sort_type": st, "page": a.page}, key)
    lst = data if isinstance(data, list) else []
    logit("search", a.keyword, len(lst), 10)
    print("搜一搜「%s」排序 %s 第 %d 页：%d 篇" % (a.keyword, a.sort or "不限", a.page, len(lst)))
    for i, it in enumerate(lst, 1):
        print("%2d. %s  %s  %s" % (i, fmt_time(it.get("pub_time")), clean(it.get("wx_name")), clean(it.get("title"), 60)))
        print("    %s" % re.sub(r"\s+", "", str(it.get("art_url") or "")))
    tail(10, bal)


def cmd_accounts(a, key):
    gate(10)
    data, bal = call("getsu", {"keyword": a.keyword, "page": a.page}, key)
    lst = data if isinstance(data, list) else []
    logit("accounts", a.keyword, len(lst), 10)
    print("搜公众号「%s」第 %d 页：%d 个" % (a.keyword, a.page, len(lst)))
    for i, it in enumerate(lst, 1):
        print("%2d. %s  原始ID %s  微信号 %s  简介 %s" % (i, clean(it.get("wx_name")), clean(it.get("wx_user")), clean(it.get("wx_id")), clean(it.get("signature"), 40)))
    tail(10, bal)


def fetch_posts(wxid, key):
    data, bal = call("getps", {"wxid": wxid}, key)
    lst = (data or {}).get("list") or []
    return lst, bal


def cmd_posts(a, key):
    gate(5)
    lst, bal = fetch_posts(a.wxid, key)
    logit("posts", a.wxid, len(lst), 5)
    print("%s 最近一页推文 %d 篇（不翻页）" % (a.wxid, len(lst)))
    for i, it in enumerate(lst, 1):
        print("%2d. %s  idx%s  %s" % (i, fmt_time(it.get("pub_time")), re.search(r"idx=(\d)", str(it.get("art_url") or "")).group(1) if re.search(r"idx=(\d)", str(it.get("art_url") or "")) else "?", clean(it.get("title"), 60)))
        print("    %s" % re.sub(r"\s+", "", str(it.get("art_url") or "")))
    tail(5, bal)


def read_article(url, key):
    data, bal = call("getrk", {"url": url}, key)
    d = data or {}
    return {"read": num(d.get("read_num")), "like": num(d.get("like_num")), "look": num(d.get("look_num")),
            "share": num(d.get("share_num")), "collect": num(d.get("collect_num")), "reward": num(d.get("reward_count"))}, bal


def cmd_article(a, key):
    url = clean_url(a.url)
    units = 2
    if "__biz=" not in url:
        gate(3)
        data, _ = call("artinfo", {"url": url}, key)
        url = clean_url(str((data or {}).get("article_url") or ""))
        units = 3
    else:
        gate(2)
    r, bal = read_article(url, key)
    logit("article", url, 1, units)
    print("阅读 %d  点赞 %d  在看 %d  分享 %d  收藏 %d  赞赏 %d" % (r["read"], r["like"], r["look"], r["share"], r["collect"], r["reward"]))
    if r["read"]:
        print("互动合计 %d 占阅读 %.1f%%（只算比例 不下判断）" % (r["like"] + r["look"] + r["share"] + r["collect"], 100.0 * (r["like"] + r["look"] + r["share"] + r["collect"]) / r["read"]))
    tail(units, bal)


def idx_of(it):
    """art_url 里的 idx=N：1 是每次推送的头条，2 起是次条。"""
    m = re.search(r"idx=(\d)", str(it.get("art_url") or ""))
    return int(m.group(1)) if m else None


def cmd_benchmark(a, key):
    n = max(1, min(a.n, 20))
    units = 5 + 2 * n
    print("对标 %s：拉最近一页推文（5 积分）再给头 %d 篇各拉一次阅读在看分享（%d 积分），合计约 %d 积分 约 %.2f 元" % (a.wxid, n, 2 * n, units, units / 100))
    if not a.yes:
        print("确认就加 --yes 再跑一次。什么都没扣。")
        return
    gate(units)
    lst, bal = fetch_posts(a.wxid, key)
    logit("benchmark-posts", a.wxid, len(lst), 5)
    if not lst:
        print("这个号最近一页没有推文，或原始ID不对（5 积分已扣）"); tail(5, bal); return
    # 只查每次推送的头条（idx=1 或没有 idx 的）：次条不代表这个号的水平，也省积分；顺序保持最新在前
    heads = [it for it in lst if (idx_of(it) or 1) == 1]
    rows = []
    spent = 5
    for it in heads[:n]:
        url = re.sub(r"\s+", "", str(it.get("art_url") or ""))
        try:
            u = clean_url(url)
        except SystemExit:
            continue
        r, bal = read_article(u, key)
        spent += 2
        rows.append({"title": clean(it.get("title"), 60), "time": fmt_time(it.get("pub_time")), "url": u, **r})
    logit("benchmark-reads", a.wxid, len(rows), spent - 5)
    if not rows:
        print("没拉到任何一篇的阅读"); tail(spent, bal); return
    reads = [r["read"] for r in rows]
    med = statistics.median(reads)
    print("%s：最近 %d 篇，阅读中位 %d，最高 %d，爆款倍率 %.1f（最高 ÷ 中位）" % (a.wxid, len(rows), med, max(reads), (max(reads) / med) if med else 0))
    print("按爆款分排（阅读 + 3 × 分享）：")
    for r in sorted(rows, key=lambda x: x["read"] + 3 * x["share"], reverse=True):
        ratio = (r["read"] / med) if med else 0
        flag = "  ← 跑赢本号 %.1f 倍" % ratio if med and ratio >= 2 else ""
        print("  爆款分 %6d  阅读 %6d  在看 %4d  分享 %4d  %s  %s%s" % (r["read"] + 3 * r["share"], r["read"], r["look"], r["share"], r["time"], r["title"], flag))
    print("怎么用：倍率 2 以上的是这个号本身的读者都格外买账的题，看它们的标题公式和角度，不抄标题不搬内容，把你自己的经历、数据、实验揉进去再写。")
    out = os.path.join(os.getcwd(), "benchmark-%s-%s.json" % (re.sub(r"[^0-9A-Za-z_-]", "", a.wxid)[:30], datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps({"wxid": a.wxid, "median_read": med, "rows": rows}, ensure_ascii=False, indent=1))
    print("明细已存：" + out)
    tail(spent, bal)


def load_feed():
    """仓库每天自动更新的内容清单。先读本仓库里的 data/hot/latest.json（在仓库里跑时），没有就从 GitHub raw 拉。"""
    if os.path.exists(FEED_LOCAL):
        try:
            return json.load(io.open(FEED_LOCAL, encoding="utf-8")), FEED_LOCAL
        except Exception:
            pass
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "wechat-topic-hunter/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", errors="replace")), FEED_URL
    except Exception as e:
        die("拉不到仓库清单（%s）。本机能上 GitHub 吗；上不了就直接跑 hot_sources.py 自己拉热点源" % type(e).__name__)


def feed_rows(feed, groups=None, kws=None, hot_only=False, n=15):
    rows = []
    if hot_only:
        for r in feed.get("hot_now", []):
            rows.append(dict(r, group=r.get("group", "")))
    else:
        for g, lst in feed.get("groups", {}).items():
            if groups and g not in groups:
                continue
            rows.extend(lst[:n])
    out = []
    for r in rows:
        r = dict(r)
        r["time"] = r.get("published") or r.get("time") or ""   # 合并组的领头条可能没时间，published 是组里最新的
        out.append(r)
    rows = out
    if kws:
        rows = [r for r in rows if any(k.lower() in r["title"].lower() for k in kws)]
    return rows


def cmd_feed(a, key=None):
    feed, where = load_feed()
    groups = [x.strip() for x in (a.group or "").split(",") if x.strip()] or None
    kws = [x.strip() for x in (a.keyword or "").split(",") if x.strip()] or None
    rows = feed_rows(feed, groups, kws, a.hot_only, a.n)
    print("仓库内容清单 %s（%s）：%d 条%s" % (feed.get("date"), "本地" if where == FEED_LOCAL else "GitHub", len(rows), "，只看多平台同聊" if a.hot_only else ""))
    cur = None
    for r in rows:
        if r.get("group") != cur and not a.hot_only:
            cur = r.get("group"); print("## %s" % cur)
        print("- [%d 个平台] %s | %s | %s | %s" % (r.get("platforms", 1), r["title"], r.get("source", ""), r.get("time") or "--", r.get("url") or "-"))
    print("这是需求侧（今天各平台在聊什么）。供给侧用 hot 看公众号上这个题读了多少、爆没爆，两边对上才是题。免费，没花积分。")


def cmd_direction(a, key):
    words = [w.strip() for w in a.keywords.split(",") if w.strip()]
    if not (2 <= len(words) <= 8):
        die("--keywords 给 2 到 8 个词 逗号隔开")
    gate(len(words))
    table = []
    bal = None
    for w in words:
        body = {"keyword": w, "content_type": "article"}
        if a.month: body["month"] = a.month
        data, bal = call("artlist", body, key)
        lst = (data or {}).get("list") or []
        reads = sorted((num(it.get("read_num")) for it in lst), reverse=True)
        shares = [num(it.get("share_num")) for it in lst]
        top = lst[0] if lst else {}
        table.append({"keyword": w, "total": (data or {}).get("total"), "n": len(reads), "max_read": reads[0] if reads else 0,
                      "median_read": int(statistics.median(reads)) if reads else 0, "over_10w": sum(1 for r in reads if r >= 100000),
                      "max_share": max(shares) if shares else 0, "top_title": clean(top.get("title"), 40), "top_url": re.sub(r"\s+", "", str(top.get("art_url") or ""))})
    logit("direction", ",".join(words), len(table), len(words))
    print("方向比较（%s，每词取离线库阅读最高的一页）：" % (a.month or "当月"))
    print("%-12s %7s %8s %8s %6s %7s  %s" % ("方向词", "命中篇", "最高阅读", "中位阅读", "10万+", "最高分享", "最高那篇"))
    for r in sorted(table, key=lambda x: (x["over_10w"], x["median_read"]), reverse=True):
        print("%-12s %7s %8d %8d %6d %7d  %s" % (r["keyword"], r["total"] if r["total"] is not None else "-", r["max_read"], r["median_read"], r["over_10w"], r["max_share"], r["top_title"]))
    print("怎么看：命中篇多说明有人在写，10万+ 多说明读者在；中位高说明普通一篇也有人看。你的号能不能挤进去，看你有没有独家。数字只标注，方向你定。")
    out = os.path.join(os.getcwd(), "direction-%s.json" % datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(table, ensure_ascii=False, indent=1))
    print("明细已存：" + out)
    tail(len(words), bal)


def plan_dates(start, per_week, n):
    """从 start 起每周 per_week 篇的日期表：第 i 篇在 start 后 round(i*7/per_week) 天，平均下来每周正好 per_week 篇（2 篇/周＝隔 4 天、3 天、4 天…）。"""
    return [start + datetime.timedelta(days=int(i * 7 / per_week + 0.5)) for i in range(n)]


def cmd_calendar(a, key):
    # 参数先核完再扣积分
    kws = [x.strip() for x in a.keyword.split(",") if x.strip()]
    if not kws:
        die("--keyword 至少给一个词")
    if not (1 <= a.per_week <= 7):
        die("--per-week 1 到 7")
    try:
        start = datetime.date.fromisoformat(a.start) if a.start else datetime.date.today() + datetime.timedelta(days=1)
    except ValueError:
        die("--start 要写成 YYYY-MM-DD，例如 2026-10-14")
    feed, where = load_feed()
    rows = feed_rows(feed, None, kws, False, 50)
    if len(rows) < a.n:
        rows += [r for r in feed.get("hot_now", []) if r not in rows]
    rows = rows[: max(a.n, 1)]
    body = {"keyword": kws[0], "content_type": "article"}
    if a.month: body["month"] = a.month
    gate(1)
    data, bal = call("artlist", body, key)
    lst = (data or {}).get("list") or []
    logit("calendar", kws[0], len(lst), 1)
    supply = {"total": (data or {}).get("total"), "max_read": max([num(it.get("read_num")) for it in lst] or [0]),
              "titles": [clean(it.get("title"), 40) for it in lst[:5]]}
    plan = []
    for i, (r, d) in enumerate(zip(rows, plan_dates(start, a.per_week, len(rows))), 1):
        plan.append({"no": i, "date": d.isoformat(), "title": r["title"], "platforms": r.get("platforms", 1), "source": r.get("source", ""), "url": r.get("url", ""), "group": r.get("group", "")})
    print("内容清单「%s」%d 条，从 %s 起每周 %d 篇（需求侧来自仓库清单 %s；供给侧 公众号上「%s」%s 命中 %s 篇 最高阅读 %d）" % (
        kws[0], len(plan), start.isoformat(), a.per_week, feed.get("date"), kws[0], a.month or "当月", supply["total"], supply["max_read"]))
    print("| 序 | 计划日期 | 题 | 平台数 | 来源 | 链接 |")
    print("|---|---|---|---|---|---|")
    for p in plan:
        print("| %d | %s | %s | %d | %s | %s |" % (p["no"], p["date"], p["title"].replace("|", "｜"), p["platforms"], p["source"], p["url"] or "-"))
    print("公众号上读得最多的 5 篇（看角度，不抄）：" + "；".join(supply["titles"]))
    print("每条写之前再用 hot --keyword 题里的核心词 看一次这个题爆没爆（1 积分）；独家栏自己填，没独家的题不建议写。")
    out = os.path.join(os.getcwd(), "calendar-%s-%s.json" % (re.sub(r"[^0-9A-Za-z一-鿿_-]", "", kws[0])[:20], datetime.datetime.now().strftime("%Y%m%d-%H%M%S")))
    io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps({"keyword": kws, "start": start.isoformat(), "per_week": a.per_week, "supply": supply, "plan": plan}, ensure_ascii=False, indent=1))
    print("清单已存：" + out)
    tail(1, bal)


def main():
    ap = argparse.ArgumentParser(description="公众号选题对标（wxrank）")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("balance")
    p = sub.add_parser("hot"); p.add_argument("--keyword", required=True); p.add_argument("--date"); p.add_argument("--month"); p.add_argument("--min-read", type=int, default=0); p.add_argument("--type"); p.add_argument("--n", type=int, default=20)
    p = sub.add_parser("search"); p.add_argument("--keyword", required=True); p.add_argument("--sort", choices=["新", "热"]); p.add_argument("--page", type=int, default=1)
    p = sub.add_parser("accounts"); p.add_argument("--keyword", required=True); p.add_argument("--page", type=int, default=1)
    p = sub.add_parser("posts"); p.add_argument("--wxid", required=True)
    p = sub.add_parser("benchmark"); p.add_argument("--wxid", required=True); p.add_argument("--n", type=int, default=10); p.add_argument("--yes", action="store_true")
    p = sub.add_parser("article"); p.add_argument("--url", required=True)
    p = sub.add_parser("feed"); p.add_argument("--group"); p.add_argument("--keyword"); p.add_argument("--n", type=int, default=15); p.add_argument("--hot-only", action="store_true")
    p = sub.add_parser("direction"); p.add_argument("--keywords", required=True); p.add_argument("--month")
    p = sub.add_parser("calendar"); p.add_argument("--keyword", required=True); p.add_argument("--n", type=int, default=10); p.add_argument("--per-week", type=int, default=2); p.add_argument("--start"); p.add_argument("--month")
    a = ap.parse_args()
    if not a.cmd:
        print(__doc__); return
    if a.cmd in ("hot",) and a.date and not re.match(r"^\d{8}$", a.date):
        die("--date 格式 yyyymmdd")
    if a.cmd in ("hot", "direction", "calendar") and getattr(a, "month", None) and not re.match(r"^\d{6}$", a.month):
        die("--month 格式 yyyymm")
    if a.cmd == "feed":
        cmd_feed(a); return
    if a.cmd in ("posts", "benchmark") and not re.match(r"^[0-9A-Za-z_-]{1,64}$", a.wxid):
        die("--wxid 只认字母数字下划线减号（建议 gh_ 开头的原始ID）")
    key = load_key()
    {"balance": cmd_balance, "hot": cmd_hot, "search": cmd_search, "accounts": cmd_accounts, "posts": cmd_posts, "benchmark": cmd_benchmark, "article": cmd_article,
     "direction": cmd_direction, "calendar": cmd_calendar}[a.cmd](a, key)


if __name__ == "__main__":
    main()
