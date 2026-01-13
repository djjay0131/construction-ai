# Construction AI - Floor Plan Analysis Integration

## 🎯 Quick Start (Ubuntu/Linux)

This guide gets you up and running quickly with the integrated floor plan analysis system.

### Prerequisites Check

```bash
# Check conda installation
conda --version

# Check if NVIDIA GPU is available (optional but recommended)
nvidia-smi
```

### 1. Setup Backend (5 minutes)

```bash
# Navigate to project
cd /path/to/construction-ai

# Create and activate conda environment
conda create -n construction-ai python=3.10 -y
conda activate construction-ai

# Install core packages via conda-forge (prevents binary issues)
conda install -c conda-forge pillow scipy opencv numpy -y

# Install PyTorch - choose ONE based on your hardware:

# For GPU with CUDA 11.8:
conda install -c pytorch -c nvidia pytorch torchvision pytorch-cuda=11.8 -y

# For CPU only:
conda install -c pytorch pytorch torchvision cpuonly -y

# Install ML packages
pip install ultralytics easyocr

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Configure environment
cp .env.example .env
nano .env  # Add your GEMINI_API_KEY

# Make startup script executable
chmod +x start_server.sh
```

### 2. Setup Frontend (2 minutes)

```bash
# In a new terminal
cd frontend

# Install Node.js (if not installed)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18

# Install dependencies
npm install

# Make startup script executable
chmod +x start_dev.sh
```

### 3. Run the Application

**Terminal 1 - Backend:**
```bash
conda activate construction-ai
cd backend
./start_server.sh
```

**Terminal 2 - Frontend:**
```bash
cd frontend
./start_dev.sh
```

**Access the app:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs

## 🚀 Using Floor Plan Analysis

### Step-by-Step Workflow

1. **Open the App**
   - Navigate to http://localhost:5173
   - Click "Floor Plan Analysis" in the navigation

2. **Upload PDF**
   - Click "Upload PDF" or drag and drop
   - Select page number (default: 1)
   - Click "Analyze PDF"
   - Wait for processing (10-30 seconds)

3. **Review Detection Results**
   - View paper size (ARCH D, ANSI A, etc.)
   - See auto-detected scale (e.g., "1/4"=1'-0"")
   - Review all detected floor plans on the page

4. **Select Floor Plan**
   - Click on a floor plan to select it
   - Adjust parameters:
     - **Confidence**: 0.05 (default) to 1.0
       - Lower = more objects detected
       - Higher = only high-confidence detections
     - **Manual Scale**: Override auto-detection if needed
       - Format: `1/4"=1'-0"` or `1/8"=1'-0"`

5. **Detect Objects**
   - Click "Detect Objects"
   - Wait for processing (5-15 seconds)

6. **View Results**
   - See object counts (walls, doors, windows)
   - View numbered annotations (Wall #1, Door #1, etc.)
   - See real-world dimensions (if scale detected)
   - Export or analyze different floor plans

### Example Use Cases

**Use Case 1: Multi-Floor Plan Drawing**
- Upload a PDF with multiple floor plans
- System automatically detects all floor plans
- Analyze each floor plan separately
- Compare object counts across floor plans

**Use Case 2: Scale Detection**
- System uses Gemini AI to find architectural scale
- Automatically calculates real-world dimensions
- Override with manual scale if needed
- Get precise measurements for material takeoff

**Use Case 3: Object Identification**
- Detects walls, doors, windows automatically
- Numbered annotations for easy reference
- Confidence scores for each detection
- Adjust threshold for accuracy vs. completeness

## 🔧 Configuration

### Environment Variables (.env)

```bash
# Required
GEMINI_API_KEY=your_key_here  # Get from https://ai.google.dev/

# Model paths (adjust if different)
YOLO_BOUNDARY_MODEL_PATH=../datascience/runs/yolo12xtrain_floorplan_boundary/yolo12x_floorplan_boundary_exp2/weights/best.pt
YOLO_OBJECT_MODEL_PATH=../datascience/runs/yolo12xtrain/yolo12x_exp3/weights/best.pt

# Optional
PDF_DPI=300  # Higher = better quality, slower processing
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_SIZE=104857600  # 100 MB
```

### Detection Parameters

**Confidence Threshold (0.01 - 1.0):**
- `0.05` (default): Balanced - good for most cases
- `0.10-0.25`: Higher precision, fewer false positives
- `0.01-0.04`: Higher recall, may include noise

**Manual Scale Examples:**
- Imperial: `1/4"=1'-0"`, `1/8"=1'-0"`, `3/32"=1'-0"`
- Metric: `1:100`, `1:50`, `1:200`

## 🐛 Troubleshooting

### Backend Won't Start

**Error: `uvicorn: command not found`**
```bash
# Solution: Use Python module directly
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Error: `PDFInfoNotInstalledError`**
```bash
# Solution: Install poppler
sudo apt install poppler-utils
```

**Error: `Module 'torch' has no attribute 'cuda'`**
```bash
# Solution: Reinstall PyTorch with correct CUDA version
conda install -c pytorch -c nvidia pytorch torchvision pytorch-cuda=11.8 -y
```

### Frontend Issues

**Error: `Failed to fetch`**
- Check backend is running: http://localhost:8000/api/health
- Check CORS settings in backend/app/main.py
- Verify frontend API URL in frontend/src/services/api.ts

**Error: `Cannot read property of undefined`**
- Check browser console (F12) for detailed errors
- Verify API response format matches TypeScript types

### Model Issues

**Error: `Model file not found`**
```bash
# Verify model paths
ls -la ../datascience/runs/yolo12xtrain_floorplan_boundary/yolo12x_floorplan_boundary_exp2/weights/best.pt
ls -la ../datascience/runs/yolo12xtrain/yolo12x_exp3/weights/best.pt
```

If models don't exist, you need to train them first using `datascience/yolo_train.ipynb`.

**Low Detection Accuracy**
- Ensure using correct model for your data
- Adjust confidence threshold
- Check input image quality
- Verify scale detection is working

### Performance Issues

**Slow Processing**
- Use GPU if available (10-50x faster)
- Reduce PDF DPI (300 → 200 for faster processing)
- Close other GPU-intensive applications
- Check system resources (RAM, GPU memory)

## 📊 API Reference

### POST /api/floor-plan/analyze-pdf
Upload PDF and detect floor plans.

**Request:**
- `file`: PDF file (multipart/form-data)
- `page_number`: Page to analyze (query param, default: 1)

**Response:**
```json
{
  "analysis_id": "uuid",
  "filename": "example.pdf",
  "num_floor_plans": 2,
  "paper_size": {
    "name": "ARCH D",
    "width_inches": 24.0,
    "height_inches": 36.0
  },
  "floor_plans": [...]
}
```

### POST /api/floor-plan/detect-objects
Detect objects in a floor plan.

**Request:**
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
  "detected_objects": [...],
  "object_counts": {"wall": 15, "door": 3, "window": 5},
  "annotated_image_url": "...",
  "numbered_image_url": "..."
}
```

### GET /api/floor-plan/image/{analysis_id}/{filename}
Get analysis images.

## 🎓 Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React)                     │
│  - FloorPlanAnalysisPage.tsx: Main UI                   │
│  - api.ts: API client                                    │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP/REST
┌─────────────────────▼───────────────────────────────────┐
│                   Backend (FastAPI)                      │
│  - floor_plan.py: API endpoints                          │
│  - floor_plan_service.py: Business logic                 │
│  ├── PDF → Images (pdf2image)                            │
│  ├── OCR (EasyOCR)                                       │
│  ├── Scale Detection (Gemini AI)                         │
│  ├── Floor Plan Boundary Detection (YOLO)                │
│  └── Object Detection (YOLO)                             │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┴──────────────┐
        │                            │
┌───────▼────────┐          ┌────────▼─────────┐
│  YOLO Boundary │          │  YOLO Object     │
│  Detection     │          │  Detection       │
│  Model         │          │  Model           │
└────────────────┘          └──────────────────┘
```

## 📚 Additional Resources

- **Full Setup Guide**: [FLOOR_PLAN_ANALYSIS_GUIDE.md](./FLOOR_PLAN_ANALYSIS_GUIDE.md)
- **API Documentation**: http://localhost:8000/api/docs
- **YOLO Training**: `datascience/yolo_train.ipynb`
- **Gemini API**: https://ai.google.dev/

## 🤝 Support

For issues:
1. Check [FLOOR_PLAN_ANALYSIS_GUIDE.md](./FLOOR_PLAN_ANALYSIS_GUIDE.md) troubleshooting section
2. Review backend logs in terminal
3. Check browser console (F12) for frontend errors
4. Verify model files exist and .env is configured
5. Test with example PDF in `data/` directory

## 📝 License

See [LICENSE](./LICENSE) file for details.

