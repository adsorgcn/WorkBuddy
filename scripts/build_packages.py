# -*- coding: utf-8 -*-
"""门禁 + 打包（GitHub 版，仓库内跑，本地和 Actions 都用）。

检查：plugin.json / marketplace.json 版本一致、plugin.skills 列全；专家与每个 SKILL 的 frontmatter 齐；
IML 工作链用官方编译器回环（IML_REPO 指向 iml-protocol 的克隆，本地没有就跳过并警告，Actions 里没有算失败）；
技能正文的 [VERSION:] 标签与版本一致；无控制字符、正文无长破折号；商店文案无效果承诺；@references 存在；脚本能编译；
scripts/test_quality.py 的回归用例全过（聚类、时间归一、排序、日程、排版、版本号同步、派活流）。
依赖：只用标准库；装了 PyYAML 就用它解 frontmatter，没装就用内置的小解析。
全过才打包：每个技能一个 zip，加一个专家 zip，默认放 dist/（BUILD_OUT 可改）。
用法：python scripts/build_packages.py [--no-zip]
"""
import datetime, io, json, os, re, subprocess, sys, tempfile, zipfile, py_compile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experts", "ilang-wechat-awesome")
SKILLS_DIR = os.path.join(EXP, "skills")
IML_REPO = os.environ.get("IML_REPO") or os.path.join(os.path.dirname(ROOT), "iml-protocol")
OUT = os.environ.get("BUILD_OUT") or os.path.join(ROOT, "dist")
TODAY = datetime.date.today().isoformat()
CHAINS = {
    "wechat-article": "[PARS:@USER]=>[GET:@SRC]=>[DRFT|sty=casual]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]",
    "wechat-draft-push": "[GET:@SRC]=>[CHEK]=>[SEND:@DST]=>[CHEK]=>[Ω]",
    "wechat-topic-hunter": "[PARS:@USER]=>[GET:@SRC]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]",
    "remote-dispatch": "[PARS:@USER]=>[SEND:@DST]=>[GET:@SRC]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]",
}
AGENT_CHAIN = "wechat-article"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

fails = []
def fail(msg): fails.append(msg); print("FAIL", msg)
def ok(msg): print("ok  ", msg)
def read(p): return io.open(p, encoding="utf-8").read()


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    try:
        import yaml
        return yaml.safe_load(m.group(1)), text[m.end():]
    except ImportError:
        return parse_simple_yaml(m.group(1)), text[m.end():]


def parse_simple_yaml(s):
    """没有 PyYAML 时的小解析：key: 值、带引号的值、[a, b] 列表、一层缩进的子键（displayName / profession 这种）。"""
    out, cur = {}, None
    for line in s.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        ind = len(line) - len(line.lstrip())
        k, _, v = line.strip().partition(":")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        elif v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
        elif v == "":
            v = {}
        if ind == 0:
            out[k] = v; cur = k if v == {} else None
        elif cur is not None and isinstance(out.get(cur), dict):
            out[cur][k] = v
    return out


def iml_available():
    return os.path.isdir(os.path.join(IML_REPO, "iml"))


def compile_chain(chain):
    r = subprocess.run([sys.executable, "-m", "iml", "compile", "-"], cwd=IML_REPO, input=chain + "\n", capture_output=True, text=True, encoding="utf-8")
    return r.returncode, r.stdout.strip()


def decompile_line(line):
    r = subprocess.run([sys.executable, "-m", "iml", "decompile", "-"], cwd=IML_REPO, input=line + "\n", capture_output=True, text=True, encoding="utf-8")
    return r.stdout


iml_re = re.compile(r"^`?(#iml/0\.5/7e29fae7f5ea [^`\n]+\$)`?$", re.M)
def iml_lines(text): return set(iml_re.findall(text))


def main():
    no_zip = "--no-zip" in sys.argv
    plugin = json.load(io.open(os.path.join(EXP, ".codebuddy-plugin", "plugin.json"), encoding="utf-8"))
    market = json.load(io.open(os.path.join(ROOT, ".codebuddy-plugin", "marketplace.json"), encoding="utf-8"))
    ver = plugin["version"]
    mp = [p for p in market["plugins"] if p["name"] == plugin["name"]]
    if not mp: fail("marketplace has no entry for " + plugin["name"])
    elif mp[0]["version"] != ver: fail("marketplace version %s != plugin %s" % (mp[0]["version"], ver))
    elif market.get("version") != ver: fail("marketplace top version %s != plugin %s" % (market.get("version"), ver))
    else: ok("plugin + marketplace json, version %s" % ver)
    for k in ("name", "version", "description", "author", "agents", "skills", "expertType", "agentName", "displayName", "profession", "displayDescription", "avatar", "categoryId", "defaultInitPrompt", "plugin", "tags", "quickPrompts"):
        if k not in plugin: fail("plugin.json missing " + k)
    zh = plugin["displayDescription"]["zh"]
    if not (40 <= len(zh) <= 50): fail("displayDescription.zh length %d not in 40-50" % len(zh))
    if len(plugin["tags"]) != 3 or len(plugin["quickPrompts"]) != 3: fail("tags/quickPrompts must be exactly 3")
    if plugin["defaultInitPrompt"]["zh"] != plugin["quickPrompts"][0]["zh"]: fail("defaultInitPrompt must equal quickPrompts[0]")
    if not os.path.exists(os.path.join(EXP, plugin["avatar"])): fail("avatar missing")
    skill_dirs = sorted(d for d in os.listdir(SKILLS_DIR) if os.path.isdir(os.path.join(SKILLS_DIR, d)))
    declared = sorted(os.path.basename(s.rstrip("/")) for s in plugin.get("skills", []))
    if declared != skill_dirs: fail("plugin.skills %s != skills/ dirs %s" % (declared, skill_dirs))
    else: ok("plugin.skills matches skills/: %s" % skill_dirs)

    agent_path = os.path.join(EXP, "agents", "ilang-wechat-awesome.md")
    afm, abody = frontmatter(read(agent_path))
    if afm is None: fail("agent frontmatter unparsable"); abody = ""
    else:
        for k in ("name", "description", "displayName", "profession", "tools", "skills"):
            if k not in afm: fail("agent frontmatter missing " + k)
        if afm.get("name") != plugin["agentName"]: fail("agent name != plugin.agentName")
        if sorted(afm.get("skills") or []) != skill_dirs: fail("agent skills %s != %s" % (afm.get("skills"), skill_dirs))
        if ("[VERSION:%s]" % ver) not in abody: fail("agent body VERSION tag != %s" % ver)
        ok("agent frontmatter yaml ok")
    skills = {}
    for d in skill_dirs:
        sfm, sbody = frontmatter(read(os.path.join(SKILLS_DIR, d, "SKILL.md")))
        if sfm is None: fail("%s SKILL frontmatter unparsable" % d); continue
        for k in ("name", "description", "description_zh", "description_en", "version", "author", "display_name", "display_name_en", "category"):
            if k not in sfm: fail("%s SKILL frontmatter missing %s" % (d, k))
        if sfm.get("name") != d: fail("%s SKILL name %s != dir" % (d, sfm.get("name")))
        if str(sfm.get("version")) != ver: fail("%s SKILL version %s != plugin %s" % (d, sfm.get("version"), ver))
        if ("[VERSION:%s]" % ver) not in sbody: fail("%s SKILL body VERSION tag != %s" % (d, ver))
        skills[d] = (sfm, sbody)
        ok("%s frontmatter yaml ok" % d)

    if iml_available():
        expected = {}
        for name, chain in CHAINS.items():
            rc, line = compile_chain(chain)
            if rc != 0: fail("compiler rejects chain for %s: %s" % (name, line)); continue
            if chain not in decompile_line(line): fail("decompile mismatch for " + name)
            expected[name] = line
            ok("%s chain round-trips: %s" % (name, line))
        def expect_line(path, name):
            found = iml_lines(read(path))
            if found != {expected.get(name)}: fail("IML line in %s is %r, expected %r" % (os.path.relpath(path, ROOT), found, expected.get(name)))
        expect_line(agent_path, AGENT_CHAIN)
        for d in skill_dirs:
            expect_line(os.path.join(SKILLS_DIR, d, "SKILL.md"), d)
        for p in (os.path.join(EXP, "README.md"), os.path.join(ROOT, "README.md"), os.path.join(ROOT, "README.en.md")):
            if expected.get(AGENT_CHAIN) not in iml_lines(read(p)): fail("README %s lacks the agent IML line" % os.path.relpath(p, ROOT))
    elif os.environ.get("GITHUB_ACTIONS") or os.environ.get("CI"):
        fail("IML_REPO 不存在（%s），Actions 里必须能回环校验" % IML_REPO)
    else:
        print("warn IML_REPO 不存在（%s），跳过工作链回环校验" % IML_REPO)

    bad_dash = re.compile("[—–]")
    for root, _, files in os.walk(EXP):
        for f in files:
            if not f.endswith((".md", ".json")): continue
            p = os.path.join(root, f); t = read(p)
            if [c for c in t if ord(c) < 32 and c not in "\n\t"]: fail("control chars in " + os.path.relpath(p, ROOT))
            if f.endswith(".md"):
                flagged = [ln for ln in t.splitlines() if bad_dash.search(ln) and not ln.lstrip().startswith(("T:", "A:", "|", "-", "::", "#")) and "破折号" not in ln and "em-dash" not in ln and "em_dash" not in ln]
                if flagged: fail("dash in prose of %s: %r" % (os.path.relpath(p, ROOT), flagged[:2]))
    ok("control-char and dash scan done")
    store = json.dumps(plugin, ensure_ascii=False) + (abody or "")
    for bad in ("8-15%", "8到15%", "分享率8", "保证", "必爆"):
        if bad in store: fail("store copy contains forbidden claim: " + bad)
    ok("no effect promises in store copy")
    for d, (sfm, sbody) in skills.items():
        text = sbody + (abody if d == AGENT_CHAIN else "")
        refs = set(re.findall(r"@references/([\w\-]+\.md)", text))
        missing = [r for r in refs if not os.path.exists(os.path.join(SKILLS_DIR, d, "references", r))]
        if missing: fail("%s missing references: %r" % (d, missing))
        sdir = os.path.join(SKILLS_DIR, d, "scripts")
        if os.path.isdir(sdir):
            for f in os.listdir(sdir):
                if f.endswith(".py"):
                    try:
                        py_compile.compile(os.path.join(sdir, f), cfile=os.path.join(tempfile.gettempdir(), f + "c"), doraise=True)
                    except Exception as e:
                        fail("%s/scripts/%s: %s" % (d, f, e))
                if f == "sources.json":
                    try:
                        cfg = json.load(io.open(os.path.join(sdir, f), encoding="utf-8"))
                        bad = [x["name"] for x in cfg["sources"] if x.get("type") not in ("rss", "json", "js", "sdata", "html") or not x.get("url", "").startswith("http")]
                        if bad: fail("sources.json 坏条目 %r" % bad[:3])
                    except Exception as e:
                        fail("sources.json: %s" % e)
        ok("%s references + scripts ok" % d)
    tq = os.path.join(ROOT, "scripts", "test_quality.py")
    if os.path.exists(tq):
        r = subprocess.run([sys.executable, tq], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0: fail("quality tests failed:\n" + (r.stdout + r.stderr)[-2500:])
        else: ok("quality tests: " + ((r.stdout.strip().splitlines() or ["passed"])[-1]))
    if fails:
        print("\n%d FAIL(s)" % len(fails)); sys.exit(1)
    if no_zip:
        print("gate passed, no zip"); return

    os.makedirs(OUT, exist_ok=True)
    def zipdir(zpath, base, arcroot):
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(base):
                if "__pycache__" in root: continue
                for f in files:
                    p = os.path.join(root, f)
                    z.write(p, os.path.join(arcroot, os.path.relpath(p, base)).replace(os.sep, "/"))
    built = []
    for d in skill_dirs:
        z = os.path.join(OUT, "%s-workbuddy-skill-v%s-%s.zip" % (d, ver, TODAY))
        zipdir(z, os.path.join(SKILLS_DIR, d), d); built.append(z)
    z2 = os.path.join(OUT, "ilang-wechat-awesome-workbuddy-expert-v%s-%s.zip" % (ver, TODAY))
    zipdir(z2, EXP, "ilang-wechat-awesome"); built.append(z2)
    for z in built:
        print("built", os.path.relpath(z, ROOT), os.path.getsize(z), "bytes")


if __name__ == "__main__":
    main()
