#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号数据的另一条路：Apify 上的采集器 zen-studio/wechat-official-account-scraper。用你自己的 Apify 令牌，花的是你自己 Apify 账号里的额度。

用法：
  python apify_wechat.py me                                             账号套餐、本期已用、月上限（免费）
  python apify_wechat.py viral [--date 2026-11-25] [--window 3d|7d|30d] [--pages 1] [--category 科技,财经] [--keyword 出海,AI] [--min-boost 0] [--n 30]
                                                                        低粉爆文日榜：小号里阅读远超平时的文章，每条带这个号平时的阅读和倍率
  python apify_wechat.py search --keyword 出海,副业 [--pages 1] [--sort relevance|latest|hot] [--time all|day|week|halfYear]
                                                                        按词搜公众号文章
  python apify_wechat.py metrics --url "<文章链接>[,<文章链接>]"         阅读 点赞 在看 分享 收藏 评论数
  python apify_wechat.py accounts --keyword AI出海 [--pages 1] [--all]   按词找公众号：名称、微信号、原始ID、主体、原创篇数（--all 连视频号小程序一起列）
  python apify_wechat.py history --account <gh_ 原始ID|微信号|号名|这个号任意一篇文章链接> [--pages 1]
                                                                        一个号的历史发文，带头条阅读中位和每篇的倍率
  python apify_wechat.py detail --url "<文章链接>"                       正文、作者、是否原创、发文地区
  python apify_wechat.py comments --url "<文章链接>" [--pages 1]         精选留言
  python apify_wechat.py index --keyword 出海,AI                        微信指数，近 30 天每天的热度
  python apify_wechat.py suggest --keyword 副业,出海                    联想词：微信搜一搜里别人接着这个词在搜什么
  python apify_wechat.py run --op <操作名> [--keyword a,b] [--url u1,u2] [--account x,y] [--link 短链或长链] [--pages N] [--json '{"字段":"值"}']
                                                                        采集器其余操作原样跑，结果存文件。16 个操作名见 references/apify-wechat.md
付费命令都可以加：--max-usd 1.0（这次运行最多花多少美元，到了采集器自己停，默认 1）、--save 结果.json（原始结果落盘）。

凭据：~/.apify.env 一行 TOKEN=你的令牌（或环境变量 APIFY_TOKEN）。没有 Apify 账号先注册：https://www.apify.com?fpr=tqio9f
      （这是我们的推广链接；免费套餐每月有 5 美元额度）。令牌在 https://console.apify.com/settings/integrations 的 Personal API tokens 里建。
纪律：只读；令牌走请求头、不进输出；按条计费的单价和这次的封顶先打印再跑；只用标准库；不填采集器输入里的 feedback 字段。
口径：数字是采集器当场从微信拿的公开数，跟公众号后台会差。爆文榜的倍率 = 这篇阅读 ÷ 这个号近 90 天的阅读基线，是采集器算好的；
      history 的倍率 = 这篇阅读 ÷ 这个号这批头条的阅读中位，是本脚本按微信列表里给的阅读算的。只标注数字，选题是你定。
"""
import argparse, datetime, io, json, os, re, statistics, sys, time, urllib.error, urllib.parse, urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

API = "https://api.apify.com/v2"
ACTOR = "zen-studio~wechat-official-account-scraper"
SIGNUP = "https://www.apify.com?fpr=tqio9f"
TOKENS_PAGE = "https://console.apify.com/settings/integrations"
BILLING_PAGE = "https://console.apify.com/billing"
ENV = os.path.join(os.path.expanduser("~"), ".apify.env")
OPS = ["articleSearch", "accountSearch", "miniProgramSearch", "searchSuggestions", "wechatIndexSearch", "articleDetail", "articleMetrics",
       "articleComments", "articleCommentReplies", "convertArticleLink", "accountBasicInfo", "accountPrincipalInfo", "accountOriginalCount",
       "accountTodayArticles", "accountHistoryArticles", "viralArticles"]
# 采集器页面 2026-11-25 的按条单价（美元，免费档；付费档略低，Starter 档低粉爆文 0.011、找号 0.007、联想词与指数 0.28，档位越高越低）。只用来在跑之前报个数，实际以 Apify 账单为准。
START_FEE = 0.05
UNIT_PRICE = {"viralArticles": 0.012, "articleSearch": 0.006, "accountHistoryArticles": 0.006, "articleMetrics": 0.03, "articleDetail": 0.03,
              "articleComments": 0.003, "articleCommentReplies": 0.025, "wechatIndexSearch": 0.30, "searchSuggestions": 0.30,
              "accountSearch": 0.008, "miniProgramSearch": 0.015, "convertArticleLink": 0.025, "accountBasicInfo": 0.03,
              "accountPrincipalInfo": 0.03, "accountOriginalCount": 0.03, "accountTodayArticles": 0.006}
DONE = ("SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED")


def die(msg, code=1):
    print("错误：" + msg); sys.exit(code)


def decode_env(raw):
    """.apify.env 多半是用户在 Windows 上用记事本或 PowerShell 写的：可能带 BOM，也可能是 UTF-16。都要读得出。"""
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace")
    return raw.decode("utf-8-sig", "replace")


def parse_env(text):
    """从 .apify.env 的内容里取令牌：认 TOKEN / APIFY_TOKEN / APIFY_API_TOKEN 三种写法。"""
    for line in text.replace("\ufeff", "").replace("\x00", "").splitlines():
        line = line.strip()
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            if k.strip().upper() in ("TOKEN", "APIFY_TOKEN", "APIFY_API_TOKEN"):
                return v.strip().strip('"').strip("'")
    return ""


def load_token():
    t = (os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN") or "").strip()
    if not t and os.path.exists(ENV):
        t = parse_env(decode_env(io.open(ENV, "rb").read()))
    if not t:
        die("没找到 Apify 令牌。\n  1 没账号先注册：%s （我们的推广链接；免费套餐每月有 5 美元额度）\n  2 在 %s 的 Personal API tokens 里建一个令牌\n  3 写进 %s 一行 TOKEN=你的令牌（自己写，别贴进对话）" % (SIGNUP, TOKENS_PAGE, ENV))
    if not re.match(r"^[A-Za-z0-9_\-]{20,200}$", t):
        die("令牌格式不对：只能是字母数字下划线减号。检查 %s 里那一行" % ENV)
    return t


def api(tok, method, path, body=None, query=None, timeout=90):
    url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("User-Agent", "wechat-topic-hunter/apify")
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    code = 200
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        code, raw = e.code, e.read()
    except Exception as e:
        die("连不上 api.apify.com（%s）。这是这台机器到 Apify 的网络问题，稍后再试" % type(e).__name__, 3)
    try:
        j = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        die("Apify 返回的不是 JSON（HTTP %s）：%s" % (code, re.sub(r"\s+", " ", raw[:160].decode("utf-8", "replace"))))
    if code >= 400:
        err = (j.get("error") or {}) if isinstance(j, dict) else {}
        if code == 401:
            die("Apify 不认这个令牌（HTTP 401）。去 %s 核对，或重新建一个写进 %s" % (TOKENS_PAGE, ENV))
        die("Apify 报错 HTTP %s %s：%s" % (code, err.get("type") or "", err.get("message") or str(j)[:200]))
    return j


def split_csv(s, limit=50):
    out = [x.strip() for x in re.split(r"[,，]", s or "") if x.strip()]
    if len(out) > limit:
        die("一次最多 %d 个，给了 %d 个" % (limit, len(out)))
    return out


def clean_url(u):
    u = u.strip().replace("&amp;", "&")
    if re.search(r"[\s\"'`$\\@]", u):
        die("链接里有空白、引号或特殊字符：" + u[:60])
    u = re.sub(r"^http://", "https://", u.split("#")[0])
    if not u.startswith("https://mp.weixin.qq.com/"):
        die("只认 mp.weixin.qq.com 的文章链接：" + u[:60])
    return u


def split_urls(s):
    # 链接里本身可能有逗号以外的各种字符，只按逗号后面紧跟 http 的地方切
    return [clean_url(x) for x in re.split(r"[,，]\s*(?=https?://)", s or "") if x.strip()]


def short_url(u):
    """榜单和搜索给的链接带一长串 chksm、scene，打印时只留能打开文章的那几个参数。"""
    u = str(u or "").replace("&amp;", "&").split("#")[0]
    m = re.match(r"^https?://mp\.weixin\.qq\.com/s\?(.+)$", u)
    if not m:
        return re.sub(r"^http://", "https://", u)
    q = urllib.parse.parse_qs(m.group(1), keep_blank_values=True)
    keep = [(k, q[k][0]) for k in ("__biz", "mid", "idx", "sn") if k in q]
    if len(keep) < 4:
        return re.sub(r"^http://", "https://", u)
    return "https://mp.weixin.qq.com/s?" + "&".join("%s=%s" % kv for kv in keep)


def clean(s, n=0):
    s = re.sub(r"<[^>]*>", "", str(s if s is not None else ""))
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:n - 1] + "…") if n and len(s) > n else s


def num(v):
    try: return int(float(v))
    except Exception: return 0


BEIJING = datetime.timezone(datetime.timedelta(hours=8))


def fmt_ts(v):
    """时间戳一律按北京时间显示，机器在哪个时区都一样。"""
    try:
        v = int(float(v))
        return datetime.datetime.fromtimestamp(v, BEIJING).strftime("%Y-%m-%d %H:%M") if v > 0 else ""
    except Exception:
        return str(v or "")[:16]


def region(v):
    """发文地区、留言地区在采集器里是一个对象：国内给省，国外给国家。"""
    if isinstance(v, dict):
        return v.get("province_name") or v.get("country_name") or ""
    return str(v or "")


def split_rows(items):
    """采集器的数据行都带 operation；不带的是它给的通知行（免费次数用完、免费预览暂停、某些条目被跳过）。"""
    rows = [x for x in items if isinstance(x, dict)]
    return [x for x in rows if x.get("operation")], [x for x in rows if not x.get("operation")]


def group_by_target(rows):
    """一次运行可以带多个词、多个号，采集器在每行的 queryTarget 里写它属于哪一个。按出现顺序分组。"""
    order, groups = [], {}
    for r in rows:
        k = str(r.get("queryTarget") or "")
        if k not in groups:
            groups[k] = []; order.append(k)
        groups[k].append(r)
    return [(k, groups[k]) for k in order]


def notice_text(n):
    msg = clean(n.get("message") or json.dumps(n, ensure_ascii=False), 300)
    if n.get("limitReached"):
        return "采集器说：%s\n  这个账号在这个采集器上的免费次数用完了（%s/%s）。在 Apify 后台升级套餐后继续：%s" % (msg, n.get("freeRunsUsed"), n.get("freeRunsLimit"), BILLING_PAGE)
    if n.get("temporarilyUnavailable"):
        return "采集器说：%s\n  这是采集器对免费套餐的临时限制，过一会再试，或在 Apify 后台升级套餐：%s" % (msg, BILLING_PAGE)
    return "采集器说：" + msg


def quote(op, max_usd):
    p = UNIT_PRICE.get(op)
    unit = ("每条约 %s 美元" % p) if p else "每条单价见采集器页面"
    print("报价（2026-11-25 抄的单价，以 Apify 账单为准）：每次运行启动 %s 美元，%s。这次最多花 %.2f 美元，到了采集器自己停。" % (START_FEE, unit, max_usd))


def run_actor(tok, inp, max_usd, timeout_s):
    q = {"waitForFinish": 60, "maxTotalChargeUsd": max_usd, "timeout": timeout_s}
    run = api(tok, "POST", "/acts/%s/runs" % ACTOR, body=inp, query=q).get("data") or {}
    if not run.get("id"):
        die("运行没启动起来：" + json.dumps(run, ensure_ascii=False)[:200])
    t0 = time.time()
    while run.get("status") not in DONE and time.time() - t0 < timeout_s + 60:
        run = api(tok, "GET", "/actor-runs/%s" % run["id"], query={"waitForFinish": 60}).get("data") or run
    if run.get("status") not in DONE:
        die("等了 %d 秒运行还没结束（运行号 %s），去 Apify 后台看它的状态" % (int(time.time() - t0), run.get("id")))
    items = api(tok, "GET", "/datasets/%s/items" % run.get("defaultDatasetId"), query={"clean": "true", "format": "json"})
    if not isinstance(items, list):
        items = []
    if run.get("status") != "SUCCEEDED":
        print("这次运行没成功（%s）：%s" % (run.get("status"), clean(run.get("statusMessage"), 200)))
        print("  多半是采集器或微信那头临时出问题，过一会原样再跑一次。没拿到数据的运行只扣启动费。")
    return run, items


def finish(run, inp, items, save, n_rows):
    """落盘原始结果（如果要），再报这次大约花了多少。"""
    if save:
        keep = {k: run.get(k) for k in ("id", "status", "startedAt", "finishedAt", "statusMessage")}
        io.open(save, "w", encoding="utf-8", newline="\n").write(json.dumps({"input": inp, "run": keep, "items": items}, ensure_ascii=False, indent=1))
        print("原始结果已存：" + save)
    est = estimate_usd(inp.get("operation"), n_rows)
    print("这次拿回 %d 行数据｜%s准数看 Apify 后台这次运行的账，本期总用量跑 me 看。" % (n_rows, ("按单价估约 %.3f 美元｜" % est) if est is not None else ""))


def estimate_usd(op, n_rows):
    """按上面那张单价表估这次花了多少：一次启动费 + 拿回的数据行数 × 这个操作的单价。单价表里没有的操作不估。
    不用 Apify 回的计费数：它刚跑完时会滞后好几秒到一两分钟，当场读不准。"""
    p = UNIT_PRICE.get(op)
    if p is None:
        return None
    return round(START_FEE + max(0, n_rows) * p, 3)


def fetch(tok, a, inp):
    quote(inp["operation"], a.max_usd)
    run, items = run_actor(tok, inp, a.max_usd, a.timeout)
    rows, notices = split_rows(items)
    for n in notices:
        print(notice_text(n))
    if not rows and not notices and run.get("status") == "SUCCEEDED" and run.get("statusMessage"):
        print("采集器说：" + clean(run.get("statusMessage"), 200))   # 跑成功但一行都没有时，它会在这里说原因
    return run, items, rows


# ---------- 低粉爆文榜 ----------
def filter_viral(rows, cats, kws, min_boost):
    out = []
    for r in rows:
        if cats and str(r.get("accountCategory") or "") not in cats:
            continue
        hay = (str(r.get("title") or "") + " " + str(r.get("accountName") or "")).lower()
        if kws and not any(k.lower() in hay for k in kws):
            continue
        if min_boost and float(r.get("boostRatio") or 0) < min_boost:
            continue
        out.append(r)
    return sorted(out, key=lambda r: num(r.get("rank")) or 10 ** 6)


def category_counts(rows):
    c = {}
    for r in rows:
        k = str(r.get("accountCategory") or "").strip() or "未分类"
        c[k] = c.get(k, 0) + 1
    return sorted(c.items(), key=lambda kv: -kv[1])


def cmd_viral(a, tok):
    inp = {"operation": "viralArticles", "rankingWindow": a.window, "maxPages": a.pages}
    if a.date:
        dates = split_csv(a.date)
        if [d for d in dates if not re.match(r"^\d{4}-\d{2}-\d{2}$", d)]:
            die("--date 格式 YYYY-MM-DD，多个用逗号隔开")
        inp["rankingDates"] = dates
    run, items, rows = fetch(tok, a, inp)
    if rows:
        cats, kws = set(split_csv(a.category)), split_csv(a.keyword)
        picked = filter_viral(rows, cats, kws, a.min_boost)
        print("低粉爆文榜 %s 窗口 %s：拿回 %d 条，筛后 %d 条，列前 %d 条" % (rows[0].get("rankingDate") or "", rows[0].get("rankingWindow") or a.window, len(rows), len(picked), min(a.n, len(picked))))
        print("这页的分类：" + "、".join("%s %d" % kv for kv in category_counts(rows)) + "（榜不能按词或分类去取，只能拿回来筛；想要的分类少就加 --pages）")
        for r in picked[:a.n]:
            print("#%s [%s] 阅读 %s｜平时 %s｜倍率 %.1f｜分享 %s｜评论 %s｜%s｜%s" % (r.get("rank"), r.get("accountCategory") or "未分类", num(r.get("read_num")), num(r.get("accountReadBaseline")),
                                                                    float(r.get("boostRatio") or 0), num(r.get("share_count")), num(r.get("comment_count")), clean(r.get("accountName"), 20), clean(r.get("title"), 40)))
            print("    " + short_url(r.get("url")))
        print("阅读显示 100001 的是 10 万加。倍率只是标注，题写不写你定；拿的是题材和角度，不搬正文。")
    finish(run, inp, items, a.save, len(rows))


# ---------- 搜文章 ----------
def cmd_search(a, tok):
    kws = split_csv(a.keyword)
    if not kws:
        die("--keyword 不能为空")
    inp = {"operation": "articleSearch", "keywords": kws, "maxPages": a.pages, "sortBy": a.sort, "publishTime": a.time}
    run, items, rows = fetch(tok, a, inp)
    for kw, mine in group_by_target(rows):
        print("「%s」搜到 %d 篇：" % (kw, len(mine)))
        for r in mine:
            src = r.get("source") if isinstance(r.get("source"), dict) else {}
            print("  %s｜%s｜%s" % (fmt_ts(r.get("timestamp") or r.get("date")), clean(src.get("title"), 20), clean(r.get("title"), 46)))
            print("    " + short_url(r.get("doc_url")))
    if rows:
        print("搜索结果不带阅读数。要看哪篇读了多少，把链接交给 metrics（按篇计费）。")
    finish(run, inp, items, a.save, len(rows))


# ---------- 单篇数据 ----------
def cmd_metrics(a, tok):
    urls = split_urls(a.url)
    if not urls:
        die("--url 不能为空")
    inp = {"operation": "articleMetrics", "articleUrls": urls}
    run, items, rows = fetch(tok, a, inp)
    for r in rows:
        print("阅读 %d｜点赞 %d｜在看 %d｜分享 %d｜收藏 %d｜评论 %d" % (num(r.get("read_num")), num(r.get("old_like_count")), num(r.get("like_count")),
                                                         num(r.get("share_count")), num(r.get("collect_count")), num(r.get("comment_count"))))
        print("    " + short_url(r.get("queryTarget")))
    if rows:
        print("点赞取的是 old_like_count、在看取的是 like_count（微信接口的老叫法）。阅读显示 100001 的是 10 万加。")
    finish(run, inp, items, a.save, len(rows))


# ---------- 找号 ----------
def account_rows(rows, include_all=False):
    """按词搜号的结果里混着视频号、小程序，默认只留公众号（订阅号和服务号都是公众号）。"""
    return [r for r in rows if include_all or str(r.get("accTypeName") or "") in ("公众号", "服务号")]


def cmd_accounts(a, tok):
    kws = split_csv(a.keyword)
    if not kws:
        die("--keyword 不能为空")
    inp = {"operation": "accountSearch", "keywords": kws, "maxPages": a.pages}
    run, items, rows = fetch(tok, a, inp)
    for kw, mine in group_by_target(rows):
        mine = [r for r in mine if r.get("userName")]   # 微信搜索夹带的提示行（如开启位置）没有原始ID，不是账号
        print("「%s」搜到 %d 个账号，其中公众号 %d 个：" % (kw, len(mine), len(account_rows(mine))))
        for r in account_rows(mine, a.all):
            print("  [%s] %s｜微信号 %s｜原始ID %s｜主体 %s｜%s｜%s" % (r.get("accTypeName") or "未知", clean(r.get("nickName") or r.get("title"), 24), r.get("aliasName") or "无", r.get("userName") or "无",
                                                              clean(r.get("principalName"), 24) or "未知", "已认证" if r.get("verified") else "未认证", clean(r.get("originalContentStr"), 16) or "原创数未知"))
            if r.get("signature"):
                print("    " + clean(r.get("signature"), 90))
    if rows:
        print("把原始ID 交给 history，看这个号最近发了什么、哪篇读得多。")
    finish(run, inp, items, a.save, len(rows))


# ---------- 一个号的历史发文 ----------
def parse_reads(desc):
    """历史发文列表里微信给的阅读写在 showDesc 里：Reads: 763、Reads: 92k、Reads: 100k+（中文界面是 阅读 763、阅读 9.2万、阅读 10万+）。
    取成 (整数, 是不是带加号的下限)；认不出给 (None, False)。过万的微信只给到千位，所以是约数。"""
    m = re.search(r"(?:Reads?|阅读)\s*[:：]?\s*([\d.]+)\s*([kKwW万]?)\s*(\+?)", re.sub(r"\s+", " ", str(desc or "")))
    if not m:
        return None, False
    try:
        v = float(m.group(1))
    except ValueError:
        return None, False
    v *= 1000 if m.group(2) in ("k", "K") else (10000 if m.group(2) in ("w", "W", "万") else 1)
    return int(v), bool(m.group(3))


def head_median(rows):
    """这批发文里头条（每次推送的第 1 条，itemIndex 从 1 起，2026-11-26 实测）的阅读中位。次条不代表这个号的水平，不算。少于 3 篇头条不算，给 None。"""
    reads = [parse_reads(r.get("showDesc"))[0] for r in rows if num(r.get("itemIndex")) == 1]
    reads = [x for x in reads if x is not None]
    return int(statistics.median(reads)) if len(reads) >= 3 else None


def cmd_history(a, tok):
    accounts = [clean_url(x) if x.startswith("http") else x for x in split_csv(a.account)]
    if not accounts:
        die("--account 不能为空")
    inp = {"operation": "accountHistoryArticles", "accounts": accounts, "maxPages": a.pages}
    run, items, rows = fetch(tok, a, inp)
    for acc, mine in group_by_target(rows):
        med = head_median(mine)
        print("%s 的历史发文 %d 篇%s：" % (acc[:40], len(mine), ("｜头条阅读中位 %d" % med) if med else ""))
        for r in mine:
            reads, plus = parse_reads(r.get("showDesc"))
            if reads is None:
                tag = clean(r.get("showDesc"), 30)
            else:
                tag = "阅读 %d%s" % (reads, "+" if plus else "") + ("｜倍率 %.1f" % (reads / float(med)) if med else "")
            print("  %s｜第 %s 条｜%s｜%s" % (fmt_ts(r.get("publishTimestamp") or r.get("sendTime")), r.get("itemIndex") or "?", clean(r.get("title"), 44), tag))
            print("    " + short_url(r.get("url") or r.get("contentUrl")))
    if rows:
        print("第 1 条是那次推送的头条。倍率 = 这篇阅读 ÷ 这批头条的阅读中位，2 以上是这个号的读者格外买账的题。")
        print("阅读是微信列表里给的数：过万只到千位，10 万以上只显示 100000+。要准数把链接交给 metrics。")
    finish(run, inp, items, a.save, len(rows))


# ---------- 正文 ----------
def cmd_detail(a, tok):
    urls = split_urls(a.url)
    if not urls:
        die("--url 不能为空")
    inp = {"operation": "articleDetail", "articleUrls": urls}
    run, items, rows = fetch(tok, a, inp)
    for r in rows:
        text = str(r.get("contentText") or "")
        print("《%s》%s｜作者 %s｜%s｜原创 %s｜发文地区 %s｜正文 %d 字" % (clean(r.get("title"), 60), clean(r.get("accountName"), 20), clean(r.get("author"), 16) or "未署名",
                                                         str(r.get("publishTime") or "")[:16], "是" if r.get("isOriginal") else "否", region(r.get("ipRegion")) or "未知", len(text)))
        print("    开头：" + clean(text, 300))
    if rows:
        print("正文只当素材看题材、角度、结构，不搬运、不洗稿。全文加 --save 落盘。")
    finish(run, inp, items, a.save, len(rows))


# ---------- 留言 ----------
def cmd_comments(a, tok):
    urls = split_urls(a.url)
    if not urls:
        die("--url 不能为空")
    inp = {"operation": "articleComments", "articleUrls": urls, "maxPages": a.pages}
    run, items, rows = fetch(tok, a, inp)
    if rows:
        print("留言 %d 条（按点赞从高到低）：" % len(rows))
    for r in sorted(rows, key=lambda r: -num(r.get("like_num"))):
        print("  赞 %d｜%s｜%s｜%s｜回复 %d" % (num(r.get("like_num")), clean(r.get("nick_name"), 14), region(r.get("ip_wording")), clean(r.get("content"), 120), num(r.get("replyTotalCount"))))
    finish(run, inp, items, a.save, len(rows))


# ---------- 微信指数 ----------
def index_stats(points):
    """dataPoints = [{index, timestamp}]，按时间排好后给：最新、最高、最低、平均、近 7 天均值比前 7 天均值的变化（百分比，算不了给 None）。"""
    pts = sorted([p for p in points or [] if isinstance(p, dict)], key=lambda p: num(p.get("timestamp")))
    vals = [num(p.get("index")) for p in pts]
    if not vals:
        return None
    last7, prev7 = vals[-7:], vals[-14:-7]
    change = None
    if len(prev7) == 7 and sum(prev7) > 0:
        change = round(100.0 * (sum(last7) / 7.0 - sum(prev7) / 7.0) / (sum(prev7) / 7.0), 1)
    return {"n": len(vals), "latest": vals[-1], "max": max(vals), "min": min(vals), "avg": int(sum(vals) / len(vals)), "change7": change,
            "tail": [(fmt_ts(p.get("timestamp"))[5:10], num(p.get("index"))) for p in pts[-7:]]}


def cmd_index(a, tok):
    kws = split_csv(a.keyword)
    if not kws:
        die("--keyword 不能为空")
    inp = {"operation": "wechatIndexSearch", "keywords": kws}
    run, items, rows = fetch(tok, a, inp)
    for r in rows:
        s = index_stats(r.get("dataPoints"))
        if not s:
            print("「%s」没拿到指数" % r.get("queryTarget")); continue
        ch = ("近 7 天均值比前 7 天 %+.1f%%" % s["change7"]) if s["change7"] is not None else "数据点不够算周变化"
        print("「%s」微信指数 %d 天：最新 %d｜最高 %d｜最低 %d｜平均 %d｜%s" % (r.get("queryTarget"), s["n"], s["latest"], s["max"], s["min"], s["avg"], ch))
        print("    近 7 天：" + "  ".join("%s %d" % t for t in s["tail"]))
    finish(run, inp, items, a.save, len(rows))


# ---------- 联想词 ----------
def suggestion_words(row):
    """联想词在 suggestions 里，一般是一串字符串；万一是对象就取里面像词的那个字段。"""
    out = []
    for x in row.get("suggestions") or []:
        w = x if isinstance(x, str) else (x.get("word") or x.get("title") or x.get("query") or "") if isinstance(x, dict) else ""
        if clean(w):
            out.append(clean(w))
    return out


def cmd_suggest(a, tok):
    kws = split_csv(a.keyword)
    if not kws:
        die("--keyword 不能为空")
    inp = {"operation": "searchSuggestions", "keywords": kws}
    run, items, rows = fetch(tok, a, inp)
    for r in rows:
        words = suggestion_words(r)
        print("「%s」的联想词 %d 个：%s" % (r.get("queryTarget"), len(words), "、".join(words)))
    if rows:
        print("联想词是微信搜一搜里别人接着这个词在搜的。挑跟品类对得上的当候选题的核心词，再用 index 看热度、用 search 看有没有人写。")
    finish(run, inp, items, a.save, len(rows))


# ---------- 其余操作原样跑 ----------
def run_input(op, keyword, url, account, pages, extra_json, link=None):
    """通用入口的输入：操作名只认那 16 个；--json 里的额外字段原样带上，但不让它改 operation，也不带 feedback（那是给采集器作者留言用的）。"""
    if op not in OPS:
        die("--op 只认这 16 个：" + " ".join(OPS))
    inp = {"operation": op}
    if keyword: inp["keywords"] = split_csv(keyword)
    if url: inp["articleUrls"] = split_urls(url)
    if account: inp["accounts"] = split_csv(account)
    if link: inp["links"] = split_urls(link)
    if pages: inp["maxPages"] = pages
    if extra_json:
        try:
            extra = json.loads(extra_json)
        except Exception as e:
            die("--json 不是合法 JSON：%s" % e)
        if not isinstance(extra, dict):
            die("--json 要是一个对象")
        extra.pop("feedback", None)
        extra.pop("operation", None)
        inp.update(extra)
    return inp


def cmd_run(a, tok):
    inp = run_input(a.op, a.keyword, a.url, a.account, a.pages, a.json, a.link)
    run, items, rows = fetch(tok, a, inp)
    save = a.save or ("apify-%s-%s.json" % (a.op, time.strftime("%Y%m%d-%H%M%S")))
    print("%s 返回 %d 行。" % (a.op, len(rows)))
    if rows:
        print("第一行的字段：" + ", ".join(list(rows[0].keys())[:40]))
    finish(run, inp, items, save, len(rows))


def cmd_me(a, tok):
    me = api(tok, "GET", "/users/me").get("data") or {}
    plan = me.get("plan") or {}
    lim = api(tok, "GET", "/users/me/limits").get("data") or {}
    cyc, cur, lm = lim.get("monthlyUsageCycle") or {}, lim.get("current") or {}, lim.get("limits") or {}
    print("Apify 账号 %s｜套餐 %s｜%s" % (me.get("username"), plan.get("id") or "未知", "付费套餐" if me.get("isPaying") else "免费套餐"))
    print("本期 %s 到 %s｜已用 %.2f 美元｜月上限 %s 美元" % (str(cyc.get("startAt") or "")[:10], str(cyc.get("endAt") or "")[:10], cur.get("monthlyUsageUsd") or 0, lm.get("maxMonthlyUsageUsd")))
    print("额度用到月上限就停。付费套餐可以在 %s 的 Limits 里调上限；免费套餐要继续用就在那里升级。" % BILLING_PAGE)


def main():
    ap = argparse.ArgumentParser(description="公众号数据（Apify 采集器 zen-studio/wechat-official-account-scraper，用你自己的令牌）")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("me")

    def paid(name):
        p = sub.add_parser(name)
        p.add_argument("--max-usd", type=float, default=1.0, help="这次运行最多花多少美元，默认 1")
        p.add_argument("--save", help="原始结果存到这个文件")
        p.add_argument("--timeout", type=int, default=600, help="最多等多少秒，默认 600")
        return p

    p = paid("viral"); p.add_argument("--date"); p.add_argument("--window", choices=["3d", "7d", "30d"], default="7d"); p.add_argument("--pages", type=int, default=1)
    p.add_argument("--category"); p.add_argument("--keyword"); p.add_argument("--min-boost", type=float, default=0); p.add_argument("--n", type=int, default=30)
    p = paid("search"); p.add_argument("--keyword", required=True); p.add_argument("--pages", type=int, default=1)
    p.add_argument("--sort", choices=["relevance", "latest", "hot"], default="relevance"); p.add_argument("--time", choices=["all", "day", "week", "halfYear"], default="all")
    p = paid("metrics"); p.add_argument("--url", required=True)
    p = paid("accounts"); p.add_argument("--keyword", required=True); p.add_argument("--pages", type=int, default=1); p.add_argument("--all", action="store_true", help="连视频号、小程序一起列")
    p = paid("history"); p.add_argument("--account", required=True); p.add_argument("--pages", type=int, default=1)
    p = paid("detail"); p.add_argument("--url", required=True)
    p = paid("comments"); p.add_argument("--url", required=True); p.add_argument("--pages", type=int, default=1)
    p = paid("index"); p.add_argument("--keyword", required=True)
    p = paid("suggest"); p.add_argument("--keyword", required=True)
    p = paid("run"); p.add_argument("--op", required=True); p.add_argument("--keyword"); p.add_argument("--url"); p.add_argument("--account"); p.add_argument("--link"); p.add_argument("--pages", type=int); p.add_argument("--json")
    a = ap.parse_args()
    if not a.cmd:
        print(__doc__); return
    if a.cmd != "me":
        if a.max_usd <= 0:
            die("--max-usd 要大于 0")
        if getattr(a, "pages", None) is not None and not 1 <= a.pages <= 50:
            die("--pages 在 1 到 50 之间")
    tok = load_token()
    {"me": cmd_me, "viral": cmd_viral, "search": cmd_search, "metrics": cmd_metrics, "accounts": cmd_accounts, "history": cmd_history,
     "detail": cmd_detail, "comments": cmd_comments, "index": cmd_index, "suggest": cmd_suggest, "run": cmd_run}[a.cmd](a, tok)


if __name__ == "__main__":
    main()
