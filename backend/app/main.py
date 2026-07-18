from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered vehicle damage assessment and fraud detection for insurance claims",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite + CRA
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(api_router)


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
