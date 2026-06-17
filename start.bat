@echo off
setlocal
cd /d "%~dp0"

echo Local Studio - starting...
echo.

if not exist ".venv" (
  echo Creating virtual environment...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

echo.
echo Open http://127.0.0.1:8787 in your browser
echo Make sure ComfyUI or Forge is running via Stability Matrix
echo.

python -m uvicorn server.main:app --host 127.0.0.1 --port 8787 --reload
