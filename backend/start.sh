#!/bin/bash
# Startup script for backend server
# This ensures we use the conda environment's uvicorn

# Activate conda environment if needed
# conda activate construction-ai

# Run uvicorn using Python module instead of direct command
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

