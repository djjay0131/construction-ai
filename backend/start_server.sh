#!/bin/bash
# Quick start script for Construction AI backend
# This script handles common issues and starts the server properly

echo "========================================"
echo "Construction AI - Backend Startup"
echo "========================================"
echo ""

# Check if we're in the backend directory
if [ ! -f "app/main.py" ]; then
    echo "❌ Error: Not in backend directory"
    echo "Please run this script from the backend/ directory"
    exit 1
fi

# Check if conda environment is activated
if [ -z "$CONDA_DEFAULT_ENV" ]; then
    echo "⚠️  Warning: No conda environment detected"
    echo "Please activate your conda environment first:"
    echo "  conda activate construction-ai"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ Conda environment: $CONDA_DEFAULT_ENV"
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    if [ -f ".env.example" ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
        echo "✓ Created .env file"
        echo "⚠️  Please edit .env and add your GEMINI_API_KEY"
        echo ""
    fi
fi

# Check if required packages are installed
echo "Checking dependencies..."
python -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ FastAPI not installed. Installing dependencies..."
    pip install -r requirements.txt
fi

python -c "import ultralytics" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Ultralytics not installed. Installing..."
    pip install ultralytics
fi

python -c "import easyocr" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  EasyOCR not installed. Installing..."
    pip install easyocr
fi

echo "✓ Dependencies OK"
echo ""

# Check if model files exist
echo "Checking model files..."
BOUNDARY_MODEL="../datascience/runs/yolo12xtrain_floorplan_boundary/yolo12x_floorplan_boundary_exp2/weights/best.pt"
OBJECT_MODEL="../datascience/runs/yolo12xtrain/yolo12x_exp3/weights/best.pt"

if [ ! -f "$BOUNDARY_MODEL" ]; then
    echo "⚠️  Warning: Floor plan boundary model not found at:"
    echo "   $BOUNDARY_MODEL"
    echo "   You may need to train this model first."
fi

if [ ! -f "$OBJECT_MODEL" ]; then
    echo "⚠️  Warning: Object detection model not found at:"
    echo "   $OBJECT_MODEL"
    echo "   You may need to train this model first."
fi

echo ""
echo "========================================"
echo "Starting server..."
echo "========================================"
echo ""
echo "Backend API: http://localhost:8000"
echo "API Docs: http://localhost:8000/api/docs"
echo "Health Check: http://localhost:8000/api/health"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start the server using Python module to avoid path issues
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

