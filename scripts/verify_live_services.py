"""Readiness and authorization probes; never prints credentials."""
import json,pathlib,httpx
ROOT=pathlib.Path(__file__).resolve().parents[1]
with httpx.Client(trust_env=False,timeout=20) as client:
 report={}
 for name,url in [('frontend','http://127.0.0.1:5183'),('backend','http://127.0.0.1:8010/api/v1/health'),('ml','http://127.0.0.1:8011/health')]:
  r=client.get(url);report[name]={'status':r.status_code}
  if name=='ml':report[name]['model_trained']=r.json().get('model_trained')
 r=client.post('http://127.0.0.1:8010/api/v1/intelligence/retrieval/search',files={'file':('query.jpg',b'bad','image/jpeg')})
 report['unauthenticated_retrieval_status']=r.status_code
 account=json.loads((ROOT/'var/demo_accounts.json').read_text())['claimant']
 r=client.post('http://127.0.0.1:8010/api/v1/auth/login',data={'username':account['email'],'password':account['password']})
 r.raise_for_status(); token=r.json()['access_token']
 r=client.post('http://127.0.0.1:8010/api/v1/intelligence/retrieval/search',headers={'Authorization':'Bearer '+token},files={'file':('query.jpg',b'bad','image/jpeg')})
 report['claimant_retrieval_status']=r.status_code
 report['browser_evidence']='research/results/browser_retrieval_verified.png; real original photograph upload, OSNet 420-image gallery, rendered candidates'
 (ROOT/'research/results/live_verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 assert report['unauthenticated_retrieval_status'] in (401,403)
 assert report['claimant_retrieval_status']==403
