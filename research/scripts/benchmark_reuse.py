"""Real-photo transformation retrieval. Does NOT test physical damage identity."""
import argparse, hashlib, io, json, pathlib, time
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
ROOT=pathlib.Path(__file__).resolve().parents[2]
def variants(im):
    b=io.BytesIO(); im.save(b,format='JPEG',quality=35)
    w,h=im.size
    return {'jpeg35':Image.open(b).convert('RGB'), 'brightness':ImageEnhance.Brightness(im).enhance(.65),
            'crop20':im.crop((w*.1,h*.1,w*.9,h*.9)).resize(im.size), 'mirror':ImageOps.mirror(im)}
def dhash(im):
    a=np.asarray(im.convert('L').resize((9,8)),dtype=float)
    return (a[:,1:]>a[:,:-1]).flatten().astype(float)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--resnet',action='store_true'); args=p.parse_args()
    paths=sorted((ROOT/'data/raw/tqvcd').rglob('*.jpg')); unique={}
    for path in paths: unique.setdefault(hashlib.sha256(path.read_bytes()).hexdigest(),path)
    paths=list(unique.values())
    if len(paths)<20: raise SystemExit('Need downloaded real images; run acquire_tqvcd.py')
    images=[Image.open(p).convert('RGB') for p in paths]
    methods={'dhash':dhash}
    if args.resnet:
        import torch
        from torchvision.models import resnet18, ResNet18_Weights
        torch.set_num_threads(4)
        weights=ResNet18_Weights.DEFAULT
        model=resnet18(weights=weights); model.fc=torch.nn.Identity(); model.eval()
        transform=weights.transforms()
        def embedding(im):
            with torch.inference_mode(): v=model(transform(im).unsqueeze(0)).numpy()[0]
            return v/(np.linalg.norm(v)+1e-12)
        methods['imagenet_resnet18']=embedding
    # Stable source-level partition; threshold tuning never sees test sources.
    order=np.random.default_rng(42).permutation(len(paths)); nval=max(5,len(paths)//4)
    val=set(order[:nval]); test=set(order[nval:]); results={}
    for name,encode in methods.items():
        gallery=np.stack([encode(im) for im in images]); rows=[]
        for i,im in enumerate(images):
            for kind,q in variants(im).items():
                start=time.perf_counter(); v=encode(q)
                scores=-(np.abs(gallery-v).mean(1)) if name=='dhash' else gallery@v
                rank=np.argsort(-scores); wrong=scores.copy(); wrong[i]=-np.inf
                rows.append({'source':i,'transform':kind,'rank':int(np.where(rank==i)[0][0])+1,
                             'positive_score':float(scores[i]),'negative_score':float(wrong.max()),
                             'ms':(time.perf_counter()-start)*1000})
        vr=[r for r in rows if r['source'] in val]; tr=[r for r in rows if r['source'] in test]
        threshold=float(np.quantile([r['negative_score'] for r in vr],.95))
        def metrics(rs):
            return {'queries':len(rs),'recall_at_1':float(np.mean([r['rank']==1 for r in rs])),
                    'recall_at_5':float(np.mean([r['rank']<=5 for r in rs])),
                    'mrr':float(np.mean([1/r['rank'] for r in rs])),
                    'match_recall_at_threshold':float(np.mean([r['positive_score']>threshold for r in rs])),
                    'false_alert_rate_removed_true_match':float(np.mean([r['negative_score']>threshold for r in rs])),
                    'median_query_ms':float(np.median([r['ms'] for r in rs]))}
        results[name]={'validation_selected_threshold':threshold,'test':metrics(tr),
                       'by_transform':{k:metrics([r for r in tr if r['transform']==k]) for k in variants(images[0])},'rows':rows}
    out=ROOT/'research/results'; out.mkdir(exist_ok=True)
    report={'task':'transformed-source-photo retrieval, NOT physical damage identity',
            'unique_sources':len(paths),'validation_sources':len(val),'test_sources':len(test),
            'gallery_sources':len(paths),'seed':42,'models':results,
            'limitations':['Small public sample','Synthetic transformations of real photos','No fraud labels','Near duplicates not audited','Threshold ties use strict greater-than']}
    (out/'reuse_benchmark.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:{a:b for a,b in v.items() if a!='rows'} for k,v in results.items()},indent=2))
if __name__=='__main__': main()
