@echo off
title RoadSense AI — Backend Server
color 0A
echo.
echo  ██████╗  ██████╗  █████╗ ██████╗ ███████╗███████╗███╗   ██╗███████╗███████╗
echo  ██╔══██╗██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔════╝████╗  ██║██╔════╝██╔════╝
echo  ██████╔╝██║   ██║███████║██║  ██║███████╗█████╗  ██╔██╗ ██║███████╗█████╗
echo  ██╔══██╗██║   ██║██╔══██║██║  ██║╚════██║██╔══╝  ██║╚██╗██║╚════██║██╔══╝
echo  ██║  ██║╚██████╔╝██║  ██║██████╔╝███████║███████╗██║ ╚████║███████║███████╗
echo  ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝╚══════╝╚══════╝
echo.
echo  Context-Aware Explainable ADAS for Indian Traffic
echo  ─────────────────────────────────────────────────
echo.

REM Activate virtualenv if it exists
if exist "..\venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment...
    call ..\venv\Scripts\activate.bat
) else (
    echo [!] No venv found — using system Python
)

echo [*] Starting FastAPI server on http://localhost:8000
echo [*] API Docs:    http://localhost:8000/docs
echo [*] Video list:  http://localhost:8000/api/videos
echo [*] Stream:      http://localhost:8000/api/stream/video_01.mp4
echo.
echo Press Ctrl+C to stop the server.
echo.

cd /d %~dp0
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
