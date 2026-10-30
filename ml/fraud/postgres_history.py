"""Shared claim-photo evidence across independently scaled ML instances."""
from ml.postgres import connection

class PostgresImageHistory:
    def __init__(self,path=None,hamming_threshold=6):
        self.hamming_threshold=hamming_threshold
        if not 0<=hamming_threshold<=64:raise ValueError('Invalid Hamming threshold')
        with connection() as db,db.cursor() as cur:
            cur.execute('''CREATE TABLE IF NOT EXISTS ml_image_history (
                claim_id TEXT NOT NULL,image_id TEXT NOT NULL,sha256 TEXT NOT NULL,
                phash TEXT NOT NULL,dhash TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY(claim_id,sha256))''')
            cur.execute('CREATE INDEX IF NOT EXISTS ix_ml_history_sha ON ml_image_history(sha256)')

    def check_and_register(self,claim_id,image_id,sha256,phash,dhash):
        if not claim_id or not claim_id.strip():return {'status':'unavailable','reason':'claim_id_required','matches':[]}
        for value,length in ((sha256,64),(phash,16),(dhash,16)):
            if len(value)!=length or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid image hash')
        from psycopg2.extras import RealDictCursor
        with connection() as db,db.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('SELECT pg_advisory_xact_lock(%s)',(172904113,))
            cur.execute('SELECT * FROM ml_image_history WHERE claim_id != %s',(claim_id,));matches=[]
            for row in cur.fetchall():
                pd=(int(phash,16)^int(row['phash'],16)).bit_count();dd=(int(dhash,16)^int(row['dhash'],16)).bit_count()
                exact=sha256==row['sha256']
                if exact or (pd<=self.hamming_threshold and dd<=self.hamming_threshold):
                    matches.append({'claim_id':row['claim_id'],'image_id':row['image_id'],'match_type':'exact_file' if exact else 'perceptual_candidate',
                        'phash_distance':pd,'dhash_distance':dd,'first_seen_at':row['created_at'].isoformat()})
            cur.execute('INSERT INTO ml_image_history(claim_id,image_id,sha256,phash,dhash) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (claim_id,image_id or sha256,sha256,phash,dhash))
        matches.sort(key=lambda m:(m['match_type']!='exact_file',m['phash_distance']+m['dhash_distance'],m['claim_id']))
        return {'status':'checked','matches':matches}
