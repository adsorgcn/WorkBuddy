#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号推草稿箱（只到草稿箱，没有发布命令，没有删草稿命令）。

用法：
  python wechat_draft.py check                                  读配置、拿 access_token、打印 ok，不推任何东西
  python wechat_draft.py render --md 文章.md [--out 文章.html]   只把 Markdown 转成微信 HTML 并校验，不联网
  python wechat_draft.py push --md 文章.md --title "标题" --cover 封面.jpg [--digest "摘要"] [--author "作者"] [--dry-run]
                                                                传图、传封面、推草稿箱、回读核对、落盘结果
  python wechat_draft.py verify --media-id XXXX                 回读一篇草稿，核对中文、图片数、字数

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
import urllib.parse
import urllib.request
import uuid
from html import escape

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://api.weixin.qq.com"
UA = "wechat-draft-push/1.0"
BODY_IMG_LIMIT = 1024 * 1024          # uploadimg：jpg/png，1MB 以内
COVER_LIMIT = 10 * 1024 * 1024        # add_material type=image：10MB 以内
TITLE_MAX, AUTHOR_MAX, DIGEST_MAX = 32, 16, 120
CONTENT_MAX_CHARS, CONTENT_MAX_BYTES = 20000, 1024 * 1024

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
def http_json(method, url, data=None, headers=None, timeout=60):
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
        die("网络请求失败：%s（%s）" % (e, url.split("?")[0]))
    try:
        return json.loads(raw.decode("utf-8"))   # 微信返回 text/plain 不带 charset，必须自己按 UTF-8 解
    except Exception:
        die("微信返回的不是 JSON：%r" % raw[:200])


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
        40007: "media_id 不合法，多半是封面没传成永久素材。",
        45110: "author 太长，16 字以内。",
        45009: "接口调用次数到上限，明天再推。",
        48001: "这个账号没有这个接口的权限。",
    }
    return "errcode=%s errmsg=%s%s" % (code, j.get("errmsg"), ("。" + tips[code]) if code in tips else "")


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
        else:
            warnings.append("正文链接已去掉网址只留文字：%s" % url[:60])
            parts.append(escape(label))
        pos = m.end()
    parts.append(escape(text[pos:]))
    s = "".join(parts)
    s = re.sub(r"`([^`]+)`", lambda m: INLINE_CODE + m.group(1) + "</span>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s


def md_to_html(md_text, drop_first_h1=True):
    """返回 (blocks, images, title_from_h1, warnings)。images = [(占位符, 路径, 说明)]。"""
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
    return ("\n" + BR + "\n").join(blocks)


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
        payload = {"articles": [{"title": title, "author": author, "digest": digest, "content": html,
                                 "thumb_media_id": "<dry-run>", "need_open_comment": 1, "only_fans_can_comment": 0}]}
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
    article = {"title": title, "author": author, "digest": digest, "content": html,
               "thumb_media_id": thumb, "need_open_comment": 1, "only_fans_can_comment": 0}
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


def readback(token, media_id, title=None, n_images=None):
    body = json.dumps({"media_id": media_id}).encode("utf-8")
    j = http_json("POST", BASE + "/cgi-bin/draft/get?access_token=" + token, body,
                  {"Content-Type": "application/json; charset=utf-8"}, timeout=60)
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


def main():
    ap = argparse.ArgumentParser(description="公众号推草稿箱（没有发布命令）")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("check", help="拿 token 验证凭据和白名单，不推")
    r = sub.add_parser("render", help="Markdown 转微信 HTML 并校验，不联网")
    r.add_argument("--md", required=True)
    r.add_argument("--out")
    r.add_argument("--title")
    p = sub.add_parser("push", help="传图、传封面、推草稿箱、回读")
    p.add_argument("--md", required=True)
    p.add_argument("--title")
    p.add_argument("--cover")
    p.add_argument("--digest", default="")
    p.add_argument("--author", default="")
    p.add_argument("--dry-run", action="store_true", help="不联网，把请求体写到文件看")
    v = sub.add_parser("verify", help="回读一篇草稿")
    v.add_argument("--media-id", required=True)
    args = ap.parse_args()
    if args.cmd == "check":
        cmd_check(args)
    elif args.cmd == "render":
        cmd_render(args)
    elif args.cmd == "push":
        cmd_push(args)
    elif args.cmd == "verify":
        cmd_verify(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
