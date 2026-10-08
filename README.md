# WorkBuddy · iLang 专家与技能

给 WorkBuddy 用的 iLang 专家和技能，从 GitHub 直接装。海外版 workbuddy.ai 看不到国内市场的上架内容，这个仓库就是给海外版准备的安装源。

[English](README.en.md)

## 现在有什么

| 名称 | 是什么 | 版本 |
|---|---|---|
| [iLang 公众号写作助手](experts/ilang-wechat-awesome/) | 公众号爆文专家：投喂素材，按 200 多篇实战文章验证的写作基因重组，12 项自查，内置去 AI 味，出 MD 正文、3 个标题和封面图提示词；定稿一句话推进草稿箱 | 2.1.0 |
| [公众号推草稿箱（技能）](experts/ilang-wechat-awesome/skills/wechat-draft-push/) | 定稿 Markdown 转微信 HTML，传图传封面，官方接口推进草稿箱并回读核对。只到草稿箱，没有发布命令，个人主体账号也能用。可单独上传 | 2.1.0 |

## 怎么装（三条路，选一条）

**一、海外版桌面端装成技能（最省事）**

1. 下载本仓库（Code → Download ZIP）或者只下载 `experts/ilang-wechat-awesome/skills/` 下的技能文件夹（写稿 `wechat-article`、推草稿 `wechat-draft-push`），Releases 里也有打好的技能包
2. 打开 WorkBuddy，进 Skills 面板：Add skill → Upload skill，选这个文件夹
3. 看一眼它要的权限，确认
4. 新开对话，说"我有素材，帮我按爆文结构写成公众号文章"，把素材贴上

**二、海外版桌面端装成专家**

1. 市场右上角「我的专家」→「创建专家」
2. 把 `experts/ilang-wechat-awesome/agents/ilang-wechat-awesome.md` 里 frontmatter（两条 `---` 之间）以外的正文整段粘进去
3. 头像用 `avatars/expert.png`，名字叫「iLang 公众号写作助手」
4. 想让它同时带技能，再按第一条把技能装上并分配给这个专家

**三、CodeBuddy 或 WorkBuddy 命令行（插件市场）**

```
/plugin marketplace add adsorgcn/WorkBuddy
/plugin install ilang-wechat-awesome@ilang-workbuddy
```

任何能读 SKILL.md 的 Agent（Claude Code、Codex、Cursor、Hermes 等）都可以直接把 `skills/wechat-article/` 拷进自己的 skills 目录用。

安装非官方技能前，先看一遍源码、权限和脚本。本仓库只有一个脚本：推草稿技能的 `scripts/wechat_draft.py`，纯 Python 标准库，只调微信官方接口，没有发布和删草稿命令，凭据从本机配置文件读。

## 怎么用

```
第 1 步  贴素材（文章 / 数据 / 笔记 / 本地文件路径），说"按爆文结构写成公众号文章"
第 2 步  它确认角度和骨架 → 你选
第 3 步  它出提纲和 3 个标题 → 你确认
第 4 步  它写初稿，去 AI 味，12 项自查 → 你审改：补个人经历、填口语位、补截图
第 5 步  MD 粘到 ilang.cn/md 预览微信样式，一键复制进公众号编辑器；或者说「推草稿箱」，它转微信 HTML、传图、推进草稿箱，你在后台看一眼再发
```

素材从哪来：你自己的经历和踩过的坑；你这个品类的热门文章和行业数据；你买过的课程笔记里挑一个知识点展开。素材是别人的知识，文章是你的观点。

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

- 2.1.0（2026-10-08）：新增推草稿箱技能。定稿 Markdown 转微信 HTML（表格转信息卡、链接去网址、长破折号换逗号），正文图上传换图床、封面做永久素材，官方接口 draft/add 进草稿箱，draft/get 回读核对，报 media_id。只到草稿箱，没有发布命令。

- 2.0.0（2026-10-08）：从国内市场版 1.2.0 升级。基因 17 条到 23 条，内置去 AI 味，两种骨架，完整脱敏与敏感词表，推荐算法与发布节奏，转微信格式与接口推草稿，多平台速查，iLang v5.0 头加 IML 0.5 工作链。
- 1.2.0（2026-09-02）：国内 WorkBuddy 市场上架版。

## 许可

MIT · © 2026 静水流深
