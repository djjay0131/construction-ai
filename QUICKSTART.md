# 🚀 QUICK START - Construction AI Floor Plan Analysis

## Copy-Paste Commands for Ubuntu/Linux

### Step 1: Install System Dependencies
```bash
sudo apt update && sudo apt install -y \
    build-essential git wget curl pkg-config \
    poppler-utils tesseract-ocr libtesseract-dev \
    libleptonica-dev libgl1 libglib2.0-0 ffmpeg
```

### Step 2: Setup Conda Environment
```bash
# Create environment
conda create -n construction-ai python=3.10 -y

# Activate environment
conda activate construction-ai

# Install core packages
conda install -c conda-forge pillow scipy opencv numpy -y

# Install PyTorch (choose one based on your hardware)
# For GPU with CUDA 11.8:
conda install -c pytorch -c nvidia pytorch torchvision pytorch-cuda=11.8 -y

# OR for CPU only:
# conda install -c pytorch pytorch torchvision cpuonly -y
```

### Step 3: Install Python Packages
```bash
# Install ML packages
pip install ultralytics easyocr

# Navigate to backend and install dependencies
cd backend
pip install -r requirements.txt
```

### Step 4: Configure Environment
```bash
# Still in backend directory
cp .env.example .env

# Edit .env file
nano .env
# Add your GEMINI_API_KEY (get from https://ai.google.dev/)
# Save and exit (Ctrl+X, Y, Enter)
```

### Step 5: Make Scripts Executable
```bash
# From project root
chmod +x launch.sh
chmod +x backend/start.sh
chmod +x backend/start_server.sh
chmod +x frontend/start_dev.sh
```

### Step 6: Setup Frontend
```bash
# Install Node.js (if not installed)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
source ~/.bashrc
nvm install 18
nvm use 18

# Install dependencies
cd frontend
npm install
```

## 🎯 Running the Application

### Option 1: Automatic Launch (Recommended)
```bash
# From project root
./launch.sh
```
This will open backend and frontend in separate terminal windows.

### Option 2: Manual Launch (Two Terminals)

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

### Option 3: Direct Commands

**Terminal 1 - Backend:**
```bash
conda activate construction-ai
cd backend
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## 🌐 Access Points

Once running:
- **Frontend UI**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/api/docs
- **Health Check**: http://localhost:8000/api/health

## 🎨 Using the Application

1. Open http://localhost:5173 in your browser
2. Click **"Floor Plan Analysis"** in the navigation
3. Upload a PDF with floor plans
4. Wait for analysis (you'll see paper size, scale, detected floor plans)
5. Click on a floor plan to select it
6. Adjust confidence threshold if needed (default 0.05 is good)
7. Click **"Detect Objects"**
8. View results: numbered annotations, object counts, measurements

## 🔍 Verify Installation

### Check Backend is Running:
```bash
curl http://localhost:8000/api/health
```
Should return: `{"status":"healthy","service":"construction-ai","version":"0.1.0"}`

### Check CUDA/GPU (Optional):
```bash
python -c "import torch; print('CUDA:', torch.cuda.is_available())"
```

### Check Models Exist:
```bash
ls -la datascience/runs/yolo12xtrain_floorplan_boundary/yolo12x_floorplan_boundary_exp2/weights/best.pt
ls -la datascience/runs/yolo12xtrain/yolo12x_exp3/weights/best.pt
```

## 🐛 Common Issues

### Issue: `uvicorn: command not found`
```bash
# Solution: Use Python module
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Issue: `PDFInfoNotInstalledError`
```bash
# Solution: Install poppler
sudo apt install poppler-utils
```

### Issue: Import errors (scipy, PIL, etc.)
```bash
# Solution: Reinstall via conda-forge
conda activate construction-ai
conda install -c conda-forge numpy scipy pillow -y
pip install --upgrade easyocr
```

### Issue: `Port 8000 already in use`
```bash
# Find and kill process
sudo lsof -ti:8000 | xargs kill -9
```

### Issue: Frontend can't connect to backend
```bash
# Check backend is running
curl http://localhost:8000/api/health

# Check CORS settings in backend/app/main.py
# Verify frontend API URL in frontend/src/services/api.ts
```

## 📚 Next Steps

- Read [FLOOR_PLAN_ANALYSIS_GUIDE.md](./FLOOR_PLAN_ANALYSIS_GUIDE.md) for detailed usage
- Read [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) for technical details
- Test with sample PDFs in `data/` directory
- Explore API at http://localhost:8000/api/docs

## 🎉 You're Ready!

The application is now running. Upload a PDF and start analyzing floor plans!

**Need help?** Check the troubleshooting section above or review the detailed guides.

