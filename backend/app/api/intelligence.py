"""Assessor research workbench; no automatic fraud decisions or score fusion."""
import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.auth import require_role
from app.core.database import get_db
from app.models.claim import Claim
from app.models.claim import ClaimImage
from app.models.intelligence import ClaimIntelligence
from app.services.invoice import parse_invoice
from app.core.claim_fields import StructuredFields
from app.core.config import get_settings
from app.services.structured_assessment import assess_record
from app.services import ml_client

router = APIRouter()
assessor = require_role(["assessor", "admin"])

class InvoiceText(BaseModel):
    text: str = Field(min_length=1, max_length=50000)

async def find_claim(claim_id, db):
    try:
        key = uuid.UUID(claim_id)
    except ValueError:
        raise HTTPException(422, "Invalid claim ID")
    claim = await db.get(Claim, key)
    if not claim:
        raise HTTPException(404, "Claim not found")
    record = await db.get(ClaimIntelligence, key)
    if not record:
        record = ClaimIntelligence(claim_id=key, structured_fields={}, tabular_result={}, invoice_result={})
        db.add(record)
    return record

@router.get("/model")
async def model_status(user=Depends(assessor)):
    health=await ml_client.get_ml_client().health_check()
    components=health.get("components",{})
    return {"tabular":components.get("tabular_classifier",{"available":False}),
            "graph":components.get("graph_baseline",{"available":False})}

@router.get("/claims/{claim_id}")
async def dossier(claim_id: str, db: AsyncSession = Depends(get_db), user=Depends(assessor)):
    record = await find_claim(claim_id, db)
    return {"structured_fields": record.structured_fields, "tabular": record.tabular_result,
            "invoice": record.invoice_result}

@router.post("/claims/{claim_id}/tabular")
async def assess_tabular(claim_id: str, fields: StructuredFields,
                         db: AsyncSession = Depends(get_db), user=Depends(assessor)):
    record = await find_claim(claim_id, db)
    record.structured_fields = fields.model_dump()
    result = await assess_record(record)
    await db.flush()
    return result

@router.post("/claims/{claim_id}/invoice")
async def assess_invoice(claim_id: str, request: InvoiceText,
                         db: AsyncSession = Depends(get_db), user=Depends(assessor)):
    record = await find_claim(claim_id, db)
    result = parse_invoice(request.text)
    record.invoice_result = result
    record.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return result

@router.get("/graph")
async def graph(db: AsyncSession = Depends(get_db), user=Depends(assessor)):
    if get_settings().GRAPH_BACKEND == "neo4j":
        from app.services.graph_projection import Neo4jProjection, synchronize_pending
        state=await synchronize_pending(db)
        try:
            result=await Neo4jProjection().graph()
            result["projection"]=state
            return result
        except Exception:
            raise HTTPException(503,"Configured Neo4j graph is unavailable; SQL claims are retained")
    # Evidence graph uses real live claims; dataset garage IDs are never mixed in.
    claims = (await db.execute(select(Claim).order_by(Claim.created_at.desc()).limit(200))).scalars().all()
    nodes, edges = {}, []
    for claim in claims:
        cid = str(claim.id)
        nodes[cid] = {"id": cid, "kind": "claim", "label": cid[:8], "status": claim.status.value}
        for kind, value in [("claimant", claim.claimant_id), ("vehicle", claim.vehicle_id)]:
            key = kind + ":" + str(value)
            nodes[key] = {"id": key, "kind": kind, "label": kind + " " + str(value)[:8]}
            edges.append({"source": cid, "target": key, "relation": "same_" + kind})
        for item in (claim.fraud_flags or {}).get("_indicators", []):
            for match in item.get("evidence", {}).get("matches", []):
                target = match.get("claim_id")
                if target and target != cid:
                    edges.append({"source": cid, "target": target,
                                  "relation": match.get("match_type", "image_candidate")})
    # Limit the graph to loaded records; never fabricate reference nodes.
    edges = [edge for edge in edges if edge["target"] in nodes]
    unique = {(edge["source"], edge["target"], edge["relation"]): edge for edge in edges}
    return {"nodes": list(nodes.values()), "edges": list(unique.values()),
            "limit": 200, "backend": "sql", "warning": "Shared entities and image candidates support investigation; they do not establish a fraud ring.",
            "gnn": {"available": False, "reason": "Teammate graph provenance and leakage-free evaluation pending"}}


@router.post("/images/{image_id}/saliency")
async def image_saliency(image_id: str, db: AsyncSession = Depends(get_db), user=Depends(assessor)):
    import httpx
    from app.core.config import get_settings
    from app.services.storage import get_storage_service
    try:
        key = uuid.UUID(image_id)
    except ValueError:
        raise HTTPException(422, "Invalid image ID")
    image = await db.get(ClaimImage, key)
    if not image:
        raise HTTPException(404, "Image not found")
    content = await run_in_threadpool(get_storage_service().download_image, image.original_url)
    try:
        return await ml_client.get_ml_client().explain_image(content)
    except httpx.HTTPError:
        raise HTTPException(503, "Saliency service unavailable; verify the damage model and retry")


@router.post("/graph/rebuild")
async def rebuild_graph(db: AsyncSession = Depends(get_db), user=Depends(require_role(["admin"]))):
    if get_settings().GRAPH_BACKEND != "neo4j":
        raise HTTPException(409,"Neo4j graph backend is not configured")
    from app.services.graph_projection import enqueue_claim, synchronize_pending
    claims=(await db.execute(select(Claim))).scalars().all()
    for claim in claims:
        await enqueue_claim(claim,db)
    await db.commit()
    return await synchronize_pending(db)

@router.post("/retrieval/search")
async def search_photographs(file: UploadFile = File(...), k: int = Form(3), user=Depends(assessor)):
    import httpx
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Images must be 10 MB or smaller")
    if not 1 <= k <= 20:
        raise HTTPException(422, "k must be between 1 and 20")
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=240) as client:
            response = await client.post(
                f"{get_settings().ML_SERVICE_URL}/retrieval/search",
                files={"file": ("query.jpg", data, file.content_type or "image/jpeg")}, data={"k": str(k)})
        if response.status_code != 200:
            raise HTTPException(503, "Retrieval service unavailable; check model provisioning and gallery configuration")
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(503, "Retrieval service unavailable")


@router.get("/retrieval/stats")
async def retrieval_stats(user=Depends(assessor)):
    import httpx
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=15) as client:
            response = await client.get(f"{get_settings().ML_SERVICE_URL}/retrieval/stats")
        if response.status_code != 200:
            raise HTTPException(503, "Retrieval service unavailable")
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(503, "Retrieval service unavailable")


@router.post("/retrieval/gallery/add")
async def add_gallery_photo(
    file: UploadFile = File(None),
    claim_image_id: str = Form(None),
    db: AsyncSession = Depends(get_db),
    user=Depends(assessor),
):
    import httpx
    from app.services.storage import get_storage_service
    image_bytes = None
    filename = None
    content_type = "image/jpeg"

    if file is not None and claim_image_id:
        raise HTTPException(422, "Provide either file or claim_image_id, not both")
    if claim_image_id:
        try:
            key = uuid.UUID(claim_image_id)
        except ValueError:
            raise HTTPException(422, "Invalid claim image ID")
        claim_image = await db.get(ClaimImage, key)
        if not claim_image:
            raise HTTPException(404, "Claim image not found")
        image_bytes = await run_in_threadpool(get_storage_service().download_image, claim_image.original_url)
        filename = f"claim_{str(claim_image.claim_id)[:8]}_{str(claim_image.id)[:8]}.jpg"
    elif file is not None:
        image_bytes = await file.read(10 * 1024 * 1024 + 1)
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(413, "Images must be 10 MB or smaller")
        filename = file.filename or "uploaded.jpg"
        content_type = file.content_type or "image/jpeg"
    else:
        raise HTTPException(422, "Either file or claim_image_id must be provided")

    try:
        async with httpx.AsyncClient(trust_env=False, timeout=120) as client:
            response = await client.post(
                f"{get_settings().ML_SERVICE_URL}/retrieval/gallery/add",
                files={"file": (filename, image_bytes, content_type)},
                data={"image_id": filename},
            )
        if response.status_code in (413, 422):
            raise HTTPException(response.status_code, response.json().get("detail", "Invalid image"))
        if response.status_code != 200:
            raise HTTPException(503, "Retrieval gallery update failed")
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(503, "Retrieval service unavailable")


@router.post('/images/{image_id}/evidence')
async def inspect_photo_evidence(image_id: str, db: AsyncSession = Depends(get_db), user=Depends(assessor)):
    import httpx
    from app.models.vehicle import Vehicle
    from app.services.storage import get_storage_service
    try:
        key=uuid.UUID(image_id)
    except ValueError:
        raise HTTPException(422,'Invalid image ID')
    image=await db.get(ClaimImage,key)
    if not image:raise HTTPException(404,'Image not found')
    claim=await db.get(Claim,image.claim_id)
    vehicle=await db.get(Vehicle,claim.vehicle_id)
    content=await run_in_threadpool(get_storage_service().download_image,image.original_url)
    try:
        async with httpx.AsyncClient(trust_env=False,timeout=240) as client:
            response=await client.post(get_settings().ML_SERVICE_URL+'/evidence/inspect',
                files={'file':('claim.jpg',content,'image/jpeg')},
                data={'vehicle_make':vehicle.make,'registration_number':vehicle.registration_number})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(503,'Photograph evidence service unavailable')
