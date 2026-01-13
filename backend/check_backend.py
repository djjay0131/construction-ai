#!/usr/bin/env python
"""
Backend Startup Diagnostic Script
Run this to check if all modules load correctly before starting the server
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

print("=" * 60)
print("Backend Startup Diagnostics")
print("=" * 60)
print()

# Test 1: Import main app
print("[1/6] Testing main app import...")
try:
    from app.main import app
    print("✓ Main app imported successfully")
except Exception as e:
    print(f"✗ Failed to import main app: {e}")
    sys.exit(1)

# Test 2: Check routers
print("\n[2/6] Checking API routers...")
try:
    from app.api import upload, takeoff, detection, floor_plan
    print("✓ All routers imported successfully")
    print(f"  - upload: {len(upload.router.routes)} routes")
    print(f"  - takeoff: {len(takeoff.router.routes)} routes")
    print(f"  - detection: {len(detection.router.routes)} routes")
    print(f"  - floor_plan: {len(floor_plan.router.routes)} routes")
except Exception as e:
    print(f"✗ Failed to import routers: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Check floor plan service
print("\n[3/6] Checking floor plan service...")
try:
    from app.core.cv.floor_plan_service import FloorPlanAnalysisService
    print("✓ Floor plan service imported successfully")
except Exception as e:
    print(f"✗ Failed to import floor plan service: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check models can load
print("\n[4/6] Checking YOLO models...")
try:
    from app.core.config import settings
    from ultralytics import YOLO
    
    print(f"  Boundary model path: {settings.YOLO_BOUNDARY_MODEL_PATH}")
    print(f"  Object model path: {settings.YOLO_OBJECT_MODEL_PATH}")
    
    if Path(settings.YOLO_BOUNDARY_MODEL_PATH).exists():
        print("  ✓ Boundary model file exists")
    else:
        print(f"  ✗ Boundary model NOT FOUND at {settings.YOLO_BOUNDARY_MODEL_PATH}")
    
    if Path(settings.YOLO_OBJECT_MODEL_PATH).exists():
        print("  ✓ Object model file exists")
    else:
        print(f"  ✗ Object model NOT FOUND at {settings.YOLO_OBJECT_MODEL_PATH}")
except Exception as e:
    print(f"✗ Model check failed: {e}")

# Test 5: Check dependencies
print("\n[5/6] Checking dependencies...")
dependencies = {
    'pdf2image': None,
    'easyocr': None,
    'google.genai': None,
    'ultralytics': None,
    'cv2': None,
}

for dep in dependencies:
    try:
        __import__(dep)
        print(f"  ✓ {dep}")
    except ImportError as e:
        print(f"  ✗ {dep} - NOT INSTALLED")
        dependencies[dep] = str(e)

# Test 6: List all registered routes
print("\n[6/6] Registered API routes:")
for route in app.routes:
    if hasattr(route, 'path'):
        methods = ', '.join(route.methods) if hasattr(route, 'methods') else 'N/A'
        print(f"  {methods:10} {route.path}")

print()
print("=" * 60)
print("Diagnostics Complete")
print("=" * 60)
print()

# Check for floor-plan routes
floor_plan_routes = [r for r in app.routes if hasattr(r, 'path') and '/floor-plan' in r.path]
if floor_plan_routes:
    print(f"✓ Found {len(floor_plan_routes)} floor-plan route(s)")
    for route in floor_plan_routes:
        methods = ', '.join(route.methods) if hasattr(route, 'methods') else 'N/A'
        print(f"  {methods:10} {route.path}")
else:
    print("✗ No floor-plan routes found! This is the problem.")
    print()
    print("Solution: The floor_plan router is not being registered.")
    print("This usually means:")
    print("  1. Import error in app/api/floor_plan.py")
    print("  2. Import error in app/core/cv/floor_plan_service.py")
    print("  3. The backend needs to be restarted (not just reloaded)")
    print()
    print("Try:")
    print("  1. Stop the backend (Ctrl+C)")
    print("  2. Run: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")

print()
if not any(dependencies.values()):
    print("✓ All dependencies installed")
    print("✓ Ready to start backend server!")
else:
    print("✗ Some dependencies are missing. Install them with:")
    for dep, error in dependencies.items():
        if error:
            print(f"  pip install {dep}")

