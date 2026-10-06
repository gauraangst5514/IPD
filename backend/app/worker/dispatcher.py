"""Run separately from workers: python -m app.worker.dispatcher [--local]."""
import argparse
import asyncio
import logging
from sqlalchemy import select
from app.core.database import async_session, engine
from app.core.config import get_settings
from app.models.processing import ProcessingAttempt
from app.services.processing_jobs import dispatch_due, reconcile, run_attempt, now


async def main(local=False):
    try:
        while True:
            try:
                if local:
                    await reconcile(async_session)
                    async with async_session() as db:
                        ids = list(await db.scalars(select(ProcessingAttempt.id).where(
                            ProcessingAttempt.state == 'queued', ProcessingAttempt.next_run_at <= now(),
                        ).order_by(ProcessingAttempt.created_at).limit(10)))
                    for attempt_id in ids:
                        await run_attempt(attempt_id, async_session)
                else:
                    from app.worker.tasks import process_claim_task
                    await dispatch_due(async_session, process_claim_task.delay)
            except Exception:
                logging.exception('Dispatcher iteration failed; retrying')
            await asyncio.sleep(get_settings().WORKER_POLL_SECONDS)
    finally:
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true', help='Process locally without Redis/Celery')
    asyncio.run(main(parser.parse_args().local))
