"""Index existing stored claim images through the running ML service.

Run from the repo root: PYTHONPATH=backend:. python scripts/backfill_image_history.py
Uses existing backend DB/storage settings. Safe to repeat; does not change claim
decisions or manufacture fraud labels. First-seen time is index time on backfill.
"""
import asyncio
import httpx
from sqlalchemy import select
from app.core.database import async_session
from app.core.config import get_settings
from app.models.claim import ClaimImage
from app.services.storage import get_storage_service


async def main():
    storage = get_storage_service()
    count = 0
    failures = 0
    async with async_session() as db, httpx.AsyncClient(timeout=120) as client:
        result = await db.execute(select(ClaimImage).order_by(ClaimImage.uploaded_at, ClaimImage.id))
        for image in result.scalars():
            try:
                content = await asyncio.to_thread(storage.download_image, image.original_url)
                response = await client.post(
                    get_settings().ML_SERVICE_URL + "/forensics",
                    files={"file": ("image", content, "application/octet-stream")},
                    data={"claim_id": str(image.claim_id), "image_id": str(image.id)},
                )
                response.raise_for_status()
                if response.json()["duplicate_check"]["status"] != "checked":
                    raise RuntimeError("Image history check was unavailable")
                count += 1
            except Exception as error:
                failures += 1
                print(f"Failed image {image.id}: {type(error).__name__}")
    print(f"Indexed {count} images; {failures} failed. Existing claim decisions were not changed.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
