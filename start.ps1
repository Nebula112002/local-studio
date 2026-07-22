param(
    [switch]$Dev,
    [switch]$Autostart
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# App on D:\AI; outputs on G: (never run the studio from G:\Generation).
if (-not $env:LOCAL_STUDIO_OUTPUT_DIR) {
    $env:LOCAL_STUDIO_OUTPUT_DIR = "G:\Generation\Local-Studio\output"
}

$Port = if ($env:LOCAL_STUDIO_PORT) { [int]$env:LOCAL_STUDIO_PORT } else { 8787 }
$PublicPort = if ($env:LOCAL_STUDIO_PUBLIC_PORT) { [int]$env:LOCAL_STUDIO_PUBLIC_PORT } else { 8787 }
$Python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$LockFile = Join-Path $PSScriptRoot ".local-studio.lock"
$LogFile = Join-Path $PSScriptRoot "local-studio.log"
$LocalUrl = "http://127.0.0.1:$PublicPort"
$TailnetUrl = "https://calebscomputer.tailfdadcb.ts.net:$PublicPort"
$Quiet = $Autostart -or ($env:LOCAL_STUDIO_AUTOSTART -eq "1")

function Write-Log([string]$Message, [string]$Color = "") {
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    if (-not $Quiet) {
        if ($Color) { Write-Host $Message -ForegroundColor $Color }
        else { Write-Host $Message }
    }
}

function Test-Listening {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalAddress -eq "127.0.0.1" })
}

if (Test-Path $LockFile) {
    $lockPid = Get-Content $LockFile -ErrorAction SilentlyContinue
    if ($lockPid -and (Get-Process -Id $lockPid -ErrorAction SilentlyContinue)) {
        if (Test-Listening) {
            Write-Log "Launcher already running (PID $lockPid). Exiting."
            exit 0
        }
    }
}

if (Test-Listening) {
    Write-Log "Local Studio is already running on http://127.0.0.1:$Port"
    if (-not $Quiet) {
        Write-Host "Open: $LocalUrl" -ForegroundColor Green
        Write-Host "Tailnet: $TailnetUrl" -ForegroundColor Cyan
        Write-Host "Outputs: $env:LOCAL_STUDIO_OUTPUT_DIR" -ForegroundColor DarkGray
        Write-Host "ComfyUI is manual-only - start it from Stability Matrix when you want to generate." -ForegroundColor Yellow
    }
    exit 0
}

New-Item -ItemType Directory -Force -Path $env:LOCAL_STUDIO_OUTPUT_DIR | Out-Null
Set-Content -Path $LockFile -Value $PID -Encoding ASCII

try {
    Write-Log "Local Studio - starting from $PSScriptRoot" "Cyan"
    Write-Log "Outputs -> $env:LOCAL_STUDIO_OUTPUT_DIR" "DarkGray"

    if (-not (Test-Path $Python)) {
        Write-Log "Creating virtual environment..."
        python -m venv .venv
    }
    if (-not (Test-Path $Python)) {
        Write-Log "ERROR: Python not found at $Python"
        exit 1
    }

    if (-not $Quiet) {
        & $Python -m pip install -q -r requirements.txt 2>&1 | Out-Null
    }

    $useReload = $Dev -or ($env:LOCAL_STUDIO_DEV -eq "1")
    $uvicornArgs = @('-m', 'uvicorn', 'server.main:app', '--host', '127.0.0.1', '--port', "$Port")
    if ($useReload) { $uvicornArgs += '--reload' }

    Write-Log ""
    Write-Log "Open $LocalUrl in your browser" "Green"
    Write-Log "Tailnet: $TailnetUrl" "Cyan"
    if ($Port -ne $PublicPort) {
        Write-Log "Backend bind: 127.0.0.1:$Port (proxied to public :$PublicPort)" "DarkGray"
    }
    Write-Log "ComfyUI is not auto-started. Launch it manually from Stability Matrix > Packages when ready." "Yellow"
    Write-Log ""

    if ($Quiet) {
        $ErrorActionPreference = "Continue"
        & $Python @uvicornArgs *>> $LogFile
    } else {
        & $Python @uvicornArgs
    }
}
finally {
    Remove-Item -Path $LockFile -ErrorAction SilentlyContinue
}
