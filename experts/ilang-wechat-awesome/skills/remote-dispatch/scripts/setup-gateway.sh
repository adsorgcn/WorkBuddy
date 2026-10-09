#!/usr/bin/env bash
# 远程机（Linux，Ubuntu 22.04 / 24.04）起 CodeBuddy Code 网关：装 Node 22 和 CodeBuddy Code，装公众号爆文专家和它的技能，起 systemd 服务。
# 用法：
#   1 先把 WorkBuddy 国内版账号的 API key（ck 开头）写进 /root/.codebuddy.env，一行：大写 CODEBUDDY_API_KEY 然后等号 然后你的 key，等号两边不留空格
#   2 bash setup-gateway.sh
# 可重复跑。只装东西、起服务，不动 SSH、不动防火墙、不改密码。口令由网关首次启动自己生成，存在 /root/.codebuddy/settings.json 的 gateway.password。
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
log(){ echo "[$(date +%H:%M:%S)] $*"; }
REPO="adsorgcn/WorkBuddy"
PORT="${GATEWAY_PORT:-8080}"
SESSION="${GATEWAY_SESSION:-gzh-worker}"
WORK=/root/gzh

ENVF=/root/.codebuddy.env
[ -f "$ENVF" ] || { echo "缺 $ENVF（一行 大写 CODEBUDDY_API_KEY 然后等号 然后你的 key）"; exit 1; }
set -a; . "$ENVF"; set +a
[ -n "${CODEBUDDY_API_KEY:-}" ] || { echo "$ENVF 里没有 CODEBUDDY_API_KEY"; exit 1; }
export CODEBUDDY_INTERNET_ENVIRONMENT=internal

log "1 基础包"
apt-get update -qq
apt-get install -y -qq curl git unzip ca-certificates python3 python3-venv >/dev/null

log "2 Node 22 + CodeBuddy Code"
if ! command -v node >/dev/null 2>&1 || [ "$(node -v | sed 's/v//' | cut -d. -f1)" -lt 20 ]; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null
  apt-get install -y -qq nodejs >/dev/null
fi
npm i -g @tencent-ai/codebuddy-code >/dev/null 2>&1 || npm i -g @tencent-ai/codebuddy-code
log "codebuddy $(codebuddy --version)"

log "3 专家包（GitHub 最新发布版）"
mkdir -p "$WORK/pkg" /root/.codebuddy/skills
cd "$WORK/pkg"
URL=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | grep -o '"browser_download_url": *"[^"]*ilang-wechat-awesome-workbuddy-expert[^"]*"' | head -1 | sed 's/.*"\(http[^"]*\)"/\1/')
[ -n "$URL" ] || { echo "拿不到发布页的专家包地址，去 https://github.com/$REPO/releases 手动下载 ilang-wechat-awesome-workbuddy-expert 开头的 zip 放到 $WORK/pkg 再跑"; exit 1; }
ZIP=$(basename "$URL")
[ -f "$ZIP" ] || curl -fsSL -o "$ZIP" "$URL"
rm -rf ilang-wechat-awesome && unzip -q -o "$ZIP"
for s in wechat-article wechat-draft-push wechat-topic-hunter remote-dispatch; do
  [ -d "ilang-wechat-awesome/skills/$s" ] || continue
  rm -rf "/root/.codebuddy/skills/$s"; cp -r "ilang-wechat-awesome/skills/$s" "/root/.codebuddy/skills/$s"
done
python3 - <<'EOF'
import io, re
t = io.open("/root/gzh/pkg/ilang-wechat-awesome/agents/ilang-wechat-awesome.md", encoding="utf-8").read()
m = re.match(r"^---\n.*?\n---\n", t, re.S)
body = t[m.end():] if m else t
io.open("/root/gzh/CODEBUDDY.md", "w", encoding="utf-8").write(body)
print("专家人设写进 /root/gzh/CODEBUDDY.md，字数", len(body))
EOF
log "专家包 $ZIP 装好"

log "4 settings.json：key 和国内版环境变量写进 CLI 设置"
python3 - <<'EOF'
import json, io, os
p = "/root/.codebuddy/settings.json"
d = json.load(io.open(p, encoding="utf-8")) if os.path.exists(p) else {}
env = d.setdefault("env", {})
env["CODEBUDDY_INTERNET_ENVIRONMENT"] = "internal"
env["CODEBUDDY_API_KEY"] = os.environ["CODEBUDDY_API_KEY"]
io.open(p, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
print("settings.json ok")
EOF

log "5 网关 systemd 服务（0.0.0.0:$PORT 口令鉴权 工作目录 $WORK）"
cat >/etc/systemd/system/codebuddy-gateway.service <<UNIT
[Unit]
Description=CodeBuddy Code HTTP gateway (remote worker)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=$WORK
EnvironmentFile=$ENVF
Environment=HOME=/root
Environment=CODEBUDDY_INTERNET_ENVIRONMENT=internal
ExecStart=/usr/bin/env codebuddy --serve --host 0.0.0.0 --port $PORT --session-id $SESSION --permission-mode bypassPermissions
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now codebuddy-gateway
sleep 8
systemctl is-active codebuddy-gateway
curl -s -m 5 -H "X-CodeBuddy-Request: 1" -H "Host: localhost:$PORT" "http://127.0.0.1:$PORT/api/v1/health"; echo
IP=$(curl -s -m 5 https://api.ipify.org || echo "<这台机的公网IP>")
log "完成。本机 ~/.dispatch.json 里这台写 http://$IP:$PORT ，口令抄 /root/.codebuddy/settings.json 里 gateway.password 的值（别贴进任何对话）"
