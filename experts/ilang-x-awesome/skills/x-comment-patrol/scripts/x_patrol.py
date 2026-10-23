#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""评论巡查：拉自己帖子下的新评论（按水位线只拿新的），把专家写好的回复发出去，推进水位线。只用标准库，复用 x-post 技能的 x_api.py。

脚本不判断回不回、怎么回。它只做三件事：
  python x_patrol.py fetch [--max 300] [--context] [--out pending.json]
        读本机 state.json 的 since_id，调 GET /2/users/{me}/mentions（Owned Reads，0.001 美元一条）按页翻到够为止，
        去掉自己发的和已经回过的，按值得先看的顺序排好（帖下评论优先、再看作者粉丝数、带链接和几个字的垫底），
        写成 pending.json 交给专家判。一条帖几百条回复的号就是为这个场景做的：人看不过来，先拉全、排好、再挑。
        --context 顺带把被回复的那条原帖正文拉回来（0.005 美元一条）。
  python x_patrol.py send --replies replies.json [--pending pending.json] [--max 20] [--dry-run]
        replies.json 是专家写好的 [{"to": "<评论id>", "text": "..."}]，可以是 []（这轮一条都不回）。
        逐条 POST /2/tweets 回复（召唤回复 0.010 美元一条），每条记进 replies.jsonl，
        全部成功后把 since_id 推到这轮拿到的最大 id。回复里不许有链接；一轮最多 --max 条；同一个人一轮最多一条；同一条评论只回一次。
  python x_patrol.py status
        打印水位线、发过回过多少条、今天的花费估算。

x_api.py 要在同一台机器上。找的顺序：环境变量 X_API_PY 指的路径 → 本脚本同目录 → 本技能目录旁边的 ../../x-post/scripts/x_api.py。
Windows 一般是 python，Mac 和 Linux 多半要写 python3。
退出码：0 成功；1 参数或门没过；2 接口报错；3 某条回复发出去没收到回复（水位线没推，先去主页看）。
"""
import argparse
import datetime as _dt
import io
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
_candidates = [os.environ.get("X_API_PY", ""), os.path.join(HERE, "x_api.py"),
               os.path.join(HERE, "..", "..", "x-post", "scripts", "x_api.py")]
for _p in _candidates:
    if _p and os.path.exists(_p):
        sys.path.insert(0, os.path.dirname(os.path.abspath(_p)))
        break
try:
    import x_api as X
except ImportError:
    print("错误：找不到 x_api.py。把 x-post 技能装在同一台机器上，或用环境变量 X_API_PY 指到它的路径。")
    sys.exit(1)

ROUND_MAX = 20


def replied_ids(d):
    return {str(r.get("to")) for r in X.read_log(d, "replies.jsonl") if r.get("status") == "ok" and r.get("to")}


def cmd_fetch(args):
    creds = X.load_credentials()
    d = X.ops_dir()
    st = X.load_state(d)
    me_id = st.get("me_id")
    if not me_id:
        u = X.me(creds)
        me_id = u["id"]
        st.update({"me_id": me_id, "handle": u["username"]})
        X.save_state(d, st)
    since = args.since_id or st.get("since_id")
    rows, newest, pages = X.get_mentions_all(creds, me_id, since, args.max)
    done = replied_ids(d)
    items = [r for r in rows if r.get("author_id") != me_id and r["id"] not in done]
    skipped = len(rows) - len(items)
    cost = len(rows) * X.PRICE["owned_read"]
    items = X.rank_mentions(items)
    if args.context:
        for r in items:
            if r.get("parent_id"):
                p = X.read_post(creds, r["parent_id"])
                r["parent_text"] = p.get("text")
                cost += X.PRICE["read"]
    newest = newest or since
    pending = {"me_id": me_id, "handle": st.get("handle"), "fetched_at": _dt.datetime.now().isoformat(timespec="seconds"),
               "since_id_before": since, "newest_id": newest, "pages": pages, "items": items}
    out = args.out or os.path.join(d, "pending.json")
    io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(pending, ensure_ascii=False, indent=1))
    X.append_log(d, "reads.jsonl", {"kind": "mentions", "n": len(rows), "cost": cost})
    st["last_fetch_at"] = pending["fetched_at"]
    X.save_state(d, st)
    kinds = {k: sum(1 for r in items if r["kind"] == k) for k in ("reply_to_me", "quote", "mention")}
    low = sum(1 for r in items if X.has_url(r.get("text") or "") or len(X.norm_text(r.get("text") or "")) < 6)
    print("拉到 %d 条新提及（翻了 %d 页），去掉自己的和回过的剩 %d 条（跳过 %d）；本轮读约 %.3f 美元。清单：%s" % (len(rows), pages, len(items), skipped, cost, out))
    print("其中：帖下评论 %d、引用 %d、@提及 %d；带链接或只有几个字的 %d 条排在最后。按值得先看的顺序：" % (kinds["reply_to_me"], kinds["quote"], kinds["mention"], low))
    for r in items:
        print("  #%d  %s  @%s(%s粉)  %s  %s" % (r["rank"], r["id"], r.get("username") or r.get("author_id"), r.get("followers") if r.get("followers") is not None else "?", r["kind"], (r.get("text") or "").replace("\n", " ")[:70]))
    if args.max and len(rows) >= args.max:
        print("拉到 --max %d 条就停了，可能还有更早的。这轮处理完（send 推了水位线）再 fetch 一次。" % args.max)
    if not items:
        print("这轮没有要判的。要把水位线推过去：python x_patrol.py send --replies 空列表文件（内容 []）")


def load_replies(path):
    if not os.path.exists(path):
        X.die("回复文件不存在：" + path)
    try:
        rows = json.load(io.open(path, encoding="utf-8"))
    except Exception as e:
        X.die("回复文件不是 JSON：%s" % e)
    if not isinstance(rows, list):
        X.die("回复文件要是列表：[{\"to\": \"<id>\", \"text\": \"...\"}, ...]")
    return rows


def cmd_send(args):
    d = X.ops_dir()
    st = X.load_state(d)
    pend_path = args.pending or os.path.join(d, "pending.json")
    if not os.path.exists(pend_path):
        X.die("先跑 fetch，没有 pending.json：" + pend_path)
    pending = json.load(io.open(pend_path, encoding="utf-8"))
    by_id = {it["id"]: it for it in pending.get("items", [])}
    replies = load_replies(args.replies)
    if len(replies) > args.max:
        X.die("一轮最多回 %d 条，给了 %d 条；挑最值得回的" % (args.max, len(replies)))
    done = replied_ids(d)
    history = [r.get("text", "") for r in X.read_log(d, "replies.jsonl", X.DUP_WINDOW) if r.get("status") == "ok"]
    seen_authors, seen_to, errors, plan = set(), set(), [], []
    for k, r in enumerate(replies, 1):
        to, text = str(r.get("to") or ""), (r.get("text") or "")
        text, warnings = X.normalize(text)
        item = by_id.get(to)
        if not item:
            errors.append("第 %d 条：to=%s 不在这轮的 pending.json 里，只回这轮拉到的" % (k, to)); continue
        if to in seen_to:
            errors.append("第 %d 条：%s 在这个文件里出现了两次，同一条评论只回一次" % (k, to)); continue
        seen_to.add(to)
        if to in done:
            errors.append("第 %d 条：%s 已经回过" % (k, to)); continue
        author = item.get("author_id")
        if author in seen_authors:
            errors.append("第 %d 条：同一个人 @%s 一轮只回一条" % (k, item.get("username"))); continue
        seen_authors.add(author)
        errs = X.gate(text, history, is_reply=True)
        for e in errs:
            errors.append("第 %d 条（回 @%s）：%s" % (k, item.get("username"), e))
        plan.append((to, text, item))
    for e in errors:
        print("  不过：" + e)
    if errors:
        X.die("先把上面的不过项改掉再发")
    print("要回 %d 条，预计 %.3f 美元" % (len(plan), len(plan) * X.PRICE["reply"]))
    if args.dry_run:
        for to, text, item in plan:
            print("--- 回 @%s（%s）\n%s" % (item.get("username"), to, text))
        print("dry-run：没联网，水位线没动。")
        return
    creds = X.load_credentials()
    for to, text, item in plan:
        status, j = X.create_post(creds, text, to)
        rec = {"to": to, "author_id": item.get("author_id"), "username": item.get("username"), "text": text}
        if status == -1:
            X.append_log(d, "replies.jsonl", dict(rec, id=None, status="UNKNOWN", error=j.get("error")))
            print("回 @%s 发出去了但没收到回复：%s。先去主页看这条回复在不在，在就别重发。水位线没推。" % (item.get("username"), j.get("error")))
            sys.exit(3)
        if status not in (200, 201) or "data" not in j:
            X.append_log(d, "replies.jsonl", dict(rec, id=None, status="FAIL", error=X.explain(status, j)))
            X.die("回 @%s 失败：%s。水位线没推，改完再跑 send。" % (item.get("username"), X.explain(status, j)), 2)
        X.append_log(d, "replies.jsonl", dict(rec, id=j["data"]["id"], status="ok"))
        print("  ok 回了 @%s  id=%s" % (item.get("username"), j["data"]["id"]))
        time.sleep(1.5)
    newest = pending.get("newest_id")
    if newest:
        st["since_id"] = str(newest)
    st["last_patrol_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    X.save_state(d, st)
    print("ok：这轮 %d 条回完，水位线推到 %s。" % (len(plan), st.get("since_id")))


def cmd_status(args):
    d = X.ops_dir()
    st = X.load_state(d)
    if not st.get("me_id"):
        print("还没认过身份：先跑 x_api.py check（它会记下 handle、id 和 App 权限）。数据目录：" + d)
        return
    posts = X.read_log(d, "posts.jsonl")
    replies = X.read_log(d, "replies.jsonl")
    reads = X.read_log(d, "reads.jsonl")
    today = _dt.date.today().isoformat()
    tp = [r for r in posts if str(r.get("at", "")).startswith(today) and r.get("status") == "ok"]
    tr = [r for r in replies if str(r.get("at", "")).startswith(today) and r.get("status") == "ok"]
    trd = [r for r in reads if str(r.get("at", "")).startswith(today)]
    write_cost = sum(X.PRICE["post_url"] if X.has_url(r.get("text", "")) else X.PRICE["post"] for r in tp if r.get("via") == "api") + len(tr) * X.PRICE["reply"]
    read_cost = sum(float(r.get("cost") or 0) for r in trd)
    print("账号 @%s  id %s  App 权限 %s  水位线 since_id=%s  上次拉取 %s  上次推水位线 %s" % (
        st.get("handle"), st.get("me_id"), st.get("access_level") or "未知", st.get("since_id"), st.get("last_fetch_at"), st.get("last_patrol_at")))
    print("累计：发 %d 条（接口 %d，手动交出 %d），回 %d 条；今天：发 %d 回 %d 读 %d 次，花费约 %.3f 美元（写 %.3f 加读 %.3f）" % (
        len([r for r in posts if r.get("status") == "ok"]), len([r for r in posts if r.get("via") == "api" and r.get("status") == "ok"]),
        len([r for r in posts if r.get("via") == "intent" and r.get("status") == "handed"]), len([r for r in replies if r.get("status") == "ok"]),
        len(tp), len(tr), len(trd), write_cost + read_cost, write_cost, read_cost))
    print("数据目录：" + d)


def main():
    ap = argparse.ArgumentParser(description="评论巡查：fetch 拉新评论给专家判，send 发专家写好的回复并推水位线，status 看状态")
    sub = ap.add_subparsers(dest="cmd")
    f = sub.add_parser("fetch", help="拉自己帖子下的新评论，写 pending.json")
    f.add_argument("--since-id"); f.add_argument("--max", type=int, default=300, help="这轮最多拉多少条，按页翻到够为止（一页 100 条，0.001 美元一条）"); f.add_argument("--context", action="store_true", help="顺带拉被回复的原帖正文（0.005 美元一条）"); f.add_argument("--out")
    s = sub.add_parser("send", help="发专家写好的回复，全部成功后推水位线")
    s.add_argument("--replies", required=True); s.add_argument("--pending"); s.add_argument("--max", type=int, default=ROUND_MAX); s.add_argument("--dry-run", action="store_true")
    sub.add_parser("status", help="看水位线和花费")
    args = ap.parse_args()
    if args.cmd == "fetch": cmd_fetch(args)
    elif args.cmd == "send": cmd_send(args)
    elif args.cmd == "status": cmd_status(args)
    else: ap.print_help()


if __name__ == "__main__":
    main()
