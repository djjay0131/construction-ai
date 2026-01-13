# 🔥 URGENT FIX: 404 Not Found Error

## The Problem
```
INFO: 127.0.0.1:38138 - "POST /api/floor-plan/analyze-pdf?page_number=1 HTTP/1.1" 404 Not Found
```

The backend is running but **the floor-plan routes are not registered**. This happens when:
1. The `floor_plan` module failed to import (dependency missing)
2. The backend wasn't restarted after adding new files
3. There's an import error in the floor_plan_service.py

## ✅ QUICK FIX (Choose One)

### Option 1: Use Diagnostic Script (Recommended)

**Windows (PowerShell):**
```powershell
cd backend
python check_backend.py
```

**Ubuntu/Linux:**
```bash
cd backend
python3 check_backend.py
```

This will tell you **exactly** what's wrong.

### Option 2: Manual Fix

**Step 1: Stop the backend** (Ctrl+C in the terminal running uvicorn)

**Step 2: Install missing dependencies**
```bash
cd backend
pip install pdf2image easyocr google-genai ultralytics opencv-python
```

**Step 3: Start backend properly**
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Use Auto-Restart Script

**Windows (PowerShell):**
```powershell
cd backend
.\restart_backend.ps1
```

**Ubuntu/Linux:**
```bash
cd backend
chmod +x restart_backend.sh
./restart_backend.sh
```

## 🔍 How to Verify It's Fixed

### Method 1: Check Startup Logs
Look for these lines when backend starts:
```
INFO:     Application startup complete.
```

NO errors about imports should appear before this.

### Method 2: Visit API Docs
Open http://localhost:8000/docs in your browser.

You should see these endpoints under "Floor Plan Analysis":
- POST `/api/floor-plan/analyze-pdf`
- POST `/api/floor-plan/detect-objects`
- GET `/api/floor-plan/image/{analysis_id}/{filename}`
- GET `/api/floor-plan/status/{analysis_id}`
- DELETE `/api/floor-plan/analysis/{analysis_id}`

### Method 3: Test with curl
```bash
curl http://localhost:8000/api/health
```
Should return: `{"status":"healthy","service":"construction-ai","version":"0.1.0"}`

## 🚨 Common Causes

### Cause 1: Missing Dependencies
**Symptom**: Backend starts but routes are missing
**Fix**:
```bash
pip install pdf2image easyocr google-genai
```

### Cause 2: Import Error (Silent Failure)
**Symptom**: No error shown, but routes don't load
**Fix**: Run `python check_backend.py` to see the actual error

### Cause 3: Backend Not Restarted
**Symptom**: Added new files but --reload didn't catch them
**Fix**: **FULLY STOP** (Ctrl+C) and restart the backend

### Cause 4: Wrong Working Directory
**Symptom**: ModuleNotFoundError
**Fix**: Make sure you're in the `backend/` directory:
```bash
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Cause 5: Python Path Issues
**Symptom**: Cannot import app.core or app.schemas
**Fix**: Use `-m` flag:
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 📋 Diagnostic Checklist

Run through these checks:

- [ ] **Backend is running**: `curl http://localhost:8000/api/health` works
- [ ] **All dependencies installed**: `python check_backend.py` shows all ✓
- [ ] **Floor-plan routes registered**: Visit http://localhost:8000/docs
- [ ] **No import errors**: Check backend terminal for tracebacks
- [ ] **Correct working directory**: You're in `backend/` folder
- [ ] **CORS configured**: Includes your frontend port (5174)

## 🎯 Expected Output After Fix

### Backend Terminal:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Browser Console (after uploading PDF):
```
Analyzing PDF: example.pdf Page: 1
Analysis complete: {
  analysis_id: "...",
  num_floor_plans: 2,
  ...
}
```

### Backend Logs (after uploading PDF):
```
INFO:     127.0.0.1:38138 - "POST /api/floor-plan/analyze-pdf?page_number=1 HTTP/1.1" 200 OK
```

Notice: **200 OK** instead of **404 Not Found**

## 🆘 Still Not Working?

If you've tried everything above and still get 404:

1. **Share the output of**:
   ```bash
   cd backend
   python check_backend.py
   ```

2. **Check if this file exists**:
   ```bash
   ls -la app/api/floor_plan.py
   ```

3. **Try importing manually**:
   ```bash
   python -c "from app.api import floor_plan; print('SUCCESS')"
   ```

4. **Check Python version**:
   ```bash
   python --version
   ```
   Should be Python 3.10 or higher.

## 💡 Pro Tips

1. **Always use `-m` flag**: `python -m uvicorn` ensures proper module resolution
2. **Full restart is better**: Don't rely on `--reload` for major changes
3. **Check docs first**: http://localhost:8000/docs shows all registered routes
4. **Use check_backend.py**: It diagnoses 90% of issues automatically

## ✅ Success Criteria

You know it's fixed when:
1. ✅ `python check_backend.py` shows floor-plan routes
2. ✅ http://localhost:8000/docs shows floor-plan endpoints
3. ✅ Uploading PDF returns **200 OK** not **404 Not Found**
4. ✅ Frontend shows floor plan selection UI

---

**TL;DR**: Stop backend (Ctrl+C), run `pip install pdf2image easyocr google-genai`, restart with `python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

