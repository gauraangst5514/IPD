"""Serve a single private photo only with its key-scoped expiring signature."""
import mimetypes
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
from app.core.auth import decode_access_token
from app.services.storage import get_storage_service

router=APIRouter()

@router.get('/media/{key:path}')
async def private_image(key:str,token:str):
    payload=decode_access_token(token)
    if payload.get('purpose')!='private_image' or payload.get('key')!=key:
        raise HTTPException(403,'Invalid image signature')
    try:
        content=await run_in_threadpool(get_storage_service().download_image,key)
    except Exception:
        raise HTTPException(404,'Photograph unavailable')
    return Response(content,media_type=mimetypes.guess_type(key)[0] or 'application/octet-stream',
        headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})
