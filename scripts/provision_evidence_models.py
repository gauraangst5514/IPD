"""Provision published evidence models at setup/build time, never per request."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    import sys
    sys.path.insert(0,str(ROOT))
    os.environ['HF_HUB_DISABLE_XET']='1'
    from huggingface_hub import hf_hub_download
    target=ROOT/'ml/weights/vehicle_make_hf';target.mkdir(parents=True,exist_ok=True)
    for name in ('config.json','preprocessor_config.json','model.safetensors'):
        hf_hub_download('nenzilea/car-classification',name,revision='40b07a61c3125b0be2e607efe6581d4e64c8b801',local_dir=target)
    (target/'provenance.json').write_text(json.dumps({'repo':'nenzilea/car-classification','revision':'40b07a61c3125b0be2e607efe6581d4e64c8b801','license':'apache-2.0'}))
    import easyocr
    easyocr.Reader(['en'],gpu=False,model_storage_directory=str(ROOT/'ml/weights/ocr'),verbose=False)
    target=ROOT/'ml/weights/trufor';target.mkdir(parents=True,exist_ok=True)
    if not (target/'trufor_state.pt').exists():
        import httpx
        import torch
        from ml.safe_checkpoint import tensor_state
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'weights.zip'
            with httpx.Client(follow_redirects=True,timeout=120,trust_env=False) as client:
                with client.stream('GET','https://www.grip.unina.it/download/prog/TruFor/TruFor_weights.zip') as r:
                    r.raise_for_status()
                    with path.open('wb') as out:
                        for chunk in r.iter_bytes():out.write(chunk)
            if hashlib.md5(path.read_bytes()).hexdigest()!='7bee48f3476c75616c3c5721ab256ff8':raise ValueError('TruFor integrity check failed')
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    name=Path(info.filename)
                    if name.is_absolute() or '..' in name.parts:raise ValueError('Unsafe archive member')
                archive.extractall(directory)
            source=next(Path(directory).rglob('trufor.pth.tar'))
            torch.save(tensor_state(source),target/'trufor_state.pt')
    from torchvision.models import ResNet18_Weights,resnet18
    resnet18(weights=ResNet18_Weights.DEFAULT)
    print('Evidence model weights provisioned; runtime inference remains offline.')

if __name__=='__main__':main()
