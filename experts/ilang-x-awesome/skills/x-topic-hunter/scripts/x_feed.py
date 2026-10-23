#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读仓库每天自动更新的内容清单，按 X 的口径过滤，给选题当免费兜底源。只用标准库。

用法：
  python x_feed.py [--group AI,科技,海外] [--lang en|zh|all] [--hours 48] [--n 10] [--keyword a,b] [--hot-only]
                   [--posted ~/.x-ops/<handle>/posts.jsonl] [--json] [--show-banned]
清单从哪来：在仓库克隆里跑就读本仓库 data/hot/latest.json；不在仓库里就从 GitHub raw 拉（X_FEED_URL 可换）。
过滤顺序：禁区（时政 地缘 选举 战争 宗教 民族，按关键词初筛，专家再判一遍）→ 时效 → 语言 → 关键词 → 和本机发过的去重。
"""
import argparse
import datetime as _dt
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

FEED_URL = os.environ.get("X_FEED_URL", "https://raw.githubusercontent.com/adsorgcn/WorkBuddy/main/data/hot/latest.json")
_up = os.path.abspath(__file__)
for _ in range(6):
    _up = os.path.dirname(_up)
FEED_LOCAL = os.environ.get("X_FEED_PATH") or os.path.join(_up, "data", "hot", "latest.json")

# 禁区初筛：时政 地缘 选举 战争 宗教 民族。宁可多拦，专家看 --show-banned 可以放回来；拦的理由打印出来。
BANNED = [
    "伊朗", "以色列", "哈马斯", "加沙", "真主党", "胡塞", "俄罗斯", "俄军", "乌克兰", "普京", "泽连斯基", "北约", "台海", "两岸", "统一", "朝鲜", "金正恩",
    "选举", "大选", "竞选", "总统", "议会", "国会", "参议院", "众议院", "政党", "民主党", "共和党", "特朗普", "川普", "拜登", "哈里斯", "首相", "总理",
    "战争", "开战", "停火", "和平协议", "导弹", "空袭", "轰炸", "袭击", "武装", "军方", "军事", "国防", "阅兵", "武装冲突", "军事冲突", "边境冲突", "地区冲突", "巴以冲突", "俄乌冲突", "制裁", "政变", "边境", "领土",
    "宗教", "穆斯林", "伊斯兰", "基督", "佛教", "教会", "民族", "种族", "新疆", "西藏", "香港", "示威", "抗议", "游行", "独立", "分裂", "人权", "外交", "国务院", "中办", "国办", "中共中央", "党中央", "关税", "中美", "美伊", "美俄",
    "iran", "israel", "hamas", "gaza", "hezbollah", "houthi", "russia", "ukraine", "putin", "zelensky", "nato", "taiwan strait", "north korea", "n. korea", "kim jong",
    "election", "midterm", "ballot", "president", "senate", "congress", "parliament", "democrat", "republican", "trump", "biden", "prime minister",
    "war", "ceasefire", "missile", "airstrike", "bombing", "military", "troops", "sanction", "coup", "border", "territory",
    "religion", "muslim", "islam", "christian", "church", "ethnic", "racial", "protest", "riot", "tariff", "diplomat", "human rights",
]
def _pat(w):
    """英文按整词匹配（免得 war 拦住 BioWare），允许复数 s/es（presidents 也拦）；中文按子串。"""
    if re.match(r"^[A-Za-z .]+$", w):
        return r"\b" + re.escape(w) + r"(?:s|es)?\b"
    return re.escape(w)


BANNED_RE = re.compile("|".join(_pat(w) for w in BANNED), re.I)


def die(msg, code=1):
    print("错误：" + msg)
    sys.exit(code)


def load_feed():
    if os.path.exists(FEED_LOCAL):
        try:
            return json.load(io.open(FEED_LOCAL, encoding="utf-8")), FEED_LOCAL
        except Exception:
            pass
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "x-topic-hunter/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", errors="replace")), FEED_URL
    except Exception as e:
        die("拉不到仓库清单（%s）。本机能上 GitHub 吗；上不了就让用户装 X榜单 MCP 或手动给素材" % type(e).__name__)


def banned_reason(title):
    m = BANNED_RE.search(title or "")
    return m.group(0) if m else None


BJ = _dt.timezone(_dt.timedelta(hours=8))


def age_hours(published, now=None):
    """清单里的时间是 MM-DD HH:MM 北京时间。本机不管在哪个时区，都换成北京时间来比（纽约的机器不这么算会少算 12 到 13 小时）。
    now 不给就取此刻；给了不带时区的，当作北京时间。按当年算，跨年往前推一年。认不出返回 None。"""
    m = re.match(r"^(\d{2})-(\d{2}) (\d{2}):(\d{2})$", published or "")
    if not m:
        return None
    if now is None:
        now = _dt.datetime.now(BJ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=BJ)
    else:
        now = now.astimezone(BJ)
    try:
        t = _dt.datetime(now.year, int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), tzinfo=BJ)
    except ValueError:
        return None
    if t > now + _dt.timedelta(days=1):
        t = t.replace(year=now.year - 1)
    return (now - t).total_seconds() / 3600.0


def norm(s):
    return re.sub(r"[\s\W_]+", "", (s or "").lower())


def bigrams(s):
    return set(s[i:i + 2] for i in range(len(s) - 1)) if len(s) > 1 else {s}


def similar(a, b, threshold=0.6):
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b or (len(a) >= 8 and (a in b or b in a)):
        return True
    ga, gb = bigrams(a), bigrams(b)
    return len(ga & gb) / float(len(ga | gb)) >= threshold


def load_posted(path):
    if not path or not os.path.exists(path):
        return []
    out = []
    for line in io.open(path, encoding="utf-8"):
        try:
            r = json.loads(line)
            if r.get("text"):
                out.append(r["text"])
        except Exception:
            pass
    return out


def pick(feed, groups=None, lang="all", hours=48, n=10, kws=None, hot_only=False, posted=None, now=None):
    """返回 (入选, 被拦的[(row, reason)])。"""
    rows = []
    if hot_only:
        rows = [dict(r) for r in feed.get("hot_now", [])]
    else:
        for g, lst in (feed.get("groups") or {}).items():
            if groups and g not in groups:
                continue
            rows.extend(dict(r) for r in lst)
    kept, dropped = [], []
    for r in rows:
        title = r.get("title") or ""
        why = banned_reason(title)
        if why:
            dropped.append((r, "禁区：" + why)); continue
        a = age_hours(r.get("published") or r.get("time") or "", now)
        if hours and a is not None and a > hours:
            dropped.append((r, "超过 %d 小时" % hours)); continue
        if lang != "all" and (r.get("lang") or "zh") != lang:
            dropped.append((r, "语言 " + str(r.get("lang")))); continue
        if kws and not any(k.lower() in title.lower() for k in kws):
            dropped.append((r, "没命中关键词")); continue
        if posted and any(similar(title, p) for p in posted):
            dropped.append((r, "本机发过相近的")); continue
        r["age_hours"] = None if a is None else round(a, 1)
        kept.append(r)
    kept.sort(key=lambda r: (-(r.get("platforms") or 1), r.get("age_hours") if r.get("age_hours") is not None else 999))
    return kept[:n], dropped, len(kept)


def main():
    ap = argparse.ArgumentParser(description="读仓库每日清单，按 X 口径过滤（禁区、时效、语言、去重）")
    ap.add_argument("--group", help="逗号分隔，默认全部：AI,科技,热榜,财经,产品,海外,热搜词")
    ap.add_argument("--lang", default="all", choices=["en", "zh", "all"])
    ap.add_argument("--hours", type=int, default=48, help="只要这么多小时内的，0 不限")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--keyword")
    ap.add_argument("--hot-only", action="store_true", help="只看多平台同聊的")
    ap.add_argument("--posted", help="本机 posts.jsonl，发过相近的去掉")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--show-banned", action="store_true", help="把被拦的也打印出来，带理由")
    a = ap.parse_args()
    feed, where = load_feed()
    groups = [x.strip() for x in (a.group or "").split(",") if x.strip()] or None
    kws = [x.strip() for x in (a.keyword or "").split(",") if x.strip()] or None
    kept, dropped, total = pick(feed, groups, a.lang, a.hours, a.n, kws, a.hot_only, load_posted(a.posted))
    if a.json:
        print(json.dumps({"date": feed.get("date"), "from": where, "passed": total, "kept": kept, "dropped": [(r.get("title"), why) for r, why in dropped]}, ensure_ascii=False, indent=1))
        return
    print("仓库内容清单 %s（%s）：通过 %d 条，显示前 %d 条，拦下 %d 条（禁区 %d）" % (feed.get("date"), "本地" if where == FEED_LOCAL else "GitHub", total, len(kept), len(dropped), sum(1 for _, w in dropped if w.startswith("禁区"))))
    for r in kept:
        print("- [%s] %s  %s  %d平台  %s\n  %s" % (r.get("group"), r.get("published") or r.get("time") or "", r.get("lang"), r.get("platforms") or 1, r.get("title"), r.get("url")))
    if a.show_banned:
        print("\n被拦的：")
        for r, why in dropped:
            print("- %s  ← %s" % ((r.get("title") or "")[:60], why))


if __name__ == "__main__":
    main()
