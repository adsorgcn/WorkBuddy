#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""贴图卡片：把带【第N页】标记的 Markdown 切成一张张 1080×1440 的 PNG，交给 push-newspic 推成公众号图片消息。

只用标准库。排版交给机器上现成的 Chromium 内核（Windows 自带 Edge，Mac/Linux 用 Chrome 或 Chromium），
一行排版算法不写：每页填进 cards.html 模板，无头截图，截完逐张校验（张数、编号、尺寸、有没有放不下）。
放不下不缩字：模板里的脚本会在图顶部画一条红条，本脚本读 PNG 顶部像素发现红条就报「第 k 张放不下了，删字」。

用法：
  python newspic_cards.py --md 贴图稿.md --out cards [--template cards.html] [--style style.json]
                          [--footer "公众号 · 名字"] [--browser 路径] [--min 2] [--max 20]
贴图稿写法：
  【第1页】         （也认【第一页】【第 1 页】）
  第一行是这张卡的标题
  后面每行一段；以「- 」开头的行当要点
  【第2页】
  ...
第 1 页是封面卡（文字落在中央正方形里，信息流会裁成 1:1），最后一页是结尾卡，中间是要点卡。
输出：cards/01.png … cards/NN.png，加 cards/manifest.json（每张的标题、字数、是否放不下）。
"""
import argparse, datetime, html, io, json, os, re, shutil, struct, subprocess, sys, tempfile, time, zlib

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE_RE = re.compile(r"^\s*【\s*第\s*([0-9一二三四五六七八九十两]+)\s*页\s*】\s*$")
MARKER_RE = re.compile(r"\[(📝|💬|🖼|📊)[^\]]*\]")
DASH_RE = re.compile("[—–]")
W, H = 1080, 1440
WARN_RGB = (200, 16, 46)          # 模板 .warn 的底色 #c8102e
DEFAULT_STYLE = {                 # 对应 cards.html :root 里的变量，--style 的 JSON 只能改这几个键
    "bg": "#f6f1e7", "ink": "#1f1b16", "muted": "#6b6257", "accent": "#c8102e", "card": "#fffdf8",
    "font": '"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif',
    "title": "64px", "body": "40px", "cover_title": "84px", "lh": "1.55",
}
BROWSERS = [
    os.environ.get("NEWSPIC_BROWSER", ""),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]


def die(msg, code=1):
    print("错误：" + msg)
    sys.exit(code)


# ---------- 切页 ----------
def split_pages(md_text):
    """按【第N页】切。返回 [(页号文本, 正文行列表)]。标记前的内容若非空，当第一页（并提醒）。"""
    pages, cur, cur_no, lead = [], [], None, []
    text = md_text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("---\n"):                      # YAML 头跳过，跟 wechat_draft.py 一样
        end = text.find("\n---\n", 4)
        if end != -1:
            text = text[end + 5:]
    for line in text.split("\n"):
        m = PAGE_RE.match(line)
        if m:
            if cur_no is None and any(l.strip() for l in cur):
                lead = cur
            elif cur_no is not None:
                pages.append((cur_no, cur))
            cur, cur_no = [], m.group(1)
            continue
        cur.append(line)
    if cur_no is not None:
        pages.append((cur_no, cur))
    if lead:
        pages.insert(0, ("0", lead))
    return pages


def page_parts(lines):
    """一页的行 → (标题, 正文行)。第一个非空行是标题。"""
    body = [l.rstrip() for l in lines]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    if not body:
        return "", []
    title = body[0].strip().lstrip("#").strip()
    rest = [l for l in body[1:]]
    # 连续空行压成一个
    out, blank = [], False
    for l in rest:
        if not l.strip():
            if out and not blank:
                out.append("")
            blank = True
        else:
            out.append(l.strip()); blank = False
    return title, out


def validate_pages(pages, min_pages=2, max_pages=20, max_chars=None):
    """切完先核：张数、每页非空、没有残留标记和长破折号。返回错误列表（空＝过）。"""
    errors = []
    if not pages:
        return ["没找到【第N页】标记，贴图稿每页开头要有一行「【第1页】」这样的标记"]
    if pages[0][0] == "0":
        errors.append("第一个【第N页】标记前面有内容，已当成第 1 页；要么删掉，要么给它加标记")
    n = len(pages)
    if n < min_pages:
        errors.append("只有 %d 页，少于 %d" % (n, min_pages))
    if n > max_pages:
        errors.append("有 %d 页，多于 %d（图片消息最多 20 张）" % (n, max_pages))
    for k, (no, lines) in enumerate(pages, 1):
        title, body = page_parts(lines)
        text = title + "\n" + "\n".join(body)
        if not title:
            errors.append("第 %d 张是空的" % k)
        if MARKER_RE.search(text):
            errors.append("第 %d 张还有 [📝/💬/🖼/📊] 标记没清" % k)
        if DASH_RE.search(text):
            errors.append("第 %d 张有长破折号，换成逗号或句号" % k)
        if max_chars and len(re.sub(r"\s", "", text)) > max_chars:
            errors.append("第 %d 张 %d 字，超过 %d" % (k, len(re.sub(r"\s", "", text)), max_chars))
    return errors


# ---------- 模板 ----------
def inline_html(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return s


def fill_template(tpl, style, kind, title, body_lines, page, total, footer, kicker=""):
    css_vars = "".join("--%s:%s;" % (k.replace("_", "-"), v) for k, v in style.items())
    paras = []
    for l in body_lines:
        if not l:
            continue
        if re.match(r"^[-*•]\s+", l):
            paras.append('<p class="li">%s</p>' % inline_html(re.sub(r"^[-*•]\s+", "", l)))
        else:
            paras.append("<p>%s</p>" % inline_html(l))
    sub = ""
    if kind == "cover" and paras:
        sub = re.sub(r"</?p[^>]*>", "", paras[0])
        paras = paras[1:]
    out = tpl
    for k, v in (("{{CSS_VARS}}", css_vars), ("{{KIND}}", kind), ("{{TITLE}}", inline_html(title)), ("{{SUB}}", sub),
                 ("{{BODY}}", "\n".join(paras)), ("{{NUM}}", "%02d" % page), ("{{PAGE}}", str(page)), ("{{TOTAL}}", str(total)),
                 ("{{FOOTER}}", html.escape(footer)), ("{{KICKER}}", html.escape(kicker))):
        out = out.replace(k, v)
    return out


# ---------- 无头浏览器截图 ----------
def find_browser(explicit=None):
    for p in [explicit] + BROWSERS:
        if p and os.path.exists(p):
            return p
    for name in ("google-chrome", "chromium", "chromium-browser", "msedge", "microsoft-edge"):
        w = shutil.which(name)
        if w:
            return w
    return None


def screenshot(browser, html_path, png_path, timeout=30):
    """启动器几十毫秒就返回，真正的截图是子进程写的，所以只认文件出现且大小稳定。"""
    profile = tempfile.mkdtemp(prefix="newspic-")
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    cmd = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
           "--disable-background-networking", "--allow-file-access-from-files", "--hide-scrollbars",
           "--user-data-dir=" + profile, "--window-size=%d,%d" % (W, H), "--screenshot=" + os.path.abspath(png_path), url]
    if os.path.exists(png_path):
        os.remove(png_path)
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout)
        t0 = time.time(); last = -1
        while time.time() - t0 < timeout:
            if os.path.exists(png_path):
                size = os.path.getsize(png_path)
                if size > 1024 and size == last:
                    return True
                last = size
            time.sleep(0.25)
        return os.path.exists(png_path) and os.path.getsize(png_path) > 1024
    finally:
        shutil.rmtree(profile, ignore_errors=True)


# ---------- PNG 校验（只用 zlib，不装 Pillow） ----------
def png_info(path):
    """返回 (宽, 高, 位深, 颜色类型)；不是 PNG 返回 None。"""
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
        return None
    w, h, depth, ctype = struct.unpack(">IIBB", head[16:26])
    return w, h, depth, ctype


def png_top_rows(path, rows=4):
    """解出 PNG 最上面几行的像素（RGB 元组列表的列表）。只解前几行，所以快。"""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, w, h, ctype = 8, [], 0, 0, 0
    while pos < len(data):
        ln, = struct.unpack(">I", data[pos:pos + 4]); tag = data[pos + 4:pos + 8]; chunk = data[pos + 8:pos + 8 + ln]
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", chunk[:10])
        elif tag == b"IDAT":
            idat.append(chunk)
        elif tag == b"IEND":
            break
        pos += 12 + ln
    bpp = {2: 3, 6: 4}.get(ctype)
    if not bpp:
        return None
    raw = zlib.decompress(b"".join(idat))
    stride = w * bpp
    prev = bytearray(stride)
    out = []
    for r in range(min(rows, h)):
        off = r * (stride + 1)
        ft = raw[off]; line = bytearray(raw[off + 1:off + 1 + stride])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if ft == 1: line[i] = (line[i] + a) & 255
            elif ft == 2: line[i] = (line[i] + b) & 255
            elif ft == 3: line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif ft == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else c))) & 255
        out.append([tuple(line[x * bpp:x * bpp + 3]) for x in range(w)])
        prev = line
    return out


def has_overflow_bar(path):
    rows = png_top_rows(path, rows=4)
    if not rows:
        return False
    hits = 0
    for x in range(20, W - 20, 40):
        r, g, b = rows[2][x]
        if abs(r - WARN_RGB[0]) < 24 and abs(g - WARN_RGB[1]) < 24 and abs(b - WARN_RGB[2]) < 24:
            hits += 1
    return hits >= 20


def validate_pngs(out_dir, n):
    errors, sizes = [], []
    for k in range(1, n + 1):
        p = os.path.join(out_dir, "%02d.png" % k)
        if not os.path.exists(p):
            errors.append("第 %d 张没出图：%s" % (k, p)); continue
        info = png_info(p)
        if not info:
            errors.append("第 %d 张不是 PNG" % k); continue
        if (info[0], info[1]) != (W, H):
            errors.append("第 %d 张尺寸 %dx%d，不是 %dx%d" % (k, info[0], info[1], W, H))
        if os.path.getsize(p) <= 1024:
            errors.append("第 %d 张只有 %d 字节，像是空图" % (k, os.path.getsize(p)))
        sizes.append(os.path.getsize(p))
    return errors, sizes


# ---------- 主流程 ----------
def main():
    ap = argparse.ArgumentParser(description="贴图卡片：【第N页】切页 → cards.html 模板 → 无头浏览器截 1080×1440 PNG → 逐张校验")
    ap.add_argument("--md", required=True, help="贴图稿 Markdown，每页开头一行【第N页】")
    ap.add_argument("--out", default="cards", help="输出目录，默认 cards")
    ap.add_argument("--template", default=os.path.join(HERE, "cards.html"))
    ap.add_argument("--style", help="JSON，只能改 bg/ink/muted/accent/card/font/title/body/cover_title/lh 这几个键")
    ap.add_argument("--footer", default="", help="每张卡底部的小字，比如「公众号 · 名字」，不填就空")
    ap.add_argument("--kicker", default="", help="封面卡标题上方的一行小字，不填就空")
    ap.add_argument("--browser", help="Chromium 内核浏览器的路径；不填自动找 Edge/Chrome")
    ap.add_argument("--min", type=int, default=2); ap.add_argument("--max", type=int, default=20)
    ap.add_argument("--max-chars", type=int, help="每张卡最多几个字（不含空白），不填不拦，放不下靠红条")
    ap.add_argument("--check-only", action="store_true", help="只切页校验，不出图")
    a = ap.parse_args()

    md = io.open(a.md, encoding="utf-8").read()
    pages = split_pages(md)
    errors = validate_pages(pages, a.min, a.max, a.max_chars)
    if errors:
        print("切页不过：\n  " + "\n  ".join(errors)); sys.exit(1)
    n = len(pages)
    print("切出 %d 张：" % n + "、".join("[%d] %s" % (k, page_parts(l)[0][:18]) for k, (_, l) in enumerate(pages, 1)))
    if a.check_only:
        return

    style = dict(DEFAULT_STYLE)
    if a.style:
        extra = json.load(io.open(a.style, encoding="utf-8"))
        bad = [k for k in extra if k not in DEFAULT_STYLE]
        if bad:
            die("--style 里有不认识的键：%s（只认 %s）" % (bad, ", ".join(DEFAULT_STYLE)))
        style.update({k: str(v) for k, v in extra.items()})
    if not os.path.exists(a.template):
        die("模板不存在：" + a.template)
    tpl = io.open(a.template, encoding="utf-8").read()
    browser = find_browser(a.browser)
    if not browser:
        die("找不到 Chromium 内核的浏览器。Windows 自带 Edge 一般在 C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe；Mac 装 Chrome；或用 --browser 指路径")
    os.makedirs(a.out, exist_ok=True)
    manifest = {"source": os.path.abspath(a.md), "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "browser": browser, "size": [W, H], "pages": []}
    overflow = []
    for k, (_, lines) in enumerate(pages, 1):
        title, body = page_parts(lines)
        kind = "cover" if k == 1 else ("end" if k == n else "point")
        page_html = fill_template(tpl, style, kind, title, body, k, n, a.footer, a.kicker)
        hp = os.path.join(a.out, "%02d.html" % k); pp = os.path.join(a.out, "%02d.png" % k)
        io.open(hp, "w", encoding="utf-8", newline="\n").write(page_html)
        ok = screenshot(browser, hp, pp)
        if not ok:
            die("第 %d 张没截出来（30 秒内没见到文件）。看看浏览器路径对不对、磁盘能不能写：%s" % (k, pp))
        over = has_overflow_bar(pp)
        if over:
            overflow.append(k)
        chars = len(re.sub(r"\s", "", title + "".join(body)))
        manifest["pages"].append({"page": k, "kind": kind, "title": title, "chars": chars, "png": os.path.abspath(pp), "overflow": over})
        print("  [%d/%d] %s %s %d 字%s" % (k, n, kind, title[:20], chars, "  放不下了" if over else ""))
    errors, sizes = validate_pngs(a.out, n)
    if overflow:
        errors.append("放不下的卡：第 %s 张，删字再跑；不缩字号" % "、".join(str(x) for x in overflow))
    manifest["errors"] = errors
    io.open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8", newline="\n").write(json.dumps(manifest, ensure_ascii=False, indent=1))
    if errors:
        print("出图校验不过：\n  " + "\n  ".join(errors)); sys.exit(1)
    print("ok：%d 张卡在 %s，共 %dKB，清单 manifest.json。人先看一遍图，再推：" % (n, os.path.abspath(a.out), sum(sizes) // 1024))
    print("  python wechat_draft.py push-newspic --title \"<标题>\" --text <配文.txt> --images-dir %s" % a.out)


if __name__ == "__main__":
    main()
