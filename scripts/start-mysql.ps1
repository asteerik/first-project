$ErrorActionPreference = "Stop"

$baseDirectory = "C:\Program Files\MySQL\MySQL Server 8.4"
$dataDirectory = Join-Path $env:LOCALAPPDATA "KovchegTruda\MySQL\data"
$serverExecutable = Join-Path $baseDirectory "bin\mysqld.exe"
$port = 3307

if (-not (Test-Path -LiteralPath $serverExecutable -PathType Leaf)) {
    throw "MySQL Server 8.4 was not found at: $serverExecutable"
}
if (-not (Test-Path -LiteralPath $dataDirectory -PathType Container)) {
    throw "MySQL data directory was not found at: $dataDirectory"
}

$listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw "Port $port is already in use. Check whether the local MySQL server is already running."
}

Write-Output "Starting MySQL on 127.0.0.1:$port. Press Ctrl+C to stop it."
& $serverExecutable `
    --console `
    "--basedir=$baseDirectory" `
    "--datadir=$dataDirectory" `
    "--port=$port" `
    --bind-address=127.0.0.1 `
    --mysqlx=0

if ($LASTEXITCODE -ne 0) {
    throw "MySQL server exited with code $LASTEXITCODE."
}
