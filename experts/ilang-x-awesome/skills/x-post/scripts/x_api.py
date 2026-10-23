#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X（Twitter）官方接口：发帖、串帖、回复、读自己的提及，外加一条不花钱的手动路。只用 Python 3.8+ 标准库。

用法：
  python x_api.py check                                  验密钥：GET /2/users/me，打印 handle、id 和 App 权限（只读的发不了帖），把 id 记进本机状态文件
                                                         Windows 一般是 python，Mac 和 Linux 多半要写 python3，下同
  python x_api.py gate --text "..." | --file 帖.txt       只过门不联网：加权长度、标记、长破折号、链接、重复
  python x_api.py post --text "..." | --file 帖.txt [--media a.jpg,b.png | v.mp4] [--reply-to <id>] [--allow-url] [--force] [--dry-run]
                                                         发一条，可带最多 4 张图或 1 个视频；--dry-run 只打印请求体
  python x_api.py thread --file 串帖.txt [--media 封面.jpg] [--dry-run]
                                                         按文件里单独一行的 --- 切条，依次发并串起来，媒体挂第一条
  python x_api.py reply --to <id> --text "..." [--dry-run]
                                                         回复一条（只回召唤你的人：@你或引用你的帖，回自己帖下的评论算）
  python x_api.py mentions [--since-id <id>] [--max 100] 读自己的提及（Owned Reads，0.001 美元一条），打印 JSON
  python x_api.py intent --text "..." | --file 帖.txt [--no-open]
                                                         手动路：生成 x.com/intent/post 链接并打开浏览器，人点发，不花钱

凭据（永远不要贴进对话）：
  ~/.x-api.env（X_API_ENV 可指定路径）四行：API_KEY= API_SECRET= ACCESS_TOKEN= ACCESS_SECRET=
  或环境变量 X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET
  四个值都在 developer.x.com 自己的应用里生成（权限 Read and Write，用自己账号授权）。

本机数据：~/.x-ops/<handle>/ 下 state.json（me_id、since_id）、posts.jsonl（发过的每条，正文全文）、replies.jsonl（回过的每条）。
价格（2026-10-22 docs.x.com）：发帖 0.015 美元一条，正文含 URL 0.20 一条，回复召唤你的人 0.010 一条，读自己提及 0.001 一条。
退出码：0 成功；1 参数或门没过；2 接口报错；3 发出去了没收到回复（先去主页看有没有发出去，有就别重发）。
"""
import argparse
import base64
import datetime as _dt
import hashlib
import hmac
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import webbrowser

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

API = "https://api.x.com/2"
UA = "x-awesome/2.3"
WEIGHTED_MAX = 280                 # X 的加权长度上限
URL_WEIGHT = 23                    # 任何链接按 t.co 长度计
DAILY_MAX = 2                      # 一天两条，再发要 --force
DUP_WINDOW = 200                   # 和最近 200 条正文比重复
SIMILAR_THRESHOLD = 0.8            # 二字片段 Jaccard 超过这个算相似
PRICE = {"post": 0.015, "post_url": 0.20, "reply": 0.010, "owned_read": 0.001, "read": 0.005, "user_read": 0.010}
LAST_HEADERS = {}                  # 最近一次接口响应的头，check 用它看 x-access-level（App 是只读还是读写）
MARKER_RE = re.compile(r"\[(📝|💬|🖼|📊)[^\]]*\]")
DASH_RE = re.compile("[—–]")
URL_RE = re.compile(r"https?://\S+|\b[\w\-]+(?:\.[\w\-]+)*\.[a-z]{2,}(?:/\S*)?", re.I)   # 裸域名要有字母后缀，3.5 这种小数不算
SPLIT_RE = re.compile(r"^\s*---\s*$", re.M)


def die(msg, code=1):
    print("错误：" + msg)
    sys.exit(code)


# ---------- 凭据与本机目录 ----------
def load_credentials():
    keys = {"API_KEY": "", "API_SECRET": "", "ACCESS_TOKEN": "", "ACCESS_SECRET": ""}
    for k in keys:
        keys[k] = os.environ.get("X_" + k, "").strip()
    path = os.environ.get("X_API_ENV") or os.path.join(os.path.expanduser("~"), ".x-api.env")
    if not all(keys.values()) and os.path.exists(path):
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().upper().replace("X_", "", 1) if k.strip().upper().startswith("X_") else k.strip().upper()
            if k in keys and not keys[k]:
                keys[k] = v.strip().strip('"').strip("'")
    if not all(keys.values()):
        die("没找到凭据。写 %s（四行：API_KEY= API_SECRET= ACCESS_TOKEN= ACCESS_SECRET=），或设环境变量 X_API_KEY 等四个" % path)
    return keys


def ops_dir(handle=None):
    base = os.environ.get("X_OPS_DIR") or os.path.join(os.path.expanduser("~"), ".x-ops")
    if handle is None:
        handle = state_handle(base)
    d = os.path.join(base, handle or "_default")
    os.makedirs(d, exist_ok=True)
    return d


def state_handle(base):
    """check 之后 state.json 记了 handle；没 check 过就用 _default。"""
    p = os.path.join(base, "current.txt")
    if os.path.exists(p):
        return io.open(p, encoding="utf-8").read().strip() or None
    return None


def load_state(d):
    p = os.path.join(d, "state.json")
    if os.path.exists(p):
        return json.load(io.open(p, encoding="utf-8"))
    return {}


def save_state(d, st):
    io.open(os.path.join(d, "state.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(st, ensure_ascii=False, indent=1))


def append_log(d, name, rec):
    rec = dict(rec, at=_dt.datetime.now().isoformat(timespec="seconds"))
    with io.open(os.path.join(d, name), "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_log(d, name, last=None):
    p = os.path.join(d, name)
    if not os.path.exists(p):
        return []
    rows = []
    for line in io.open(p, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows[-last:] if last else rows


# ---------- OAuth 1.0a ----------
def pct(s):
    return urllib.parse.quote(str(s), safe="-._~")


def oauth_header(method, url, query, creds, nonce=None, ts=None):
    """RFC 5849：oauth_* 加查询参数一起签，JSON 请求体不参与签名。"""
    params = {
        "oauth_consumer_key": creds["API_KEY"],
        "oauth_nonce": nonce or uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": ts or str(int(time.time())),
        "oauth_token": creds["ACCESS_TOKEN"],
        "oauth_version": "1.0",
    }
    allp = dict(params)
    allp.update(query or {})
    norm = "&".join("%s=%s" % (pct(k), pct(allp[k])) for k in sorted(allp))
    base = "&".join([method.upper(), pct(url), pct(norm)])
    key = pct(creds["API_SECRET"]) + "&" + pct(creds["ACCESS_SECRET"])
    sig = base64.b64encode(hmac.new(key.encode("utf-8"), base.encode("utf-8"), hashlib.sha1).digest()).decode("ascii")
    params["oauth_signature"] = sig
    return "OAuth " + ", ".join('%s="%s"' % (pct(k), pct(params[k])) for k in sorted(params))


def call(method, path, creds, query=None, body=None, timeout=60, fatal=True):
    """返回 (status, json)。网络层没回复时 status=-1（fatal=False 时交给调用方处理）。"""
    url = API + path
    full = url + ("?" + urllib.parse.urlencode(query) if query else "")
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(full, data=data, method=method)
    req.add_header("Authorization", oauth_header(method, url, query, creds))
    req.add_header("User-Agent", UA)
    if data is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    global LAST_HEADERS
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw, status = resp.read(), resp.status
            LAST_HEADERS = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
        LAST_HEADERS = {k.lower(): v for k, v in (e.headers or {}).items()}
    except Exception as e:
        if not fatal:
            return -1, {"error": "没收到回复：%s" % e}
        die("网络请求失败：%s（%s）" % (e, path), 2)
    try:
        j = json.loads(raw.decode("utf-8")) if raw else {}
    except Exception:
        j = {"raw": raw[:300].decode("utf-8", "replace")}
    return status, j


def explain(status, j):
    tips = {
        401: "密钥不对、过期，或应用权限不是 Read and Write。去 developer.x.com 重新生成四个密钥再写进配置文件。",
        402: "积分不够了。去开发者控制台充值（自动充值最低 5 美元）。",
        403: "被拒。先看 check 打印的权限：App 不是 Read and write 就会 403，去 developer.x.com 把 App 权限改成 Read and write，再重新生成 Access Token 和 Secret 写进配置文件。权限对的话，回复多半是对方没有召唤你（只能回 @你或引用你的帖）。",
        429: "限频，等一会再发。",
        503: "X 那边暂时不可用，稍后再试。",
    }
    detail = j.get("detail") or j.get("title") or (j.get("errors") or [{}])[0].get("message") or j.get("error") or j.get("raw") or ""
    return "HTTP %s %s%s" % (status, detail, ("。" + tips[status]) if status in tips else "")


# ---------- 文本门 ----------
def weighted_len(text):
    """X 的加权长度（近似）：链接按 23；中日韩、全角、emoji 算 2；其余算 1。官方按 Unicode 区间细分，这里按常见区间估，边界差一两个字不影响。"""
    n = 0
    text = URL_RE.sub(lambda m: "\x00" * 1, text)
    for ch in text:
        if ch == "\x00":
            n += URL_WEIGHT
            continue
        o = ord(ch)
        if (0x1100 <= o <= 0x11FF or 0x2E80 <= o <= 0xA4CF or 0xAC00 <= o <= 0xD7A3 or 0xF900 <= o <= 0xFAFF
                or 0xFE30 <= o <= 0xFE4F or 0xFF00 <= o <= 0xFFEF or o >= 0x10000):
            n += 2
        else:
            n += 1
    return n


def has_url(text):
    return bool(URL_RE.search(text))


def norm_text(text):
    return re.sub(r"[\s\W_]+", "", text.lower())


def bigrams(s):
    return set(s[i:i + 2] for i in range(len(s) - 1)) if len(s) > 1 else {s}


def similar(a, b):
    a, b = norm_text(a), norm_text(b)
    if not a or not b:
        return False
    if a == b:
        return True
    ga, gb = bigrams(a), bigrams(b)
    return len(ga & gb) / float(len(ga | gb)) >= SIMILAR_THRESHOLD


def normalize(text):
    """归一：换行统一、去尾空格、长破折号换逗号（提醒）。不动别的。"""
    warnings = []
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    n = len(re.findall("[—–]+", text))
    if n:
        warnings.append("长破折号 %d 处已换成逗号" % n)
        text = re.sub("[—–]+", "，", text)
    text = "\n".join(l.rstrip() for l in text.split("\n")).strip()
    return text, warnings


def gate(text, history, allow_url=False, is_reply=False):
    """返回错误列表，空＝过。history 是本机日志里最近的正文列表。"""
    errors = []
    if not text.strip():
        errors.append("正文是空的")
    n = weighted_len(text)
    if n > WEIGHTED_MAX:
        errors.append("加权长度 %d，超过 %d（中日韩每字算 2，链接算 23）；拆成串帖或删字" % (n, WEIGHTED_MAX))
    if MARKER_RE.search(text):
        errors.append("还有待作者处理的标记 [📝/💬/🖼/📊]")
    if DASH_RE.search(text):
        errors.append("仍有长破折号")
    if has_url(text):
        if is_reply:
            errors.append("回复里不放链接")
        elif not allow_url:
            errors.append("正文含链接：走接口按 %.2f 美元一条计，而且算法压外链。真要发加 --allow-url；建议链接放评论区" % PRICE["post_url"])
    for old in history:
        if similar(text, old):
            errors.append("和最近发过的一条相同或高度相似：%s" % old[:40])
            break
    return errors


def split_thread(raw):
    parts = [p.strip() for p in SPLIT_RE.split(raw.replace("\r\n", "\n")) if p.strip()]
    return parts


def today_count(d):
    today = _dt.date.today().isoformat()
    return sum(1 for r in read_log(d, "posts.jsonl") if str(r.get("at", "")).startswith(today) and r.get("kind") in ("post", "thread"))


# ---------- 接口动作 ----------
def me(creds):
    status, j = call("GET", "/users/me", creds, query={"user.fields": "id,username,name"})
    if status != 200 or "data" not in j:
        die("GET /2/users/me 失败：" + explain(status, j), 2)
    return j["data"]


def create_post(creds, text, reply_to=None, media_ids=None):
    body = {"text": text}
    if reply_to:
        body["reply"] = {"in_reply_to_tweet_id": str(reply_to)}
    if media_ids:
        body["media"] = {"media_ids": [str(m) for m in media_ids]}
    return call("POST", "/tweets", creds, body=body, timeout=60, fatal=False)


# ---------- 媒体上传（图直接传，视频分块传；按 2025 年起的 v2 媒体接口写，没拿真密钥测过，第一次用看 api-notes 的「没实测」） ----------
MEDIA_LIMITS = {"image": 5 * 1024 * 1024, "gif": 15 * 1024 * 1024, "video": 512 * 1024 * 1024}
MEDIA_TYPES = {".jpg": ("image", "image/jpeg"), ".jpeg": ("image", "image/jpeg"), ".png": ("image", "image/png"), ".webp": ("image", "image/webp"),
               ".gif": ("gif", "image/gif"), ".mp4": ("video", "video/mp4"), ".mov": ("video", "video/quicktime")}
CHUNK = 4 * 1024 * 1024


def media_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext not in MEDIA_TYPES:
        die("只收 jpg/png/webp/gif/mp4/mov：" + path)
    return MEDIA_TYPES[ext]


def multipart(fields, file_field, filename, data, ctype):
    boundary = "----xawesome" + uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body.extend(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode("utf-8"))
    body.extend(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n" % (boundary, file_field, filename, ctype)).encode("utf-8"))
    body.extend(data)
    body.extend(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    return bytes(body), "multipart/form-data; boundary=" + boundary


def call_raw(method, path, creds, query=None, data=None, content_type=None, timeout=180):
    """multipart 这类非 JSON 请求体：签名只签查询参数，请求体原样发。"""
    url = API + path
    full = url + ("?" + urllib.parse.urlencode(query) if query else "")
    req = urllib.request.Request(full, data=data, method=method)
    req.add_header("Authorization", oauth_header(method, url, query, creds))
    req.add_header("User-Agent", UA)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw, status = resp.read(), resp.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        die("媒体上传网络请求失败：%s（%s）" % (e, path), 2)
    try:
        return status, (json.loads(raw.decode("utf-8")) if raw else {})
    except Exception:
        return status, {"raw": raw[:300].decode("utf-8", "replace")}


def upload_media(creds, path):
    """返回 media_id。图和 gif 一次传完；视频 initialize → append 分块 → finalize → 轮询到处理完。"""
    kind, ctype = media_kind(path)
    if not os.path.exists(path):
        die("媒体文件不存在：" + path)
    data = io.open(path, "rb").read()
    if len(data) > MEDIA_LIMITS[kind]:
        die("%s 超过 %dMB：%s" % (kind, MEDIA_LIMITS[kind] // 1024 // 1024, path))
    name = os.path.basename(path)
    category = {"image": "tweet_image", "gif": "tweet_gif", "video": "tweet_video"}[kind]
    if kind != "video":
        body, ct = multipart({"media_category": category}, "media", name, data, ctype)
        status, j = call_raw("POST", "/media/upload", creds, data=body, content_type=ct)
        mid = (j.get("data") or {}).get("id") or j.get("media_id_string")
        if status not in (200, 201) or not mid:
            die("图片上传失败（%s）：%s" % (name, explain(status, j)), 2)
        return str(mid)
    status, j = call("POST", "/media/upload/initialize", creds, body={"media_type": ctype, "total_bytes": len(data), "media_category": category}, fatal=False)
    mid = (j.get("data") or {}).get("id")
    if status not in (200, 201, 202) or not mid:
        die("视频上传 initialize 失败（%s）：%s" % (name, explain(status, j)), 2)
    for i in range(0, len(data), CHUNK):
        body, ct = multipart({"segment_index": str(i // CHUNK)}, "media", name, data[i:i + CHUNK], ctype)
        status, j = call_raw("POST", "/media/upload/%s/append" % mid, creds, data=body, content_type=ct)
        if status not in (200, 201, 204):
            die("视频上传 append 第 %d 块失败：%s" % (i // CHUNK, explain(status, j)), 2)
    status, j = call("POST", "/media/upload/%s/finalize" % mid, creds, body={}, fatal=False)
    if status not in (200, 201):
        die("视频上传 finalize 失败：%s" % explain(status, j), 2)
    info = (j.get("data") or {}).get("processing_info") or {}
    waited = 0
    while info.get("state") in ("pending", "in_progress") and waited < 300:
        secs = int(info.get("check_after_secs") or 5)
        time.sleep(secs); waited += secs
        status, j = call("GET", "/media/upload", creds, query={"command": "STATUS", "media_id": mid}, fatal=False)
        info = (j.get("data") or {}).get("processing_info") or {}
    if info.get("state") == "failed":
        die("视频处理失败：%s" % json.dumps(info, ensure_ascii=False), 2)
    return str(mid)


def upload_all(creds, media_arg):
    paths = [p.strip() for p in (media_arg or "").split(",") if p.strip()]
    if len(paths) > 4:
        die("一条帖最多 4 张图，或 1 个视频，或 1 个 gif")
    kinds = [media_kind(p)[0] for p in paths]
    if ("video" in kinds or "gif" in kinds) and len(paths) > 1:
        die("视频或 gif 只能单独一个，不能和别的混")
    ids = []
    for p in paths:
        mid = upload_media(creds, p)
        ids.append(mid)
        print("  媒体已传：%s -> %s" % (os.path.basename(p), mid))
    return ids


def read_post(creds, pid):
    status, j = call("GET", "/tweets/%s" % pid, creds, query={"tweet.fields": "created_at,text"}, fatal=False)
    return (j.get("data") or {}) if status == 200 else {}


def get_mentions(creds, me_id, since_id=None, max_results=100, pagination_token=None):
    """读一页自己的提及（最多 100 条）。返回 (rows, meta)，meta.next_token 有值就还有下一页。"""
    q = {"max_results": str(max(5, min(100, int(max_results)))),
         "tweet.fields": "created_at,author_id,conversation_id,in_reply_to_user_id,referenced_tweets,text",
         "expansions": "author_id", "user.fields": "username,name,public_metrics"}
    if since_id:
        q["since_id"] = str(since_id)
    if pagination_token:
        q["pagination_token"] = pagination_token
    status, j = call("GET", "/users/%s/mentions" % me_id, creds, query=q)
    if status != 200:
        die("读提及失败：" + explain(status, j), 2)
    users = {u["id"]: u for u in (j.get("includes") or {}).get("users", [])}
    out = []
    for t in j.get("data") or []:
        refs = t.get("referenced_tweets") or []
        kind = "reply_to_me" if t.get("in_reply_to_user_id") == me_id else ("quote" if any(r.get("type") == "quoted" for r in refs) else "mention")
        u = users.get(t.get("author_id"), {})
        out.append({"id": t["id"], "text": t.get("text", ""), "created_at": t.get("created_at"), "author_id": t.get("author_id"),
                    "username": u.get("username"), "name": u.get("name"), "followers": (u.get("public_metrics") or {}).get("followers_count"),
                    "kind": kind, "conversation_id": t.get("conversation_id"), "in_reply_to_user_id": t.get("in_reply_to_user_id"),
                    "parent_id": next((r.get("id") for r in refs if r.get("type") == "replied_to"), None)})
    return out, (j.get("meta") or {})


def get_mentions_all(creds, me_id, since_id=None, max_total=300):
    """一条帖几百条回复的号，一页 100 条拉不完：按 next_token 翻页拉到没有下一页或够 max_total 为止。返回 (rows, newest_id, pages)。"""
    rows, token, pages, newest = [], None, 0, None
    while True:
        page, meta = get_mentions(creds, me_id, since_id, min(100, max_total - len(rows)) if max_total else 100, token)
        pages += 1
        rows.extend(page)
        if newest is None and meta.get("newest_id"):
            newest = meta.get("newest_id")
        token = meta.get("next_token")
        if not token or not page or (max_total and len(rows) >= max_total) or pages >= 50:
            break
    if newest is None and rows:
        newest = max((r["id"] for r in rows), key=int)
    return rows, newest, pages


def rank_mentions(items):
    """排出值得先看的：自己帖下的评论优先，再按作者粉丝数，再按正文长短；带链接和几个字的放最后。只排序不判断，判断是专家的。"""
    def key(r):
        low = 1 if (has_url(r.get("text") or "") or len(norm_text(r.get("text") or "")) < 6) else 0
        kind = {"reply_to_me": 0, "quote": 1, "mention": 2}.get(r.get("kind"), 3)
        return (low, kind, -(r.get("followers") or 0), -len(r.get("text") or ""))
    out = sorted(items, key=key)
    for i, r in enumerate(out, 1):
        r["rank"] = i
    return out


def post_one(creds, d, text, kind, reply_to=None, via="api", media_ids=None):
    """发一条并落日志。没收到回复＝UNKNOWN，退出码 3。"""
    status, j = create_post(creds, text, reply_to, media_ids)
    rec = {"kind": kind, "text": text, "reply_to": reply_to, "via": via, "media_ids": media_ids or []}
    if status == -1:
        append_log(d, "posts.jsonl", dict(rec, id=None, status="UNKNOWN", error=j.get("error")))
        print("发出去了但没收到 X 的回复：%s" % j.get("error"))
        print("先去自己的主页看这条有没有发出去，有就别重发；确定没有再发一次。已记 UNKNOWN 进 posts.jsonl。")
        sys.exit(3)
    if status not in (200, 201) or "data" not in j:
        append_log(d, "posts.jsonl", dict(rec, id=None, status="FAIL", error=explain(status, j)))
        die("发帖失败：" + explain(status, j), 2)
    pid = j["data"]["id"]
    append_log(d, "posts.jsonl", dict(rec, id=pid, status="ok"))
    return pid


# ---------- 子命令 ----------
def read_text(args):
    if getattr(args, "file", None):
        if not os.path.exists(args.file):
            die("文件不存在：" + args.file)
        return io.open(args.file, encoding="utf-8").read()
    if getattr(args, "text", None):
        return args.text
    die("给 --text 或 --file")


def cmd_check(args):
    creds = load_credentials()
    u = me(creds)
    level = LAST_HEADERS.get("x-access-level", "")
    base = os.environ.get("X_OPS_DIR") or os.path.join(os.path.expanduser("~"), ".x-ops")
    os.makedirs(base, exist_ok=True)
    io.open(os.path.join(base, "current.txt"), "w", encoding="utf-8").write(u["username"])
    d = ops_dir(u["username"])
    st = load_state(d)
    st.update({"me_id": u["id"], "handle": u["username"], "access_level": level, "checked_at": _dt.datetime.now().isoformat(timespec="seconds")})
    save_state(d, st)
    append_log(d, "reads.jsonl", {"kind": "me", "n": 1, "cost": PRICE["user_read"]})
    print("ok：@%s（id %s）密钥通，App 权限 %s。本机数据目录：%s。什么都没发。" % (u["username"], u["id"], level or "（响应头没带 x-access-level）", d))
    if level and "write" not in level:
        print("注意：这套密钥只能读不能发。去 developer.x.com 的 App 设置把权限改成 Read and write，再重新生成 Access Token 和 Secret 写进配置文件，然后再跑一次 check。")


def cmd_gate(args):
    text, warnings = normalize(read_text(args))
    d = ops_dir()
    history = [r.get("text", "") for r in read_log(d, "posts.jsonl", DUP_WINDOW) if r.get("status") == "ok"]
    errors = gate(text, history, allow_url=getattr(args, "allow_url", False))
    print("加权长度 %d / %d；%d 字" % (weighted_len(text), WEIGHTED_MAX, len(text)))
    for w in warnings:
        print("  提醒：" + w)
    for e in errors:
        print("  不过：" + e)
    if getattr(args, "show", False) or not errors:
        print("---\n" + text)
    sys.exit(1 if errors else 0)


def cmd_post(args, kind="post"):
    text, warnings = normalize(read_text(args))
    d = ops_dir()
    history = [r.get("text", "") for r in read_log(d, "posts.jsonl", DUP_WINDOW) if r.get("status") == "ok"]
    is_reply = kind == "reply"
    errors = gate(text, history, allow_url=getattr(args, "allow_url", False), is_reply=is_reply)
    for w in warnings:
        print("  提醒：" + w)
    for e in errors:
        print("  不过：" + e)
    if errors:
        die("先把上面的不过项改掉再发")
    reply_to = getattr(args, "reply_to", None) or getattr(args, "to", None)
    if not is_reply and today_count(d) >= DAILY_MAX and not getattr(args, "force", False):
        die("今天本机日志里已经有 %d 条了，一天一到两条，宁缺毋滥。真要发加 --force" % DAILY_MAX)
    price = PRICE["reply"] if reply_to else (PRICE["post_url"] if has_url(text) else PRICE["post"])
    media_arg = getattr(args, "media", None)
    media_paths = [p.strip() for p in (media_arg or "").split(",") if p.strip()]
    for p in media_paths:
        media_kind(p)
        if not os.path.exists(p):
            die("媒体文件不存在：" + p)
    print("加权长度 %d / %d；预计 %.3f 美元%s" % (weighted_len(text), WEIGHTED_MAX, price, ("；带 %d 个媒体文件（媒体上传本身价目表没单列）" % len(media_paths)) if media_paths else ""))
    if args.dry_run:
        body = {"text": text}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": str(reply_to)}
        if media_paths:
            body["media"] = {"media_ids": ["<dry-run:%s>" % os.path.basename(p) for p in media_paths]}
        print("dry-run：没联网。请求体：\n" + json.dumps(body, ensure_ascii=False, indent=1))
        return
    creds = load_credentials()
    media_ids = upload_all(creds, media_arg) if media_paths else None
    pid = post_one(creds, d, text, kind, reply_to, media_ids=media_ids)
    print("ok：已发，id=%s，https://x.com/i/status/%s" % (pid, pid))
    back = read_post(creds, pid)
    if back.get("text") is not None:
        same = norm_text(back["text"]).startswith(norm_text(text)[:40])
        print(("ok：回读一致" if same else "注意：回读正文和发的不一样，去主页看一眼") + "（回读 0.001 美元）")
    else:
        print("注意：回读没拿到正文，去主页看一眼")


def cmd_thread(args):
    raw = read_text(args)
    parts = split_thread(raw)
    if len(parts) < 2:
        die("串帖要至少两条，文件里用单独一行的 --- 分隔")
    d = ops_dir()
    history = [r.get("text", "") for r in read_log(d, "posts.jsonl", DUP_WINDOW) if r.get("status") == "ok"]
    normed, bad = [], False
    for k, p in enumerate(parts, 1):
        t, warnings = normalize(p)
        errors = gate(t, history, allow_url=getattr(args, "allow_url", False))
        print("[%d/%d] 加权 %d / %d" % (k, len(parts), weighted_len(t), WEIGHTED_MAX))
        for w in warnings:
            print("  提醒：" + w)
        for e in errors:
            print("  不过：" + e); bad = True
        normed.append(t)
    if bad:
        die("先把上面的不过项改掉再发")
    if today_count(d) >= DAILY_MAX and not getattr(args, "force", False):
        die("今天本机日志里已经有 %d 条了，一天一到两条，宁缺毋滥。真要发加 --force" % DAILY_MAX)
    print("预计 %.3f 美元（%d 条）" % (sum(PRICE["post_url"] if has_url(t) else PRICE["post"] for t in normed), len(normed)))
    if args.dry_run:
        print("dry-run：没联网。各条正文：")
        for k, t in enumerate(normed, 1):
            print("--- [%d]\n%s" % (k, t))
        return
    creds = load_credentials()
    first_media = upload_all(creds, getattr(args, "media", None)) if getattr(args, "media", None) else None
    prev = None
    ids = []
    for k, t in enumerate(normed, 1):
        pid = post_one(creds, d, t, "thread", prev, media_ids=first_media if k == 1 else None)
        ids.append(pid)
        print("  [%d/%d] 已发 id=%s" % (k, len(normed), pid))
        prev = pid
        time.sleep(1.5)
    print("ok：串帖发完，首条 https://x.com/i/status/%s" % ids[0])


def cmd_reply(args):
    if not args.to:
        die("--to 要给被回复那条的 id")
    cmd_post(args, kind="reply")


def cmd_mentions(args):
    creds = load_credentials()
    d = ops_dir()
    st = load_state(d)
    me_id = st.get("me_id") or me(creds)["id"]
    rows, meta = get_mentions(creds, me_id, args.since_id or st.get("since_id"), args.max)
    append_log(d, "reads.jsonl", {"kind": "mentions", "n": len(rows), "cost": len(rows) * PRICE["owned_read"]})
    print(json.dumps({"me_id": me_id, "count": len(rows), "newest_id": meta.get("newest_id"), "mentions": rows}, ensure_ascii=False, indent=1))


def cmd_intent(args):
    raw = read_text(args)
    parts = split_thread(raw) if getattr(args, "thread", False) else [raw]
    d = ops_dir()
    for k, p in enumerate(parts, 1):
        t, warnings = normalize(p)
        n = weighted_len(t)
        url = "https://x.com/intent/post?text=" + urllib.parse.quote(t, safe="")
        print(("[%d/%d] " % (k, len(parts)) if len(parts) > 1 else "") + "加权 %d / %d%s" % (n, WEIGHTED_MAX, "（超了，编辑框里会标红）" if n > WEIGHTED_MAX else ""))
        for w in warnings:
            print("  提醒：" + w)
        print(url)
        append_log(d, "posts.jsonl", {"id": None, "kind": "intent", "text": t, "via": "intent", "status": "link" if args.no_open else "handed"})
        if not args.no_open:
            webbrowser.open(url)
            if len(parts) > 1:
                time.sleep(2)
    if args.no_open:
        print("链接已生成，没开浏览器：复制到浏览器打开就是填好的编辑框，你自己点发。日志记了「link」，发没发以你为准。")
    else:
        print("浏览器里的编辑框已填好，你自己点发。日志记了「handed」，发没发以你为准。")


def main():
    ap = argparse.ArgumentParser(description="X 官方接口：check / gate / post / thread / reply / mentions / intent。发帖二选一：接口花钱，intent 不花钱人点发。")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("check", help="验密钥，记 handle 和 id，不发")
    g = sub.add_parser("gate", help="只过门不联网")
    g.add_argument("--text"); g.add_argument("--file"); g.add_argument("--allow-url", action="store_true"); g.add_argument("--show", action="store_true")
    p = sub.add_parser("post", help="发一条")
    p.add_argument("--text"); p.add_argument("--file"); p.add_argument("--reply-to"); p.add_argument("--allow-url", action="store_true", help="正文带链接也发（0.20 美元一条）")
    p.add_argument("--media", help="配图或视频，逗号分隔：最多 4 张 jpg/png/webp，或 1 个 gif，或 1 个 mp4/mov")
    p.add_argument("--force", action="store_true", help="今天已经两条了还要发"); p.add_argument("--dry-run", action="store_true")
    t = sub.add_parser("thread", help="串帖：文件里单独一行的 --- 分隔")
    t.add_argument("--file", required=True); t.add_argument("--media", help="挂在第一条上的配图或视频"); t.add_argument("--allow-url", action="store_true"); t.add_argument("--force", action="store_true"); t.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("reply", help="回复一条（只回召唤你的人）")
    r.add_argument("--to", required=True); r.add_argument("--text"); r.add_argument("--file"); r.add_argument("--dry-run", action="store_true")
    m = sub.add_parser("mentions", help="读自己的提及（Owned Reads）")
    m.add_argument("--since-id"); m.add_argument("--max", type=int, default=100)
    i = sub.add_parser("intent", help="手动路：生成编辑框链接并打开浏览器")
    i.add_argument("--text"); i.add_argument("--file"); i.add_argument("--thread", action="store_true", help="文件按 --- 切成多条，一条一个编辑框"); i.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    if args.cmd == "check": cmd_check(args)
    elif args.cmd == "gate": cmd_gate(args)
    elif args.cmd == "post": cmd_post(args)
    elif args.cmd == "thread": cmd_thread(args)
    elif args.cmd == "reply": cmd_reply(args)
    elif args.cmd == "mentions": cmd_mentions(args)
    elif args.cmd == "intent": cmd_intent(args)
    else: ap.print_help()


if __name__ == "__main__":
    main()
