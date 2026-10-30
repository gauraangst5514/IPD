from fastapi import APIRouter

from app.api import auth, claims, vehicles, assessments, health
from app.api import intelligence, media

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(media.router,tags=["Private images"])

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(intelligence.router, prefix="/intelligence", tags=["Investigator intelligence"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(claims.router, prefix="/claims", tags=["Claims"])
api_router.include_router(vehicles.router, prefix="/vehicles", tags=["Vehicles"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["Assessments"])
