"""Freeze one gallery; calibrate/test on separate unknown filename identities.

Reports uncertainty explicitly. Does not establish real-world identity semantics,
exchangeability, or fraud decisions. Never tunes thresholds against test data.
"""
import json
import hashlib
import sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research.abstention import upper_tail_threshold, binomial_upper


def main():
    results = ROOT / 'research/results'
    report = {'seed': 42, 'protocol': 'Fixed gallery from 10 identities; 19 separate unknown calibration identities; 10 separate unknown test identities; two deterministic queries per identity; calibration uses each identity maximum; strict score > threshold',
        'assumptions': ['Filename prefixes denote damage identity; not independently audited', 'Unknown calibration and test groups must be exchangeable for a conformal interpretation', 'The gallery and encoder must remain frozen; adding a photo requires recalibration', 'No target-domain training overlap audit', '10 unknown test identities provide weak evidence; the confidence bound must accompany point estimates'], 'encoders': {}}
    for encoder in ('resnet18', 'osnet'):
        path = results / f'generali_{encoder}_embeddings.npz'
        cache = np.load(path); labels = cache['labels']; names = cache['names']; vectors = cache['vectors']
        identities = np.array(sorted(set(labels))); np.random.default_rng(42).shuffle(identities)
        gallery_ids = np.array([identity for identity in identities if np.sum(labels == identity) >= 3][:10])
        remaining = np.array([identity for identity in identities if identity not in gallery_ids])
        calibration_ids, unknown_test_ids = remaining[:19], remaining[19:]
        gallery, matched, calibration, unknown = [], [], [], []
        for identity in gallery_ids:
            indices = np.flatnonzero(labels == identity)
            if len(indices) < 3: raise ValueError('Need held-out queries and a gallery image per identity')
            matched.extend(indices[:2]); gallery.extend(indices[2:])
        def rows(groups):
            output=[]
            for identity in groups:
                for i in np.flatnonzero(labels == identity)[:2]:
                    scores=vectors[gallery] @ vectors[i]; j=gallery[int(np.argmax(scores))]
                    output.append({'query':str(names[i]),'identity':str(identity),'score':float(scores.max()),'candidate':str(names[j]),'candidate_identity':str(labels[j])})
            return output
        calibration=rows(calibration_ids); unknown=rows(unknown_test_ids)
        matched_rows=[]
        for i in matched:
            scores=vectors[gallery] @ vectors[i];j=gallery[int(np.argmax(scores))]
            matched_rows.append({'query':str(names[i]),'identity':str(labels[i]),'score':float(scores.max()),'correct':bool(labels[j] == labels[i])})
        calibration_scores=[max(r['score'] for r in calibration if r['identity']==identity) for identity in calibration_ids]
        operating_points={}
        for alpha in (.05,.1,.2):
            threshold=upper_tail_threshold(calibration_scores,alpha)
            errors=sum(any(r['score'] > threshold for r in unknown if r['identity']==identity) for identity in unknown_test_ids)
            accepted=[r for r in matched_rows if r['score']>threshold]
            operating_points[str(alpha)]={'target_group_false_alert_rate':alpha,'threshold':threshold if np.isfinite(threshold) else None,'abstain_all':not np.isfinite(threshold),
                'unknown_group_false_alerts':errors,'unknown_test_groups':len(unknown_test_ids),'unknown_group_false_alert_rate':errors/len(unknown_test_ids),
                'unknown_group_false_alert_rate_95_upper_bound':binomial_upper(errors,len(unknown_test_ids)),
                'matched_query_acceptance':len(accepted)/len(matched_rows),'precision_among_accepted':float(np.mean([r['correct'] for r in accepted])) if accepted else None,
                'reliability_established':False}
        gallery_names=[str(names[i]) for i in gallery]
        report['encoders'][encoder]={'embedding_cache_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'gallery_fingerprint':hashlib.sha256('\n'.join(gallery_names).encode()).hexdigest(),
            'gallery_images':len(gallery),'gallery_identities':gallery_ids.tolist(),'gallery_names':gallery_names,'calibration_identities':calibration_ids.tolist(),'unknown_test_identities':unknown_test_ids.tolist(),
            'operating_points':operating_points,'calibration_queries':calibration,'unknown_test_queries':unknown,'matched_queries':matched_rows}
    (results/'fixed_gallery_abstention_evaluation.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps({e:r['operating_points'] for e,r in report['encoders'].items()},indent=2))

if __name__=='__main__': main()
