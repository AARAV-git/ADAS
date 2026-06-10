#!/bin/bash
echo "=================================================="
echo "  RoadSense AI — Backend Server"
echo "  Context-Aware Explainable ADAS for Indian Traffic"
echo "=================================================="
echo ""

# Get the script's directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Activate virtual env if exists
if [ -d "../venv" ]; then
    echo "[*] Activating virtual environment..."
    source ../venv/bin/activate
elif [ -d "../env" ]; then
    echo "[*] Activating virtual environment..."
    source ../env/bin/activate
elif [ -d "../.venv" ]; then
    echo "[*] Activating virtual environment..."
    source ../.venv/bin/activate
else
    echo "[!] No venv found — using system Python"
fi

echo "[*] Starting FastAPI server on http://localhost:8000"
echo "[*] API Docs:    http://localhost:8000/docs"
echo "[*] Video list:  http://localhost:8000/api/videos"
echo ""
echo "Press Ctrl+C to stop the server."
echo ""

python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
