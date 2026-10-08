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
ENV = os.path.join(os.path.expanduser("~"), ".wxrank.env")
LOG = os.path.join(os.path.expanduser("~"), ".wxrank-usage.log")
DAILY_CAP = int(os.environ.get("WXRANK_DAILY_CAP", "300"))
PRICE = {"score": 0, "artlist": 1, "getso": 10, "getsu": 10, "getps": 5, "getrk": 2, "artinfo": 1, "artdata": 5}
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
    # only the first article of each push (idx=1) is the headline; keep order newest first
    rows = []
    spent = 5
    for it in lst[:n]:
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
    a = ap.parse_args()
    if not a.cmd:
        print(__doc__); return
    if a.cmd in ("hot",) and a.date and not re.match(r"^\d{8}$", a.date):
        die("--date 格式 yyyymmdd")
    if a.cmd in ("hot",) and a.month and not re.match(r"^\d{6}$", a.month):
        die("--month 格式 yyyymm")
    if a.cmd in ("posts", "benchmark") and not re.match(r"^[0-9A-Za-z_-]{1,64}$", a.wxid):
        die("--wxid 只认字母数字下划线减号（建议 gh_ 开头的原始ID）")
    key = load_key()
    {"balance": cmd_balance, "hot": cmd_hot, "search": cmd_search, "accounts": cmd_accounts, "posts": cmd_posts, "benchmark": cmd_benchmark, "article": cmd_article}[a.cmd](a, key)


if __name__ == "__main__":
    main()
