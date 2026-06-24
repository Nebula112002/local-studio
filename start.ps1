$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$existing = Get-NetTCPConnection -LocalPort 8787 -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -eq "127.0.0.1" }
if ($existing) {
    Write-Host "Local Studio is already running on http://127.0.0.1:8787" -ForegroundColor Green
    Write-Host "Tailnet: https://calebscomputer.tailfdadcb.ts.net:8787" -ForegroundColor Cyan
    Write-Host "Start ComfyUI in Stability Matrix first if the backend shows disconnected." -ForegroundColor Yellow
    exit 0
}

Write-Host "Local Studio - starting..." -ForegroundColor Cyan

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

& .\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

Write-Host ""
Write-Host "Open http://127.0.0.1:8787 in your browser" -ForegroundColor Green
Write-Host "Tailnet: https://calebscomputer.tailfdadcb.ts.net:8787" -ForegroundColor Cyan
Write-Host "Start ComfyUI or Forge in Stability Matrix first." -ForegroundColor Yellow
Write-Host ""

python -m uvicorn server.main:app --host 127.0.0.1 --port 8787 --reload
