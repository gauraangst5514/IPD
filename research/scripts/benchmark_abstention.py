"""Fixed validation threshold; simulated no-match galleries remove entire identity."""
import pathlib,json,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[2];out=ROOT/'research/results'
ids=np.array(sorted(set(np.load(out/'generali_osnet_embeddings.npz')['labels'])))
np.random.default_rng(42).shuffle(ids);val=set(ids[:10]);test=set(ids[10:]);results={}
for encoder in ['resnet18','osnet']:
 c=np.load(out/f'generali_{encoder}_embeddings.npz');v=c['vectors'];labels=c['labels'];names=c['names'];rows=[]
 for split,allowed in [('validation',val),('test',test)]:
  indices=np.flatnonzero(np.isin(labels,list(allowed)))
  for i in indices:
   gallery=indices[indices!=i];scores=v[gallery]@v[i];same=labels[gallery]==labels[i]
   if not same.any() or same.all():continue
   winner=np.argmax(scores)
   rows.append({'split':split,'query':str(names[i]),'identity':str(labels[i]),'top_score':float(scores[winner]),'top_correct':bool(same[winner]),'no_match_top_score':float(scores[~same].max())})
 vr=[r for r in rows if r['split']=='validation'];tr=[r for r in rows if r['split']=='test']
 threshold=float(np.quantile([r['no_match_top_score'] for r in vr],.95))
 accepted=[r for r in tr if r['top_score']>threshold]
 results[encoder]={'threshold':threshold,'validation_queries':len(vr),'test_queries':len(tr),
 'test_match_coverage':len(accepted)/len(tr),'test_precision_among_accepted':float(np.mean([r['top_correct'] for r in accepted])) if accepted else None,
 'test_correct_accepted_fraction':float(np.mean([r['top_correct'] and r['top_score']>threshold for r in tr])),
 'test_no_match_false_alert_rate':float(np.mean([r['no_match_top_score']>threshold for r in tr])), 'rows':rows}
report={'protocol':'disjoint 10 validation /29 test identities; full split-specific galleries; no-match removes all same-identity images; threshold validation 95th percentile impostor maximum; strict greater-than',
 'limitations':['Small dependent queries within identities','No independent external corpus','No probability calibration','Threshold is gallery-size dependent','No guarantee of 5% test false alerts'], 'encoders':results}
(out/'abstention_evaluation.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:{a:b for a,b in v.items() if a!='rows'} for k,v in results.items()},indent=2))
