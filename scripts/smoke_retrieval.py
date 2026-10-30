"""Exercise the ML HTTP endpoint in process with real photographs and weights."""
import json,os,pathlib,tempfile,shutil,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['RETRIEVAL_MATCHER']='lightglue'
import torch
torch.set_num_threads(4)
from fastapi.testclient import TestClient
from ml.serve import app
source=ROOT/'data/raw/generali/extracted/paper/test_papers_2.1.0_for_repo'
paths=sorted(source.glob('*.jpg'))
if not paths:raise SystemExit('Generali images missing')
query=paths[0];identity=query.stem.split('_')[0]
positive=next(p for p in paths if p!=query and p.stem.split('_')[0]==identity)
negatives=[p for p in paths if p.stem.split('_')[0]!=identity][:8]
with tempfile.TemporaryDirectory() as folder:
 for p in [positive,*negatives]:shutil.copy2(p,folder)
 os.environ['RETRIEVAL_GALLERY']=folder
 start=time.perf_counter()
 # No lifespan: isolate retrieval from unrelated detector and database startup.
 client=TestClient(app)
 response=client.post('/retrieval/search',files={'file':(query.name,query.read_bytes(),'image/jpeg')},data={'k':'3'})
 report={'http_status':response.status_code,'query':query.name,'known_same_prefix_candidate':positive.name,
         'elapsed_seconds':time.perf_counter()-start,'response':response.json(),
         'scope':'In-process ML endpoint; real downloaded images, configured pretrained embedding encoder and LightGlue weights. Not full browser/backend workflow.'}
 out=ROOT/'research/results/retrieval_api_smoke.json';out.write_text(json.dumps(report,indent=2))
 print(json.dumps({**{k:v for k,v in report.items() if k!='response'},'candidates':[
 {'image_id':r['image_id'],'cosine_similarity':r['cosine_similarity'],'matcher':r['verification']['method'],
 'matches':r['verification']['matches']} for r in report['response'].get('candidates',[])]},indent=2))
 if response.status_code!=200:raise SystemExit(1)
