#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号推草稿箱，外加一个只在人说「发」之后才跑的发布命令（没有删草稿命令）。

用法：
  python wechat_draft.py check                                  读配置、拿 access_token、打印 ok，不推任何东西
  python wechat_draft.py render --md 文章.md [--out 文章.html]   只把 Markdown 转成微信 HTML 并校验，不联网
  python wechat_draft.py push --md 文章.md --title "标题" --cover 封面.jpg [--digest "摘要"] [--author "作者"] [--dry-run]
                                                                传图、传封面、推草稿箱、回读核对、落盘结果
  python wechat_draft.py verify --media-id XXXX                 回读一篇草稿，核对中文、图片数、字数
  python wechat_draft.py publish --media-id XXXX --reviewed     人在后台看过草稿、说了「发」之后才跑：
                                                                回读确认草稿存在并打印标题，提交发布，轮询状态，落盘结果
                                                                没有 --reviewed 直接拒绝。只有微信认证企业号能用发布接口。

凭据（二选一，永远不要贴进对话）：
  环境变量 WECHAT_MP_APPID / WECHAT_MP_SECRET
  或配置文件 ~/.wechat-mp.env（可用 WECHAT_MP_ENV 指定路径），内容两行：
      APPID=wx...
      SECRET=...

只依赖 Python 3.8+ 标准库。装了 Pillow 时正文图超过 1MB 会自动压到 1MB 以内，没装就报错让你自己压。
"""
import argparse
import datetime as _dt
import io
import json
import mimetypes
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import uuid
import http.client
import socket
import ssl
from html import escape

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://api.weixin.qq.com"
UA = "wechat-draft-push/2.3"
CITATIONS = []            # 正文里的外链 → 文末「参考链接」[n]
NO_CITE = False           # --no-cite：外链只留文字不留引用
TUNNEL = None             # (host, port)，本机→远程机的 ssh -L 隧道口，走它去 api.weixin.qq.com
BODY_IMG_LIMIT = 1024 * 1024          # uploadimg：jpg/png，1MB 以内
COVER_LIMIT = 10 * 1024 * 1024        # add_material type=image：10MB 以内
TITLE_MAX, AUTHOR_MAX, DIGEST_MAX = 32, 16, 120
CONTENT_MAX_CHARS, CONTENT_MAX_BYTES = 20000, 1024 * 1024

# 发布状态（freepublish/get 的 publish_status）
PUBLISH_POLL_TIMES = 6                # 最多查 6 次
PUBLISH_POLL_INTERVAL = 5             # 每次隔 5 秒
PUBLISH_STATUS = {
    0: "发布成功",
    1: "发布中",
    2: "原创失败",
    3: "常规失败",
    4: "平台审核不通过",
    5: "成功后用户删除",
    6: "成功后系统封禁",
}
PUBLISH_PERMISSION_NOTE = ("只有微信认证企业号能用发布接口，个人主体账号 2025 年 7 月起被回收。"
                           "草稿还在草稿箱里没动，去公众号后台点发布。")
NO_PERMISSION_CODES = {48001}
NO_PERMISSION_RE = re.compile(r"unauthorized|not authorized|no permission", re.I)

# 排版常量（内联样式，微信只认这个）
FONT = "font-size:15px;color:#333;line-height:1.8;letter-spacing:0.5px;"
P = '<p style="%smargin:0;">' % FONT
H = '<p style="font-size:17px;font-weight:bold;color:#111;line-height:1.8;letter-spacing:0.5px;margin:0;">'
BR = "<p><br/></p>"
CAPTION = '<p style="font-size:12px;color:#999;text-align:center;letter-spacing:0.5px;margin:0;">'
HR = '<p style="text-align:center;color:#ccc;margin:0;">────────</p>'
CODE_LINE = '<p style="font-family:Menlo,Consolas,monospace;font-size:13px;color:#e5e7eb;line-height:1.6;margin:0;word-break:break-all;">'
INLINE_CODE = '<span style="font-family:Menlo,Consolas,monospace;background-color:#f3f4f6;padding:1px 4px;border-radius:3px;font-size:14px;">'

MARKER_RE = re.compile(r"\[(📝|💬|🖼|📊)[^\]]*\]")
DASH_RE = re.compile("[—–]")
IMG_LINE_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
INLINE_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
FORBIDDEN_HTML = [
    (re.compile(r"<table[\s>]", re.I), "table 标签微信不渲染"),
    (re.compile(r"</?div[\s>]", re.I), "div 会被改写，用 section"),
    (re.compile(r"<style[\s>]", re.I), "style 标签会被过滤"),
    (re.compile(r"<script[\s>]", re.I), "script 会被过滤"),
    (re.compile(r"\sclass\s*=", re.I), "class 属性会被剥离"),
    (re.compile(r"\sid\s*=", re.I), "id 属性会被剥离"),
    (re.compile(r"position\s*:\s*(fixed|absolute|sticky)", re.I), "position fixed/absolute 不支持"),
]


def die(msg, code=1):
    print("错误：" + msg)
    sys.exit(code)


def cjk_count(text):
    return sum(1 for c in text if "一" <= c <= "鿿")


# ---------- 凭据 ----------
def load_tunnel():
    """TUNNEL=127.0.0.1:8443 写在环境变量 WECHAT_MP_TUNNEL 或 ~/.wechat-mp.env 里。有就把对 api.weixin.qq.com 的请求全走它。"""
    global TUNNEL
    v = os.environ.get("WECHAT_MP_TUNNEL", "").strip()
    path = os.environ.get("WECHAT_MP_ENV") or os.path.join(os.path.expanduser("~"), ".wechat-mp.env")
    if not v and os.path.exists(path):
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, val = line.split("=", 1)
                if k.strip().upper() in ("TUNNEL", "WECHAT_MP_TUNNEL"):
                    v = val.strip().strip('"').strip("'")
    if v:
        host, _, port = v.rpartition(":")
        if host and port.isdigit():
            TUNNEL = (host, int(port))
    return TUNNEL


def tunnel_request(method, url, data=None, headers=None, timeout=60):
    """连隧道口（本机 ssh -L 开的端口），TLS 的 SNI 和证书校验仍按 api.weixin.qq.com，证书对得上。"""
    u = urllib.parse.urlsplit(url)
    path = u.path + ("?" + u.query if u.query else "")
    ctx = ssl.create_default_context()
    raw_sock = socket.create_connection(TUNNEL, timeout=timeout)
    sock = ctx.wrap_socket(raw_sock, server_hostname=u.hostname)
    conn = http.client.HTTPConnection(u.hostname, 443, timeout=timeout)
    conn.sock = sock
    hdrs = {"User-Agent": UA, "Host": u.hostname}
    hdrs.update(headers or {})
    conn.request(method, path, body=data, headers=hdrs)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return body


def load_credentials():
    appid = os.environ.get("WECHAT_MP_APPID", "").strip()
    secret = os.environ.get("WECHAT_MP_SECRET", "").strip()
    path = os.environ.get("WECHAT_MP_ENV") or os.path.join(os.path.expanduser("~"), ".wechat-mp.env")
    if (not appid or not secret) and os.path.exists(path):
        for line in io.open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip().upper(), v.strip().strip('"').strip("'")
            if k in ("APPID", "WECHAT_MP_APPID") and not appid:
                appid = v
            if k in ("SECRET", "APPSECRET", "WECHAT_MP_SECRET") and not secret:
                secret = v
    if not appid or not secret:
        die("没找到凭据。设环境变量 WECHAT_MP_APPID / WECHAT_MP_SECRET，或写配置文件 %s（两行：APPID=... 与 SECRET=...）" % path)
    return appid, secret


# ---------- HTTP（标准库） ----------
def http_json(method, url, data=None, headers=None, timeout=60, fatal=True):
    """fatal=True 时网络错误或非 JSON 直接退出；fatal=False 时返回 {"errcode": -1, "errmsg": ...} 交给调用方处理。"""
    if TUNNEL and urllib.parse.urlsplit(url).hostname == "api.weixin.qq.com":
        try:
            raw = tunnel_request(method, url, data, headers, timeout)
        except Exception as e:
            if not fatal:
                return {"errcode": -1, "errmsg": "隧道请求失败：%s" % e}
            die("隧道请求失败：%s。隧道口 %s:%d 开着吗（本机先跑 ssh -N -L，见 tunnel 子命令）" % (e, TUNNEL[0], TUNNEL[1]))
    else:
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("User-Agent", UA)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raw = e.read()
        except Exception as e:
            if not fatal:
                return {"errcode": -1, "errmsg": "网络请求失败：%s" % e}
            die("网络请求失败：%s（%s）" % (e, url.split("?")[0]))
    try:
        return json.loads(raw.decode("utf-8"))   # 微信返回 text/plain 不带 charset，必须自己按 UTF-8 解
    except Exception:
        if not fatal:
            return {"errcode": -1, "errmsg": "返回的不是 JSON：%r" % raw[:200]}
        die("微信返回的不是 JSON：%r" % raw[:200])


def post_json(token, path, payload, timeout=60, fatal=True):
    """带 access_token 的 JSON POST，请求体按 UTF-8 直传不转义中文。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return http_json("POST", BASE + path + "?access_token=" + token, body,
                     {"Content-Type": "application/json; charset=utf-8"}, timeout=timeout, fatal=fatal)


def multipart(fields, file_field, filename, file_bytes, content_type):
    boundary = "----wechatdraft" + uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body.extend(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, k, v)).encode("utf-8"))
    body.extend(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                 % (boundary, file_field, filename, content_type)).encode("utf-8"))
    body.extend(file_bytes)
    body.extend(("\r\n--%s--\r\n" % boundary).encode("utf-8"))
    return bytes(body), "multipart/form-data; boundary=" + boundary


def explain(j):
    code = j.get("errcode")
    tips = {
        40164: "调接口的这台机器的公网 IP 不在白名单里。去公众号后台「设置与开发 → 基本配置 → IP 白名单」加上 errmsg 里那个 IP。",
        40013: "AppID 不对。",
        40125: "AppSecret 不对，或者被重置过。",
        40001: "access_token 失效，重跑一次。",
        40002: "参数不合法，多半是 media_id 或 publish_id 写错了。",
        40007: "media_id 不合法。推草稿时：先看封面是不是传成了永久素材（结果文件里有 thumb_media_id），不是就重传封面再推，是的话就是 media_id 抄错了；发布时：草稿 media_id 抄错了，从最近一份 draft-result 文件重新复制。",
        45110: "author 太长，16 字以内。",
        45003: "标题太长，32 字以内。",
        45004: "digest 太长，120 字以内。",
        45166: "content 不合法：正文里有微信不认的标签或属性（script/iframe/外站图片地址/未转义的尖括号之类），或小绿书 newspic 的正文传了 HTML。先跑 render 看 HTML，去掉可疑标签再推。",
        53404: "文章内容涉嫌违规，到公众号后台看具体提示，改正文后再推。",
        53405: "文章含敏感内容，到公众号后台看具体提示，改正文后再推。",
        45009: "接口调用次数到上限，明天再推。",
        48001: "这个账号没有这个接口的权限。",
        53503: "这篇草稿没过发布检查，去后台看草稿内容。",
        53504: "这篇草稿要去公众平台官网里用，接口发不了。",
        53505: "要先在公众平台官网手动保存成功，再发布。",
    }
    return "errcode=%s errmsg=%s%s" % (code, j.get("errmsg"), ("。" + tips[code]) if code in tips else "")


def is_no_permission(j):
    code = j.get("errcode")
    msg = str(j.get("errmsg") or "")
    return code in NO_PERMISSION_CODES or bool(NO_PERMISSION_RE.search(msg))


def get_token(appid, secret):
    q = urllib.parse.urlencode({"grant_type": "client_credential", "appid": appid, "secret": secret})
    j = http_json("GET", BASE + "/cgi-bin/token?" + q, timeout=20)
    if "access_token" not in j:
        die("拿 access_token 失败：" + explain(j))
    return j["access_token"]


def read_image(path, limit, shrink):
    if not os.path.exists(path):
        die("图片不存在：" + path)
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png"):
        die("只收 jpg/png：" + path)
    data = io.open(path, "rb").read()
    ctype = "image/png" if ext == ".png" else "image/jpeg"
    if len(data) > limit:
        if not shrink:
            die("图片超过 %dKB：%s" % (limit // 1024, path))
        try:
            from PIL import Image
        except Exception:
            die("图片超过 %dKB 且没装 Pillow 压不了：%s（自己压一下，或 pip install pillow）" % (limit // 1024, path))
        im = Image.open(io.BytesIO(data)).convert("RGB")
        quality, scale = 88, 1.0
        while True:
            w, h = im.size
            out = io.BytesIO()
            im.resize((max(1, int(w * scale)), max(1, int(h * scale)))).save(out, "JPEG", quality=quality, optimize=True)
            if out.tell() <= limit or (quality <= 50 and scale <= 0.4):
                break
            if quality > 50:
                quality -= 8
            else:
                scale *= 0.85
        data, ctype = out.getvalue(), "image/jpeg"
        path = os.path.splitext(path)[0] + ".jpg"
        print("  图片已压到 %dKB：%s" % (len(data) // 1024, os.path.basename(path)))
    return os.path.basename(path), data, ctype


def upload_body_image(token, path):
    name, data, ctype = read_image(path, BODY_IMG_LIMIT, shrink=True)
    body, ct = multipart({}, "media", name, data, ctype)
    j = http_json("POST", BASE + "/cgi-bin/media/uploadimg?access_token=" + token, body, {"Content-Type": ct}, timeout=120)
    if "url" not in j:
        die("uploadimg 失败（%s）：%s" % (path, explain(j)))
    return j["url"].replace("http://", "https://")


def upload_cover(token, path):
    name, data, ctype = read_image(path, COVER_LIMIT, shrink=False)
    body, ct = multipart({}, "media", name, data, ctype)
    j = http_json("POST", BASE + "/cgi-bin/material/add_material?access_token=%s&type=image" % token, body, {"Content-Type": ct}, timeout=180)
    if "media_id" not in j:
        die("封面 add_material 失败：" + explain(j))
    return j["media_id"]


# ---------- Markdown → 微信 HTML ----------
def inline(text, warnings):
    """行内：转义、图片占位、链接去 URL、粗体、斜体、行内代码。"""
    parts = []
    pos = 0
    for m in LINK_RE.finditer(text):
        parts.append(escape(text[pos:m.start()]))
        label, url = m.group(1), m.group(2).strip()
        if url.startswith("https://mp.weixin.qq.com/"):
            parts.append('<a href="%s">%s</a>' % (escape(url, quote=True), escape(label)))
        elif NO_CITE:
            warnings.append("正文链接已去掉网址只留文字：%s" % url[:60])
            parts.append(escape(label))
        else:
            CITATIONS.append((label, url))
            parts.append(escape(label) + '<sup>[%d]</sup>' % len(CITATIONS))
        pos = m.end()
    parts.append(escape(text[pos:]))
    s = "".join(parts)
    s = re.sub(r"`([^`]+)`", lambda m: INLINE_CODE + m.group(1) + "</span>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def md_to_html(md_text, drop_first_h1=True):
    """返回 (blocks, images, title_from_h1, warnings)。images = [(占位符, 路径, 说明)]。"""
    del CITATIONS[:]
    text = md_text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:]
    warnings = []
    n = len(DASH_RE.findall(text))
    if n:
        warnings.append("长破折号 %d 处已换成逗号" % n)
        text = DASH_RE.sub("，", text)
    lines = text.split("\n")
    blocks, images, title = [], [], None
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            inner = "".join(CODE_LINE + (escape(c) or "&nbsp;") + "</p>" for c in code)
            blocks.append('<section style="padding:12px 14px;background-color:#1f2937;border-radius:6px;">' + inner + "</section>")
            continue
        m = IMG_LINE_RE.match(s)
        if m:
            alt, src = m.group(1).strip(), m.group(2).strip()
            ph = "{{IMG:%d}}" % len(images)
            images.append((ph, src, alt))
            b = '<p style="margin:0;"><img src="%s" style="width:100%%;"/></p>' % ph
            if alt:
                b += CAPTION + escape(alt) + "</p>"
            blocks.append(b)
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
            blocks.append(HR)
            i += 1
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", s)
        if hm:
            if hm.group(1) == "#" and title is None and drop_first_h1:
                title = hm.group(2).strip()
                i += 1
                continue
            blocks.append(H + inline(hm.group(2).strip(), warnings) + "</p>")
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1].strip()):
            header = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            for row in rows:
                cells = [inline(c, warnings) for c in row]
                card = '<section style="padding:12px 15px;background-color:#f0f7ff;border-left:4px solid #1a73e8;margin:0;">'
                card += '<p style="font-size:15px;font-weight:bold;color:#111;line-height:1.8;letter-spacing:0.5px;margin:0;">%s</p>' % (cells[0] if cells else "")
                for k, c in enumerate(cells[1:], 1):
                    label = inline(header[k], warnings) if k < len(header) and header[k] else ""
                    card += P + (label + "：" if label else "") + c + "</p>"
                card += "</section>"
                blocks.append(card)
            continue
        if s.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            inner = "".join(P + inline(q, warnings) + "</p>" for q in quote if q)
            blocks.append('<section style="padding:12px 15px;background-color:#fff8e1;border-left:4px solid #ff8f00;margin:0;">' + inner + "</section>")
            continue
        if re.match(r"^([-*•]|\d+[.、])\s+", s):
            items = []
            while i < len(lines) and re.match(r"^([-*•]|\d+[.、])\s+", lines[i].strip()):
                t = lines[i].strip()
                mm = re.match(r"^(\d+[.、])\s+(.*)$", t)
                items.append((mm.group(1) + " " + mm.group(2)) if mm else "• " + re.sub(r"^[-*•]\s+", "", t))
                i += 1
            blocks.append("".join(P + inline(it, warnings) + "</p>" for it in items))
            continue
        para = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|>|\||!\[|[-*•]\s|\d+[.、]\s|-{3,}$)", lines[i].strip()):
            para.append(lines[i].strip())
            i += 1
        ptxt = "".join(para)
        for mm in INLINE_IMG_RE.finditer(ptxt):
            warnings.append("行内图片请单独成行：" + mm.group(2)[:60])
        ptxt = INLINE_IMG_RE.sub(lambda mm: mm.group(1), ptxt)
        blocks.append(P + inline(ptxt, warnings) + "</p>")
    return blocks, images, title, warnings


def assemble(blocks):
    body = ("\n" + BR + "\n").join(blocks)
    if CITATIONS:
        rows = "".join('<p style="font-size:13px;color:#888;line-height:1.7;margin:0 0 4px;word-break:break-all;">[%d] %s：%s</p>'
                       % (i + 1, escape(label), escape(url)) for i, (label, url) in enumerate(CITATIONS))
        body += "\n" + BR + '\n<section style="margin-top:24px;padding-top:12px;border-top:1px solid #eee;"><p style="font-size:13px;color:#888;margin:0 0 6px;">参考链接</p>%s</section>' % rows
    return body


def check_html(html, mode, images):
    errors, warnings = [], []
    for rx, msg in FORBIDDEN_HTML:
        if rx.search(html):
            errors.append(msg)
    if DASH_RE.search(html):
        errors.append("仍有长破折号")
    markers = MARKER_RE.findall(html)
    if markers:
        (warnings if mode == "render" else errors).append("还有 %d 处待作者处理的标记 [📝/💬/🖼/📊]，推之前要清掉" % len(markers))
    if mode == "final":
        for src in re.findall(r'<img src="([^"]+)"', html):
            if not src.startswith("https://mmbiz.qpic.cn/") and not src.startswith("https://mmbiz.qlogo.cn/"):
                errors.append("正文图不是微信图床地址：" + src[:60])
    elif mode == "render" and images:
        warnings.append("%d 张图在 render 模式下未上传，push 时会自动传" % len(images))
    chars = len(html)
    nbytes = len(html.encode("utf-8"))
    if chars > CONTENT_MAX_CHARS:
        errors.append("正文 HTML %d 字符，超过 %d" % (chars, CONTENT_MAX_CHARS))
    if nbytes > CONTENT_MAX_BYTES:
        errors.append("正文 HTML %d 字节，超过 1MB" % nbytes)
    return errors, warnings


def build(md_path, title, mode):
    md_text = io.open(md_path, encoding="utf-8").read()
    blocks, images, h1, warnings = md_to_html(md_text)
    title = (title or h1 or "").strip()
    html = assemble(blocks)
    errors, w2 = check_html(html, mode, images)
    warnings += w2
    if not title:
        errors.append("没有标题：用 --title 给，或者 Markdown 第一行写 # 标题")
    if len(title) > TITLE_MAX:
        errors.append("标题 %d 字，超过 %d" % (len(title), TITLE_MAX))
    return html, images, title, errors, warnings, cjk_count(md_text)


def report_build(title, html, images, errors, warnings, chars):
    print("标题：%s（%d 字）" % (title, len(title)))
    print("正文：约 %d 个汉字，%d 个区块，%d 张图" % (chars, html.count(BR) + 1, len(images)))
    for w in warnings:
        print("  提醒：" + w)
    for e in errors:
        print("  不过：" + e)


# ---------- 子命令 ----------
def cmd_check(args):
    appid, secret = load_credentials()
    token = get_token(appid, secret)
    print("ok：AppID %s… 拿到 access_token（长度 %d），白名单通。什么都没推。" % (appid[:6], len(token)))


def cmd_render(args):
    html, images, title, errors, warnings, chars = build(args.md, args.title, "render")
    report_build(title, html, images, errors, warnings, chars)
    out = args.out or os.path.splitext(args.md)[0] + ".wechat.html"
    for ph, src, _ in images:
        html = html.replace(ph, escape(src, quote=True))
    io.open(out, "w", encoding="utf-8", newline="\n").write(html)
    print("HTML 已写到：" + out + ("（有不过项，推之前先改）" if errors else ""))
    sys.exit(1 if errors else 0)


def article_opts(args):
    """draft/add 的三个可选项：留言开关、仅粉丝留言、「阅读原文」地址。"""
    comment = getattr(args, "comment", "open") or "open"
    d = {"need_open_comment": 0 if comment == "off" else 1,
         "only_fans_can_comment": 1 if comment == "fans" else 0}
    src = (getattr(args, "source_url", None) or "").strip()
    if src:
        if not src.startswith(("http://", "https://")):
            die("--source-url 要以 http:// 或 https:// 开头")
        d["content_source_url"] = src
    return d


def cmd_tunnel(args):
    vps = args.vps or "root@远程机IP"
    print("本机没有固定 IP 时这么用：白名单只填远程机的 IP，本机开一条隧道，微信接口的流量从远程机出去，AppSecret 不离开本机。")
    print("一 本机开着一条隧道（开着别关）：")
    print("    ssh -N -L 127.0.0.1:8443:api.weixin.qq.com:443 %s" % vps)
    print("二 ~/.wechat-mp.env 加一行：TUNNEL=127.0.0.1:8443")
    print("三 之后 check / push / publish 照常跑，流量自动走隧道。")
    if not TUNNEL:
        print("现在没配 TUNNEL，先做第二步再回来测。")
        return
    q = urllib.parse.urlencode({"grant_type": "client_credential", "appid": "tunnel-test", "secret": "tunnel-test"})
    j = http_json("GET", BASE + "/cgi-bin/token?" + q, timeout=20, fatal=False)
    if j.get("errcode") in (40013, 40125, 41002, 40001):
        print("ok：隧道通，微信那头收到了请求（回 errcode=%s 是因为用的测试 appid，正常）。" % j.get("errcode"))
    else:
        print("隧道不通或微信没回：%s" % explain(j))


def cmd_push(args):
    html, images, title, errors, warnings, chars = build(args.md, args.title, "prepush")
    report_build(title, html, images, errors, warnings, chars)
    if errors:
        die("先把上面的不过项改掉再推")
    author = (args.author or "").strip()
    if len(author) > AUTHOR_MAX:
        die("作者 %d 字，超过 %d" % (len(author), AUTHOR_MAX))
    digest = (args.digest or "").strip()
    if len(digest) > DIGEST_MAX:
        die("摘要 %d 字，超过 %d" % (len(digest), DIGEST_MAX))
    if not args.cover or not os.path.exists(args.cover):
        die("封面必填（--cover 封面.jpg），图文草稿没有封面推不进去")
    base_dir = os.path.dirname(os.path.abspath(args.md))
    paths = []
    for ph, src, _ in images:
        p = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if src.startswith("https://mmbiz.qpic.cn/"):
            paths.append((ph, None, src))
        elif src.startswith("http://") or src.startswith("https://"):
            die("正文图是外链，先下载到本地再引用：" + src[:80])
        elif not os.path.exists(p):
            die("正文图不存在：" + p)
        else:
            paths.append((ph, p, None))
    if args.dry_run:
        for ph, p, url in paths:
            html = html.replace(ph, url or escape(p, quote=True))
        payload = {"articles": [dict({"title": title, "author": author, "digest": digest, "content": html,
                                      "thumb_media_id": "<dry-run>"}, **article_opts(args))]}
        out = os.path.splitext(args.md)[0] + ".draft-dryrun.json"
        io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(payload, ensure_ascii=False, indent=1))
        print("dry-run：没联网。请求体已写到 " + out)
        return
    appid, secret = load_credentials()
    token = get_token(appid, secret)
    print("ok：access_token 拿到")
    img_urls = {}
    for ph, p, url in paths:
        if url is None:
            url = upload_body_image(token, p)
            print("  正文图已传：%s -> %s…" % (os.path.basename(p), url[:48]))
        img_urls[ph] = url
        html = html.replace(ph, url)
    thumb = upload_cover(token, args.cover)
    print("  封面已传为永久素材：thumb_media_id=" + thumb)
    errors, _ = check_html(html, "final", images)
    if errors:
        die("推送前校验不过：" + "；".join(errors))
    article = dict({"title": title, "author": author, "digest": digest, "content": html,
                    "thumb_media_id": thumb}, **article_opts(args))
    body = json.dumps({"articles": [article]}, ensure_ascii=False).encode("utf-8")
    j = http_json("POST", BASE + "/cgi-bin/draft/add?access_token=" + token, body,
                  {"Content-Type": "application/json; charset=utf-8"}, timeout=120)
    if "media_id" not in j:
        die("draft/add 失败：" + explain(j))
    media_id = j["media_id"]
    print("ok：草稿已进草稿箱，media_id=" + media_id)
    ok, msg = readback(token, media_id, title, len(img_urls))
    print(("ok：" if ok else "注意：") + msg)
    result = {"title": title, "media_id": media_id, "thumb_media_id": thumb, "images": img_urls,
              "chinese_chars": chars, "pushed_at": _dt.datetime.now().isoformat(timespec="seconds"), "readback": msg}
    out = os.path.splitext(args.md)[0] + ".draft-result-%s.json" % _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(result, ensure_ascii=False, indent=1))
    print("结果已落盘：" + out + "（报 media_id 从这里复制，别手抄）")
    print("接下来是人的活：去公众号后台草稿箱点进这篇，看图和排版，勾「声明原创」，开「赞赏」，没问题再点发布。")


def draft_get(token, media_id):
    """draft/get 原样返回 JSON（响应是 text/plain 不带 charset，http_json 已按 UTF-8 解）。"""
    return post_json(token, "/cgi-bin/draft/get", {"media_id": media_id}, timeout=60)


def readback(token, media_id, title=None, n_images=None):
    j = draft_get(token, media_id)
    if "news_item" not in j:
        return False, "draft/get 失败：" + explain(j)
    a = j["news_item"][0]
    content = a.get("content", "")
    imgs = content.count("mmbiz.qpic.cn")
    problems = []
    if title and a.get("title") != title:
        problems.append("标题回读不一致：%r" % a.get("title"))
    if n_images is not None and imgs < n_images:
        problems.append("图片回读 %d 张，少于上传的 %d 张" % (imgs, n_images))
    if DASH_RE.search(content):
        problems.append("回读正文里有长破折号")
    summary = "回读：标题《%s》，正文约 %d 汉字，%d 张微信图床图" % (a.get("title"), cjk_count(content), imgs)
    return (not problems), summary + ("" if not problems else "；" + "；".join(problems))


def cmd_verify(args):
    appid, secret = load_credentials()
    token = get_token(appid, secret)
    ok, msg = readback(token, args.media_id)
    print(("ok：" if ok else "注意：") + msg)


# ---------- 发布（只在人说「发」之后、只对微信认证企业号） ----------
def publish_status_text(status):
    return PUBLISH_STATUS.get(status, "未知状态")


def cmd_publish(args):
    if not args.reviewed:
        print("拒绝：人要先在后台看过草稿 说一句发 才能跑。看过了、说了发，再加 --reviewed 跑一次。什么都没发。")
        sys.exit(2)
    media_id = (args.media_id or "").strip()
    if not media_id:
        die("--media-id 不能为空，从 *.draft-result-<时间>.json 里复制")
    out_dir = os.path.abspath(args.out_dir or os.getcwd())
    if not os.path.isdir(out_dir):
        die("--out-dir 不存在，什么都没发：" + out_dir)
    appid, secret = load_credentials()
    token = get_token(appid, secret)
    print("ok：access_token 拿到")

    # 1. 回读：确认草稿还在，打印标题
    j = draft_get(token, media_id)
    if "news_item" not in j:
        die("draft/get 失败，草稿不存在、media_id 不对或这个号的草稿箱接口没开通，什么都没发：" + explain(j))
    items = j["news_item"]
    titles = [a.get("title") or "" for a in items]
    print("回读：草稿存在，%d 篇，标题《%s》" % (len(items), "》《".join(titles)))
    print("提交发布后接口收不回来，发之前确认人已经在后台看过这篇草稿。")

    # 2. 提交发布
    j = post_json(token, "/cgi-bin/freepublish/submit", {"media_id": media_id}, timeout=60)
    if j.get("errcode", 0) != 0 or "publish_id" not in j:
        if is_no_permission(j):
            die("freepublish/submit 没权限：%s %s" % (explain(j), PUBLISH_PERMISSION_NOTE))
        die("freepublish/submit 失败：" + explain(j))
    publish_id = j["publish_id"]
    msg_data_id = j.get("msg_data_id")
    print("ok：发布任务已提交，publish_id=%s" % publish_id)

    # 提交成功就先落一次盘：publish_id 一定进文件，后面查状态出什么错都不丢
    now = _dt.datetime.now()
    safe_id = re.sub(r"[^A-Za-z0-9_\-]", "_", media_id)
    out = os.path.join(out_dir, "%s.publish-result-%s.json" % (safe_id, now.strftime("%Y%m%d-%H%M%S")))

    def write_result(status, last, polls):
        detail = last.get("article_detail") or {}
        urls = [it.get("article_url") for it in (detail.get("item") or []) if it.get("article_url")]
        fail_idx = last.get("fail_idx") or []
        result = {
            "media_id": media_id,
            "titles": titles,
            "publish_id": publish_id,
            "msg_data_id": msg_data_id,
            "publish_status": status,
            "publish_status_text": publish_status_text(status) if status is not None else "没查到状态",
            "article_id": last.get("article_id"),
            "article_urls": urls,
            "fail_idx": fail_idx,
            "polls": polls,
            "submitted_at": now.isoformat(timespec="seconds"),
        }
        io.open(out, "w", encoding="utf-8", newline="\n").write(json.dumps(result, ensure_ascii=False, indent=1))
        return urls, fail_idx

    write_result(None, {}, [])
    print("结果已落盘（publish_id 已记进去，查状态之后会覆盖写）：" + out)

    # 3. 轮询状态：最多 6 次，每次隔 5 秒。查状态的网络错误不致命，记进 polls 继续查
    status, last, polls = None, {}, []
    for attempt in range(1, PUBLISH_POLL_TIMES + 1):
        last = post_json(token, "/cgi-bin/freepublish/get", {"publish_id": publish_id}, timeout=60, fatal=False)
        if "publish_status" not in last:
            print("  第 %d 次查状态失败：%s" % (attempt, explain(last)))
            polls.append({"attempt": attempt, "error": explain(last)})
        else:
            status = last.get("publish_status")
            polls.append({"attempt": attempt, "publish_status": status})
            print("  第 %d 次查状态：%s（publish_status=%s）" % (attempt, publish_status_text(status), status))
            if status != 1:
                break
        if attempt < PUBLISH_POLL_TIMES:
            time.sleep(PUBLISH_POLL_INTERVAL)

    # 4. 落盘：同一个文件名覆盖写
    urls, fail_idx = write_result(status, last, polls)
    print("结果已落盘：" + out)

    # 5. 按状态报中文
    if status == 0:
        print("ok：发布成功，《%s》已发布。" % "》《".join(titles))
        for u in urls:
            print("  article_url=" + u)
        if not urls:
            print("  接口没回 article_url，去后台「已发表」里拿链接。")
        print("接下来是人的活：把文章链接交回群。原创和赞赏要在后台草稿里勾好再说发，评论置顶去后台做。")
        return
    if status == 1:
        print("注意：查了 %d 次还在发布中，不再等了。publish_id=%s 已记在结果文件里，几分钟后去后台「已发表」看结果。"
              % (PUBLISH_POLL_TIMES, publish_id))
        return
    if status is None:
        die("提交成功但 %d 次都没查到状态。publish_id=%s 已记在结果文件里，去后台「已发表」看结果。"
            % (PUBLISH_POLL_TIMES, publish_id))
    hint = {
        2: "原创声明没过，去后台看这篇的原创状态，改完重新推草稿再发。",
        3: "常规失败，去后台看这篇草稿，fail_idx=%s。" % fail_idx,
        4: "平台审核不通过，去后台看通知里的原因，改完重新推草稿再发。",
        5: "发出去过，之后被用户在后台删了。",
        6: "发出去过，之后被系统封了，去后台看通知。",
    }.get(status, "publish_status=%s 不在已知表里，去后台看。" % status)
    die("发布没成：%s。%s" % (publish_status_text(status), hint))


def main():
    ap = argparse.ArgumentParser(description="公众号推草稿箱；publish 只在人说「发」之后跑，只有微信认证企业号能用；没有删草稿命令")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("check", help="拿 token 验证凭据和白名单，不推")
    r = sub.add_parser("render", help="Markdown 转微信 HTML 并校验，不联网")
    r.add_argument("--md", required=True)
    r.add_argument("--out")
    r.add_argument("--title")
    r.add_argument("--no-cite", action="store_true", help="外链只留文字，不生成文末「参考链接」")
    p = sub.add_parser("push", help="传图、传封面、推草稿箱、回读")
    p.add_argument("--no-cite", action="store_true", help="外链只留文字，不生成文末「参考链接」")
    p.add_argument("--comment", choices=["open", "fans", "off"], default="open", help="留言：open 所有人可留言（默认）/ fans 仅粉丝 / off 关闭")
    p.add_argument("--source-url", help="「阅读原文」指向的地址（content_source_url），不填就没有")
    p.add_argument("--md", required=True)
    p.add_argument("--title")
    p.add_argument("--cover")
    p.add_argument("--digest", default="")
    p.add_argument("--author", default="")
    p.add_argument("--dry-run", action="store_true", help="不联网，把请求体写到文件看")
    v = sub.add_parser("verify", help="回读一篇草稿")
    v.add_argument("--media-id", required=True)
    pb = sub.add_parser("publish", help="人在后台看过草稿、说了「发」之后才跑：回读、提交发布、轮询状态；只有微信认证企业号能用")
    pb.add_argument("--media-id", required=True, help="草稿的 media_id，从 *.draft-result-<时间>.json 里复制")
    pb.add_argument("--reviewed", action="store_true", help="人已经在后台看过这篇草稿并说了发。没有这个参数直接拒绝")
    pb.add_argument("--out-dir", help="结果文件 *.publish-result-<时间>.json 放哪个目录，默认当前目录")
    tn = sub.add_parser("tunnel", help="本机没有固定 IP：借远程机的 IP 过白名单。打印 ssh 命令，配了 TUNNEL 就顺带测一下通不通")
    tn.add_argument("--vps", help="远程机 用户@IP，只用来打印 ssh 命令")
    args = ap.parse_args()
    load_tunnel()
    global NO_CITE
    NO_CITE = bool(getattr(args, "no_cite", False))
    if args.cmd == "check":
        cmd_check(args)
    elif args.cmd == "render":
        cmd_render(args)
    elif args.cmd == "push":
        cmd_push(args)
    elif args.cmd == "verify":
        cmd_verify(args)
    elif args.cmd == "publish":
        cmd_publish(args)
    elif args.cmd == "tunnel":
        cmd_tunnel(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
