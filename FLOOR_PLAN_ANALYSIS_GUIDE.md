# Floor Plan Analysis - Setup and Run Guide

This guide explains how to set up and run the integrated floor plan analysis system that uses YOLO models to detect floor plans, extract scales, and identify objects.

## System Architecture

The system consists of three main components:

1. **Backend (FastAPI)**: PDF processing, YOLO detection, scale extraction, Gemini API integration
2. **Frontend (React + Vite)**: User interface for uploading PDFs and viewing results
3. **ML Models**: YOLO boundary detection and object detection models

## Prerequisites

### System Requirements
- Ubuntu/Linux (tested on Ubuntu 20.04+)
- NVIDIA GPU with CUDA support (recommended) or CPU
- 16GB+ RAM recommended
- conda or miniconda installed

### External Dependencies
```bash
# Install system packages
sudo apt update
sudo apt install -y build-essential git wget curl pkg-config \
    poppler-utils tesseract-ocr libtesseract-dev libleptonica-dev \
    libgl1 libglib2.0-0 ffmpeg
```

## Setup Instructions

### 1. Create Conda Environment

```bash
# Navigate to project root
cd /path/to/construction-ai

# Create conda environment
conda create -n construction-ai python=3.10 -y
conda activate construction-ai

# Install core scientific packages via conda-forge (avoids binary issues)
conda install -c conda-forge pillow scipy opencv numpy -y
```

### 2. Install PyTorch (Choose based on your hardware)

**For GPU with CUDA 11.8:**
```bash
conda install -c pytorch -c nvidia pytorch torchvision pytorch-cuda=11.8 -y
```

**For CPU only:**
```bash
conda install -c pytorch pytorch torchvision cpuonly -y
```

**For GPU with CUDA 12.1:**
```bash
conda install -c pytorch -c nvidia pytorch torchvision pytorch-cuda=12.1 -y
```

### 3. Install Python Dependencies

```bash
# Install ML and CV packages
pip install ultralytics easyocr

# Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..
```

### 4. Configure Environment Variables

```bash
cd backend

# Copy example env file
cp .env.example .env

# Edit .env with your settings
nano .env  # or use your preferred editor
```

**Important configurations in `.env`:**
- `GEMINI_API_KEY`: Get from https://ai.google.dev/ (required for scale detection)
- `YOLO_BOUNDARY_MODEL_PATH`: Path to floor plan boundary detection model
- `YOLO_OBJECT_MODEL_PATH`: Path to object detection model

### 5. Verify Model Paths

Ensure the YOLO model weights exist:
```bash
# Floor plan boundary model
ls ../datascience/runs/yolo12xtrain_floorplan_boundary/yolo12x_floorplan_boundary_exp2/weights/best.pt

# Object detection model
ls ../datascience/runs/yolo12xtrain/yolo12x_exp3/weights/best.pt
```

If models don't exist, you need to train them first using the notebooks in `datascience/`.

## Running the Application

### Start Backend Server

```bash
cd backend

# Option 1: Using Python module (recommended)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Option 2: Using the startup script
chmod +x start.sh
./start.sh
```

Backend will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/api/health

### Start Frontend Development Server

In a new terminal:

```bash
cd frontend

# Install Node.js if not already installed (using nvm)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend will be available at: http://localhost:5173

## Using the Floor Plan Analysis Feature

### Workflow

1. **Upload PDF**
   - Navigate to "Floor Plan Analysis" page
   - Upload a PDF containing architectural floor plans
   - Select which page to analyze
   - System detects paper size, scale, and floor plan boundaries

2. **Select Floor Plan**
   - View all detected floor plans
   - Click on a floor plan to select it
   - Adjust detection parameters:
     - **Confidence threshold**: Lower = more detections (0.01-1.0)
     - **Manual scale**: Override auto-detected scale (e.g., `1/4"=1'-0"`)

3. **View Results**
   - See annotated images with numbered objects
   - View object counts (walls, doors, windows, etc.)
   - See real-world dimensions if scale was detected
   - Export or analyze different floor plans

### API Endpoints

The following new endpoints are available:

#### `POST /api/floor-plan/analyze-pdf`
Upload and analyze a PDF to detect floor plans.

**Parameters:**
- `file`: PDF file
- `page_number`: Page to process (default: 1)

**Response:**
```json
{
  "analysis_id": "uuid",
  "filename": "example.pdf",
  "num_floor_plans": 2,
  "paper_size": {
    "name": "ARCH D",
    "width_inches": 24.0,
    "height_inches": 36.0,
    "orientation": "Landscape"
  },
  "floor_plans": [...],
  "full_page_scale": {
    "found": true,
    "notation": "1/4\"=1'-0\"",
    "scale_ratio": 96.0
  }
}
```

#### `POST /api/floor-plan/detect-objects`
Detect objects in a specific floor plan.

**Request Body:**
```json
{
  "analysis_id": "uuid",
  "floor_plan_id": 1,
  "confidence": 0.05,
  "manual_scale": "1/4\"=1'-0\""  // optional
}
```

**Response:**
```json
{
  "floor_plan_id": 1,
  "detected_objects": [...],
  "object_counts": {
    "wall": 15,
    "door": 3,
    "window": 5
  },
  "annotated_image_url": "/api/floor-plan/image/...",
  "numbered_image_url": "/api/floor-plan/image/...",
  "scale_used": {...}
}
```

#### `GET /api/floor-plan/image/{analysis_id}/{filename}`
Retrieve analysis images (original, annotated, or numbered).

## Troubleshooting

### Issue: `uvicorn: command not found` or `/usr/bin/uvicorn: No such file or directory`

**Solution:** Use Python module invocation instead:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Issue: `PDFInfoNotInstalledError: Unable to get page count`

**Solution:** Install poppler-utils:
```bash
sudo apt install poppler-utils
```

### Issue: `easyocr` import errors (scipy/numpy/PIL issues)

**Solution:** Reinstall via conda-forge:
```bash
conda install -c conda-forge numpy scipy pillow -y
pip install --upgrade easyocr
```

### Issue: `operator torchvision::nms does not exist`

**Solution:** Torch and torchvision versions don't match. Reinstall both:
```bash
conda install -c pytorch pytorch torchvision -y
```

### Issue: `AttributeError: module 'PIL.Image' has no attribute 'ANTIALIAS'`

**Solution:** Update Pillow:
```bash
pip install --upgrade Pillow>=10.0.0
```

### Issue: GPU not detected / CUDA errors

**Check CUDA availability:**
```python
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

**Solution:** Install correct PyTorch version for your CUDA:
```bash
# Check CUDA version
nvidia-smi

# Install matching PyTorch (example for CUDA 11.8)
conda install -c pytorch -c nvidia pytorch torchvision pytorch-cuda=11.8 -y
```

### Issue: Gemini API errors

**Check API key:**
```bash
# In backend directory
cat .env | grep GEMINI_API_KEY
```

**Test Gemini:**
```python
import os
from dotenv import load_dotenv
import google.genai as genai

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
print("Gemini initialized successfully!")
```

### Issue: Models not found

**Verify paths:**
```bash
ls -la ../datascience/runs/yolo12xtrain_floorplan_boundary/yolo12x_floorplan_boundary_exp2/weights/best.pt
ls -la ../datascience/runs/yolo12xtrain/yolo12x_exp3/weights/best.pt
```

If models don't exist, train them using:
- `datascience/yolo_train.ipynb` for object detection
- Floor plan boundary dataset for boundary detection

## Performance Tips

1. **Use GPU**: Detection is 10-50x faster on GPU
2. **Adjust confidence**: Higher confidence = faster but may miss objects
3. **Image size**: Larger images take longer to process
4. **Batch processing**: Process multiple floor plans from same analysis without re-uploading

## Development Notes

### Backend Structure
```
backend/
├── app/
│   ├── api/
│   │   ├── floor_plan.py      # Floor plan analysis endpoints
│   │   ├── detection.py       # Object detection endpoints
│   │   └── upload.py          # File upload endpoints
│   ├── core/
│   │   └── cv/
│   │       └── floor_plan_service.py  # Main analysis service
│   ├── schemas/
│   │   └── floor_plan.py      # Pydantic models
│   └── main.py                # FastAPI app
```

### Frontend Structure
```
frontend/
├── src/
│   ├── pages/
│   │   └── FloorPlanAnalysisPage.tsx  # Main analysis UI
│   ├── services/
│   │   └── api.ts             # API client
│   └── App.tsx                # Router configuration
```

### Key Technologies
- **Backend**: FastAPI, Ultralytics YOLO, EasyOCR, Gemini API, pdf2image
- **Frontend**: React, TypeScript, Vite, TailwindCSS, Axios
- **ML**: YOLOv12x for detection, EasyOCR for text extraction, Gemini for scale parsing

## Next Steps

1. Implement multi-page PDF support
2. Add measurement export (CSV, JSON)
3. Add drawing comparison features
4. Implement material takeoff integration
5. Add user authentication and project management

## Support

For issues, check:
- Backend logs: Terminal running uvicorn
- Frontend logs: Browser console (F12)
- API docs: http://localhost:8000/api/docs
- Model validation: Test with sample PDFs in `data/` directory

