from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered vehicle damage assessment and fraud detection for insurance claims",
    redirect_slashes=False,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(api_router)

# Serve uploaded images locally (dev without MinIO)
uploads_dir = Path(settings.UPLOADS_DIR)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.on_event("startup")
async def startup_event():
    # Create DB tables (for dev without Alembic migrations)
    from app.core.database import create_tables
    from app.models import User, Claim, ClaimImage, ClaimAssessment, Vehicle, FraudFlag  # noqa: F401
    await create_tables()
    print(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting...")


@app.on_event("shutdown")
async def shutdown_event():
    print(f"👋 {settings.APP_NAME} shutting down...")
