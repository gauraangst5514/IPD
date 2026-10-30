import json,pathlib,numpy as np
p=pathlib.Path(__file__).resolve().parents[2]/'research/results'
a=json.loads((p/'generali_resnet18.json').read_text());b=json.loads((p/'generali_osnet.json').read_text())
aa={r['query']:r for r in a['queries']};bb={r['query']:r for r in b['queries']};assert aa.keys()==bb.keys()
ids=sorted({r['identity'] for r in bb.values()});groups={i:[q for q in bb if bb[q]['identity']==i] for i in ids}
rng=np.random.default_rng(42);rows=[]
for _ in range(2000):
 qs=[q for i in rng.choice(ids,len(ids),replace=True) for q in groups[i]]
 rows.append([np.mean([float(bb[q]['recall1'])-float(aa[q]['recall1']) for q in qs]),np.mean([bb[q]['ap']-aa[q]['ap'] for q in qs])])
r={'scope':'Paired comparison on identical 420-photo leave-one-out protocol','delta_recall_at_1':b['recall_at_1']-a['recall_at_1'],'delta_map':b['map']-a['map'],'identity_cluster_bootstrap_95_intervals':np.quantile(rows,[.025,.975],axis=0).tolist(),'note':'Sampling uncertainty only. No novelty claim or proof of absence of pretrained-model training overlap. OSNet is prior work.'}
(p/'osnet_vs_resnet.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
