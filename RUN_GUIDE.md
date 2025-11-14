# 🚀 Running the Application - Quick Commands

## Current Status

✅ Frontend is running on http://localhost:5173/
⏳ Backend needs to be started

## Start Backend Server

### Option 1: Terminal (Recommended for development)

```bash
cd /Users/ryan/PycharmProjects/construction-ai/backend
python -m app.main
```

### Option 2: Using uvicorn

```bash
cd /Users/ryan/PycharmProjects/construction-ai/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Loading YOLO model from ...
INFO:     YOLO model loaded successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## Access the Application

Once both servers are running:

- **Material Takeoff**: http://localhost:5173/
- **Object Detection**: http://localhost:5173/detection
- **API Documentation**: http://localhost:8000/api/docs
- **Backend Health Check**: http://localhost:8000/api/health

## Testing the Object Detection Feature

1. Open http://localhost:5173/detection
2. Click "Click to upload" or drag a floor plan image (PNG/JPG)
3. Adjust confidence threshold (default 25%)
4. Select which object types to detect (default: all)
5. Click "Detect Objects"
6. View results with annotated image
7. For calibration:
   - Select a reference object from dropdown
   - Enter its real-world size
   - Choose the dimension (width or height)
   - Select unit (meters/feet/inches/cm)
   - Click "Calculate Real Dimensions"
8. Download measurements as CSV

## Troubleshooting

### Backend Won't Start

**Issue**: `FileNotFoundError: best.pt`

```bash
# Copy the YOLO model file
cp /Users/ryan/PycharmProjects/floor-plan-object-detection/best.pt \
   /Users/ryan/PycharmProjects/construction-ai/backend/app/core/cv/best.pt
```

**Issue**: Import errors for ultralytics, torch, etc.

```bash
cd /Users/ryan/PycharmProjects/construction-ai/backend
pip install -r requirements.txt
```

### Frontend Issues

**Issue**: "Cannot find module" errors

```bash
cd /Users/ryan/PycharmProjects/construction-ai/frontend
npm install
```

**Issue**: TypeScript errors in IDE

- These are expected and won't prevent the app from running
- They occur because TypeScript is checking against installed packages

### CORS Issues

If you see CORS errors in browser console:

1. Ensure backend is running on port 8000
2. Check `backend/app/main.py` has correct CORS origins
3. Frontend should be on http://localhost:5173

## Quick Test Commands

### Test Backend API

```bash
# Health check
curl http://localhost:8000/api/health

# Upload test image (if you have one)
curl -X POST "http://localhost:8000/api/detection/detect" \
  -F "file=@/path/to/floor_plan.png" \
  -F "confidence=0.25"
```

### Check Logs

Backend logs will show in the terminal where you started `python -m app.main`

## Development Mode

Both servers support hot-reload:

- **Backend**: Auto-reloads when Python files change (with `--reload` flag)
- **Frontend**: Auto-reloads when React/TS files change (Vite default)

## Stop Servers

- Press `Ctrl+C` in each terminal to stop the servers

## Next Steps After Testing

1. ✅ Test basic image upload
2. ✅ Test object detection
3. ✅ Test calibration
4. ✅ Export CSV
5. 📝 Add more sample floor plans
6. 📝 Fine-tune confidence thresholds
7. 📝 Integrate with material takeoff workflow

---

Happy testing! 🎯
