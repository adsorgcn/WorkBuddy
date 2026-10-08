# WorkBuddy · iLang experts and skills

iLang experts and skills for WorkBuddy, installable straight from GitHub. The international edition (workbuddy.ai) cannot see the listings of the domestic market, so this repository is the install source for it.

[中文](README.md)

## What is here

| Name | What it does | Version |
|---|---|---|
| [iLang WeChat-Awesome](experts/ilang-wechat-awesome/) | WeChat official account article structure expert: feed it your source material, it restructures the piece with writing genes distilled from 200+ field-tested articles, runs a 12-point self-check with built-in de-AI editing, and outputs Markdown, three titles and a cover image prompt | 2.0.0 |

## Install

**Desktop app, as a skill**

1. Download this repository, or just the folder `experts/ilang-wechat-awesome/skills/wechat-article/` (the Releases page has a ready zip)
2. In WorkBuddy open Skills → Add skill → Upload skill and pick that folder
3. Review the permissions it asks for, confirm
4. Start a chat: "I have source material, turn it into a WeChat article", then paste the material

**Desktop app, as an expert**

Market → My experts → Create expert, paste the body of `experts/ilang-wechat-awesome/agents/ilang-wechat-awesome.md` (everything below the frontmatter), use `avatars/expert.png`.

**CodeBuddy or WorkBuddy CLI (plugin marketplace)**

```
/plugin marketplace add adsorgcn/WorkBuddy
/plugin install ilang-wechat-awesome@ilang-workbuddy
```

Any SKILL.md-compatible agent (Claude Code, Codex, Cursor, Hermes) can copy `skills/wechat-article/` into its skills directory.

## Protocol

The expert and the skill are written in the iLang protocol. The first body line `#iml/0.5/...` is the IML 0.5 machine-layer chain, round-trip verified with the official compiler:

```
[PARS:@USER]=>[GET:@SRC]=>[DRFT|sty=casual]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]
#iml/0.5/7e29fae7f5ea PS@US GT@SR DRst=casual CK SV@DSgr=date $
```

ilang.ai · ilang.cn · github.com/ilang-ai/ilang-spec · github.com/ilang-ai/iml-protocol

## License

MIT · © 2026 静水流深 (Long Quan Zhu)
