"""Small preselected diagnostic; no tuning, no claims of reranking improvement."""
import sys,pathlib,json,time
import numpy as np
import torch
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ml.retrieval.engine import RetrievalEngine
from ml.retrieval.damage_evidence import DamageEvidence
torch.set_num_threads(4)
folder=ROOT/'data/raw/generali/extracted/paper/test_papers_2.1.0_for_repo'
cache=np.load(ROOT/'research/results/generali_resnet18_embeddings.npz')
names=cache['names']; vectors=cache['vectors'];labels=cache['labels']
engine=RetrievalEngine(folder)
# Load encoder without redundantly embedding full gallery.
from torchvision.models import resnet18,ResNet18_Weights
engine.model=resnet18(weights=ResNet18_Weights.DEFAULT).eval();engine.model.fc=torch.nn.Identity();engine.transform=ResNet18_Weights.DEFAULT.transforms()
evidence=DamageEvidence();rows=[];start=time.perf_counter()
for i in range(0,len(names),53):
 scores=vectors@vectors[i];scores[i]=-np.inf
 for j in np.argsort(-scores)[:3]:
  q=Image.open(folder/str(names[i])).convert('RGB');c=Image.open(folder/str(names[j])).convert('RGB')
  verification=engine.verify(q,c)
  item={'query':str(names[i]),'candidate':str(names[j]),'same_filename_identity':bool(labels[i]==labels[j]),'cosine':float(scores[j]),'evidence':evidence.explain(engine,q,c,verification)}
  rows.append(item);print(item['query'],item['candidate'],item['evidence'].get('damage_minus_background_drop'),flush=True)
report={'scope':'8 deterministic test queries; top3 candidates each; exploratory diagnostic, not reranking validation','matcher':'SIFT_RANSAC','elapsed_seconds':time.perf_counter()-start,'pairs':rows}
(ROOT/'research/results/damage_evidence_pilot.json').write_text(json.dumps(report,indent=2))
print('Pairs',len(rows),'with evidence',sum(r['evidence']['available'] for r in rows))
