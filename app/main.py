"""
FastAPI SaaS Backend Application
Main application entry point with route registration and middleware setup
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import uvicorn

# Core imports
from app.core.config import settings
from app.core.db import init_db, close_db

# Middleware imports
from app.middlewares.auth_middleware import AuthMiddleware

# Route imports
from app.modules.auth.routes import router as auth_router
from app.modules.users.routes import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    print("🚀 Starting FastAPI application...")
    print(f"📝 App Name: {settings.APP_NAME}")
    print(f"🔖 Version: {settings.APP_VERSION}")
    print(f"🔧 Debug Mode: {settings.DEBUG}")
    
    # Initialize database (uncomment if not using Alembic)
    # await init_db()
    print("✅ Database initialized")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down FastAPI application...")
    await close_db()
    print("✅ Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready FastAPI backend for SaaS applications with modular architecture",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)


# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================

# CORS Middleware - Configure allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Custom Auth Middleware - JWT verification
# NOTE: Add this after setting up routes that should be public
app.add_middleware(AuthMiddleware)


# ============================================================================
# EXCEPTION HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for unhandled exceptions
    Returns standardized error response
    """
    print(f"❌ Unhandled exception: {exc}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "data": {
                "detail": str(exc) if settings.DEBUG else "An unexpected error occurred"
            }
        }
    )


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

# Health check endpoint (public)
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify API is running
    Returns service status and version
    """
    return {
        "success": True,
        "message": "Service is healthy",
        "data": {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "ok"
        }
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information
    """
    return {
        "success": True,
        "message": "Welcome to FastAPI SaaS Chat bot Backend",
        "data": {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health"
        }
    }


# Include module routers
app.include_router(auth_router)      # /auth/*
app.include_router(users_router)     # /users/*

# Add more module routers here as your application grows
# Example:
# from app.modules.client.routes import router as client_router
# app.include_router(client_router)  # /client/*


# ============================================================================
# APPLICATION RUNNER
# ============================================================================

if __name__ == "__main__":
    """
    Run application directly with uvicorn
    For production, use: uvicorn app.main:app --host 0.0.0.0 --port 8000
    """
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
