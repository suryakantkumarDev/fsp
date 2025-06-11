import sys
import os
from pathlib import Path
import logging
from typing import Union
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse

# Add Backend directory to Python path
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from fastapi import FastAPI, Depends, status
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from routers import auth, profile, subscription, webhook, plans, features
from middleware.verification import verify_email_required
from config import settings
from models.database import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

app = FastAPI(
    title=settings.APP_NAME,
    description="FastAPI Backend for FSP",
    version=settings.API_VERSION,
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

@app.on_event("startup")
async def startup_event():
    await init_db()
    
    # Use settings for template directory
    settings.EMAIL_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    partials_dir = settings.EMAIL_TEMPLATES_DIR / "partials"
    partials_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Application startup complete.")

# CORS middleware configuration using settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# Add response logging middleware
@app.middleware("http")
async def log_requests(request, call_next):
    response = await call_next(request)
    logger.info(f"{request.method} {request.url.path} - Status: {response.status_code}")
    return response

# Include routers with correct prefixes
app.include_router(
    auth.router, 
    prefix="/api/auth",
    tags=["Authentication"]
)
app.include_router(profile.router, prefix="/api/profile", tags=["Profile"])
app.include_router(
    subscription.router,
    prefix="/api/subscription",
    tags=["Subscription"],
    dependencies=[Depends(verify_email_required)]
)
app.include_router(webhook.router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(plans.router, prefix="/api/plans", tags=["Plans"])
app.include_router(features.router, prefix="/api/features", tags=["Features"])

@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}

# Define the frontend directory path correctly
FRONTEND_DIR = Path(BACKEND_DIR).parent / "frontend" / "dist"
STATIC_DIR = FRONTEND_DIR / "assets"

# Ensure the directory exists before mounting
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR)), name="static")
else:
    logger.warning(f"Static directory not found: {STATIC_DIR}")

@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_react_app(full_path: str):
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        logger.warning(f"Index file not found: {index_path}")
        return HTMLResponse("<h1>Frontend not built</h1><p>Please run 'npm run build' in the frontend directory.</p>")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )