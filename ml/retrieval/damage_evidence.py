"""Detector-guided correspondence attribution and controlled masking diagnostics."""
import io
import numpy as np
from PIL import Image, ImageDraw

class DamageEvidence:
    def __init__(self):
        from ml.detection.detector import DamageDetector
        self.detector=DamageDetector(device='cpu')
        self.cache={}

    def boxes(self, image):
        original=image.size
        image=image.copy();image.thumbnail((1280,1280))
        buf=io.BytesIO(); image.save(buf,format='JPEG',quality=95); data=buf.getvalue()
        import hashlib
        key=hashlib.sha256(data).hexdigest()
        if key not in self.cache:
            result=self.detector.detect(data)
            boxes=result.get('detections',[])
            converted=[]
            for b in boxes:
                cx,cy,bw,bh=b['bbox']  # Detector contract: normalized centre x/y and width/height.
                converted.append({**b,'bbox':[(cx-bw/2)*original[0],(cy-bh/2)*original[1],(cx+bw/2)*original[0],(cy+bh/2)*original[1]],'bbox_format':'pixel_xyxy'})
            self.cache[key]=converted
        return self.cache[key]

    def explain(self, engine, query, candidate, verification):
        if not self.detector.trained:
            return {'available':False,'reason':self.detector.unavailable_reason}
        qb=self.boxes(query); cb=self.boxes(candidate)
        if not qb or not cb:
            return {'available':False,'reason':'no_damage_detected_in_one_or_both_images','query_detections':qb,'candidate_detections':cb}
        sizeq=verification.get('query_size',query.size); sizec=verification.get('candidate_size',candidate.size)
        def inside(point, boxes, original, resized):
            x,y=point[0]*original[0]/resized[0],point[1]*original[1]/resized[1]
            return any(b['bbox'][0]<=x<=b['bbox'][2] and b['bbox'][1]<=y<=b['bbox'][3] for b in boxes)
        pairs=verification.get('correspondences',[])
        supported=sum(inside(p['query'],qb,query.size,sizeq) and inside(p['candidate'],cb,candidate.size,sizec) for p in pairs)
        # One highest-confidence box, compared with a same-sized non-overlapping background box.
        b=max(qb,key=lambda b:b['confidence'])['bbox']; w,h=query.size
        x0,y0,x1,y1=[int(round(v)) for v in b]; x0=max(0,x0);y0=max(0,y0);x1=min(w,x1);y1=min(h,y1)
        bw,bh=x1-x0,y1-y0
        background=None
        if bw>0 and bh>0:
            for x,y in [(0,0),(w-bw,0),(0,h-bh),(w-bw,h-bh)]:
                rect=(x,y,x+bw,y+bh)
                if all(rect[2]<=d['bbox'][0] or rect[0]>=d['bbox'][2] or rect[3]<=d['bbox'][1] or rect[1]>=d['bbox'][3] for d in qb):
                    background=rect;break
        v=engine.encode(candidate);base=float(engine.encode(query)@v)
        fill=tuple(np.asarray(query).reshape(-1,3).mean(0).astype(int))
        def masked_score(rect):
            im=query.copy();ImageDraw.Draw(im).rectangle((rect[0],rect[1],rect[2]-1,rect[3]-1),fill=fill)
            return float(engine.encode(im)@v)
        damage_drop=base-masked_score((x0,y0,x1,y1)) if bw>0 and bh>0 else None
        background_drop=base-masked_score(background) if background else None
        return {'available':True,'query_detections':qb,'candidate_detections':cb,
                'evaluated_correspondences':len(pairs),'damage_supported_correspondences':supported,
                'damage_supported_fraction':supported/len(pairs) if pairs else None,
                'damage_mask_score_drop':damage_drop,'background_mask_score_drop':background_drop,
                'damage_minus_background_drop':damage_drop-background_drop if damage_drop is not None and background_drop is not None else None,
                'background_control_available':background is not None,'mask_fill':'query_mean_RGB',
                'mask_direction':'query_only','warning':'Detector boxes are predictions. Masking introduces artifacts; score changes are model sensitivity, not causal proof. Correspondences capped at 100.'}
