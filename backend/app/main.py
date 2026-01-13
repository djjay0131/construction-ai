"""
Construction AI - Material Takeoff Application
FastAPI Main Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

# Import API routers
from app.api import upload, takeoff, detection, floor_plan
from app.db.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="Construction AI API",
    description="Automated material take-off from architectural drawings",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",  # Vite dev server (alternative port)
        "http://localhost:3000",
    ],  # Vite & React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("Starting Construction AI API...")
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    # TODO: Load ML models
    logger.info("Construction AI API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down Construction AI API...")
    # TODO: Close database connections
    # TODO: Cleanup resources


@app.get("/")
async def root():
    """Root endpoint - API health check."""
    return {"message": "Construction AI API", "version": "0.1.0", "status": "running"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "construction-ai", "version": "0.1.0"}


# Exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if app.debug else "An unexpected error occurred",
        },
    )


# Include API routers
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(takeoff.router, prefix="/api/takeoff", tags=["Takeoff"])
app.include_router(detection.router, prefix="/api/detection", tags=["Object Detection"])
app.include_router(floor_plan.router, prefix="/api/floor-plan", tags=["Floor Plan Analysis"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
