#!/bin/bash
# Quick Fix and Restart Script for Backend

echo "========================================"
echo "Backend Fix & Restart"
echo "========================================"
echo ""

cd "$(dirname "$0")"

echo "[1/4] Running diagnostics..."
python check_backend.py

echo ""
echo "[2/4] Checking for missing dependencies..."
pip install -q pdf2image easyocr google-genai 2>/dev/null && echo "✓ Dependencies OK" || echo "⚠ Some dependencies may be missing"

echo ""
echo "[3/4] Verifying .env file..."
if [ ! -f ".env" ]; then
    echo "⚠ .env file not found! Copying from .env.example..."
    cp .env.example .env
    echo "✗ Please edit .env and add your GEMINI_API_KEY"
    exit 1
else
    echo "✓ .env file exists"
fi

echo ""
echo "[4/4] Starting backend server..."
echo "Backend will start at http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

