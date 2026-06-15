"""
Construction AI - Material Takeoff Application
FastAPI Main Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

# Import API routers
from app.api import upload, takeoff, detection, floor_plan, models, health, catalog
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


# Knowledge Graph client + loaded specs cache (populated at startup, read-only thereafter).
# These module-level singletons let request handlers fetch the loaded specs dict in O(1)
# without going through FastAPI dependency injection for every takeoff call.
_kg_client = None
_lumber_specs_cache: dict = {}


def get_lumber_specs() -> dict:
    """Return the in-memory lumber-specs dict loaded from the KG at startup.

    Returns the empty dict when the KG isn't configured (NEO4J_URI unset) —
    consumers should fall back to ``DEFAULT_LUMBER_SPECS`` in that case.
    """
    return _lumber_specs_cache


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

    # Initialize Knowledge Graph (Sprint 2a) — only if NEO4J_URI is set.
    # Leaving NEO4J_URI empty in .env disables KG startup, which is the
    # supported posture for early dev before AuraDB is provisioned.
    from app.core.config import settings
    if settings.NEO4J_URI:
        global _kg_client, _lumber_specs_cache
        try:
            from app.core.kg.client import Neo4jClient
            from app.core.kg.loader import load_lumber_specs
            from app.core.kg.seed import seed_kg

            _kg_client = Neo4jClient(
                settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD
            )
            _kg_client.verify()
            with _kg_client.session() as s:
                seed_kg(s)
                _lumber_specs_cache = load_lumber_specs(s)
            logger.info(
                f"Knowledge Graph initialized: {len(_lumber_specs_cache)} lumber specs loaded"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Knowledge Graph: {e}")
    else:
        logger.info("NEO4J_URI empty — skipping KG startup (using DEFAULT_LUMBER_SPECS)")

    # TODO: Load ML models
    logger.info("Construction AI API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("Shutting down Construction AI API...")
    global _kg_client
    if _kg_client is not None:
        try:
            _kg_client.close()
            logger.info("Knowledge Graph driver closed")
        except Exception as e:
            logger.warning(f"Error closing Knowledge Graph driver: {e}")
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
app.include_router(models.router, prefix="/api/models", tags=["Model Management"])
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(catalog.router, prefix="/api/catalog", tags=["Catalog"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
