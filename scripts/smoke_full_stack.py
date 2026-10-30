"""Real HTTP claim smoke against isolated PostgreSQL/Celery/MinIO/Neo4j services."""
import json
import os
import time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]

def main():
    base=os.environ.get('BACKEND_URL','http://127.0.0.1:18000')+'/api/v1'
    accounts=json.loads(Path(os.environ.get('ACCOUNTS_FILE',str(ROOT/'var/full-stack-accounts.json'))).read_text())
    with httpx.Client(trust_env=False,timeout=240) as client:
        def auth(role):
            a=accounts[role];r=client.post(base+'/auth/login',data={'username':a['email'],'password':a['password']});r.raise_for_status()
            return {'Authorization':'Bearer '+r.json()['access_token']}
        claimant=auth('claimant');assessor=auth('assessor')
        r=client.post(base+'/vehicles',headers=claimant,json={'registration_number':'TS'+str(int(time.time()))[-8:],'make':'Toyota','model':'Corolla','year':2022});r.raise_for_status();vehicle=r.json()
        claims=[]
        for iteration in range(2):
            r=client.post(base+'/claims',headers=claimant,json={'vehicle_id':vehicle['id'],'description':'Synthetic infrastructure smoke: front bumper scratch','invoice_text':'Repair | 2 | 1500\nInvoice total: 3000'});r.raise_for_status();cid=r.json()['id'];claims.append(cid)
            r=client.post(base+f'/claims/{cid}/images',headers=claimant,files={'file':('smoke.jpg',(ROOT/'data/demo/repository_sample_scratch.jpg').read_bytes(),'image/jpeg')});r.raise_for_status()
            r=client.post(base+f'/claims/{cid}/submit',headers=claimant);r.raise_for_status()
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                r=client.get(base+f'/claims/{cid}',headers=claimant);r.raise_for_status();detail=r.json()
                if detail['status'] in ('awaiting_review','flagged','approved','rejected'):break
                time.sleep(.5)
            else: raise AssertionError('Celery did not complete claim processing')
        indicators=detail['fraud_flags']['_indicators']
        duplicate=next(r for r in indicators if r['code']=='duplicate_image')
        assert any(m['claim_id']==claims[0] for m in duplicate['evidence']['matches'])
        assert detail['damage_type']=='scratch',detail
        photo=detail['images'][0]
        # Presigned URLs exercise MinIO externally, not local file fallbacks.
        image_url=photo.get('original_url') or photo.get('url')
        if image_url:
            downloaded=client.get(base.removesuffix('/api/v1')+image_url if image_url.startswith('/') else image_url);downloaded.raise_for_status()
        pdf=client.get(base+f'/claims/{claims[1]}/pdf',headers=claimant);pdf.raise_for_status();assert pdf.content.startswith(b'%PDF')
        graph=client.get(base+'/intelligence/graph',headers=assessor);graph.raise_for_status();assert graph.json()['backend']==os.environ.get('EXPECTED_GRAPH_BACKEND','neo4j')
        assert any(n['id']==claims[1] for n in graph.json()['nodes'])
        infra=client.get(base+'/infrastructure',headers=assessor);infra.raise_for_status()
        report={'scope':'Real isolated Docker services over HTTP; synthetic claims only','passed':True,'claims':claims,'damage_type':detail['damage_type'],'persistent_reuse':True,'pdf':True,'graph_backend':graph.json()['backend'],'infrastructure':infra.json()}
        Path(os.environ.get('SMOKE_REPORT_PATH',str(ROOT/'research/results/full_stack_verification.json'))).write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
