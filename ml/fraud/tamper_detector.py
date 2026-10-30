"""Published TruFor inference; nonprofit research diagnostics, no fraud verdict."""
import base64
import io
import logging
import threading
from pathlib import Path
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
WEIGHTS=ROOT/'weights/trufor/weights/trufor.pth.tar'

class TamperDetector:
    def __init__(self):
        self.model=None
        self.reason='checkpoint_missing'
        self.lock=threading.RLock()
        candidates=list((ROOT/'weights/trufor').rglob('trufor_state.pt'))
        self.weights=candidates[0] if candidates else WEIGHTS
        if self.weights.is_file():
            try:
                import torch
                from ml.vendor.trufor.config import _C
                from ml.vendor.trufor.models.cmx.builder_np_conf import myEncoderDecoder
                cfg=_C.clone();cfg.merge_from_file(str(ROOT/'vendor/trufor/trufor.yaml'));cfg.freeze()
                model=myEncoderDecoder(cfg=cfg)
                state=torch.load(self.weights,map_location='cpu',weights_only=True)
                model.load_state_dict(state,strict=True)
                self.model=model.eval()
                self.reason=None
            except Exception:
                self.reason='checkpoint_load_failed'
                logging.getLogger(__name__).exception('TruFor model could not load')

    def status(self):
        return {'available':self.model is not None,'method':'TruFor_pretrained','reason':self.reason,
            'license':'Informational and nonprofit use only',
            'limitation':'Published pretrained forgery localization model; no vehicle-insurance accuracy or calibrated authenticity probability established.'}

    def analyze(self,content):
        if self.model is None:return {**self.status()}
        import torch
        from ml.image_input import open_upload
        with open_upload(content) as image:
            image=image.convert('RGB');original_size=list(image.size);image.thumbnail((768,768));array=np.asarray(image).copy()
        # Follow the authors' /256 normalization, rather than silently /255.
        tensor=torch.from_numpy(array).permute(2,0,1).float().unsqueeze(0)/256.
        with self.lock,torch.inference_mode():
            prediction,confidence,detection,_=self.model(tensor)
            localization=prediction.softmax(dim=1)[0,1].numpy()
            reliability=confidence.sigmoid()[0,0].numpy()
            score=float(detection.sigmoid().item())
        heat=Image.fromarray(np.uint8(np.stack([localization*255,np.zeros_like(localization), (1-localization)*255],axis=-1)))
        heat.thumbnail((384,384));stream=io.BytesIO();heat.save(stream,format='PNG')
        return {'available':True,'method':'TruFor_pretrained','model_score':score,
            'score_type':'uncalibrated_forgery_model_score','original_size':original_size,'analysis_size':list(image.size),
            'mean_localization_reliability':float(reliability.mean()),
            'localization_data_url':'data:image/png;base64,'+base64.b64encode(stream.getvalue()).decode(),
            'decision':'investigator_review','limitation':'A model score or localization map does not prove editing, fraudulent intent, or image authenticity. Nonprofit research use only.'}
