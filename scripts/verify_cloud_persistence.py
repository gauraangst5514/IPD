"""Synthetic-only cross-instance persistence checks against a fresh cloud DB."""
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1]

def main():
    import sys
    sys.path.insert(0,str(ROOT))
    values=dotenv_values(ROOT/'var/vercel.production.env')
    os.environ['IMAGE_DATABASE_URL']=values['DATABASE_URL']
    from ml.fraud.image_history import ImageHistory
    from ml.retrieval.postgres_engine import PostgresRetrievalEngine
    from ml.postgres import connection
    digest=hashlib.sha256(b'isolated-postgres-test').hexdigest()
    ImageHistory().check_and_register('persistence-smoke-a','a',digest,'0'*16,'0'*16)
    result=ImageHistory().check_and_register('persistence-smoke-b','b',digest,'0'*16,'0'*16)
    assert any(m['claim_id']=='persistence-smoke-a' for m in result['matches'])
    stream=io.BytesIO();Image.new('RGB',(12,12),'red').save(stream,format='PNG');data=stream.getvalue()
    with tempfile.TemporaryDirectory() as directory:
        engine=PostgresRetrievalEngine(directory);engine.model=True;engine.embedding_name='synthetic_persistence_test';engine.encode=lambda image:np.array([1.,0.])
        engine.add_image(data)
        with tempfile.TemporaryDirectory() as other:
            second=PostgresRetrievalEngine(other);second.model=True;second.embedding_name=engine.embedding_name;second.encode=engine.encode;second._refresh()
            assert len(second.records)==1 and not second.add_image(data)['added']
    with connection() as db,db.cursor() as cursor:
        cursor.execute('DELETE FROM ml_retrieval_gallery WHERE digest=%s AND embedding=%s',(hashlib.sha256(data).hexdigest(),'synthetic_persistence_test'))
        cursor.execute('DELETE FROM ml_image_history WHERE claim_id IN (%s,%s)',('persistence-smoke-a','persistence-smoke-b'))
    report={'postgres_photo_history_cross_instance':True,'postgres_gallery_cross_instance':True,'duplicate_detection_after_new_instance':True,'synthetic_test_rows_removed':True}
    (ROOT/'research/results/postgres_persistence_verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
