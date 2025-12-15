"""
NIDS Backend - Main Application Entry Point
Network Intrusion Detection System
"""
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from config import settings
from logging_config import app_logger as logger
from ml.detection_engine import DetectionEngine

# Import Routers
from api.routers import auth, system, alerts, stats, ws, datasets, logs, models

# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    description="Network Intrusion Detection System - Real-time threat detection with ML/DL models",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Detection Engine
engine = DetectionEngine()
app.state.engine = engine

# Include Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_PREFIX}/auth", tags=["Authentication"])
app.include_router(system.router, prefix=f"{settings.API_V1_PREFIX}/system", tags=["System Control"])
app.include_router(alerts.router, prefix=f"{settings.API_V1_PREFIX}/alerts", tags=["Alerts"])
app.include_router(stats.router, prefix=f"{settings.API_V1_PREFIX}/stats", tags=["Statistics"])
app.include_router(datasets.router, prefix=f"{settings.API_V1_PREFIX}/datasets", tags=["Datasets"])
app.include_router(logs.router, prefix=f"{settings.API_V1_PREFIX}/logs", tags=["Logs"])
app.include_router(models.router, prefix=f"{settings.API_V1_PREFIX}/models", tags=["Models"])
app.include_router(ws.router) # WebSocket

@app.on_event("startup")
async def startup_event():
    """Application startup event"""
    logger.info("=" * 60)
    logger.info("NIDS Backend Starting...")
    logger.info(f"Project: {settings.PROJECT_NAME}")
    logger.info(f"API Prefix: {settings.API_V1_PREFIX}")
    logger.info(f"Log Level: {settings.LOG_LEVEL}")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event"""
    logger.info("NIDS Backend Shutting Down...")
    # Stop engine if running
    if app.state.engine:
        app.state.engine.stop()


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


@app.get("/")
async def root():
    """Root endpoint"""
    logger.debug("Root endpoint accessed")
    return {
        "message": "NIDS Backend API",
        "version": "1.0.0",
        "status": "running",
        "docs": f"{settings.API_V1_PREFIX}/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    engine_status = "unknown"
    if app.state.engine:
        engine_status = app.state.engine.state.value
        
    return {
        "status": "healthy",
        "engine_state": engine_status
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting NIDS Backend with uvicorn...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level=settings.LOG_LEVEL.lower()
    )
