"""
CricGeo backend application.
Main application entry point with route registration and middleware setup.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.security import HTTPBearer
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
from app.modules.profiles.routes import router as profiles_router
from app.modules.locations.routes import router as locations_router


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
    description="CricGeo modular FastAPI backend",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    servers=[
        {"url": "http://localhost:8000", "description": "Local development"},
        {"url": "http://127.0.0.1:8000", "description": "Local development (IP)"},
    ],
)

# Security scheme for Swagger UI
security = HTTPBearer()


# ============================================================================
# MIDDLEWARE CONFIGURATION
# ============================================================================

# CORS Middleware - Configure allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
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
    import traceback
    
    # Print full error to console for debugging
    print(f"❌ Unhandled exception: {exc}")
    print(f"❌ Traceback: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "data": {
                "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
                "type": type(exc).__name__ if settings.DEBUG else None,
                "traceback": traceback.format_exc() if settings.DEBUG else None
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
        "message": "Welcome to CricGeo Backend",
        "data": {
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health"
        }
    }


@app.get("/sso-test", tags=["Testing"], response_class=HTMLResponse)
async def sso_test_page():
        """
        Minimal page to manually test Google SSO flow.
        """
        return """
<!doctype html>
<html lang=\"en\">
<head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
    <title>CricGeo SSO Test</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; background: #f3f6fb; margin: 0; padding: 24px; }
        .card { max-width: 760px; margin: 0 auto; background: #fff; border-radius: 14px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,.08); }
        h1 { margin-top: 0; font-size: 24px; }
        button { background: #0d6efd; color: #fff; border: 0; border-radius: 10px; padding: 12px 16px; cursor: pointer; font-size: 15px; }
        button:hover { background: #0a58ca; }
        pre { background: #0f172a; color: #e2e8f0; padding: 14px; border-radius: 10px; overflow-x: auto; }
        .muted { color: #475569; font-size: 14px; }
    </style>
</head>
<body>
    <div class=\"card\">
        <h1>Google SSO Test</h1>
        <p class=\"muted\">Click the button, sign in with Google, and you will be redirected back here with tokens.</p>
        <button id=\"loginBtn\">Login With Google</button>
        <h3>Callback Result</h3>
        <pre id=\"result\">No callback data yet.</pre>
    </div>

    <script>
        function parseHash() {
            const raw = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : window.location.hash;
            const params = new URLSearchParams(raw);
            const data = {};
            for (const [key, value] of params.entries()) data[key] = value;
            return data;
        }

        async function startGoogleLogin() {
            const redirectTo = `${window.location.protocol}//${window.location.hostname}:${window.location.port || 8000}/sso-test`;
            const url = `/auth/google/login?redirect_to=${encodeURIComponent(redirectTo)}`;
            const res = await fetch(url);
            const body = await res.json();
            if (!body.success) {
                document.getElementById('result').textContent = JSON.stringify(body, null, 2);
                return;
            }
            window.location.href = body.data.authorization_url;
        }

        document.getElementById('loginBtn').addEventListener('click', startGoogleLogin);

        const result = parseHash();
        if (Object.keys(result).length > 0) {
            document.getElementById('result').textContent = JSON.stringify(result, null, 2);
        }
    </script>
</body>
</html>
"""


# Include module routers
app.include_router(auth_router)       # /auth/*
app.include_router(users_router)      # /users/*
app.include_router(profiles_router)   # /profiles/*
app.include_router(locations_router)  # /locations/*


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
