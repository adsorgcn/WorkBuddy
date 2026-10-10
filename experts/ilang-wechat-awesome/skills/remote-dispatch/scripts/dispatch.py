#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""remote-dispatch: 把一段命令块派给远程机上的 CodeBuddy Code 网关跑，收回结果。只用标准库。

配置文件 ~/.dispatch.json（用户自己写，脚本只读）：
{
  "default": "vps",
  "remotes": {
    "vps": {"url": "http://1.2.3.4:8080", "password": "网关口令"}
  }
}

命令：
  python dispatch.py list                         列出配置的远程机并探活
  python dispatch.py send --file 块.md [--to vps] [--timeout 900] [--max-wait 3600]
  python dispatch.py send --text "一句话" [--to vps]
  python dispatch.py sessions [--to vps] [--n 5]  远程最近的会话
  python dispatch.py history --session <id> [--to vps]
  python dispatch.py cancel --run <runId> [--to vps]

网关的三个硬规矩（实测）：请求头带 X-CodeBuddy-Request: 1、Authorization: Bearer 口令、Host: localhost:<端口>；
正文 UTF-8；结果要在跑的时候挂 /runs/{id}/stream 收，跑完再挂就没了（脚本会自动回退到会话历史）。
"""
import socket
import argparse, datetime, io, json, os, re, sys, time, uuid
import urllib.request, urllib.error
from urllib.parse import urlparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

CFG = os.path.expanduser("~/.dispatch.json")
LOGDIR = os.path.expanduser("~/dispatch-logs")
VIA_NOTE = "::NOTE{via:remote-dispatch 这段是本机派活技能一次性发来的 没人会回答你的追问 要人决定的按命令里的默认值走 做到能做的最后一步 结果和回执一次给全}"


def die(msg, code=1):
    print(msg)
    sys.exit(code)


def load_cfg():
    if not os.path.exists(CFG):
        die("没找到 %s。用户主目录建这个文件，写 default 和 remotes，见本技能 SKILL.md。" % CFG)
    try:
        return json.load(io.open(CFG, encoding="utf-8"))
    except Exception as e:
        die("%s 不是合法 JSON：%s" % (CFG, e))


def pick(cfg, name):
    remotes = cfg.get("remotes") or {}
    name = name or cfg.get("default") or (next(iter(remotes)) if remotes else None)
    if not name or name not in remotes:
        die("远程机 %r 没配置。配置里有：%s" % (name, ", ".join(remotes) or "空"))
    r = remotes[name]
    url = (r.get("url") or "").rstrip("/")
    pw = r.get("password") or ""
    if not url or not pw:
        die("远程机 %s 缺 url 或 password" % name)
    u = urlparse(url)
    port = u.port or (443 if u.scheme == "https" else 80)
    return name, url, pw, port


def headers(pw, port, extra=None):
    h = {
        "X-CodeBuddy-Request": "1",
        "Authorization": "Bearer " + pw,
        "Host": "localhost:%d" % port,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, text/event-stream",
    }
    if extra:
        h.update(extra)
    return h


def call(url, pw, port, method="GET", body=None, timeout=30):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers(pw, port))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:500]}
    except Exception as e:
        return 0, {"error": str(e)}
    try:
        return 200, json.loads(raw)
    except Exception:
        return 200, {"raw": raw[:500]}


def mask(s, pw):
    return s.replace(pw, "<口令>") if pw else s


def cmd_list(args):
    cfg = load_cfg()
    for name in (cfg.get("remotes") or {}):
        _, url, pw, port = pick(cfg, name)
        code, d = call(url + "/api/v1/health", pw, port, timeout=10)
        st = (d.get("data") or {}).get("status") if isinstance(d, dict) else None
        plats = ",".join((d.get("data") or {}).get("platforms", [])) if isinstance(d, dict) and d.get("data") else ""
        print("%-12s %-32s %s %s" % (name, url, "在线 " + plats if st == "ok" else "不通 http %s %s" % (code, mask(json.dumps(d, ensure_ascii=False)[:120], pw)), "(默认)" if name == cfg.get("default") else ""))


def extract_texts(obj, out):
    """从任意 JSON 里捞 assistant 的文字（markdown / text / content 字符串）。"""
    if isinstance(obj, dict):
        role = obj.get("role")
        for k in ("markdown", "text"):
            v = obj.get(k)
            if isinstance(v, str) and v.strip() and role != "user":
                out.append(v)
        c = obj.get("content")
        if isinstance(c, str) and c.strip() and role == "assistant":
            out.append(c)
        for v in obj.values():
            extract_texts(v, out)
    elif isinstance(obj, list):
        for v in obj:
            extract_texts(v, out)


def read_stream(url, pw, port, run_id, max_wait):
    """挂 SSE，收 message 事件里的 content.markdown，到 done 为止。返回 (markdowns, status, raw_error)。
    流中途卡住、断掉都不抛栈：返回已收到的部分和 timeout / 流中断 的状态。"""
    req = urllib.request.Request(url + "/api/v1/runs/%s/stream" % run_id, headers=headers(pw, port, {"Accept": "text/event-stream"}))
    mds, status, event = [], None, None
    deadline = time.time() + max_wait
    try:
        resp = urllib.request.urlopen(req, timeout=max_wait)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        return mds, status, raw[:300]
    except Exception as e:
        return mds, status, str(e)
    ctype = resp.headers.get("Content-Type", "")
    if "json" in ctype:
        return mds, status, resp.read().decode("utf-8", "replace")[:300]
    buf = []
    try:
        for line in resp:
            if time.time() > deadline:
                return mds, status or "timeout", "超时 %ds" % max_wait
            line = line.decode("utf-8", "replace").rstrip("\r\n")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                buf.append(line[5:].strip())
            elif line == "":
                if buf:
                    data = "\n".join(buf); buf = []
                    try:
                        d = json.loads(data)
                    except Exception:
                        d = {"raw": data}
                    if event == "message":
                        status = d.get("status") or status
                        md = (d.get("content") or {}).get("markdown") if isinstance(d.get("content"), dict) else None
                        if md:
                            mds.append(md)
                        calls = (d.get("agent") or {}).get("toolCalls") or []
                        if calls:
                            print("  [远程动了 %d 个工具]" % len(calls), file=sys.stderr)
                    elif event == "done":
                        return mds, status or "completed", None
                    elif event in ("error",):
                        return mds, "error", data[:300]
                event = None
    except (TimeoutError, socket.timeout) as e:
        return mds, status or "timeout", "超时 %ds（流卡住：%s）" % (max_wait, e)
    except Exception as e:
        return mds, status or "stream-broken", "流中断 %s: %s" % (type(e).__name__, str(e)[:120])
    return mds, status or "closed", None


def fallback_history(url, pw, port, text):
    code, d = call(url + "/api/v1/sessions?limit=5", pw, port, timeout=20)
    sess = (d.get("data") or {}).get("sessions") if isinstance(d, dict) else None
    if not sess:
        return None
    head = text.strip()[:20]
    cand = [s for s in sess if str(s.get("name", "")).startswith(head)] or sess[:1]
    sid = cand[0].get("id")
    code, h = call(url + "/api/v1/sessions/%s/history" % sid, pw, port, timeout=30)
    out = []
    extract_texts(h, out)
    return out[-1] if out else None


def save_log(name, run_id, text, result, status):
    day = datetime.datetime.now().strftime("%Y-%m-%d")
    d = os.path.join(LOGDIR, day)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "%s-%s-%s.md" % (datetime.datetime.now().strftime("%H%M%S"), name, run_id[:8]))
    with io.open(p, "w", encoding="utf-8") as f:
        f.write("# 派活记录\n\n- 远程机: %s\n- runId: %s\n- 状态: %s\n- 时间: %s\n\n## 发出去的\n\n%s\n\n## 收回来的\n\n%s\n" % (name, run_id, status, datetime.datetime.now().isoformat(timespec="seconds"), text, result or "(空)"))
    return p


def cmd_send(args):
    cfg = load_cfg()
    name, url, pw, port = pick(cfg, args.to)
    if args.file:
        text = io.open(args.file, encoding="utf-8").read()
    elif args.text:
        text = args.text
    else:
        die("要 --file 或 --text")
    if not text.strip():
        die("要发的内容是空的")
    orig = text
    if not getattr(args, "raw", False):
        text = VIA_NOTE + "\n\n" + text
    client_id = "dispatch-" + uuid.uuid4().hex[:12]
    body = {
        "id": client_id, "type": "message", "version": "1.0",
        "source": {"platform": "generic", "sender": {"id": "dispatch", "name": "dispatch"},
                   "conversation": {"id": client_id, "type": "direct"}},
        "payload": {"text": text},
        "timeoutMs": int(args.timeout) * 1000,
    }
    code, d = call(url + "/api/v1/runs", pw, port, method="POST", body=body, timeout=30)
    run_id = (d.get("data") or {}).get("runId") if isinstance(d, dict) else None
    if not run_id:
        die("派活失败 http %s：%s" % (code, mask(json.dumps(d, ensure_ascii=False)[:400], pw)))
    print("已派给 %s，runId %s，等结果…" % (name, run_id), file=sys.stderr)
    mds, status, err = read_stream(url, pw, port, run_id, int(args.max_wait))
    result = "\n\n".join(m for m in mds if m) if mds else None
    if not result and err and "RUN_NOT_FOUND" in err:
        print("  跑得太快没挂上流，改从会话历史读…", file=sys.stderr)
        result = fallback_history(url, pw, port, orig)   # 用原正文对会话名，不带 ::NOTE 前缀
        status = status or "completed"
    if not result and err:
        status = status or "error"
        result = "(没收到结果) " + mask(err, pw)
    p = save_log(name, run_id, text, result, status)
    print(result or "(空)")
    print("\n[状态 %s · 记录 %s]" % (status, p), file=sys.stderr)


def cmd_sessions(args):
    cfg = load_cfg()
    name, url, pw, port = pick(cfg, args.to)
    code, d = call(url + "/api/v1/sessions?limit=%d" % int(args.n), pw, port, timeout=20)
    sess = (d.get("data") or {}).get("sessions") if isinstance(d, dict) else None
    if not sess:
        die("没拿到会话：http %s %s" % (code, mask(json.dumps(d, ensure_ascii=False)[:300], pw)))
    for s in sess:
        ts = datetime.datetime.fromtimestamp((s.get("updatedAt") or 0) / 1000).strftime("%m-%d %H:%M")
        print("%s  %s  %s" % (s.get("id"), ts, str(s.get("name", ""))[:60]))


def cmd_history(args):
    cfg = load_cfg()
    name, url, pw, port = pick(cfg, args.to)
    code, h = call(url + "/api/v1/sessions/%s/history" % args.session, pw, port, timeout=30)
    out = []
    extract_texts(h, out)
    if not out:
        print(mask(json.dumps(h, ensure_ascii=False)[:1500], pw))
    else:
        print("\n\n---\n\n".join(out[-int(args.n):]))


def cmd_cancel(args):
    cfg = load_cfg()
    name, url, pw, port = pick(cfg, args.to)
    code, d = call(url + "/api/v1/runs/%s/cancel" % args.run, pw, port, method="POST", body={}, timeout=20)
    print("http %s %s" % (code, mask(json.dumps(d, ensure_ascii=False)[:300], pw)))


def main():
    ap = argparse.ArgumentParser(description="把命令块派给远程 CodeBuddy 网关跑")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    p = sub.add_parser("send"); p.add_argument("--to"); p.add_argument("--file"); p.add_argument("--text")
    p.add_argument("--timeout", default=900, help="远程单次执行超时 秒"); p.add_argument("--max-wait", default=3600, help="本地最多等多久 秒"); p.add_argument("--raw", action="store_true", help="不在正文前加 ::NOTE{via:remote-dispatch …} 那一行")
    p = sub.add_parser("sessions"); p.add_argument("--to"); p.add_argument("--n", default=5)
    p = sub.add_parser("history"); p.add_argument("--to"); p.add_argument("--session", required=True); p.add_argument("--n", default=1)
    p = sub.add_parser("cancel"); p.add_argument("--to"); p.add_argument("--run", required=True)
    args = ap.parse_args()
    if not args.cmd:
        ap.print_help(); return
    {"list": cmd_list, "send": cmd_send, "sessions": cmd_sessions, "history": cmd_history, "cancel": cmd_cancel}[args.cmd](args)


if __name__ == "__main__":
    main()
