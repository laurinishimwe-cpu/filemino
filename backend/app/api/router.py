from fastapi import APIRouter

from app.api.routes import health, images, jobs, uploads, videos

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(uploads.router, prefix="/uploads", tags=["uploads"])
