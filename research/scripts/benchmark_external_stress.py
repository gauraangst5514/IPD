"""External-source stress: TQVCD public examples against a frozen Generali gallery.

Exact hashes are checked for overlap. Unknown identities across sources are an
explicit assumption, so these are apparent false alerts, not validated FPR.
No raw external images are published or added to the demonstration gallery.
"""
import hashlib
import json
import os
import sys
import time
from pathlib import Path
import numpy as np
import torch
from PIL import Image
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from ml.retrieval.engine import RetrievalEngine
from research.data_access import generali_test_paths

def main():
    torch.set_num_threads(4)
    manifest=json.loads((ROOT/'research/data/tqvcd_manifest.json').read_text())
    sources=[]; seen=set()
    reference_hashes={hashlib.sha256(p.read_bytes()).hexdigest() for p in generali_test_paths()}
    overlap=[]
    for row in manifest['files']:
        path=ROOT/'data/raw/tqvcd'/row['path']
        data=path.read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if blob!=row['git_blob_sha']: raise ValueError('Altered source: '+row['path'])
        digest=hashlib.sha256(data).hexdigest()
        if digest in reference_hashes: overlap.append(row['path'])
        if digest not in seen:
            sources.append((path,digest));seen.add(digest)
    if overlap: raise ValueError('Exact overlap with reference gallery: '+str(overlap))
    fixed=json.loads((ROOT/'research/results/fixed_gallery_abstention_evaluation.json').read_text())
    report={'source':'TQVCD public repository sample','source_commit':manifest['tree_sha'],'source_url':'https://github.com/dxlabskku/TQVCD',
        'unique_external_images':len(sources),'exact_hash_overlaps':overlap,
        'interpretation':'Apparent no-match alerts under an unverified cross-source physical-identity disjointness assumption. External-source stress only; not external same-damage recognition accuracy.',
        'limitations':['No matching same-damage identity labels in the external sample','Filename/category labels do not establish physical identity','Training-corpus overlap remains unknown','No explicit raw-image redistribution license; raw images remain local','Repeated views may remain dependent after exact deduplication','Thresholds are frozen from Generali; domain exchangeability is unverified'],
        'encoders':{}}
    for encoder in ('resnet18','osnet'):
        os.environ['RETRIEVAL_ENCODER']=encoder
        engine=RetrievalEngine(ROOT/'var/external-stress-empty-gallery');engine.load()
        c=np.load(ROOT/f'research/results/generali_{encoder}_embeddings.npz')
        names=c['names'];vectors=c['vectors']
        ref=fixed['encoders'][encoder]
        indices=[int(np.flatnonzero(names==name)[0]) for name in ref['gallery_names']]
        gallery=vectors[indices];rows=[];start=time.perf_counter()
        for path,digest in sources:
            with Image.open(path) as image: vector=engine.encode(image.convert('RGB'))
            scores=gallery@vector;j=int(np.argmax(scores))
            rows.append({'query':str(path.relative_to(ROOT/'data/raw/tqvcd')),'sha256':digest,'top_score':float(scores[j]),'candidate':str(names[indices[j]])})
        points={}
        for alpha,point in ref['operating_points'].items():
            threshold=point['threshold'];alerts=sum(r['top_score']>threshold for r in rows) if threshold is not None else 0
            points[alpha]={'frozen_threshold':threshold,'apparent_alerts':alerts,'queries':len(rows),'apparent_alert_fraction':alerts/len(rows),'validated_false_positive_rate':None}
        report['encoders'][encoder]={'embedding':engine.embedding_name,'gallery_fingerprint':ref['gallery_fingerprint'],'gallery_images':len(indices),
            'elapsed_seconds':time.perf_counter()-start,'operating_points':points,'rows':rows}
    (ROOT/'research/results/external_stress_evaluation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({e:r['operating_points'] for e,r in report['encoders'].items()},indent=2))

if __name__=='__main__': main()
