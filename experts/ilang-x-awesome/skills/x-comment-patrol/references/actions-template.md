# 用 GitHub Actions 定时跑（零服务器）

适合没有 Muse、Hermes 这类带定时器的宿主，又不想开机器的人。思路：自己开一个私有仓，把两个技能的脚本放进去，密钥放 Secrets，水位线和日志 commit 回仓，Actions 每两小时跑一轮。

这条路没有专家在中间判。所以模板只做两件事：拉新评论，把 pending.json commit 回仓给你看；要回的你（或你的 Agent）写好 replies.json 推上去，下一轮 send 发出去。不做无人判断的自动回复。

## 仓库结构

```
my-x-ops/                      私有仓
├── scripts/x_api.py           从 x-post 技能拷
├── scripts/x_patrol.py        从 x-comment-patrol 技能拷
├── state/                     X_OPS_DIR 指到这里，水位线和日志都在
└── .github/workflows/patrol.yml
```

## Secrets

仓库 Settings → Secrets and variables → Actions：`X_API_KEY`、`X_API_SECRET`、`X_ACCESS_TOKEN`、`X_ACCESS_SECRET`。脚本会从环境变量读，不用配置文件。

## patrol.yml

```yaml
name: x-patrol
on:
  schedule:
    - cron: "0 */2 * * *"
  workflow_dispatch:
concurrency: patrol
jobs:
  patrol:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    env:
      PYTHONUTF8: "1"
      X_OPS_DIR: ${{ github.workspace }}/state
      X_API_PY: ${{ github.workspace }}/scripts/x_api.py
      X_API_KEY: ${{ secrets.X_API_KEY }}
      X_API_SECRET: ${{ secrets.X_API_SECRET }}
      X_ACCESS_TOKEN: ${{ secrets.X_ACCESS_TOKEN }}
      X_ACCESS_SECRET: ${{ secrets.X_ACCESS_SECRET }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: 第一次跑先验密钥
        run: python scripts/x_api.py check
      - name: 发上一轮写好的回复（没有就跳过）
        run: |
          if [ -f state/replies.json ]; then
            python scripts/x_patrol.py send --replies state/replies.json && rm -f state/replies.json
          fi
      - name: 拉新评论
        run: python scripts/x_patrol.py fetch
      - name: 把水位线、日志、待判清单 commit 回仓
        run: |
          git config user.name "x-patrol"
          git config user.email "x-patrol@users.noreply.github.com"
          git add state
          git diff --cached --quiet || git commit -m "patrol: $(date -u +%Y-%m-%dT%H:%MZ) [skip ci]"
          git push
```

## 怎么用

1. 第一次手动 Run workflow，看 check 那步打印出你的 @handle。
2. 每轮 fetch 完，`state/<handle>/pending.json` 在仓库里。你或你的 Agent 看一遍，把要回的写成 `state/replies.json`（格式 `[{"to": "<评论id>", "text": "..."}]`），推上去。
3. 下一轮开头先 send 再 fetch。send 成功水位线自动推进。
4. 一条都不回也放一个 `[]` 的 replies.json，水位线才会过去。

## 没实测

这份模板按 x_patrol.py 的参数写，在 Actions 里没有真跑过。第一次跑有问题，先看 Actions 日志里 check 和 fetch 两步的输出。
