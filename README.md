# WorkBuddy · iLang 专家与技能

给 WorkBuddy 用的「公众号爆文专家」和它的三个技能，国内版、海外版都能装。国内版 workbuddy.cn 市场里直接加；海外版 workbuddy.ai 看不到国内市场，从这里装。

[English](README.en.md)

## 现在有什么

| 名称 | 是什么 | 版本 |
|---|---|---|
| [公众号爆文专家](experts/ilang-wechat-awesome/) | 专家正文。投喂素材，按 200 多篇实战文章验证的写作基因重组，出 MD 正文、3 个标题、封面图提示词；没素材不写，不编数字不编经历。带下面三个技能 | 2.3.3 |
| [写稿 wechat-article](experts/ilang-wechat-awesome/skills/wechat-article/) | 23 条写作基因，六段式和八区块两种骨架，标题四个公式，12 项自查，去 AI 味三件套，脱敏表和敏感词红线，封面提示词模板，X、HN、Reddit 速查 | 2.3.3 |
| [推草稿箱 wechat-draft-push](experts/ilang-wechat-awesome/skills/wechat-draft-push/) | check 验凭据和白名单，render 转微信 HTML，push 传图传封面推进草稿箱并回读，verify 回读，publish 只在人看完草稿说「发」后对微信认证号可用。个人主体账号也能推草稿箱。没有删草稿命令 | 2.3.3 |
| [选题对标 wechat-topic-hunter](experts/ilang-wechat-awesome/skills/wechat-topic-hunter/) | 用你自己的 wxrank key 看榜、搜文章、找号、推文列表、单号对标算阅读中位和爆款倍率、单篇数据。每次花积分前先报价，日上限 300 积分。只拿标题角度和数据，不搬运 | 2.3.3 |
| [远程派活 remote-dispatch](experts/ilang-wechat-awesome/skills/remote-dispatch/) | 本机当总控：把头上写 [RUN:VPS] 的命令块派给远程机上的 CodeBuddy Code 网关跑，收回结果和回执，每次留记录。口令只在本机配置文件里，远程机的审批由人点 | 2.3.3 |

## 怎么装

### 国内版 workbuddy.cn

市场里搜「公众号爆文专家」，点下图红框那个。绿色小机器人头像，标签「公众号 去AI味 推草稿箱」。旁边那个「公众号爆文写作专家」不是。

![市场里的公众号爆文专家](docs/market-expert-2026-10-09.png)

市场版自带写稿和推草稿两个技能。选题技能市场里没有，要的话从 [发布页](https://github.com/adsorgcn/WorkBuddy/releases) 下 zip，解压后在 Skills 面板「上传技能」选 `skills/wechat-topic-hunter`。

### 海外版 workbuddy.ai

海外版看不到国内市场，两种装法选一种。先说一个坑：海外版的自定义模型只认 OpenAI 兼容接口，Claude 协议的接口填不进去。用自带模型，或者接一个 OpenAI 兼容的中转站。

**装法一：贴一条命令，让 WorkBuddy 自己装**

新开一个对话，整段复制贴进去。它会去发布页下包、把三个技能装进自己的技能目录、按专家正文建专家、挂上技能。它自己装不了的那一步会告诉你在界面上点哪里。

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

**装法二：手动装，三步**

1. 装技能。[发布页](https://github.com/adsorgcn/WorkBuddy/releases) 下最新的 `ilang-wechat-awesome-workbuddy-expert-*.zip`，解压。WorkBuddy 进 Skills 面板，Add skill → Upload skill，依次选 `skills/wechat-article`、`skills/wechat-draft-push`、`skills/wechat-topic-hunter`、`skills/remote-dispatch` 四个文件夹，看一眼权限，确认。
2. 建专家。专家页右上角「我的专家」→「创建专家」。打开 `agents/ilang-wechat-awesome.md`，开头两行 `---` 之间那段设置跳过，从下面第一行起整段复制到文件末尾，粘进专家提示词。名字填「公众号爆文专家」，头像用 `avatars/expert.png`，把三个技能分配给它。
3. 选模型。自带模型直接用；自定义模型只能填 OpenAI 兼容接口。

界面上的字以你看到的为准，不同版本叫法有出入。

### 命令行（CodeBuddy 或 WorkBuddy CLI）

```
/plugin marketplace add adsorgcn/WorkBuddy
/plugin install ilang-wechat-awesome@ilang-workbuddy
```

任何能读 SKILL.md 的 Agent（Claude Code、Codex、Cursor、Hermes 等）都可以直接把 `skills/` 下的文件夹拷进自己的 skills 目录用。

### 装完自检

切进「公众号爆文专家」的对话，整段贴进去。五项全有就装齐了。

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

安装非官方技能前，先看一遍源码、权限和脚本。本仓库有两个脚本，都是纯 Python 标准库、凭据从本机配置文件读：推草稿技能的 `scripts/wechat_draft.py`（只调微信官方接口，发布命令只在人说「发」之后对认证号可用，没有删草稿命令）和选题技能的 `scripts/wxrank_topics.py`（只读调用 wxrank 数据接口，用用户自己的 key，花积分前报价）。

## 怎么用

```
第 1 步  贴素材（文章 / 数据 / 笔记 / 本地文件路径），说"写成公众号爆文"
第 2 步  它确认角度和骨架 → 你选
第 3 步  它出提纲和 3 个标题 → 你确认
第 4 步  它写初稿，去 AI 味，12 项自查 → 你审改：补个人经历、填口语位、补截图
第 5 步  MD 粘到 ilang.cn/md 预览微信样式，一键复制进公众号编辑器；或者说「推草稿箱」，它转微信 HTML、传图、推进草稿箱，你在后台看一眼再发
```

素材从哪来：你自己的经历和踩过的坑；你这个品类的热门文章和行业数据；你买过的课程笔记里挑一个知识点展开。素材是别人的知识，文章是你的观点。没素材想先找题，对它说「看榜选题」，它用你的 wxrank key 出一份带数据的选题清单。

## 它不做的事

- 没素材不写
- 不编数字、引语、个人经历
- 不引导点赞转发收藏关注
- 不在文章里放网址和个人微信号
- 不碰政治、赌博、色情、翻墙类话题
- 不做矩阵号、批量操作、搬运洗稿
- 不用于规避各平台对 AI 辅助内容的披露要求

## 协议

专家正文和技能用 iLang 协议写，开头那行 `#iml/0.5/...` 是它的机器层 IML 0.5 工作链，用官方编译器回环验证过：

```
[PARS:@USER]=>[GET:@SRC]=>[DRFT|sty=casual]=>[CHEK]=>[SAVE:@DST|grp=date]=>[Ω]
#iml/0.5/7e29fae7f5ea PS@US GT@SR DRst=casual CK SV@DSgr=date $
```

| 资源 | 地址 |
|---|---|
| iLang 官网 | ilang.ai |
| iLang 中文站 | ilang.cn |
| 公众号排版工具 | ilang.cn/md |
| 协议正典 | github.com/ilang-ai/ilang-spec |
| 机器层 IML | github.com/ilang-ai/iml-protocol |

## 更新记录

- 2.3.3（2026-10-09）：新增远程派活技能 remote-dispatch。本机 WorkBuddy 当总控，把 [RUN:VPS] 的命令块发给远程机上的 CodeBuddy Code 网关（命令行版 WorkBuddy，Linux 也能跑）执行，SSE 收结果，跑完存记录；附网关调用实测笔记（三个必带请求头、UTF-8、结果要在跑的时候收）。
- 2.3.2（2026-10-09）：只改安装说明。README 分国内版和海外版两条路，国内版放市场截图；海外版给「贴命令让 WorkBuddy 自己装」和手动三步，写明自定义模型只认 OpenAI 兼容接口；加「装完自检」命令。专家和技能内容不变。
- 2.3.1（2026-10-09）：专家改名「公众号爆文专家」（去掉「结构」两个字，自我介绍和开场白同步改）；写稿技能显示名改「公众号爆文写作」；功能不变。
- 2.3.0（2026-10-09）：新增选题对标技能 wechat-topic-hunter。用用户自己的 wxrank key：看榜（1 积分，返回阅读在看分享字数和链接，按爆款分排）、搜文章、找号、推文列表、单号对标（阅读中位、爆款倍率、爆款分）、单篇数据；每次花积分前报价，对标要用户点头；日上限 300 积分。专家在用户没素材时先走它出选题清单。

- 2.2.0（2026-10-09）：推草稿箱技能加 publish 命令。只在人已在后台看过草稿并说「发」后、且账号是微信认证企业号时才调 freepublish/submit，先回读标题确认是哪篇，再轮询 freepublish/get 报状态和链接；个人号报没权限并引导去后台点。仍无删草稿命令。

- 2.1.0（2026-10-08）：新增推草稿箱技能。定稿 Markdown 转微信 HTML（表格转信息卡、链接去网址、长破折号换逗号），正文图上传换图床、封面做永久素材，官方接口 draft/add 进草稿箱，draft/get 回读核对，报 media_id。只到草稿箱，没有发布命令。

- 2.0.0（2026-10-08）：从国内市场版 1.2.0 升级。基因 17 条到 23 条，内置去 AI 味，两种骨架，完整脱敏与敏感词表，推荐算法与发布节奏，转微信格式与接口推草稿，多平台速查，iLang v5.0 头加 IML 0.5 工作链。
- 1.2.0（2026-09-02）：国内 WorkBuddy 市场上架版。

## 许可

MIT · © 2026 静水流深
