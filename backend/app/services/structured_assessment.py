"""All learned structured inference runs in the ML service."""
from datetime import datetime, timezone

async def assess_record(record):
    from app.services.ml_client import get_ml_client
    try:
        result=await get_ml_client().assess_structured(record.structured_fields)
    except Exception:
        result={"available":False,"reason":"ml_service_unavailable",
                "graph_baseline":{"available":False,"reason":"ml_service_unavailable"}}
    record.tabular_result=result
    record.updated_at=datetime.now(timezone.utc)
    return result
