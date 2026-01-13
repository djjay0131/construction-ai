# Network Error Troubleshooting Guide

## Problem
Frontend shows "Network Error" when analyzing PDF, but backend works properly.

## Solutions Implemented

### 1. Enhanced Error Handling
**File**: `frontend/src/pages/FloorPlanAnalysisPage.tsx`

Added detailed error logging to identify the exact issue:
- Logs full error details (message, response, status, stack)
- Differentiates between server errors, network errors, and client errors
- Provides helpful error messages

### 2. Fixed TypeScript Interface
**File**: `frontend/src/services/api.ts`

Made `detected_objects` and `object_counts` optional in `FloorPlanInfo`:
```typescript
detected_objects?: DetectedObject[]
object_counts?: Record<string, number>
```

### 3. Created Test Tool
**File**: `backend_test.html`

A standalone HTML test tool to diagnose backend connectivity issues.

## How to Troubleshoot

### Step 1: Open Browser Console
1. Open the frontend in your browser
2. Press F12 to open Developer Tools
3. Go to "Console" tab
4. Try uploading a PDF
5. Look for detailed error logs

### Step 2: Check Error Message
The enhanced error handling will show one of these:

**Server Error (Backend responded but with error):**
```
Server error: 500
or
{detailed error from backend}
```
**Solution**: Check backend logs for the Python error

**Network Error (No response from server):**
```
No response from server. Is the backend running at http://localhost:8000?
```
**Solutions**:
- Verify backend is running: `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`
- Check backend URL in `frontend/src/services/api.ts`
- Verify firewall isn't blocking port 8000

**CORS Error:**
```
CORS policy: No 'Access-Control-Allow-Origin' header is present
```
**Solution**: Backend CORS is already configured for `http://localhost:5173`

### Step 3: Use Test Tool
1. Open `backend_test.html` in your browser
2. Click "Test /api/health" - should show backend is running
3. Click "Test CORS Headers" - should show CORS is configured
4. Select PDF and click "Test /api/floor-plan/analyze-pdf"

### Step 4: Check Backend Console
Look for Python errors or tracebacks:
- Import errors (missing packages)
- YOLO model loading errors
- Gemini API errors
- File processing errors

## Common Issues and Solutions

### Issue 1: Backend Not Running
**Symptom**: "No response from server"
**Solution**:
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Issue 2: Missing Dependencies
**Symptom**: Backend crashes with ImportError
**Solution**:
```bash
pip install pdf2image easyocr google-genai
```

### Issue 3: Model Files Not Found
**Symptom**: Backend error "Model file not found"
**Solution**: Verify model paths in `backend/.env`:
```
YOLO_BOUNDARY_MODEL_PATH=../datascience/runs/yolo12xtrain_floorplan_boundary/yolo12x_floorplan_boundary_exp2/weights/best.pt
YOLO_OBJECT_MODEL_PATH=../datascience/runs/yolo12xtrain/yolo12x_exp3/weights/best.pt
```

### Issue 4: Poppler Not Installed
**Symptom**: "PDFInfoNotInstalledError"
**Solution**:
```bash
sudo apt install poppler-utils
```

### Issue 5: Gemini API Key Missing
**Symptom**: Backend works but scale detection fails
**Solution**: Add to `backend/.env`:
```
GEMINI_API_KEY=your_actual_api_key_here
```

### Issue 6: Large PDF Timeout
**Symptom**: Request times out after long wait
**Solution**: Increase timeout in `frontend/src/services/api.ts`:
```typescript
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000, // 2 minutes
  headers: {
    'Content-Type': 'application/json',
  },
})
```

### Issue 7: CORS Error (Different Port)
**Symptom**: CORS error even though CORS is configured
**Solution**: If frontend runs on different port, add to `backend/app/main.py`:
```python
allow_origins=[
    "http://localhost:5173",
    "http://localhost:5174",  # Add your port
    "http://localhost:3000",
],
```
**Note**: You MUST restart the backend after changing CORS settings!

### Issue 8: 404 Not Found Error
**Symptom**: Backend logs show "POST /api/floor-plan/analyze-pdf HTTP/1.1" 404 Not Found
**Root Cause**: The floor_plan router is not registered (import error or backend not restarted)
**Solution**:
```bash
# 1. Run diagnostic script
cd backend
python check_backend.py

# 2. If it shows missing dependencies, install them:
pip install pdf2image easyocr google-genai ultralytics opencv-python

# 3. FULLY RESTART the backend (Ctrl+C to stop, then):
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Why this happens**:
- The `--reload` flag sometimes doesn't detect new files
- Import errors prevent the router from loading
- Missing dependencies cause silent import failures

**How to verify it's fixed**:
- Run `python check_backend.py` - should show floor-plan routes
- Or check backend startup logs for any import errors
- Or visit http://localhost:8000/docs - should see floor-plan endpoints

## Debugging Commands

### Check if backend is accessible:
```bash
curl http://localhost:8000/api/health
```

### Test PDF upload via curl:
```bash
curl -X POST http://localhost:8000/api/floor-plan/analyze-pdf?page_number=1 \
  -F "file=@/path/to/your.pdf" \
  -H "Content-Type: multipart/form-data"
```

### Check backend logs:
Look at the terminal where you started the backend server.

### Check frontend network requests:
1. F12 → Network tab
2. Upload PDF
3. Look for failed requests (red)
4. Click on failed request
5. Check Response tab for error details

## Expected Behavior

### Successful Flow:
1. User uploads PDF
2. Console logs: "Analyzing PDF: filename.pdf Page: 1"
3. Backend processes (10-30 seconds)
4. Console logs: "Analysis complete: {...}"
5. Floor plans displayed in UI

### Successful Response Structure:
```json
{
  "analysis_id": "uuid",
  "filename": "example.pdf",
  "num_floor_plans": 2,
  "paper_size": {
    "name": "ANSI B (Tabloid)",
    "width_inches": 17.0,
    "height_inches": 11.0,
    "orientation": "Landscape"
  },
  "floor_plans": [
    {
      "id": 1,
      "bbox": {...},
      "image_url": "...",
      "width_pixels": 1352,
      "height_pixels": 2513,
      "scale": {
        "found": true,
        "notation": "1/8\"=1'-0\"",
        "scale_ratio": 96.0
      }
    }
  ],
  "full_page_scale": {...},
  "processing_time_seconds": 15.23,
  "warnings": []
}
```

## Next Steps If Issue Persists

1. **Check browser console** for exact error message
2. **Use test tool** (backend_test.html) to isolate the issue
3. **Check backend terminal** for Python errors
4. **Verify all dependencies** are installed
5. **Test with small PDF first** (1 page, simple floor plan)
6. **Check firewall/antivirus** isn't blocking connections

## Contact Information

If you've tried all the above and still have issues, provide:
- Exact error message from browser console
- Backend terminal output
- Browser and OS version
- PDF file size and complexity
- Screenshot of network error

