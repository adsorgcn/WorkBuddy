#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""每日内容清单：拉全部热点源 → 跨平台聚类 → 按方向分组 → 写 data/hot/<日期>.json、data/hot/latest.json、HOT-LIST.md → UPDATES.md 记一行。
顺带管源：候选池（data/source-candidates.json）里能拉到东西又不在清单里的自动加进 sources.json；
连续 7 天拉不到的源自动下线（disabled），下线的源以后每天还探，探通了自动恢复。
只用标准库。本地跑：python scripts/update_hot_list.py [--n 15] [--no-discover]
"""
import argparse, concurrent.futures, datetime, io, json, os, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_SCRIPTS = os.path.join(ROOT, "experts", "ilang-wechat-awesome", "skills", "wechat-topic-hunter", "scripts")
sys.path.insert(0, SKILL_SCRIPTS)
import hot_sources as hs  # noqa: E402

SOURCES = os.path.join(SKILL_SCRIPTS, "sources.json")
CANDS = os.path.join(ROOT, "data", "source-candidates.json")
HEALTH = os.path.join(ROOT, "data", "source-health.json")
HOT_DIR = os.path.join(ROOT, "data", "hot")
HOT_MD = os.path.join(ROOT, "HOT-LIST.md")
UPDATES = os.path.join(ROOT, "UPDATES.md")
GROUPS = ["AI", "科技", "热榜", "财经", "产品", "海外"]
MAX_ADD_PER_DAY = 5
DEAD_AFTER_DAYS = 7
RAW_LATEST = "https://raw.githubusercontent.com/adsorgcn/WorkBuddy/main/data/hot/latest.json"


def jload(p, default):
    if not os.path.exists(p):
        return default
    return json.load(io.open(p, encoding="utf-8"))


def jdump(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def pull_all(srcs, n):
    out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for src, items, note in ex.map(lambda s: hs.pull(s, n), srcs):
            out.append((src, items, note))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=15, help="每源最多取几条")
    ap.add_argument("--no-discover", action="store_true", help="不探候选源")
    a = ap.parse_args()
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    cfg = jload(SOURCES, {"sources": []})
    sources = cfg["sources"]
    health = jload(HEALTH, {})
    changes = {"added": [], "disabled": [], "revived": []}

    # 1 拉现役源
    active = [s for s in sources if not s.get("disabled")]
    results = pull_all(active, a.n)
    for src, items, note in results:
        h = health.setdefault(src["name"], {"fails": 0, "last_ok": None})
        if items:
            h["fails"] = 0; h["last_ok"] = today
        else:
            h["fails"] = h.get("fails", 0) + 1
            if h["fails"] >= DEAD_AFTER_DAYS:
                src["disabled"] = True; src["disabled_on"] = today
                changes["disabled"].append(src["name"])

    # 2 下线的源再探一次，通了就恢复
    for src in sources:
        if src.get("disabled"):
            _, items, _ = hs.pull(src, 5)
            if items:
                src.pop("disabled", None); src.pop("disabled_on", None)
                health.setdefault(src["name"], {})["fails"] = 0
                health[src["name"]]["last_ok"] = today
                changes["revived"].append(src["name"])
                results.append((src, items, "revived"))

    # 3 探候选池，能拉到的自动加
    if not a.no_discover:
        known_urls = {s["url"] for s in sources}
        live_platforms = {s.get("platform") for s in sources if not s.get("disabled")}
        cands = [c for c in jload(CANDS, {"candidates": []})["candidates"]
                 if c["url"] not in known_urls and c.get("platform") not in live_platforms]
        probe = pull_all([{"name": c["name"], "url": c["url"], "type": c.get("type", "json")} for c in cands], 5)
        added = 0
        for (src, items, _), c in zip(probe, cands):
            if len(items) >= 5 and added < MAX_ADD_PER_DAY:
                if c.get("platform") in live_platforms:
                    continue
                new = {"name": c["name"], "url": c["url"], "type": c.get("type", "json"), "group": c.get("group", "热榜"), "platform": c.get("platform"), "added": today}
                sources.append(new); known_urls.add(c["url"]); live_platforms.add(c.get("platform"))
                health[new["name"]] = {"fails": 0, "last_ok": today}
                changes["added"].append(new["name"]); added += 1
                results.append((new, items, "new"))
    cfg["sources"] = sources
    jdump(SOURCES, cfg)
    jdump(HEALTH, health)

    # 4 聚类 + 分组
    entries = []  # (source, title, url, time, group)
    plat_of = {}
    for src, items, _ in results:
        plat_of[src["name"]] = src.get("platform") or src["name"]
        for t, l, d in items:
            entries.append((src["name"], t, l, hs.norm_time(d), src.get("group", "热榜")))
    clusters = hs.cluster([(e[0], e[1], e[2], e[3]) for e in entries])
    grp_of = {(e[0], e[1]): e[4] for e in entries}
    rows = []
    for g in clusters:
        names = sorted(set(plat_of.get(m[0], m[0]) for m in g))
        groups = [grp_of.get((m[0], m[1]), "热榜") for m in g]
        group = max(set(groups), key=groups.count)
        lead = g[0]
        rows.append({"title": lead[1], "url": lead[2] or "", "source": lead[0], "time": lead[3], "group": group,
                     "platforms": len(names), "sources": sorted(set(m[0] for m in g)),
                     "members": [{"source": m[0], "title": m[1], "url": m[2] or ""} for m in g[1:]]})
    by_group = {k: [] for k in GROUPS}
    for r in rows:
        by_group.setdefault(r["group"], []).append(r)
    for k in by_group:
        by_group[k].sort(key=lambda r: (-r["platforms"], r["time"] == "", r["title"]))
        by_group[k] = by_group[k][: a.n]
    hot_now = sorted([r for r in rows if r["platforms"] >= 2], key=lambda r: -r["platforms"])[:20]
    total = sum(len(v) for v in by_group.values())

    out = {"date": today, "generated_at": now, "feed": RAW_LATEST,
           "how_to_use": "这是需求侧：今天各平台在聊什么。供给侧用你自己的 wxrank key 查公众号上这些题读了多少、爆没爆，两边对上才是题。",
           "sources": {"active": len([s for s in sources if not s.get("disabled")]), "total": len(sources), **changes},
           "hot_now": hot_now, "groups": by_group}
    jdump(os.path.join(HOT_DIR, today + ".json"), out)
    jdump(os.path.join(HOT_DIR, "latest.json"), out)

    # 5 人读的清单
    md = ["# 今日内容清单 · %s" % today, "",
          "需求侧：今天各平台在聊什么，%d 个源，每天早上自动拉一次，机器生成。供给侧（公众号上这些题读了多少、爆没爆）用你自己的 wxrank key 查，两边对上才是题。机器可读版 `data/hot/latest.json`。" % out["sources"]["active"], ""]
    if hot_now:
        md += ["## 多个平台同时在聊（%d 组）" % len(hot_now), "", "| 平台数 | 题 | 哪几个源 | 链接 |", "|---|---|---|---|"]
        for r in hot_now:
            md.append("| %d | %s | %s | %s |" % (r["platforms"], r["title"].replace("|", "｜"), "、".join(r["sources"]), r["url"] or "-"))
        md.append("")
    for k in GROUPS:
        lst = by_group.get(k) or []
        if not lst:
            continue
        md += ["## %s（%d 条）" % (k, len(lst)), "", "| 题 | 源 | 平台数 | 时间 | 链接 |", "|---|---|---|---|---|"]
        for r in lst:
            md.append("| %s | %s | %d | %s | %s |" % (r["title"].replace("|", "｜"), r["source"], r["platforms"], r["time"] or "-", r["url"] or "-"))
        md.append("")
    md += ["## 源的变动", "", "- 新增：%s" % ("、".join(changes["added"]) or "无"), "- 下线：%s" % ("、".join(changes["disabled"]) or "无"), "- 恢复：%s" % ("、".join(changes["revived"]) or "无"), "",
           "## 怎么用", "", "把下面这段贴给你的 Agent（WorkBuddy、Claude Code、Codex、CodeBuddy、Hermes 都行）：", "",
           "```", "::ILANG", "[TYPE:command][PROJECT:wechat_awesome][TASK:daily_topics][LANG:zh]", "",
           "::STATE{@FEED, url:%s, what:今天各平台在聊什么 按方向分组 platforms 是几个平台同时在聊}" % RAW_LATEST,
           "::STATE{@USER, niche:<你的品类词 一到三个>}",
           "::OBJECTIVE{daily_topics|pri:OVERRIDE_ALL}",
           "  target: 读 @FEED 挑出跟我品类有关的 5 条 再用 wechat-topic-hunter 技能查每条在公众号上的阅读和分享 给我一份带两边数据的选题清单",
           "  ACCEPT: 5 条 每条有来源 平台数 公众号最高阅读 篇数 还没写爆的标出来",
           "  NON_GOALS: 替我定题 搬运原文 没报价就扣积分", "```", "",
           "生成时间 %s。" % now]
    io.open(HOT_MD, "w", encoding="utf-8", newline="\n").write("\n".join(md) + "\n")

    # 6 UPDATES.md（最新在上）
    line = "- %s：清单 %d 条（%d 个方向），多平台同聊 %d 组；新增源 %s；下线 %s；恢复 %s。" % (
        today, total, len([k for k in GROUPS if by_group.get(k)]), len(hot_now),
        "、".join(changes["added"]) or "无", "、".join(changes["disabled"]) or "无", "、".join(changes["revived"]) or "无")
    head = "# 更新记录（机器每天写一行，发版说明看 GitHub Releases）\n\n"
    old = io.open(UPDATES, encoding="utf-8").read() if os.path.exists(UPDATES) else head
    body = old[len(head):] if old.startswith(head) else old
    body = "\n".join(l for l in body.splitlines() if not l.startswith("- %s：" % today))
    io.open(UPDATES, "w", encoding="utf-8", newline="\n").write(head + line + "\n" + body.lstrip("\n") + ("\n" if body.strip() else ""))
    print(line)
    print("源 %d 个在役 / %d 总" % (out["sources"]["active"], out["sources"]["total"]))


if __name__ == "__main__":
    main()
