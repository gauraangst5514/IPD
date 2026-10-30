"""Private Vercel Blob originals and overlays; short-lived signed app URLs."""
import hashlib
import mimetypes
import uuid
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote
from vercel.blob import sync as blob
from app.core.auth import create_access_token

class BlobStorageService:
    use_local=False
    backend='vercel_blob_private'

    def upload_image(self,file_bytes,claim_id,filename):
        ext=Path(filename or 'image.jpg').suffix.lower() or '.jpg'
        key=f'claims/{claim_id}/{uuid.uuid4().hex}{ext}'
        blob.put_blob(key,file_bytes,access='private',content_type=mimetypes.guess_type(key)[0] or 'image/jpeg')
        return {'key':key,'url':self.get_presigned_url(key),'file_hash':hashlib.sha256(file_bytes).hexdigest(),'size_bytes':len(file_bytes)}

    def upload_heatmap(self,heatmap_bytes,claim_id,image_id):
        key=f'claims/{claim_id}/heatmaps/{image_id}_annotated.png'
        blob.put_blob(key,heatmap_bytes,access='private',content_type='image/png',allow_overwrite=True)
        return key

    def get_presigned_url(self,key,expires_in=900):
        token=create_access_token({'purpose':'private_image','key':key},expires_delta=timedelta(seconds=min(expires_in,900)))
        return '/api/v1/media/'+quote(key,safe='/')+'?token='+token

    def download_image(self,key):
        return blob.get_blob(key,access='private').body

    def delete_image(self,key):
        blob.delete_blob(key)

    def health(self):
        next(blob.query_blobs(page_size=1),None)
        return {'status':'healthy','backend':self.backend}
