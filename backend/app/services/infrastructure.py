"""Live infrastructure probes; declarations and model files are not readiness."""
import asyncio
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text, select, func
from app.core.config import get_settings
from app.services.ml_client import get_ml_client
from app.models.graph_projection import GraphProjection

async def infrastructure_status(db):
    settings=get_settings()
    services={}
    try:
        await db.execute(text("SELECT 1"))
        services["database"]={"status":"healthy","backend":"sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql"}
    except Exception:
        services["database"]={"status":"unreachable"}
    async def storage():
        try:
            from app.services.storage import get_storage_service
            service=await run_in_threadpool(get_storage_service)
            if hasattr(service,"health"):
                return await run_in_threadpool(service.health)
            if service.use_local:
                return {"status":"healthy","backend":"local"}
            await run_in_threadpool(service.client.head_bucket,Bucket=service.bucket)
            return {"status":"healthy","backend":"minio_s3"}
        except Exception:return {"status":"unreachable","backend":settings.STORAGE_BACKEND}
    async def redis():
        if settings.PROCESSING_MODE!="celery":return {"status":"not_configured","mode":"inline"}
        client=None
        try:
            from redis.asyncio import from_url
            client=from_url(settings.REDIS_URL,socket_connect_timeout=2,socket_timeout=2)
            await client.ping()
            return {"status":"healthy","backend":"redis"}
        except Exception:return {"status":"unreachable","backend":"redis"}
        finally:
            if client:await client.aclose()
    async def workers():
        if settings.PROCESSING_MODE!="celery":return {"status":"not_configured"}
        try:
            from app.worker.celery_app import celery_app
            result=await run_in_threadpool(lambda:celery_app.control.inspect(timeout=2).ping())
            return {"status":"healthy" if result else "unreachable","count":len(result or {})}
        except Exception:return {"status":"unreachable","count":0}
    async def neo4j():
        if settings.GRAPH_BACKEND!="neo4j":return {"status":"not_configured","backend":"sql"}
        try:
            from app.services.graph_projection import Neo4jProjection
            return await Neo4jProjection().health()
        except Exception:return {"status":"unreachable","backend":"neo4j"}
    results=await asyncio.gather(storage(),redis(),workers(),neo4j(),get_ml_client().health_check())
    for key,value in zip(["storage","redis","workers","graph","ml"],results):services[key]=value
    pending=None
    if services["database"]["status"]=="healthy":
        pending=(await db.execute(select(func.count()).select_from(GraphProjection)
                                 .where(GraphProjection.applied_at.is_(None)))).scalar() or 0
    services["graph"]["pending_projections"]=pending
    if pending and settings.GRAPH_BACKEND=="neo4j" and services["graph"]["status"]=="healthy":
        services["graph"]["status"]="pending_sync"
    healthy=all(value.get("status") in {"healthy","not_configured"} for value in services.values())
    return {"status":"healthy" if healthy else "degraded","services":services,
            "mode":{"processing":settings.PROCESSING_MODE,"graph":settings.GRAPH_BACKEND,"storage":settings.STORAGE_BACKEND}}
