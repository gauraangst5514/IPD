"""Durable gallery and vectors with process-local file/model caches only."""
import hashlib
import json
from pathlib import Path
import numpy as np
from ml.retrieval.engine import RetrievalEngine
from ml.image_input import open_upload
from ml.postgres import connection

class PostgresRetrievalEngine(RetrievalEngine):
    def __init__(self,gallery):
        super().__init__(gallery)
        with connection() as db,db.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS ml_retrieval_gallery (
                digest TEXT PRIMARY KEY,image_id TEXT NOT NULL,embedding TEXT NOT NULL,
                vector JSONB NOT NULL,content BYTEA NOT NULL,created_at TIMESTAMPTZ DEFAULT now())''')

    def _load_gallery(self):
        self.gallery.mkdir(parents=True,exist_ok=True)
        self.records=[];self.vectors=None;self.seen_hashes=set()

    def load(self):
        super().load()
        self._refresh()

    def _refresh(self):
        with connection() as db,db.cursor() as cur:
            cur.execute('SELECT digest,image_id,vector FROM ml_retrieval_gallery WHERE embedding=%s ORDER BY digest',(self.embedding_name,))
            rows=cur.fetchall();records=[];vectors=[];digests=set()
            for digest,name,vector in rows:
                path=self.gallery/name
                if not path.is_file():
                    cur.execute('SELECT content FROM ml_retrieval_gallery WHERE digest=%s',(digest,))
                    content=bytes(cur.fetchone()[0])
                    if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('Stored image integrity failed')
                    path.write_bytes(content)
                records.append(path);vectors.append(vector);digests.add(digest)
        self.records=records;self.vectors=np.array(vectors,dtype=np.float32) if vectors else None;self.seen_hashes=digests

    def search(self,content,k=5):
        with self.lock:
            if self.model is None:self.load()
            else:self._refresh()
            return super().search(content,k)

    def add_image(self,content,identifier=None):
        with self.lock:
            with open_upload(content) as source:
                ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}[source.format];source.verify()
            with open_upload(content) as source:image=source.convert('RGB')
            if self.model is None:self.load()
            digest=hashlib.sha256(content).hexdigest();name=digest+ext
            with connection() as db,db.cursor() as cur:
                # Serialize same-gallery writes: encode failures cannot publish partial rows.
                cur.execute('SELECT pg_advisory_xact_lock(%s)',(172904114,))
                cur.execute('SELECT image_id FROM ml_retrieval_gallery WHERE digest=%s',(digest,));existing=cur.fetchone()
                added=existing is None
                if added:
                    vector=self.encode(image)
                    cur.execute('INSERT INTO ml_retrieval_gallery(digest,image_id,embedding,vector,content) VALUES(%s,%s,%s,%s,%s)',
                        (digest,name,self.embedding_name,json.dumps(vector.tolist()),content))
                else:name=existing[0]
            self._refresh()
            return {'added':added,'reason':None if added else 'duplicate_image','image_id':name,'gallery_size':len(self.records),'embedding':self.embedding_name}

    def stats(self):
        with connection() as db,db.cursor() as cur:
            cur.execute('SELECT count(*) FROM ml_retrieval_gallery');count=cur.fetchone()[0]
        return {'gallery_size':count,'embedding':self.embedding_name if self.model is not None else None,
            'model_loaded':self.model is not None,'gallery_path':'postgresql:ml_retrieval_gallery','persistence':'postgresql'}
