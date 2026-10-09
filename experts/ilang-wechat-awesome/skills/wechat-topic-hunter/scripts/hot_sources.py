#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号代写 · 拉热点源。只用标准库，只读公开的 RSS / JSON / 页面，8 秒超时，打不开就跳过。

用法：
  python hot_sources.py                               全部源，每源最多 8 条
  python hot_sources.py --group AI,热榜                只拉某几个方向（AI 科技 热榜 财经 产品 海外）
  python hot_sources.py --n 5 --keyword 公众号,副业     每源 5 条，只留标题含关键词的
  python hot_sources.py --cluster                     跨平台同事件聚一起，标出几个源同时在爆
  python hot_sources.py --words 订阅词.txt              按订阅词文件筛（语法见下）
  python hot_sources.py --json                        机器可读输出

订阅词文件：一行一个词，空行分组。普通词＝命中任一即可；+词＝这组必须含；!词＝这组排除；/正则/＝正则；@数字＝这组最多留几条。
例：
  AI写作
  公众号
  +副业
  !招聘
  @5

输出每条：源 | 时间 | 标题 | 链接。只拿标题和链接当选题线索，不搬正文。
"""
import argparse, concurrent.futures, datetime, html, io, json, math, os, re, sys, time
import urllib.request, urllib.error
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def fetch(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_rss(raw):
    items = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return items
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for it in root.iter("item"):
        t = strip_tags((it.findtext("title") or ""))
        l = (it.findtext("link") or "").strip()
        d = (it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
        if t:
            items.append((t, l, d))
    if not items:
        for e in root.findall(".//a:entry", ns):
            t = strip_tags(e.findtext("a:title", default="", namespaces=ns))
            le = e.find("a:link", ns)
            l = le.get("href") if le is not None else ""
            d = (e.findtext("a:updated", default="", namespaces=ns) or e.findtext("a:published", default="", namespaces=ns)).strip()
            if t:
                items.append((t, l, d))
    return items


def _get(obj, keys):
    """大小写不敏感地按顺序取第一个像样的字符串字段。"""
    low = {str(k).lower(): v for k, v in obj.items()}
    for k in keys:
        v = low.get(k.lower())
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


JUNK = re.compile(r"榜单介绍|上榜规则|登录|注册|VIP|充值|©|^\d{4}-\d{2}-\d{2}$|^https?://")


TIME_KEYS = ("time", "pubDate", "publishDate", "publish_time", "created", "created_at", "createtime", "display_time", "ctime", "pubtime", "updated_at", "date")


def walk_json(obj, out, url_tpl=None, depth=0, ctx=None):
    """从任意 JSON 里捞 {标题, 链接, 时间} 三元组，键名大小写不敏感。url_tpl 用字段值拼链接，如 {contId}；
    ctx 是祖先节点的标量字段，拼链接和取时间时兜底（金十的 id、time 在外层，title 在 data 里）。"""
    if depth > 7:
        return
    ctx = ctx or {}
    if isinstance(obj, dict):
        scal = dict(ctx)
        scal.update({k: v for k, v in obj.items() if isinstance(v, (str, int))})
        t = _get(obj, ("title", "word", "query", "topic", "topic_name", "name", "hotWord", "keyword"))
        if not (t and 4 <= len(t) <= 120):
            t2 = _get(obj, ("text", "content"))
            t = t2 if t2 and 6 <= len(t2) <= 90 else None
        if t and not JUNK.search(t):
            l = _get(obj, ("url", "link", "mobileUrl", "mobil_url", "href", "short_link_v2", "short_link", "shareUrl", "article_url", "appUrl", "pcUrl", "topic_url", "topicUrl", "source_link")) or ""
            if not l and isinstance(obj.get("links"), dict):
                l = next((v for v in obj["links"].values() if isinstance(v, str) and v.startswith("http")), "")
            if not l and isinstance(obj.get("bvid"), str):
                l = "https://www.bilibili.com/video/" + obj["bvid"]
            if not l and url_tpl:
                try:
                    l = url_tpl.format(**scal)
                except Exception:
                    l = ""
            l = html.unescape(l) if l else ""
            if l and not l.startswith("http"):
                l = ""
            d = _get(obj, TIME_KEYS) or _get({k: str(v) for k, v in scal.items()}, TIME_KEYS) or ""
            out.append((strip_tags(t), l, d))
            scal = {}
        for v in obj.values():
            walk_json(v, out, url_tpl, depth + 1, scal)
    elif isinstance(obj, list):
        for v in obj:
            walk_json(v, out, url_tpl, depth + 1, ctx)


def dedupe(items):
    seen, uniq = set(), []
    for it in items:
        if it[0] not in seen:
            seen.add(it[0]); uniq.append(it)
    return uniq


def parse_json(raw, url_tpl=None):
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except Exception:
        return []
    out = []
    walk_json(data, out, url_tpl)
    return dedupe(out)


def parse_js(raw, url_tpl=None):
    s = raw.decode("utf-8", "replace").strip()
    s = re.sub(r"^\s*(var|let|const)\s+\w+\s*=\s*", "", s).rstrip(";").strip()
    return parse_json(s.encode("utf-8"), url_tpl)


def parse_sdata(raw, url_tpl=None):
    s = raw.decode("utf-8", "replace")
    m = re.search(r"<!--s-data:(.*?)-->", s, re.S)
    if not m:
        return []
    return parse_json(m.group(1).encode("utf-8"), url_tpl)


def parse_html(raw, src):
    s = raw.decode("utf-8", "replace")
    pat = src.get("pattern")
    if not pat:
        return []
    base = src.get("base") or re.match(r"https?://[^/]+", src["url"]).group(0)
    items = []
    for m in re.finditer(pat, s, re.S | re.I):
        g = m.groupdict()
        t = strip_tags(g.get("title") or "")
        l = (g.get("href") or "").strip()
        if l.startswith("/"):
            l = base + l
        if 6 <= len(t) <= 120 and not JUNK.search(t):
            items.append((t, l, ""))
    return dedupe(items)


def norm_time(d):
    if not d:
        return ""
    if re.fullmatch(r"\d{10}", d):
        return datetime.datetime.fromtimestamp(int(d)).strftime("%m-%d %H:%M")
    if re.fullmatch(r"\d{13}", d):
        return datetime.datetime.fromtimestamp(int(d) / 1000).strftime("%m-%d %H:%M")
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})", d)
    if m:
        return "%s-%s %s:%s" % (m.group(2), m.group(3), m.group(4), m.group(5))
    try:
        import email.utils
        dt = email.utils.parsedate_to_datetime(d)
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return d[:16]


def pull(src, n):
    t0 = time.time()
    url = src["url"]
    if src.get("cache_bust"):
        url += ("&" if "?" in url else "?") + "%s=%d" % (src["cache_bust"], int(time.time() * 1000))
    try:
        raw = fetch(url)
    except Exception as e:
        return src, [], "打不开 %s" % type(e).__name__
    typ = src.get("type", "rss")
    if typ == "rss":
        items = parse_rss(raw)
    elif typ == "json":
        items = parse_json(raw, src.get("url_tpl"))
    elif typ == "js":
        items = parse_js(raw, src.get("url_tpl"))
    elif typ == "sdata":
        items = parse_sdata(raw, src.get("url_tpl"))
    else:
        items = parse_html(raw, src)
    if src.get("need_link"):
        items = [it for it in items if it[1]]
    return src, items[:n], "%.1fs" % (time.time() - t0)


# ---------- 跨平台同事件聚类（照 beacon 的思路自己写：去数字标点停用字模板词，2-gram 余弦） ----------
STOP = set("的了是在和与及对为被从把这那个吗呢啊吧也都就还又很之其中于上下里外后前")
TEMPLATE = re.compile(r"如何看待|如何评价|怎么看|怎样看待|直击|重磅|突发|官方回应|网友热议|最新消息|刚刚|今日|今天|图集|视频|组图|实探|深度|观察|独家")


def norm_title(t):
    t = TEMPLATE.sub("", t)
    t = re.sub(r"[0-9０-９]+", "", t)
    t = re.sub(r"[^\w一-鿿]+", "", t)
    return "".join(ch for ch in t if ch not in STOP)


def grams(t):
    t = norm_title(t)
    return set(t[i:i + 2] for i in range(len(t) - 1)) if len(t) >= 2 else set()


def cosine(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / math.sqrt(len(a) * len(b))


def cluster(entries, th=0.42):
    """entries: [(source, title, url, time)]。返回 [[entry,...], ...]，按不同源的个数降序。"""
    gs = [grams(e[1]) for e in entries]
    used = [False] * len(entries)
    clusters = []
    for i in range(len(entries)):
        if used[i]:
            continue
        if re.fullmatch(r"[\x00-\x7f]*", entries[i][1]):
            used[i] = True; clusters.append([entries[i]]); continue
        group = [entries[i]]; used[i] = True
        for j in range(i + 1, len(entries)):
            if not used[j] and cosine(gs[i], gs[j]) >= th:
                group.append(entries[j]); used[j] = True
        clusters.append(group)
    clusters.sort(key=lambda g: (-len(set(e[0] for e in g)), -len(g)))
    return clusters


# ---------- 订阅词（照 TrendRadar 的语法自己写一版简化的） ----------
def _valid(g):
    return bool(g and (g["any"] or g["must"] or g["regex"]))


def load_words(path):
    """空行分组；「# 名字」给下一组起名；普通词任一命中；+词 必须含；!词 排除；/正则/；@数字 这组最多留几条。"""
    groups, cur, pending = [], None, None
    for line in io.open(path, encoding="utf-8"):
        s = line.strip()
        if not s or s.startswith("#"):
            if _valid(cur):
                groups.append(cur)
            cur = None
            if s.startswith("#"):
                pending = s.lstrip("#").strip() or None
            continue
        if cur is None:
            cur = {"any": [], "must": [], "exclude": [], "regex": [], "cap": None, "name": pending or s}
            pending = None
        if s.startswith("+"):
            cur["must"].append(s[1:].strip())
        elif s.startswith("!"):
            cur["exclude"].append(s[1:].strip())
        elif s.startswith("@") and s[1:].strip().isdigit():
            cur["cap"] = int(s[1:].strip())
        elif len(s) >= 3 and s.startswith("/") and s.endswith("/"):
            try:
                cur["regex"].append(re.compile(s[1:-1], re.I))
            except re.error:
                pass
        elif "=>" in s:
            continue
        else:
            cur["any"].append(s)
    if _valid(cur):
        groups.append(cur)
    return groups


def match_group(title, g):
    t = title.lower()
    if any(w.lower() in t for w in g["exclude"]):
        return False
    if any(w.lower() not in t for w in g["must"]):
        return False
    if g["any"] or g["regex"]:
        return any(w.lower() in t for w in g["any"]) or any(r.search(title) for r in g["regex"])
    return True


def load_sources(path=None):
    """读 sources.json，跳过 disabled 的源。"""
    cfg = json.load(io.open(path or os.path.join(HERE, "sources.json"), encoding="utf-8"))
    return [s for s in cfg["sources"] if not s.get("disabled")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", help="AI 科技 热榜 财经 产品 海外，逗号隔开")
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--keyword", help="只留标题含这些词的，逗号隔开")
    ap.add_argument("--words", help="订阅词文件")
    ap.add_argument("--cluster", action="store_true", help="跨平台同事件聚一起")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    srcs = load_sources()
    if a.group:
        gs = set(x.strip() for x in a.group.split(","))
        srcs = [s for s in srcs if s.get("group") in gs]
    kws = [k.strip() for k in (a.keyword or "").split(",") if k.strip()]
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for src, items, note in ex.map(lambda s: pull(s, a.n), srcs):
            if kws:
                items = [it for it in items if any(k.lower() in it[0].lower() for k in kws)]
            results.append((src, items, note))
    got = {s["name"] for s, items, _ in results if items}
    results = [(s, items, note) for s, items, note in results
               if not (s.get("fallback_for") and s["fallback_for"] in got)]
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if a.words:
        groups = load_words(a.words)
        entries = [(s["name"], t, l, norm_time(d)) for s, items, _ in results for t, l, d in items]
        out = {}
        for g in groups:
            hits = [e for e in entries if match_group(e[1], g)]
            if g["cap"]:
                hits = hits[:g["cap"]]
            out[g["name"]] = hits
        if a.json:
            print(json.dumps({k: [{"source": s, "title": t, "url": l, "time": d} for s, t, l, d in v] for k, v in out.items()}, ensure_ascii=False, indent=1)); return
        for k, v in out.items():
            print("## 订阅组 %s（%d 条）" % (k, len(v)))
            for s, t, l, d in v:
                print("- %s | %s | %s | %s" % (s, d or "--", t, l or "-"))
            print()
        print("拉取时间 %s。" % now); return

    if a.cluster:
        entries = [(s["name"], t, l, norm_time(d)) for s, items, _ in results for t, l, d in items]
        cl = cluster(entries)
        if a.json:
            print(json.dumps([{"sources": sorted(set(e[0] for e in g)), "items": [{"source": s, "title": t, "url": l, "time": d} for s, t, l, d in g]} for g in cl], ensure_ascii=False, indent=1)); return
        multi = [g for g in cl if len(set(e[0] for e in g)) >= 2]
        print("## 多个源同时在爆（%d 组，按源数排）" % len(multi))
        for g in multi:
            names = sorted(set(e[0] for e in g))
            print("- [%d 个源] %s" % (len(names), g[0][1]))
            for s, t, l, d in g:
                print("    · %s | %s | %s" % (s, t, l or "-"))
        print()
        print("## 单源条目 %d 条（略）" % sum(1 for g in cl if len(set(e[0] for e in g)) < 2))
        print("拉取时间 %s。" % now); return

    total = 0
    if a.json:
        print(json.dumps([{"source": s["name"], "group": s.get("group"), "note": note,
                           "items": [{"title": t, "url": l, "time": norm_time(d)} for t, l, d in items]}
                          for s, items, note in results], ensure_ascii=False, indent=1))
        return
    for s, items, note in results:
        print("## %s（%s，%s）" % (s["name"], s.get("group", ""), note if not items else "%d 条 %s" % (len(items), note)))
        for t, l, d in items:
            total += 1
            print("- %s | %s | %s" % (norm_time(d) or "--", t, l or "-"))
        print()
    print("共 %d 条，拉取时间 %s。只拿标题和角度当选题线索，不搬正文。" % (total, now))


if __name__ == "__main__":
    main()
