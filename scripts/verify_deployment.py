"""Bounded live release checks; writes no credentials or bearer tokens."""
import argparse
import concurrent.futures
import json
import time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('url');args=parser.parse_args()
    base=args.url.rstrip('/');accounts=json.loads((ROOT/'var/production_accounts.json').read_text())
    report={'base_url':base,'checks':{}}
    with httpx.Client(trust_env=False,timeout=300) as client:
        for path in ('/','/retrieval','/api/v1/health'):
            r=client.get(base+path);r.raise_for_status();report['checks'][path]=r.status_code
        def login(role):
            a=accounts[role];r=client.post(base+'/api/v1/auth/login',data={'username':a['email'],'password':a['password']});r.raise_for_status()
            return {'Authorization':'Bearer '+r.json()['access_token']}
        claimant=login('claimant');assessor=login('assessor')
        caps=client.get(base+'/api/v1/capabilities',headers=assessor);caps.raise_for_status();caps=caps.json()
        for key in ('damage_detection','vehicle_make','plate_reader','tamper_detection','damage_reidentification'):
            assert caps['components'][key]['available'],(key,caps['components'][key])
        report['capabilities']={k:v for k,v in caps['components'].items() if k in ('vehicle_make','plate_reader','tamper_detection','damage_reidentification')}
        for role,headers,expected in [('anonymous',{},401),('claimant',claimant,403)]:
            for endpoint in ('/api/v1/intelligence/retrieval/stats','/api/v1/intelligence/retrieval/gallery/add'):
                r=client.post(base+endpoint,headers=headers,files={'file':('bad.png',b'bad','image/png')}) if endpoint.endswith('/add') else client.get(base+endpoint,headers=headers)
                assert r.status_code==expected,(role,endpoint,r.status_code)
                report['checks'][role+':'+endpoint]=r.status_code
        r=client.post(base+'/api/v1/auth/register',json={'email':'forbidden-role-test@intelliclaim.test','password':'not-a-real-account','full_name':'Synthetic test','role':'admin'})
        assert r.status_code==422,r.text;report['checks']['public_role_escalation_denied']=True
        r=client.post(base+'/api/v1/intelligence/retrieval/gallery/add',headers=assessor,files={'file':('invalid.png',b'invalid','image/png')})
        assert r.status_code==422,r.status_code;report['checks']['invalid_upload_rejected']=True
        infra=client.get(base+'/api/v1/infrastructure',headers=assessor);infra.raise_for_status();report['infrastructure']=infra.json()
        assert report['infrastructure']['services']['database']['status']=='healthy'
        assert report['infrastructure']['services']['storage']['status']=='healthy'
    def probe(_):
        started=time.perf_counter()
        with httpx.Client(trust_env=False,timeout=30) as c:
            r=c.get(base+'/api/v1/health');r.raise_for_status()
        return time.perf_counter()-started
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:latencies=list(pool.map(probe,range(20)))
    latencies.sort();report['bounded_health_load']={'requests':20,'concurrency':4,'failures':0,'p95_seconds':latencies[18],
        'scope':'Small health-endpoint concurrency probe; does not establish peak inference capacity or a production security audit'}
    (ROOT/'research/results/deployment_verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':main()
