# WorkBuddy · iLang experts and skills

The WeChat viral-article expert (公众号爆文专家) and its three skills for WorkBuddy. Works on both editions: the domestic edition (workbuddy.cn) has it in the market; the international edition (workbuddy.ai) cannot see that market, so this repository is its install source.

[中文](README.md)

## What is here

| Name | What it does | Version |
|---|---|---|
| [公众号爆文专家 (expert)](experts/ilang-wechat-awesome/) | The expert prompt. Feed it your own source material, it restructures the piece with writing genes distilled from 200+ field-tested articles and outputs Markdown, three titles and a cover image prompt. No material, no article; no invented numbers or anecdotes. Ships with the three skills below | 2.3.3 |
| [wechat-article (skill)](experts/ilang-wechat-awesome/skills/wechat-article/) | 23 writing genes, two skeletons, four title formulas, 12-point self-check, built-in de-AI editing, WeChat compliance tables, cover prompt template, quick notes for X, HN and Reddit | 2.3.3 |
| [wechat-draft-push (skill)](experts/ilang-wechat-awesome/skills/wechat-draft-push/) | check credentials and IP allowlist, render Markdown to WeChat HTML, push images and cover and the draft into the WeChat draft box with read-back, verify, and publish only after a human reviewed the draft and said so, and only for verified enterprise accounts. Personal accounts can use the draft box. No delete command | 2.3.3 |
| [wechat-topic-hunter (skill)](experts/ilang-wechat-awesome/skills/wechat-topic-hunter/) | On the user's own wxrank key: hot lists, article search, account lookup, post lists, per-account benchmark (median reads, viral multiple), single-article data. Quotes the cost before every paid call, 300 credits a day by default. Takes titles, angles and numbers only, never copies content | 2.3.3 |
| [remote-dispatch (skill)](experts/ilang-wechat-awesome/skills/remote-dispatch/) | The local WorkBuddy stays in control: blocks tagged [RUN:VPS] are sent to a remote CodeBuddy Code gateway (the headless, Linux-capable WorkBuddy), results and receipts come back over SSE and are logged. The password lives only in a local config file; approvals on the remote are clicked by a human | 2.3.3 |

## Install

### Domestic edition (workbuddy.cn)

Search the market for 公众号爆文专家 and pick the one in the red box below: green robot avatar, tags 公众号 / 去AI味 / 推草稿箱. The neighbouring 公众号爆文写作专家 is someone else's.

![公众号爆文专家 in the market](docs/market-expert-2026-10-09.png)

The market version bundles the writing and draft-push skills. The topic-hunter skill is not in the market: download the zip from the [Releases](https://github.com/adsorgcn/WorkBuddy/releases) page, unzip, and upload `skills/wechat-topic-hunter` from the Skills panel.

### International edition (workbuddy.ai)

One thing first: custom models on the international edition accept OpenAI-compatible endpoints only. A Claude-protocol endpoint will not work. Use the built-in model or an OpenAI-compatible relay.

**Option A: paste one command and let WorkBuddy install itself**

Open a new chat and paste the whole block. It downloads the release package, installs the three skills into its own skills directory, creates the expert from the prompt file and attaches the skills. Whatever it cannot do by itself, it tells you where to click. The block is written in Chinese, which is what the expert speaks.

```
::ILANG
[TYPE:command][PROJECT:wechat_awesome][TASK:install][LANG:zh]

::STATE{@USER, role:owner, has:WorkBuddy 桌面端}
::STATE{@SELF, role:installer, runtime:WorkBuddy 桌面端 任意对话, can:Bash Read Write WebFetch}
::STATE{@PACKAGE, url:https://github.com/adsorgcn/WorkBuddy/releases 最新版里文件名以 ilang-wechat-awesome-workbuddy-expert 开头的 zip, has:解压后一个 ilang-wechat-awesome 文件夹 里面 agents 一份专家正文 skills 三个技能文件夹 avatars 一张头像}
::STATE{@TARGET, skills:你自己的技能目录 三个文件夹各放一份, expert:用 agents 里那份 md 去掉开头两行 --- 之间的设置 建一个专家 名字 公众号爆文专家 头像 avatars 里那张 挂上三个技能}
::STATE{@OUT, kind:装完报告, items:三个技能在不在技能列表 专家建没建 怎么切进专家对话}

::OBJECTIVE{install|pri:OVERRIDE_ALL}
  target: 把包下下来 装进你自己 装不了的那一步告诉我在界面上点哪里 装完报告
  ACCEPT: 三个技能在技能列表里 专家建好且设定里有 [PROJECT:wechat_awesome]
  NON_GOALS: 改专家正文 改技能内容 碰我的任何密钥

::RULE{下载⇒用 WebFetch 或 curl 从 @PACKAGE 的地址下 本机打不开 GitHub 就停下告诉我 我自己下好把路径给你}
::RULE{技能目录装不进⇒告诉我去 Skills 面板 Add skill 然后 Upload skill 选解压后 skills 下那三个文件夹 一个一个传}
::RULE{专家建不了⇒告诉我去专家页 创建专家 把 agents 正文整段粘进去 名字 公众号爆文专家 挂上三个技能}
::BOUNDARY{never:改动包里任何文件的内容|scope:permanent}

::MODULE{HOW}
  [STEP:1] 下包 解压 列出 agents 文件和三个技能文件夹的路径
  [STEP:2] 装技能 装完看技能列表 报哪几个在
  [STEP:3] 建专家 建完告诉我怎么切进它的对话
  [STEP:4] 报告 然后让我在专家对话里贴下面「装完自检」那条
```

**Option B: install by hand, three steps**

1. Skills. Download the latest `ilang-wechat-awesome-workbuddy-expert-*.zip` from [Releases](https://github.com/adsorgcn/WorkBuddy/releases) and unzip it. In WorkBuddy open the Skills panel, Add skill → Upload skill, and pick `skills/wechat-article`, `skills/wechat-draft-push` and `skills/wechat-topic-hunter` one after another. Review the permissions, confirm.
2. Expert. Experts page → My experts → Create expert. Open `agents/ilang-wechat-awesome.md`, skip the frontmatter between the two `---` lines at the top, copy everything below it to the end of the file and paste it as the expert prompt. Name it 公众号爆文专家, use `avatars/expert.png`, attach the three skills.
3. Model. Use the built-in model, or a custom model with an OpenAI-compatible endpoint.

Labels differ slightly between versions; go by what your app shows.

### CodeBuddy or WorkBuddy CLI (plugin marketplace)

```
/plugin marketplace add adsorgcn/WorkBuddy
/plugin install ilang-wechat-awesome@ilang-workbuddy
```

Any SKILL.md-compatible agent (Claude Code, Codex, Cursor, Hermes) can copy the folders under `skills/` into its own skills directory.

### Self-check after install

Switch into the 公众号爆文专家 chat and paste the whole block. Five items present means the install is complete.

```
::ILANG
[TYPE:command][PROJECT:wechat_awesome][TASK:env_check][LANG:zh]

::STATE{@USER, role:owner}
::STATE{@SELF, role:checker, runtime:WorkBuddy 桌面端 专家对话, can:Read Bash Glob}
::STATE{@OUT, kind:自检报告, items:五项 专家 模型 技能文件 技能绑定 wxrank}

::OBJECTIVE{env_check|pri:OVERRIDE_ALL}
  target: 核五项 缺的告诉我怎么补 能跑的自己跑
  ACCEPT: 五项各一行 有 或 缺 最后一行 全部就绪 或 还缺几项
  NON_GOALS: 替我填任何密钥 猜没核过的状态

::RULE{检查靠跑命令或读文件⇒不靠猜 跑不了的写 没核到}
::RULE{密钥⇒只看文件在不在 不读内容 不复述}

::MODULE{HOW}
  [STEP:1] 看你自己的设定里有没有 [PROJECT:wechat_awesome] 有就报 VERSION 后面的版本号 没有写 缺
  [STEP:2] 一句话证明模型在回话 说清用的是自带模型还是自定义模型
  [STEP:3] Glob 找 **/wechat-article/SKILL.md **/wechat-draft-push/scripts/wechat_draft.py **/wechat-topic-hunter/SKILL.md 在下载目录或桌面的不算 那只是包
  [STEP:4] 看本对话能用的技能列表里有没有这三个
  [STEP:5] 用户主目录有没有 .wxrank.env 有就用 Python 标准库 GET http://data.wxrank.com/weixin/score 带 key 参数 报余额 没有写 缺 这项可选 不用选题技能可以不配
  [STEP:6] 五项各一行 项目 有或缺 怎么补
```

Read the source, permissions and scripts before installing any unofficial skill. The two scripts here are plain Python standard library and read credentials from local config files only: `scripts/wechat_draft.py` (official WeChat API only, publish only after a human said so and only on verified accounts, no delete) and `scripts/wxrank_topics.py` (read-only wxrank calls on the user's own key, quotes before spending).

## Protocol

The expert and the skills are written in the iLang protocol. The first body line `#iml/0.5/...` is the IML 0.5 machine-layer chain, round-trip verified with the official compiler:

```
[PARS:@USER]=>[GET:@SRC]=>[DRFT|sty=casual]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]
#iml/0.5/7e29fae7f5ea PS@US GT@SR DRst=casual CK SV@DSgr=date $
```

ilang.ai · ilang.cn · github.com/ilang-ai/ilang-spec · github.com/ilang-ai/iml-protocol

## License

MIT · © 2026 静水流深 (Long Quan Zhu)
