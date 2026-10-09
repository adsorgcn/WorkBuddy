#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动发版：主分支一有东西更新就升一个小版本号、打包、打 tag、建 GitHub Release，发版说明自动写改了什么。

用法：python scripts/release.py [--dry-run] [--bump patch|minor|major]
步骤：读 plugin.json 的版本 → 升号 → 把版本号同步到所有带版本的文件 → 跑门禁打包 → 生成说明（上个 tag 以来的提交和改动文件）→ commit [skip ci] → tag → push → gh release create。
需要：git、gh（Actions 里用 GITHUB_TOKEN）。--dry-run 只改文件打包不提交。
"""
import argparse, datetime, io, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "experts", "ilang-wechat-awesome")
PLUGIN = os.path.join(EXP, ".codebuddy-plugin", "plugin.json")
MARKET = os.path.join(ROOT, ".codebuddy-plugin", "marketplace.json")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def sh(*cmd, check=True, capture=True):
    r = subprocess.run(cmd, cwd=ROOT, text=True, encoding="utf-8", capture_output=capture)
    if check and r.returncode != 0:
        raise SystemExit("命令失败 %s\n%s" % (" ".join(cmd), (r.stderr or r.stdout)))
    return (r.stdout or "").strip()


def read(p): return io.open(p, encoding="utf-8").read()
def write(p, t): io.open(p, "w", encoding="utf-8", newline="\n").write(t)


def bump(ver, how):
    a, b, c = (int(x) for x in ver.split("."))
    return {"patch": "%d.%d.%d" % (a, b, c + 1), "minor": "%d.%d.0" % (a, b + 1), "major": "%d.0.0" % (a + 1)}[how]


def sync_versions(old, new):
    changed = []
    def sub(path, pairs):
        t = read(path); t2 = t
        for o, n in pairs:
            t2 = t2.replace(o, n)
        if t2 != t:
            write(path, t2); changed.append(os.path.relpath(path, ROOT))
    sub(PLUGIN, [('"version": "%s"' % old, '"version": "%s"' % new)])
    sub(MARKET, [('"version": "%s"' % old, '"version": "%s"' % new)])
    sub(os.path.join(EXP, "agents", "ilang-wechat-awesome.md"), [("[VERSION:%s]" % old, "[VERSION:%s]" % new)])
    sub(os.path.join(EXP, "README.md"), [("v%s" % old, "v%s" % new)])
    skills = os.path.join(EXP, "skills")
    for d in sorted(os.listdir(skills)):
        p = os.path.join(skills, d, "SKILL.md")
        if os.path.exists(p):
            sub(p, [("version: %s" % old, "version: %s" % new), ("[VERSION:%s]" % old, "[VERSION:%s]" % new)])
    for name in ("README.md", "README.en.md"):
        sub(os.path.join(ROOT, name), [("| %s |" % old, "| %s |" % new), ("v%s" % old, "v%s" % new)])
    return changed


def release_notes(last_tag, new, today):
    rng = ("%s..HEAD" % last_tag) if last_tag else "HEAD"
    commits = sh("git", "log", "--no-merges", "--format=- %s", rng, check=False)
    commits = "\n".join(l for l in commits.splitlines() if l.strip() and not l.startswith("- release:"))
    files = sh("git", "diff", "--stat", "--stat-width=120", rng, check=False) if last_tag else ""
    hot = ""
    up = os.path.join(ROOT, "UPDATES.md")
    if os.path.exists(up):
        for l in read(up).splitlines():
            if l.startswith("- %s：" % today):
                hot = l[2:]; break
    parts = ["## v%s（%s）" % (new, today), ""]
    if hot:
        parts += ["今日清单：" + hot, ""]
    parts += ["### 这次改了什么", "", commits or "- 例行发版，内容无变化", ""]
    if files:
        parts += ["### 改动的文件", "", "```", files, "```", ""]
    parts += ["### 装法", "", "WorkBuddy 国内版：市场搜「公众号爆文专家」；海外版和其他 Agent：下面的 zip 或直接拷 `skills/` 目录，见仓库 README。唯一要花钱的是 wxrank 的 API 额度：https://wxrank.com/api-services"]
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bump", choices=["patch", "minor", "major"], default="patch")
    a = ap.parse_args()
    today = datetime.date.today().isoformat()
    plugin = json.load(io.open(PLUGIN, encoding="utf-8"))
    old = plugin["version"]; new = bump(old, a.bump)
    last_tag = sh("git", "describe", "--tags", "--abbrev=0", check=False) or ""
    print("版本 %s → %s（上个 tag %s）" % (old, new, last_tag or "无"))
    changed = sync_versions(old, new)
    print("同步版本号：", ", ".join(changed))
    env = dict(os.environ); env["BUILD_OUT"] = os.path.join(ROOT, "dist")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_packages.py")], cwd=ROOT, env=env, text=True, encoding="utf-8")
    if r.returncode != 0:
        raise SystemExit("门禁没过，不发版")
    notes = release_notes(last_tag, new, today)
    notes_path = os.path.join(ROOT, "dist", "RELEASE-NOTES-v%s.md" % new)
    write(notes_path, notes)
    print(notes)
    if a.dry_run:
        for f in changed:
            subprocess.run(["git", "checkout", "--", f], cwd=ROOT)
        print("dry-run：不提交不发版，版本号已还原"); return
    sh("git", "add", "-A", "--", ".", ":!dist")
    if sh("git", "status", "--porcelain", "--", ".", ":!dist"):
        sh("git", "commit", "-q", "-m", "release: v%s [skip ci]" % new)
    sh("git", "tag", "-a", "v%s" % new, "-m", "v%s" % new)
    sh("git", "push", "-q", "origin", "HEAD", "--follow-tags")
    zips = sorted(os.path.join(ROOT, "dist", f) for f in os.listdir(os.path.join(ROOT, "dist")) if f.endswith(".zip") and ("-v%s-" % new) in f)
    sh("gh", "release", "create", "v%s" % new, *zips, "--title", "v%s · %s" % (new, today), "--notes-file", notes_path)
    print("released v%s" % new)


if __name__ == "__main__":
    main()
