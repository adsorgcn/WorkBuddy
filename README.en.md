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

### WorkBuddy, domestic edition (primary)

Search the marketplace for 公众号爆文专家 and add the one in the red box below: green robot avatar, tags 公众号 / 去AI味 / 推草稿箱. The similarly named 公众号爆文写作专家 next to it is someone else's.

![the expert in the marketplace](docs/market-expert-2026-10-09.png)

The marketplace version ships the writing and draft-push skills. The topic hunter is GitHub only: download the `wechat-topic-hunter` zip from [Releases](https://github.com/adsorgcn/WorkBuddy/releases), upload the folder in the Skills panel, assign it to the expert.

### WorkBuddy, international edition

The international edition cannot see the domestic marketplace. One caveat first: its custom-model setting only accepts OpenAI-compatible endpoints. Use the built-in model or an OpenAI-compatible relay.

Either paste the install command from the [Chinese README](README.md#workbuddy-海外版) into a new chat and let WorkBuddy install itself, or do it by hand: download the latest `ilang-wechat-awesome-workbuddy-expert-*.zip` from Releases, upload each folder under `skills/` in the Skills panel, create an expert from `agents/ilang-wechat-awesome.md` (skip the YAML between the first two `---` lines), name it 公众号爆文专家, use `avatars/expert.png`, assign the skills.

### Other agents

Each skill is a standard `SKILL.md` plus stdlib-only Python scripts; the expert is one Markdown file. Installing into any agent is two moves: copy the skill folders into its skills directory, put the expert text into its persona file.

| Agent | Skills go to | Expert text goes to |
|---|---|---|
| CodeBuddy CLI | `~/.codebuddy/skills/`, or `/plugin marketplace add adsorgcn/WorkBuddy` then `/plugin install ilang-wechat-awesome@ilang-workbuddy` | project `CODEBUDDY.md` |
| Claude Code | `~/.claude/skills/` or project `.claude/skills/` | project `CLAUDE.md` |
| Codex | `~/.codex/skills/` | project `AGENTS.md` |
| Hermes | `~/.hermes/skills/` | a section in `SOUL.md` |
| OpenClaw | `~/.openclaw/skills/` or the workspace `skills/`; `openclaw skills list` shows the live directories | its agent config |
| Doubao | create a custom skill in the Skills page and paste the `SKILL.md` content | the agent's persona field |
| Muse | Muse Code reads standard `SKILL.md` folders | the assistant's persona field |
| Anything else | if it reads `SKILL.md`, copy the folders; if not, paste `SKILL.md` as a prompt | system prompt |

The expert text is `experts/ilang-wechat-awesome/agents/ilang-wechat-awesome.md`; skip the YAML between the first two `---` lines. Scripts need Python 3.8 or newer and no packages.

### The only thing you pay for: wxrank

Supply-side numbers come from the wxrank WeChat API on your own key. Buy credit at https://wxrank.com/api-services , register and top up at https://data.wxrank.com , 100 credits = 1 CNY, one hot-list query = 1 credit, default daily cap 300. Put the key in `.wxrank.env` in your home directory as one line `KEY=yourkey`; the script reads it, never paste it into a chat.

The API is reachable from anywhere; we tested from fourteen machines in different regions. If it fails, it is that machine's own network.

Optional second cost: an OpenAI-compatible image endpoint such as gpt-image-2 on apikey.fun if you want the AI to render covers. Without it the expert gives you the cover prompt and you render it yourself.

## Skills

| Name | What | Version |
|---|---|---|
| [Expert](experts/ilang-wechat-awesome/) | The expert prompt. Feed it your own material, it restructures the piece with writing genes distilled from 200+ field-tested articles; no material, no article; no invented numbers or anecdotes | 2.3.6 |
| [wechat-topic-hunter](experts/ilang-wechat-awesome/skills/wechat-topic-hunter/) | `feed` reads the daily list for free, `direction` compares niches, `calendar` builds a dated content list, `hot` ranks WeChat articles, plus account lookup, benchmarking and per-article data; quotes before every paid call. Ships `hot_sources.py` for pulling sources yourself when GitHub is unreachable | 2.3.6 |
| [wechat-article](experts/ilang-wechat-awesome/skills/wechat-article/) | 23 writing genes, two skeletons, four title formulas, 12-point self-check, built-in de-AI editing, compliance rules, cover prompt template | 2.3.6 |
| [wechat-draft-push](experts/ilang-wechat-awesome/skills/wechat-draft-push/) | check credentials and IP allowlist, render Markdown to WeChat HTML, push images and cover and the draft into the WeChat draft box with read-back, verify, and publish only after a human reviewed the draft and said so, and only for verified enterprise accounts. External links become a numbered reference list, comment switch and read-more URL are settable. No delete command | 2.3.6 |
| [remote-dispatch](experts/ilang-wechat-awesome/skills/remote-dispatch/) | Optional, for people with two machines: the local agent dispatches [RUN:VPS] blocks to a remote CodeBuddy gateway and collects the result; gateway setup scripts for Linux and Windows included | 2.3.6 |

## What it will not do

No material, no article. No invented numbers, quotes or anecdotes. No like-and-share bait. No URLs or personal WeChat IDs in the body. No politics, gambling, adult content or circumvention topics. No account farms, bulk posting or rewriting other people's articles. No automatic publishing: a human always publishes, or says so before the API clicks the last button. Not for evading platform disclosure rules for AI-assisted content.

## How the repository runs itself

- 06:30 Beijing time daily, Actions runs `scripts/update_hot_list.py`: pull sources, cluster, write the list, manage sources, commit.
- Every push to main runs `scripts/release.py`: bump the patch version everywhere, run the gate `scripts/build_packages.py`, build five zips, tag, create a release with notes generated from the commits and the day's list. Releases therefore appear daily; install the latest.

## Protocol

The expert and skills are written in the iLang protocol; the `#iml/0.5/...` line is the IML 0.5 machine-layer chain, round-tripped through the official compiler:

```
[PARS:@USER]=>[GET:@SRC]=>[DRFT|sty=casual]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]
#iml/0.5/7e29fae7f5ea PS@US GT@SR DRst=casual CK SV@DSgr=date $
```

ilang.ai · ilang.cn · ilang.cn/md · github.com/ilang-ai/ilang-spec · github.com/ilang-ai/iml-protocol

## License

MIT · © 2026 静水流深
