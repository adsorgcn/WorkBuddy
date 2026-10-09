# 远程机（Windows）起 CodeBuddy Code 网关：装 CodeBuddy Code，把 key 写进 CLI 设置，开一个窗口跑网关。Windows PowerShell 5.1 和 PowerShell 7 都能跑。
# 用法：
#   1 先装 Node（nodejs.org 下 LTS 安装包装好，PowerShell 里 node -v 能出版本号）
#   2 用记事本在用户主目录建 .codebuddy.env，一行：大写 CODEBUDDY_API_KEY 然后等号 然后你的 key（WorkBuddy 国内版账号的 API key，ck 开头），等号两边不留空格
#   3 PowerShell 里：powershell -ExecutionPolicy Bypass -File setup-gateway.ps1
# 可重复跑。远程机重启后再跑一次就行。网关跑在一个最小化的窗口里，远程桌面只断开别注销，注销了窗口就没了。
# 口令由网关首次启动自己生成，存在用户主目录 .codebuddy\settings.json 的 gateway.password。
# 这个文件必须保持 UTF-8 带 BOM 保存，否则 Windows PowerShell 5.1 读中文会乱。
param([int]$Port = 8080, [string]$Session = "gzh-worker")
$ErrorActionPreference = "Continue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
function Log($m) { Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $m) }
function Probe($p) {
  # 网关在就回 200 或 401（没带口令），都算在
  try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Headers @{ "X-CodeBuddy-Request" = "1" } "http://127.0.0.1:$p/api/v1/health" | Out-Null; return $true }
  catch {
    $resp = $_.Exception.Response
    if ($resp -and ([int]$resp.StatusCode) -eq 401) { return $true }
    return $false
  }
}

$envFile = Join-Path $HOME ".codebuddy.env"
if (-not (Test-Path $envFile)) { Write-Host "缺 $envFile（一行 大写 CODEBUDDY_API_KEY 然后等号 然后你的 key）"; exit 1 }
$key = $null
foreach ($line in Get-Content $envFile) {
  if ($line -match '^\s*CODEBUDDY_API_KEY\s*=\s*(.+?)\s*$') { $key = $Matches[1].Trim('"').Trim("'") }
}
if (-not $key) { Write-Host "$envFile 里没有 CODEBUDDY_API_KEY"; exit 1 }

Log "1 Node"
$nv = (cmd /c "node -v 2>nul" | Out-String).Trim()
if (-not $nv) { Write-Host "没装 Node，去 nodejs.org 装 LTS 版再跑"; exit 1 }
Log "node $nv"

Log "2 CodeBuddy Code"
cmd /c "npm i -g @tencent-ai/codebuddy-code >nul 2>&1"
$cb = Get-Command codebuddy.cmd -ErrorAction SilentlyContinue
if (-not $cb) { $cb = Get-Command codebuddy -ErrorAction SilentlyContinue }
if (-not $cb) { Write-Host "npm 装完找不到 codebuddy 命令，关掉 PowerShell 重开一个再跑"; exit 1 }
$cv = (cmd /c "codebuddy --version 2>nul" | Out-String).Trim()
Log "codebuddy $cv"

Log "3 settings.json：key 和国内版环境变量写进 CLI 设置"
$dir = Join-Path $HOME ".codebuddy"
New-Item -ItemType Directory -Force $dir | Out-Null
$sp = Join-Path $dir "settings.json"
$obj = New-Object PSObject
if (Test-Path $sp) { $obj = (Get-Content $sp -Raw -Encoding UTF8 | ConvertFrom-Json) }
if (-not $obj.PSObject.Properties["env"]) { $obj | Add-Member -NotePropertyName "env" -NotePropertyValue (New-Object PSObject) }
foreach ($kv in @(@("CODEBUDDY_INTERNET_ENVIRONMENT", "internal"), @("CODEBUDDY_API_KEY", $key))) {
  if ($obj.env.PSObject.Properties[$kv[0]]) { $obj.env.($kv[0]) = $kv[1] }
  else { $obj.env | Add-Member -NotePropertyName $kv[0] -NotePropertyValue $kv[1] }
}
[System.IO.File]::WriteAllText($sp, ($obj | ConvertTo-Json -Depth 10), (New-Object System.Text.UTF8Encoding $false))
Log "settings.json ok"

Log "4 网关（0.0.0.0:$Port 口令鉴权）"
$work = Join-Path $HOME "gzh"
New-Item -ItemType Directory -Force $work | Out-Null
if (Probe $Port) {
  Log "端口 $Port 上已经有网关在跑，不重复起"
} else {
  $env:CODEBUDDY_INTERNET_ENVIRONMENT = "internal"
  $env:CODEBUDDY_API_KEY = $key
  Start-Process -FilePath $cb.Source -ArgumentList @("--serve", "--host", "0.0.0.0", "--port", "$Port", "--session-id", $Session, "--permission-mode", "bypassPermissions") -WorkingDirectory $work -WindowStyle Minimized
  $ok = $false
  for ($i = 0; $i -lt 30; $i++) { Start-Sleep -Seconds 2; if (Probe $Port) { $ok = $true; break } }
  if (-not $ok) { Write-Host "网关 60 秒内没起来，看任务栏那个最小化的窗口里报什么"; exit 1 }
  Log "网关起来了（窗口最小化在任务栏，别关）"
}
$ip = "<这台机的公网IP>"
try { $ip = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 5 "https://api.ipify.org").Content.Trim() } catch {}
Log ("完成。本机 ~/.dispatch.json 里这台写 http://{0}:{1} ，口令抄 {2} 里 gateway.password 的值（别贴进任何对话）" -f $ip, $Port, $sp)
