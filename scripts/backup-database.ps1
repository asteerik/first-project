$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env"
$backupDirectory = Join-Path $projectRoot "backups"

if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing settings file: $envFile"
}

$settingsJson = & py -c 'from dotenv import dotenv_values; import json, sys; print(json.dumps(dotenv_values(sys.argv[1])))' $envFile
if ($LASTEXITCODE -ne 0) {
    throw "Could not read .env settings using Python."
}
$settings = $settingsJson | ConvertFrom-Json

$databaseName = $settings.DB_NAME
$databaseUser = $settings.DB_USER
$databasePassword = $settings.DB_PASSWORD
$databaseHost = $settings.DB_HOST
$databasePort = $settings.DB_PORT

if ([string]::IsNullOrWhiteSpace($databaseName) -or $databaseName -notmatch '^[A-Za-z0-9_]+$') {
    throw "DB_NAME is missing or contains invalid characters."
}
if ([string]::IsNullOrWhiteSpace($databaseUser) -or $null -eq $databasePassword) {
    throw "DB_USER and DB_PASSWORD must be set in .env."
}
if (
    $databaseUser -match '[\r\n"]' -or
    $databaseHost -match '[\r\n"]' -or
    $databasePassword -match '[\r\n]'
) {
    throw "Database connection settings contain unsupported line breaks or quotes."
}
if ([string]::IsNullOrWhiteSpace($databaseHost)) {
    $databaseHost = "127.0.0.1"
}
if ([string]::IsNullOrWhiteSpace($databasePort)) {
    $databasePort = "3306"
}
if ($databasePort -notmatch '^\d{1,5}$' -or [int]$databasePort -lt 1 -or [int]$databasePort -gt 65535) {
    throw "DB_PORT must be a port number between 1 and 65535."
}

$mysqldumpCommand = Get-Command mysqldump -ErrorAction SilentlyContinue
if ($mysqldumpCommand) {
    $mysqldumpPath = $mysqldumpCommand.Source
} else {
    $mysqldumpPath = "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe"
}
if (-not (Test-Path -LiteralPath $mysqldumpPath -PathType Leaf)) {
    throw "mysqldump was not found on PATH or at: $mysqldumpPath"
}
New-Item -ItemType Directory -Path $backupDirectory -Force | Out-Null

$timestamp = [DateTime]::UtcNow.ToString("yyyyMMdd-HHmmss")
$backupPath = Join-Path $backupDirectory "$($databaseName)-$timestamp.sql"
$partialPath = "$backupPath.partial"
$optionsPath = Join-Path ([System.IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString() + ".cnf")
$errorPath = "$optionsPath.stderr"

try {
    $escapedPassword = $databasePassword.Replace("\", "\\").Replace('"', '\"')
    $options = @(
        "[client]"
        "host=$databaseHost"
        "port=$databasePort"
        "user=$databaseUser"
        ('password="{0}"' -f $escapedPassword)
    )
    [System.IO.File]::WriteAllLines($optionsPath, $options, [System.Text.UTF8Encoding]::new($false))

    $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $fileSecurity = New-Object System.Security.AccessControl.FileSecurity
    $fileSecurity.SetAccessRuleProtection($true, $false)
    $accessRule = [System.Security.AccessControl.FileSystemAccessRule]::new(
        $currentUser,
        [System.Security.AccessControl.FileSystemRights]::FullControl,
        [System.Security.AccessControl.AccessControlType]::Allow
    )
    $fileSecurity.AddAccessRule($accessRule)
    Set-Acl -LiteralPath $optionsPath -AclObject $fileSecurity

    $arguments = @(
        "--defaults-extra-file=`"$optionsPath`""
        "--single-transaction"
        "--routines"
        "--triggers"
        "--default-character-set=utf8mb4"
        "--databases"
        $databaseName
    ) -join " "

    $process = Start-Process `
        -FilePath $mysqldumpPath `
        -ArgumentList $arguments `
        -NoNewWindow `
        -Wait `
        -PassThru `
        -RedirectStandardOutput $partialPath `
        -RedirectStandardError $errorPath

    if ($process.ExitCode -ne 0) {
        $errorMessage = if (Test-Path -LiteralPath $errorPath) {
            Get-Content -LiteralPath $errorPath -Raw
        } else {
            "mysqldump exited with code $($process.ExitCode)."
        }
        throw "Backup was not created: $errorMessage"
    }

    Move-Item -LiteralPath $partialPath -Destination $backupPath
    Write-Output "Backup created: $backupPath"
}
finally {
    foreach ($temporaryPath in @($optionsPath, $errorPath, $partialPath)) {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
}
