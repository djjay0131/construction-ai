# Quick Setup Guide - Object Detection Feature

## Prerequisites

- Python 3.8+
- Node.js 16+
- YOLO model file (`best.pt`)

## Setup Steps

### 1. Copy YOLO Model

```bash
# Copy best.pt from your floor-plan-object-detection project
cp /Users/ryan/PycharmProjects/floor-plan-object-detection/best.pt \
   /Users/ryan/PycharmProjects/construction-ai/backend/app/core/cv/best.pt
```

### 2. Install Backend Dependencies

```bash
cd /Users/ryan/PycharmProjects/construction-ai/backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

**Note**: PyTorch and YOLO packages are large (~2GB). Installation may take 5-10 minutes.

### 3. Install Frontend Dependencies

```bash
cd /Users/ryan/PycharmProjects/construction-ai/frontend

# Install if not already done
npm install
```

### 4. Start Backend Server

```bash
cd /Users/ryan/PycharmProjects/construction-ai/backend

# With virtual environment activated
python -m app.main

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 5. Start Frontend Server

```bash
cd /Users/ryan/PycharmProjects/construction-ai/frontend

npm run dev
```

Expected output:

```
VITE v5.0.8  ready in 500 ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### 6. Access Application

- **Material Takeoff**: http://localhost:5173/
- **Object Detection**: http://localhost:5173/detection

## Quick Test

1. Navigate to http://localhost:5173/detection
2. Upload a floor plan image (PNG or JPG)
3. Click "Detect Objects"
4. View annotated results
5. Select a reference object and enter its real size
6. Click "Calculate Real Dimensions"
7. Download measurements as CSV

## Troubleshooting

### Backend Issues

**Issue**: `ImportError: cannot import name 'YOLO' from 'ultralytics'`

```bash
pip install ultralytics --upgrade
```

**Issue**: `FileNotFoundError: best.pt`

```bash
# Ensure model file exists
ls backend/app/core/cv/best.pt
```

**Issue**: `torch not found`

```bash
# Install PyTorch (CPU version)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Frontend Issues

**Issue**: Lint errors in IDE

- These are expected if dependencies aren't installed
- Run `npm install` in the frontend directory

**Issue**: CORS errors

- Ensure backend is running on port 8000
- Check CORS settings in `backend/app/main.py`

### Model Issues

**Issue**: YOLO model fails to load

```bash
# Test model loading
cd backend
python -c "from ultralytics import YOLO; model = YOLO('app/core/cv/best.pt'); print('Model loaded successfully')"
```

## API Testing with curl

Test detection endpoint:

```bash
curl -X POST "http://localhost:8000/api/detection/detect" \
  -F "file=@your_floor_plan.png" \
  -F "confidence=0.25"
```

Check API docs:

- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Environment Variables

### Backend (`.env` in backend directory)

```env
DATABASE_URL=sqlite:///./construction_ai.db
UPLOAD_DIR=data/uploads
MAX_UPLOAD_SIZE=104857600  # 100MB
```

### Frontend (`.env` in frontend directory)

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Development Tips

### Hot Reload

- Backend: Use `--reload` flag with uvicorn
- Frontend: Vite automatically hot reloads

### Debugging Backend

```bash
# Add to code for debugging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Debugging Frontend

- Open browser DevTools (F12)
- Check Network tab for API calls
- Check Console for errors

## Docker Setup (Alternative)

If you prefer Docker:

```bash
# Start services
docker-compose up -d

# Check logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Performance Notes

- **First Detection**: May take 5-10 seconds (model loading)
- **Subsequent Detections**: 1-3 seconds
- **Large Images (>4000px)**: May take longer
- **Confidence Threshold**: Lower values = more detections but slower

## Next Steps

1. ✅ Test basic detection
2. ✅ Test calibration
3. ✅ Export CSV
4. 📝 Integrate with material takeoff workflow
5. 📝 Add database persistence
6. 📝 Implement batch processing

## Support

- Check `OBJECT_DETECTION_IMPLEMENTATION.md` for detailed documentation
- Review API docs at http://localhost:8000/api/docs
- Check console logs for errors

---

Happy detecting! 🎯
