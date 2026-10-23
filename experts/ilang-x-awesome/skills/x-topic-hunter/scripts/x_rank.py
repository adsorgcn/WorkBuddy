#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读 X榜单（xbangdan.com）的公开榜单页，免费，不要 MCP 也不要账号。只用标准库，页面是服务端渲染的 HTML，直接解析。

用法：
  python x_rank.py --board posts   [--n 20]            24 小时最火推文（按每小时曝光）
  python x_rank.py --board words   [--n 20]            话题榜：今天中文区在聊什么，带帖数、人数、曝光、升温还是退烧
  python x_rank.py --board articles [--n 20] [--zone cn|global]   长文榜：近 7 天收藏最多的长文（中文区或海外区）
  python x_rank.py --board global  [--n 20]            海外榜：海外热门推文，点赞 曝光 转发 收藏
  python x_rank.py --board all     [--n 10]            四个榜各取前 N
  加 --json 出 JSON；加 --show-banned 把被禁区初筛拦下的也列出来；--posted 指向本机发帖日志，发过相近的去掉。
禁区初筛和去重复用同目录的 x_feed.py。页面结构变了解析不出来时，脚本会报，让 Agent 直接打开页面读。
对标账号：直接打开 https://xbangdan.com/account/<handle>/ 看，不在本脚本里。
"""
import argparse
import html as _html
import io
import json
import os
import re
import sys
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import x_feed
except ImportError:
    x_feed = None

BASE = "https://xbangdan.com"
BOARDS = {
    "posts": ("/posts/", "24 小时最火推文"),
    "words": ("/words/", "话题榜"),
    "articles": ("/articles/", "长文榜（近 7 天）"),
    "global": ("/global/", "海外榜"),
}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) x-topic-hunter/1.0"}


def die(msg, code=1):
    print("错误：" + msg)
    sys.exit(code)


def fetch(path, timeout=20):
    req = urllib.request.Request(BASE + path, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        die("打不开 %s%s（%s）。本机能上 xbangdan.com 吗；上不了就让 Agent 自己开浏览器读，或读仓库清单" % (BASE, path, type(e).__name__), 2)


def strip(s):
    s = re.sub(r"<[^>]+>", "", s or "")
    return re.sub(r"\s+", " ", _html.unescape(s)).strip()


def num(s):
    """「4.2万」→ 42000，「3千」→ 3000，「1,234」→ 1234，认不出返回 None。"""
    s = strip(s).replace(",", "")
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*(万|千|亿|k|K|w|W)?", s)
    if not m:
        return None
    v = float(m.group(1)); u = m.group(2) or ""
    v *= {"万": 1e4, "w": 1e4, "W": 1e4, "千": 1e3, "k": 1e3, "K": 1e3, "亿": 1e8}.get(u, 1)
    return int(v)


def first(pattern, block, flags=re.S):
    m = re.search(pattern, block, flags)
    return m.group(1) if m else ""


# ---------- 各榜解析 ----------
def parse_posts(h):
    out = []
    for blk in re.split(r'<a class="prow"', h)[1:]:
        head = blk[:400]
        out.append({
            "id": first(r'data-id="(\d+)"', head), "cat": first(r'data-cat="([^"]*)"', head),
            "age_hours": float(first(r'data-age="([\d.]+)"', head) or 0), "url": first(r'href="([^"]+)"', head),
            "text": strip(first(r'<span class="n tw2">(.*?)</span>', blk)),
            "author": strip(first(r'<span class="s-av"[^>]*></span>(.*?)<span class="prow-seen"', blk)),
            "views_per_hour": num(first(r'<span class="v"><b>(.*?)</b>', blk)),
        })
    return [r for r in out if r["id"]]


def parse_words(h):
    out = []
    for blk in re.split(r'<details class="hwe-row', h)[1:]:
        head = blk[:200]
        out.append({
            "cat": first(r'data-c="([^"]*)"', head), "trend": first(r'data-s="([^"]*)"', head),
            "group": strip(first(r'<span class="hwe-wm">(.*?)</span>', blk)),
            "title": strip(first(r'<span class="hwe-t">(.*?)</span>', blk)),
            "summary": strip(first(r'<span class="hwe-s">(.*?)</span>', blk)),
            "meta": strip(first(r'<span class="hwe-m">(.*?)</span>', blk)),
            "views": num(first(r'<span class="hwe-r"><b>(.*?)</b>', blk)),
            "signal": strip(first(r'<span class="hwe-sg[^"]*">(.*?)</span>', blk)),
        })
    return [r for r in out if r["title"]]


def parse_articles(h, zone="cn"):
    out = []
    for blk in re.split(r'<a class="ac t\d"', h)[1:]:
        head = blk[:400]
        z = first(r'data-zone="([^"]*)"', head)
        if zone and z != zone:
            continue
        out.append({
            "zone": z, "age_hours": float(first(r'data-age="([\d.]+)"', head) or 0), "handle": first(r'data-h="([^"]+)"', head),
            "cat": first(r'data-c="([^"]*)"', head), "url": first(r'href="([^"]+)"', head),
            "group": strip(first(r'<span class="ac-c">(.*?)</span>', blk)),
            "title": strip(first(r'<span class="ac-t">(.*?)</span>', blk)),
            "name": strip(first(r'<span class="ac-nm"><b>(.*?)</b>', blk)),
            "views": num(first(r'<span class="ac-nm"><b>.*?</b><i>[^<]*?·\s*(.*?)\s*曝光', blk)),
            "bookmarks": num(first(r'<span class="ac-q">(.*?)</span>', blk)),
            "preview": strip(first(r'<span class="ac-pv">(.*?)</span>', blk))[:120],
        })
    return [r for r in out if r["title"]]


def parse_global(h):
    out = []
    for blk in re.split(r'<tr class="gl2-row"', h)[1:]:
        head = blk[:200]
        tds = dict(re.findall(r'<td class="gc-(\w+)[^"]*"[^>]*>(.*?)</td>', blk, re.S))
        out.append({
            "id": first(r'data-id="(\d+)"', head), "cat": first(r'data-cat="([^"]*)"', head),
            "handle": first(r'href="https://x\.com/([^"/]+)"', blk), "name": strip(first(r'<span class="tc-nm"><b>(.*?)</b>', blk)),
            "sub": strip(first(r'<span class="gl2-sub-t">(.*?)</span>', blk)),
            "text": strip(re.sub(r'<i class="tc-mk[^"]*">.*?</i>', "", first(r'<div class="tc-clamp">(.*?)</div>', blk))),
            "likes": num(tds.get("likes", "")), "views": num(tds.get("views", "")), "rts": num(tds.get("rts", "")), "bookmarks": num(tds.get("bookmarks", "")),
        })
    return [r for r in out if r["id"]]


PARSERS = {"posts": parse_posts, "words": parse_words, "articles": parse_articles, "global": parse_global}


def title_of(r):
    return r.get("title") or r.get("text") or ""


def filter_rows(rows, posted=None, show_banned=False):
    kept, dropped = [], []
    for r in rows:
        t = title_of(r)
        why = x_feed.banned_reason(t) if x_feed else None
        if why:
            r["banned"] = why; dropped.append(r)
            continue
        if posted and x_feed and any(x_feed.similar(t, p) for p in posted):
            r["banned"] = "本机发过相近的"; dropped.append(r)
            continue
        kept.append(r)
    return kept, dropped


def show(board, rows, dropped, n, show_banned):
    label = BOARDS[board][1]
    print("== X榜单 %s（%s%s）：%d 条，禁区和去重拦下 %d 条，显示前 %d" % (label, BASE, BOARDS[board][0], len(rows) + len(dropped), len(dropped), min(n, len(rows))))
    for i, r in enumerate(rows[:n], 1):
        if board == "posts":
            print("%2d. %s曝光/时  %s  %s\n    %s  %.1f 小时前" % (i, fmt(r["views_per_hour"]), r["author"], r["text"][:80], r["url"], r["age_hours"]))
        elif board == "words":
            print("%2d. [%s] %s  %s曝光  %s\n    %s ｜ %s" % (i, r["group"], r["title"], fmt(r["views"]), r["signal"], r["meta"], r["summary"][:90]))
        elif board == "articles":
            print("%2d. [%s] %s  收藏 %s  %s @%s  %s曝光\n    %s" % (i, r["group"], r["title"], fmt(r["bookmarks"]), r["name"], r["handle"], fmt(r["views"]), r["url"]))
        else:
            print("%2d. [%s] %s  赞 %s 曝光 %s 转 %s 藏 %s\n    %s" % (i, r["cat"], r["sub"], fmt(r["likes"]), fmt(r["views"]), fmt(r["rts"]), fmt(r["bookmarks"]), r["text"][:90]))
    if show_banned and dropped:
        print("  被拦的：")
        for r in dropped:
            print("  - %s  ← %s" % (title_of(r)[:60], r.get("banned")))


def fmt(v):
    if v is None:
        return "?"
    return ("%.1f万" % (v / 1e4)) if v >= 1e4 else str(v)


def main():
    ap = argparse.ArgumentParser(description="读 X榜单 公开榜单页：posts / words / articles / global / all")
    ap.add_argument("--board", default="all", choices=list(BOARDS) + ["all"])
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--zone", default="cn", choices=["cn", "global"], help="长文榜看中文区还是海外区")
    ap.add_argument("--posted", help="本机 posts.jsonl，发过相近的去掉")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show-banned", action="store_true")
    a = ap.parse_args()
    boards = list(BOARDS) if a.board == "all" else [a.board]
    posted = x_feed.load_posted(a.posted) if (a.posted and x_feed) else None
    result = {}
    for b in boards:
        h = fetch(BOARDS[b][0])
        rows = parse_articles(h, a.zone) if b == "articles" else PARSERS[b](h)
        if not rows:
            print("== X榜单 %s：页面打开了但一条都没解析出来，页面结构可能变了。让 Agent 直接打开 %s%s 读。" % (BOARDS[b][1], BASE, BOARDS[b][0]))
            result[b] = {"rows": [], "dropped": [], "note": "parse_failed"}
            continue
        kept, dropped = filter_rows(rows, posted, a.show_banned)
        result[b] = {"rows": kept[:a.n], "dropped": [(title_of(r), r.get("banned")) for r in dropped]}
        if not a.json:
            show(b, kept, dropped, a.n, a.show_banned)
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    bad = [b for b in boards if result[b].get("note") == "parse_failed"]
    sys.exit(2 if bad and len(bad) == len(boards) else 0)


if __name__ == "__main__":
    main()
