from fastapi import APIRouter

from app.api.routes import health, jobs, uploads, videos

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
