"""Identity-separated validation/test reranking; cached frozen embeddings.
Not the author protocol; filename identity semantics remain an assumption.
"""
import pathlib,sys,json,time
import numpy as np
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ml.retrieval.engine import RetrievalEngine
cache=np.load(ROOT/'research/results/generali_resnet18_embeddings.npz')
names=cache['names']; labels=cache['labels'];vectors=cache['vectors']
folder=ROOT/'data/raw/generali/extracted/paper/test_papers_2.1.0_for_repo'
identities=np.array(sorted(set(labels)));np.random.default_rng(42).shuffle(identities)
validation=set(identities[:10]);test=set(identities[10:]);engine=RetrievalEngine(folder)
similarities=vectors@vectors.T;np.fill_diagonal(similarities,-np.inf)
rows=[];start=time.perf_counter()
# Two deterministic queries per identity. Gallery limited to the same partition.
for identity in identities:
 split='validation' if identity in validation else 'test'
 allowed=validation if split=='validation' else test
 gallery=np.flatnonzero(np.isin(labels,list(allowed)))
 for i in np.flatnonzero(labels==identity)[:2]:
  order=gallery[np.argsort(-similarities[i,gallery])];order=order[order!=i]
  q=Image.open(folder/str(names[i])).convert('RGB'); candidates=[]
  for j in order[:5]:
   c=Image.open(folder/str(names[j])).convert('RGB');v=engine.verify(q,c)
   candidates.append({'image':str(names[j]),'identity':str(labels[j]),'cosine':float(similarities[i,j]),
                      'inliers':v.get('inliers',0),'matches':v['matches']})
  rows.append({'query':str(names[i]),'identity':str(identity),'split':split,'candidates':candidates})
 print(split,str(identity),'queries',len(rows),flush=True)
 # Checkpoint incrementally for recoverability.
 (ROOT/'research/results/reranking_progress.json').write_text(json.dumps({'rows':rows},indent=2))
def metric(rs,alpha):
 wins=[];rr=[]
 for row in rs:
  ordered=sorted(row['candidates'],key=lambda c:c['cosine']+alpha*np.log1p(c['inliers'])/np.log(101),reverse=True)
  relevant=[i+1 for i,c in enumerate(ordered) if c['identity']==row['identity']]
  wins.append(bool(relevant and relevant[0]==1));rr.append(1/relevant[0] if relevant else 0)
 return {'queries':len(rs),'recall_at_1':float(np.mean(wins)),'truncated_mrr_at_5':float(np.mean(rr))}
vr=[r for r in rows if r['split']=='validation'];tr=[r for r in rows if r['split']=='test']
alphas=[0.,.025,.05,.1,.2,.4]
chosen=max(alphas,key=lambda a:metric(vr,a)['recall_at_1'])
baseline=metric(tr,0);reranked=metric(tr,chosen)
rng=np.random.default_rng(123);deltas=[]
for _ in range(1000):
 sampled=rng.choice(list(test),len(test),replace=True)
 rs=[r for ident in sampled for r in tr if r['identity']==ident]
 deltas.append(metric(rs,chosen)['recall_at_1']-metric(rs,0)['recall_at_1'])
report={'method':'cosine + alpha * log1p(SIFT_RANSAC_inliers)/log(101)',
 'protocol':'2 queries per filename identity; top5 reranking; disjoint validation and test identity galleries',
 'validation_identities':sorted(validation),'test_identities':sorted(test),
 'alpha_validation_scores':{str(a):metric(vr,a) for a in alphas},'selected_alpha':chosen,
 'test_baseline':baseline,'test_reranked':reranked,
 'identity_bootstrap_delta_recall1_95_interval':np.quantile(deltas,[.025,.975]).tolist(),
 'elapsed_seconds':time.perf_counter()-start,
 'limitations':['Filename identities not independently verified','Small sample: two queries per identity','General local features, not damage-specific','No fraud labels','Not comparable to full-gallery earlier baseline','No no-match queries'], 'rows':rows}
(ROOT/'research/results/reranking_evaluation.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
