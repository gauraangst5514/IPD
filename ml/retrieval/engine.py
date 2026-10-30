import hashlib, io, threading, os, base64, tempfile
from pathlib import Path
import numpy as np
from PIL import Image

class RetrievalEngine:
    """Frozen ImageNet embedding retrieval with optional learned local verification.

    Models load only from provisioned caches; requests never download weights.
    The gallery contains photographs, not asserted physical-damage identities.
    """
    def __init__(self, gallery):
        self.gallery=Path(gallery); self.lock=threading.RLock(); self.model=None
        self.embedding_name='ImageNet_ResNet18'; self.damage_evidence=None; self.matcher=None; self.extractor=None; self.records=[]; self.vectors=None
        self.seen_hashes=set()

    def load(self):
        import torch
        from torchvision.models import resnet18, ResNet18_Weights
        weights=ResNet18_Weights.DEFAULT
        checkpoint=Path(torch.hub.get_dir())/'checkpoints'/Path(weights.url).name
        if not checkpoint.exists(): raise RuntimeError('Pretrained ResNet18 weights missing; run scripts/provision_retrieval.py')
        self.model=resnet18(weights=weights).eval(); self.model.fc=torch.nn.Identity()
        self.transform=weights.transforms()
        state_path=Path(__file__).resolve().parents[1]/'weights/osnet_similarity_state.pt'
        if os.environ.get('RETRIEVAL_ENCODER','osnet') == 'osnet' and state_path.exists():
            from ml.retrieval.osnet_ain_arch import osnet_ain_x1_0
            from torchvision import transforms
            model=osnet_ain_x1_0(num_classes=10415,pretrained=False).eval()
            model.load_state_dict(torch.load(state_path,map_location='cpu',weights_only=True),strict=True)
            self.model=model
            self.transform=transforms.Compose([transforms.Resize((256,128)),transforms.ToTensor(),transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
            self.embedding_name='Generali_OSNet_AIN_x1_0'

        try:
            self._load_gallery()
        except Exception:
            self.model = None
            raise

    def _load_gallery(self):
        self.gallery.mkdir(parents=True,exist_ok=True)
        records=[]; seen=set()
        for p in sorted(self.gallery.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in {'.jpg','.jpeg','.png','.webp'}: continue
            digest=hashlib.sha256(p.read_bytes()).hexdigest()
            if digest in seen: continue
            seen.add(digest); records.append(p)
        vectors=[]
        for path in records:
            with Image.open(path) as image:
                vectors.append(self.encode(image.convert('RGB')))
        self.vectors=np.stack(vectors) if vectors else None
        self.records=records
        self.seen_hashes=seen

    def encode(self,image):
        import torch
        with torch.inference_mode(): vector=self.model(self.transform(image).unsqueeze(0)).numpy()[0]
        return vector/(np.linalg.norm(vector)+1e-12)

    def extract_lightglue(self, image):
        """Extract once per image; callers may reuse features within a frozen run."""
        import torch
        from lightglue import SuperPoint, LightGlue
        if self.matcher is None:
            self.extractor=SuperPoint(max_num_keypoints=int(os.environ.get('RETRIEVAL_KEYPOINTS','1024'))).eval()
            self.matcher=LightGlue(features='superpoint').eval()
        image=image.copy()
        edge=int(os.environ.get('RETRIEVAL_EDGE','1024'))
        image.thumbnail((edge,edge))
        tensor=torch.from_numpy(np.asarray(image.convert('RGB')).copy()).permute(2,0,1).float()/255
        with torch.inference_mode():
            # SuperPoint otherwise resizes back to 1024, undoing the CPU bound.
            features=self.extractor.extract(tensor, resize=None)
        return features, list(image.size)

    def match_lightglue(self, query_features, candidate_features):
        import torch
        from lightglue.utils import rbd
        fa, query_size=query_features
        fb, candidate_size=candidate_features
        with torch.inference_mode():
            matched=self.matcher({'image0':fa,'image1':fb})
        fa,fb,matched=[rbd(x) for x in (fa,fb,matched)]
        indices=matched['matches']; a=fa['keypoints'][indices[:,0]].numpy(); b=fb['keypoints'][indices[:,1]].numpy()
        return {'method':'SuperPoint_LightGlue','matches':len(indices),
                'query_size':query_size,'candidate_size':candidate_size,
                'correspondences':[{'query':x.tolist(),'candidate':y.tolist()} for x,y in zip(a[:100],b[:100])],
                'status':'local_correspondences_only','physical_identity_proven':False}

    def verify_lightglue(self, query, candidate):
        return self.match_lightglue(self.extract_lightglue(query), self.extract_lightglue(candidate))

    def verify(self,query,candidate):
        """SIFT/RANSAC is an explicit baseline, never presented as LightGlue."""
        if os.environ.get('RETRIEVAL_MATCHER') == 'lightglue':
            return self.verify_lightglue(query,candidate)
        import cv2
        query=query.copy(); candidate=candidate.copy()
        query.thumbnail((1024,1024)); candidate.thumbnail((1024,1024))
        a=np.asarray(query.convert('L')); b=np.asarray(candidate.convert('L'))
        detector=cv2.SIFT_create(nfeatures=1500)
        ka,da=detector.detectAndCompute(a,None); kb,db=detector.detectAndCompute(b,None)
        if da is None or db is None or len(db)<2:
            return {'method':'SIFT_RANSAC','matches':0,'inliers':0,'status':'insufficient_features'}
        matches=cv2.BFMatcher().knnMatch(da,db,k=2)
        good=[m for pair in matches if len(pair)==2 for m,n in [pair] if m.distance<.75*n.distance]
        if len(good)<4: return {'method':'SIFT_RANSAC','matches':len(good),'inliers':0,'status':'insufficient_matches'}
        src=np.float32([ka[m.queryIdx].pt for m in good]); dst=np.float32([kb[m.trainIdx].pt for m in good])
        matrix,mask=cv2.findHomography(src,dst,cv2.RANSAC,5.)
        valid=mask.ravel().astype(bool) if matrix is not None else np.zeros(len(good),dtype=bool)
        return {'method':'SIFT_RANSAC','query_size':list(query.size),'candidate_size':list(candidate.size),'matches':len(good),'inliers':int(valid.sum()),
                'correspondences':[{'query':x.tolist(),'candidate':y.tolist()} for x,y in zip(src[valid][:100],dst[valid][:100])],
                'status':'geometric_evidence_only','limitation':'Planar geometry may fail for genuine cross-view damage; inliers can come from undamaged bodywork.'}

    def search(self,content,k=5):
        with self.lock:
            if self.model is None: self.load()
            if self.vectors is None: return {'available':True,'candidates':[],'gallery_size':0}
            query=Image.open(io.BytesIO(content)).convert('RGB'); vector=self.encode(query)
            scores=self.vectors@vector; indices=np.argsort(-scores)[:max(1,min(k,20))]
            candidates=[]
            for i in indices:
                path=self.records[i]
                thumb=Image.open(path).convert('RGB'); thumb.thumbnail((640,640))
                buffer=io.BytesIO(); thumb.save(buffer,format='JPEG',quality=80)
                candidate=Image.open(path).convert('RGB')
                verification=self.verify(query,candidate)
                damage=None
                if os.environ.get('RETRIEVAL_DAMAGE_EVIDENCE') == '1':
                    from ml.retrieval.damage_evidence import DamageEvidence
                    if self.damage_evidence is None: self.damage_evidence=DamageEvidence()
                    damage=self.damage_evidence.explain(self,query,candidate,verification)
                candidates.append({'damage_evidence':damage, 'thumbnail':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode(), 'image_id':str(path.relative_to(self.gallery)),'cosine_similarity':float(scores[i]),
                                   'verification':verification})
            return {'available':True,'embedding':self.embedding_name,'gallery_size':len(self.records),
                    'candidates':candidates,'decision':'investigator_review','score_type':'similarity_not_probability',
                    'physical_damage_identity_validated':False}

    def add_image(self, content: bytes, identifier: str = None):
        with self.lock:
            from ml.image_input import open_upload
            try:
                with open_upload(content) as source:
                    if source.format not in {'JPEG', 'PNG', 'WEBP'}:
                        raise ValueError('Upload a JPEG, PNG or WebP image')
                    ext = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}[source.format]
                    source.verify()
                with open_upload(content) as source:
                    img = source.convert('RGB')
            except (OSError, ValueError, SyntaxError, EOFError, Image.DecompressionBombError) as exc:
                raise ValueError('Upload a valid JPEG, PNG or WebP image') from exc
            if self.model is None:
                self.load()

            digest = hashlib.sha256(content).hexdigest()
            if digest in self.seen_hashes:
                for p in self.records:
                    if p.exists() and hashlib.sha256(p.read_bytes()).hexdigest() == digest:
                        return {
                            'added': False,
                            'reason': 'duplicate_image',
                            'image_id': str(p.relative_to(self.gallery)),
                            'gallery_size': len(self.records),
                            'embedding': self.embedding_name,
                        }
                return {
                    'added': False,
                    'reason': 'duplicate_image',
                    'image_id': '',
                    'gallery_size': len(self.records),
                    'embedding': self.embedding_name,
                }

            # Compute everything that can fail before changing disk or index state.
            vector = self.encode(img)
            vectors = np.vstack([self.vectors, vector]) if self.vectors is not None else np.array([vector])
            self.gallery.mkdir(parents=True, exist_ok=True)
            stem = Path(identifier or f'claim_{digest[:12]}').stem
            stem = ''.join(c for c in stem if c.isalnum() or c in '-_')[:100] or 'claim'
            dest = self.gallery / f'{stem}{ext}'
            if dest.exists():
                dest = self.gallery / f'{stem}_{digest}{ext}'

            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.gallery, suffix='.tmp', delete=False) as file:
                    temporary = Path(file.name)
                    file.write(content)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, dest)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            self.records.append(dest)
            self.vectors = vectors
            self.seen_hashes.add(digest)

            return {
                'added': True,
                'image_id': str(dest.relative_to(self.gallery)),
                'gallery_size': len(self.records),
                'embedding': self.embedding_name,
            }

    def stats(self):
        with self.lock:
            if not self.records and self.gallery.exists():
                count = len({hashlib.sha256(p.read_bytes()).hexdigest() for p in self.gallery.rglob('*')
                             if p.is_file() and p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}})
            else:
                count = len(self.records) if self.records else 0
            return {
                'gallery_size': count,
                'embedding': self.embedding_name if self.model is not None else None,
                'model_loaded': self.model is not None,
                'gallery_path': str(self.gallery),
            }
