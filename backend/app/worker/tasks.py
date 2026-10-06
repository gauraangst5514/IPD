"""Broker deliveries refer to durable attempt IDs, never mutable claim IDs."""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.core.config import get_settings
from app.worker.celery_app import celery_app
from app.services.processing_jobs import run_attempt


async def _process_attempt_async(attempt_id):
    # A Celery invocation owns its event loop and connections. Never reuse an
    # asyncpg connection pooled by a previous asyncio.run or a parent process.
    engine = create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        return await run_attempt(attempt_id, factory)
    finally:
        await engine.dispose()


@celery_app.task(name='process_attempt', acks_late=True, reject_on_worker_lost=True)
def process_claim_task(attempt_id):
    return asyncio.run(_process_attempt_async(attempt_id))
