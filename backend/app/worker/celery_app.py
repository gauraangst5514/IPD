"""
Celery Application Configuration

Worker that processes ML tasks asynchronously.

Start with:
    celery -A app.worker.celery_app worker --loglevel=info --pool=solo
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "intelliclaim",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    broker_connection_timeout=5,
    task_publish_retry=False,
    task_time_limit=2100,  # Bounded 12-image processing run
    task_soft_time_limit=2040,
    worker_prefetch_multiplier=1,  # One task at a time (ML is memory-heavy)
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.worker"])
