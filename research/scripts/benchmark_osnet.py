"""Independent leave-one-out retrieval; NOT reproduction of authors' protocol."""
import hashlib,json,pathlib,time
import numpy as np
import torch
from PIL import Image
from torchvision.models import ResNet18_Weights
import sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[2]))
from ml.retrieval.osnet_ain_arch import osnet_ain_x1_0
from torchvision import transforms
ROOT=pathlib.Path(__file__).resolve().parents[2]
def main():
 torch.set_num_threads(4)
 folder=ROOT/'data/raw/generali/extracted/paper/test_papers_2.1.0_for_repo'
 import sys
 sys.path.insert(0,str(ROOT))
 from research.data_access import generali_test_paths
 paths=generali_test_paths(); seen=set(); unique=[]
 for p in paths:
  digest=hashlib.sha256(p.read_bytes()).hexdigest()
  if digest not in seen: unique.append(p);seen.add(digest)
 paths=unique
 if not paths: raise SystemExit('No Generali test images')
 labels=np.array([p.stem.split('_')[0] for p in paths])
 weights=ResNet18_Weights.DEFAULT
 checkpoint=pathlib.Path(torch.hub.get_dir())/'checkpoints'/pathlib.Path(weights.url).name
 if not checkpoint.exists():raise SystemExit('Provision pretrained ResNet18 weights first')
 model=osnet_ain_x1_0(num_classes=10415,pretrained=False).eval()
 state=torch.load(ROOT/'ml/weights/osnet_similarity_state.pt',map_location='cpu',weights_only=True)
 model.load_state_dict(state,strict=True)
 transform=transforms.Compose([transforms.Resize((256,128)),transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
 vectors=[];start=time.perf_counter()
 with torch.inference_mode():
  for i in range(0,len(paths),16):
   batch=torch.stack([transform(Image.open(p).convert('RGB')) for p in paths[i:i+16]])
   v=model(batch);v=torch.nn.functional.normalize(v,dim=1);vectors.append(v.numpy())
   print(f'Encoded {min(i+16,len(paths))}/{len(paths)}',flush=True)
 vectors=np.concatenate(vectors);scores=vectors@vectors.T;np.fill_diagonal(scores,-np.inf)
 rows=[]
 for i in range(len(paths)):
  order=np.argsort(-scores[i]);order=order[order!=i];rel=labels[order]==labels[i]
  positives=int(rel.sum())
  if not positives:continue
  positions=np.flatnonzero(rel);ap=float(np.mean(np.arange(1,positives+1)/(positions+1)))
  rows.append({'query':paths[i].name,'identity':labels[i],'recall1':bool(rel[0]),'recall5':bool(rel[:5].any()),'ap':ap,
               'top5':[paths[j].name for j in order[:5]]})
 report={'model':'Generali pretrained OSNet-AIN x1.0; strict state match; 256x128 ImageNet normalization, author preprocessing not yet reproduced','protocol':'leave-one-out within downloaded test subset; self and exact duplicates excluded',
         'label_assumption':'filename prefix is identity; pending author-protocol confirmation',
         'images':len(paths),'identities':len(set(labels)),'eligible_queries':len(rows),
         'recall_at_1':float(np.mean([r['recall1'] for r in rows])), 'recall_at_5':float(np.mean([r['recall5'] for r in rows])),
         'map':float(np.mean([r['ap'] for r in rows])),'elapsed_seconds':time.perf_counter()-start,
         'limitations':['Not authors protocol reproduction','No target-domain training','Filename labels not independently verified','Same-vehicle/background shortcuts possible','No no-match decision evaluated'], 'queries':rows}
 out=ROOT/'research/results';out.mkdir(exist_ok=True)
 (out/'generali_osnet.json').write_text(json.dumps(report,indent=2));np.savez(out/'generali_osnet_embeddings.npz',vectors=vectors,names=np.array([p.name for p in paths]),labels=labels)
 print(json.dumps({k:v for k,v in report.items() if k!='queries'},indent=2))
if __name__=='__main__':main()
