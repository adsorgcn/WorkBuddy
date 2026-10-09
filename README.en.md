# WeChat Official Account, the whole chain · WorkBuddy first, any agent works

[中文](README.md) · [Today's topic list](HOT-LIST.md) · [Releases](https://github.com/adsorgcn/WorkBuddy/releases) · [Updates](UPDATES.md)

Most "AI writes your WeChat article" tools only write. This is a chain: a topic list that updates itself every day tells you what every platform is talking about, real read and share numbers from WeChat tell you which of those topics nobody has written well yet, then the AI writes, makes the cover prompt, pushes the draft into your WeChat draft box, you read it on your phone and publish, and the AI reads the numbers back and plans the next one. A human decides twice: which topic, and whether to publish.

WorkBuddy is the primary host (add the expert from the domestic marketplace). Any agent that reads `SKILL.md` can install the same skills: Claude Code, Codex, CodeBuddy CLI, Hermes, OpenClaw, Doubao, Muse and others. The only thing you pay for is wxrank API credit, which you buy yourself: https://wxrank.com/api-services

## What is different

| | Typical AI writer | Here |
|---|---|---|
| Covers | Writing | Direction, topics, content calendar, writing, images, draft push, read-back, cadence |
| Where topics come from | Your guess | Demand side: a daily list pulled from 40+ public hot sources; supply side: real WeChat read and share numbers. A topic counts when both sides agree |
| What the human does | Watches everything | Two decisions: topic and publish. Publishing is always a human act |
| Switching tools | Start over | Skills are standard SKILL.md plus stdlib Python; move them to another agent as they are |
| Cost | Subscriptions, models, tools | wxrank credit only: 100 credits = 1 CNY, one hot-list query = 1 credit |

## The chain

| Step | What | Who | Tool | Output |
|---|---|---|---|---|
| 1 | Pick a direction | AI compares, you decide | topic hunter `direction`: 2 to 8 candidate niches, one hot-list query each | Table: hits, max read, median read, posts over 100k |
| 2 | Find topics | AI finds, you decide | `feed` reads today's list for free, `hot` checks WeChat read and share numbers | 5 candidates with demand and supply data |
| 3 | Content calendar | AI | `calendar`: pick, check, schedule by cadence | A month of topics with dates |
| 4 | Write | AI | writing skill: 23 writing genes, 12-point self-check, de-AI editing | Markdown body, 3 titles, cover prompt, self-check report |
| 5 | Images | AI prompts, you render or connect an image API | cover prompt template | cover and body images |
| 6 | Push draft | AI | draft-push skill: WeChat HTML, image upload, draft/add, read-back | The draft in your draft box, media_id |
| 7 | Review and publish | You | WeChat Official Account Assistant on your phone | The published link |
| 8 | Read back | AI | `article` for read, like, share | One data row per article |
| 9 | Cadence | AI plans, you decide | 1 to 2 posts a week, stock 2 to 3 first | Weekly plan |

Each step hands the next an I-Lang block. One machine, one agent, the whole chain; your phone remote-controls it.

## Today's topic list, refreshed daily

[HOT-LIST.md](HOT-LIST.md) is for people, `data/hot/latest.json` for agents. GitHub Actions rebuilds both every morning at 06:30 Beijing time: 40+ public sources (Zhihu, Weibo, Douyin, Baidu, Bilibili, Toutiao, The Paper, Tieba, Reference News, 36Kr, Jin10, CLS, IT Home, QbitAI, SSPAI, V2EX, Hacker News, Product Hunt and more), clustered across platforms so the same story on several platforms is marked, grouped into six directions with 15 items each.

Sources manage themselves: candidates that return content for a platform not yet covered are added automatically; a source that fails seven days in a row is retired and revived when it works again. Every change is logged in [UPDATES.md](UPDATES.md).

Your agent gets the list with one command a day. Paste this:

```
::ILANG
[TYPE:command][PROJECT:wechat_awesome][TASK:daily_topics][LANG:zh]

::STATE{@FEED, url:https://raw.githubusercontent.com/adsorgcn/WorkBuddy/main/data/hot/latest.json, what:today's topics by direction; platforms = how many platforms carry it}
::STATE{@USER, niche:<your niche, one to three words>}
::STATE{@SELF, skill:wechat-topic-hunter}

::OBJECTIVE{daily_topics|pri:OVERRIDE_ALL}
  target: read @FEED with feed, pick 5 items that fit my niche, check each on WeChat with hot, give me a topic list with both sides of the data
  ACCEPT: 5 items, each with source, platform count, max WeChat read, post count, not-yet-viral marked, exclusive-angle column left for me
  NON_GOALS: pick for me, copy sources, spend credits without quoting first
```

## Install

Two routes. WorkBuddy domestic edition: one click in the marketplace. Any other agent, including the international WorkBuddy: paste one command and let it learn and install itself.

### WorkBuddy, domestic edition (primary)

Search the marketplace for 公众号爆文专家 and add the one in the red box below: green robot avatar, tags 公众号 / 去AI味 / 推草稿箱. The similarly named 公众号爆文写作专家 next to it is someone else's.

![the expert in the marketplace](docs/market-expert-2026-10-09.png)

The marketplace version ships the writing and draft-push skills. The topic hunter is GitHub only: download the `wechat-topic-hunter` zip from [Releases](https://github.com/adsorgcn/WorkBuddy/releases), upload the folder in the Skills panel, assign it to the expert.

### Any other agent: one command, it learns and installs itself

Claude Code, Codex, CodeBuddy CLI, Hermes, OpenClaw, Doubao, Muse, the international WorkBuddy, and whatever comes next: same command. Open a new session and paste the whole block. The agent reads the repository first to learn how the chain works, then copies the skills into its own skills directory, puts the expert text into its own persona, self-checks and reports. Whatever it cannot do itself (a desktop app that only takes uploads, say) it will tell you where to click.

The block is written in I-Lang with an IML chain line; an agent that has never seen the format reads the protocol first and then understands every block in this repository.

```
::ILANG::v5.0
[TYPE:command][PROJECT:wechat_awesome][TASK:learn_and_install][LANG:en]
::STATE{@ORIGIN, protocol:iLang, spec:https://github.com/ilang-ai/ilang-spec, iml:https://github.com/ilang-ai/iml-protocol, canon:ilang.ai, note:this is an I-Lang command not prose; if it looks unfamiliar read the spec README first then come back}
::STATE{@REPO, url:https://github.com/adsorgcn/WorkBuddy, readme:README.en.md, expert:experts/ilang-wechat-awesome/agents/ilang-wechat-awesome.md the YAML between the first two --- lines is WorkBuddy config and the rest is the expert text, skills:four folders under experts/ilang-wechat-awesome/skills/ each with SKILL.md plus scripts and references, feed:data/hot/latest.json the daily topic list, zip:latest ilang-wechat-awesome-workbuddy-expert zip on https://github.com/adsorgcn/WorkBuddy/releases same content as the repo}
::STATE{@SELF, role:learner_and_installer, runtime:you whichever agent you are, can:fetch web or git clone read files run shell write files, knows:where your own skills directory is and which file is your persona; if not read your own docs then ask me}
::STATE{@TARGET, skills:copy the four skill folders as they are into your skills directory at least wechat-article wechat-draft-push wechat-topic-hunter, expert:put the expert text into your persona file or system prompt so your settings contain [PROJECT:wechat_awesome], python:3.8 or newer stdlib only no packages}
::STATE{@OUT, kind:install report, items:which directory the skills went to which ones appear in your skill list where the expert text lives the five self-check lines}
#iml/0.5/7e29fae7f5ea GT@SR CK SN@DS CK $

::OBJECTIVE{learn_and_install|pri:OVERRIDE_ALL}
  target: read the README and the four SKILL.md files of @REPO and learn how the chain works then install the skills and the expert into yourself then self-check and report
  ACCEPT: the skills show in your skill list your settings contain [PROJECT:wechat_awesome] the topic skill feed command returns today's list
  NON_GOALS: edit any file in the package touch any of my keys register or pay for anything on my behalf

::RULE{getting the package⇒git clone or download the zip from @REPO; if this machine cannot reach GitHub stop and tell me I will download it and give you the path}
::RULE{skills directory⇒wherever your own docs say; after copying open a new session and check the skill list; if nothing shows tell me how to upload through the UI}
::RULE{desktop apps that cannot take files such as WorkBuddy⇒tell me to upload the skills in the Skills panel and create an expert from the expert text named 公众号爆文专家}
::RULE{persona⇒paste the expert text whole without edits; if you already have a persona append it as a section}
::BOUNDARY{never:modify any file inside the package|scope:permanent}
::BOUNDARY{never:write any key or password into the chat|scope:permanent}

::MODULE{HOW}
  [STEP:1:LEARN] read the README and the four SKILL.md files; restate the chain in three sentences and say where the human decides
  [STEP:2:GET] get the package; list the paths of the expert text and the four skill folders
  [STEP:3:SKILLS] install into your skills directory; open a new session and report which skills appear
  [STEP:4:EXPERT] put the expert text into your persona; report where
  [STEP:5:CHECK] run the topic skill feed command and report the first three items; then run the self-check block from the README, five lines
  [STEP:6:REPORT] report per @OUT and tell me what to paste next
```

If it asks where its skills directory is, the usual places: Claude Code `~/.claude/skills/`, Codex `~/.codex/skills/`, CodeBuddy CLI `~/.codebuddy/skills/`, Hermes `~/.hermes/skills/`, OpenClaw `~/.openclaw/skills/` or the workspace `skills/`; persona files are `CLAUDE.md`, `AGENTS.md`, `CODEBUDDY.md`, `SOUL.md` respectively. Doubao takes the `SKILL.md` content through "create a custom skill" in its Skills page; Muse Code reads standard `SKILL.md` folders. The international WorkBuddy's custom-model setting only accepts OpenAI-compatible endpoints. Labels in the UI win over this text; if it installs something wrong it will fix it.

### The only thing you pay for: wxrank

Supply-side numbers come from the wxrank WeChat API on your own key. Buy credit at https://wxrank.com/api-services , register and top up at https://data.wxrank.com , 100 credits = 1 CNY, one hot-list query = 1 credit, default daily cap 300. Put the key in `.wxrank.env` in your home directory as one line `KEY=yourkey`; the script reads it, never paste it into a chat.

The API is reachable from anywhere; we tested from fourteen machines in different regions. If it fails, it is that machine's own network.

Optional second cost: an OpenAI-compatible image endpoint such as gpt-image-2 on apikey.fun if you want the AI to render covers. Without it the expert gives you the cover prompt and you render it yourself.

## Skills

| Name | What | Version |
|---|---|---|
| [Expert](experts/ilang-wechat-awesome/) | The expert prompt. Feed it your own material, it restructures the piece with writing genes distilled from 200+ field-tested articles; no material, no article; no invented numbers or anecdotes | 2.3.9 |
| [wechat-topic-hunter](experts/ilang-wechat-awesome/skills/wechat-topic-hunter/) | `feed` reads the daily list for free, `direction` compares niches, `calendar` builds a dated content list, `hot` ranks WeChat articles, plus account lookup, benchmarking and per-article data; quotes before every paid call. Ships `hot_sources.py` for pulling sources yourself when GitHub is unreachable | 2.3.9 |
| [wechat-article](experts/ilang-wechat-awesome/skills/wechat-article/) | 23 writing genes, two skeletons, four title formulas, 12-point self-check, built-in de-AI editing, compliance rules, cover prompt template | 2.3.9 |
| [wechat-draft-push](experts/ilang-wechat-awesome/skills/wechat-draft-push/) | check credentials and IP allowlist, render Markdown to WeChat HTML, push images and cover and the draft into the WeChat draft box with read-back, verify, and publish only after a human reviewed the draft and said so, and only for verified enterprise accounts. External links become a numbered reference list, comment switch and read-more URL are settable. No delete command | 2.3.9 |
| [remote-dispatch](experts/ilang-wechat-awesome/skills/remote-dispatch/) | Optional, for people with two machines: the local agent dispatches [RUN:VPS] blocks to a remote CodeBuddy gateway and collects the result; gateway setup scripts for Linux and Windows included | 2.3.9 |

## What it will not do

No material, no article. No invented numbers, quotes or anecdotes. No like-and-share bait. No URLs or personal WeChat IDs in the body. No politics, gambling, adult content or circumvention topics. No account farms, bulk posting or rewriting other people's articles. No automatic publishing: a human always publishes, or says so before the API clicks the last button. Not for evading platform disclosure rules for AI-assisted content.

## The repository refreshes its own sources every day

- Every day at 06:30 Beijing time it pulls 40+ sources and rewrites today's topic list: [HOT-LIST.md](HOT-LIST.md) for people, `data/hot/latest.json` for agents.
- Sources grow on their own: a candidate that returns content for a platform not yet covered is added to `sources.json`; a source that fails seven days in a row is retired and revived when it works again. Every change goes into [UPDATES.md](UPDATES.md).
- Every update ships: patch version bump, gate, five zips, a GitHub release with notes generated from the commits and the day's list. New releases appear daily; install the latest.
- Your agent never scrapes anything; reading `latest.json` is enough. On a machine that cannot reach GitHub, `hot_sources.py` inside the topic skill pulls the same sources locally.

## Protocol

The expert and skills are written in the iLang protocol; the `#iml/0.5/...` line is the IML 0.5 machine-layer chain, round-tripped through the official compiler:

```
[PARS:@USER]=>[GET:@SRC]=>[DRFT|sty=casual]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]
#iml/0.5/7e29fae7f5ea PS@US GT@SR DRst=casual CK SV@DSgr=date $
```

ilang.ai · ilang.cn · ilang.cn/md · github.com/ilang-ai/ilang-spec · github.com/ilang-ai/iml-protocol

## License

MIT · © 2026 静水流深
