"""
Celery Tasks

Background tasks for processing claims through the ML pipeline.
"""

import asyncio
from app.worker.celery_app import celery_app


@celery_app.task(bind=True, name="process_claim", max_retries=2)
def process_claim_task(self, claim_id: str):
    """
    Process a claim through the full ML pipeline.

    This task:
    1. Loads claim images from storage
    2. Sends each to the ML service for analysis
    3. Stores annotated images
    4. Updates the claim record with results
    5. Sets status to awaiting_review (or flagged if fraud detected)
    """
    try:
        # We need to run async code from a sync Celery task
        asyncio.run(_process_claim_async(claim_id))
    except Exception as exc:
        print(f"❌ Task failed for claim {claim_id}: {exc}")
        # Retry with exponential backoff
        self.retry(exc=exc, countdown=30 * (self.request.retries + 1))


async def _process_claim_async(claim_id: str):
    """Async wrapper for the claim processing pipeline."""
    from app.core.database import async_session
    from app.services.claim_processor import process_claim

    from app.core.database import engine
    try:
        async with async_session() as db:
            try:
                result = await process_claim(claim_id, db)
                await db.commit()
                from app.services.graph_projection import synchronize_pending
                await synchronize_pending(db)
                print(f"✅ Claim {claim_id} processed: {result}")
            except Exception:
                await db.rollback()
                raise
    finally:
        await engine.dispose()
