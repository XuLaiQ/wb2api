# WorkBuddy Manager —— 本机启动脚本（Windows / PowerShell）
#
#   powershell -ExecutionPolicy Bypass -File start.ps1
#
# 等价于 Linux 上的 systemd 常驻服务：前台运行，Ctrl+C 退出。
# 环境变量全部读根目录的 .env（路径、端口、初始密码都在那里改）。
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) {
    Write-Error "未找到虚拟环境 $python，请先执行：python -m venv .venv; .\.venv\Scripts\python -m pip install -r server\requirements.txt"
}

$config = Join-Path $root 'config.json'
if (-not (Test-Path $config)) {
    Copy-Item (Join-Path $root 'config.example.json') $config
    Write-Warning 'config.json was created from config.example.json. Set api_key before serving traffic.'
}

$binaryName = if ($env:OS -eq 'Windows_NT') { 'wb2api.exe' } else { 'wb2api' }
$binary = Join-Path $root $binaryName
if (-not (Test-Path $binary)) {
    $go = Get-Command go -ErrorAction SilentlyContinue
    if (-not $go) { Write-Error "Missing $binary and Go is not installed. Build with: go -C gateway build -o $binary ./cmd/server" }
    Write-Host "Building embedded Go gateway $binaryName ..."
    & $go.Source -C (Join-Path $root 'gateway') build -o $binary ./cmd/server
    if ($LASTEXITCODE -ne 0) { Write-Error 'Go gateway build failed' }
}

# 中文 Windows 的默认编码是 GBK，而 docker logs / 腾讯接口返回的都是 UTF-8：
# 不开 UTF-8 模式会让「读上游日志」的线程抛 UnicodeDecodeError（任务记录页取不到数据）。
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

# 监听地址与端口从 .env 读，改一处即可（需要局域网访问就把 WB_MANAGER_HOST 改成 0.0.0.0）
$bindHost = '127.0.0.1'
$bindPort = '7864'
$envPath = Join-Path $root '.env'
if (Test-Path $envPath) {
    foreach ($line in Get-Content $envPath) {
        if ($line -match '^\s*WB_MANAGER_HOST\s*=\s*(\S+)') { $bindHost = $Matches[1] }
        elseif ($line -match '^\s*WB_MANAGER_PORT\s*=\s*(\S+)') { $bindPort = $Matches[1] }
    }
}

if (-not (Test-Path (Join-Path $root 'web\out\index.html'))) {
    Write-Warning 'web\out is missing: build the frontend in web before opening the panel.'
}

$uvicornArgs = @('-m', 'uvicorn', 'server.main:app', '--host', $bindHost, '--port', $bindPort)
if (Test-Path $envPath) { $uvicornArgs += @('--env-file', '.env') }
Write-Host "WorkBuddy unified application starting at http://${bindHost}:${bindPort} (Ctrl+C to stop)"
& $python @uvicornArgs
