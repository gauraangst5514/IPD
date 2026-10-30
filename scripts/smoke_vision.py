"""Actual-checkpoint API smoke test. Synthetic fixtures test plumbing, not accuracy."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault("YOLO_CONFIG_DIR",str(ROOT/"var/yolo-config"))
os.environ.setdefault("MPLCONFIGDIR",str(ROOT/"var/matplotlib"))
from PIL import Image
from fastapi.testclient import TestClient

def main():
    with tempfile.TemporaryDirectory() as directory:
        os.environ["IMAGE_HISTORY_PATH"]=str(Path(directory)/"history.sqlite3")
        from ml.serve import app
        fixture=io.BytesIO()
        Image.new("RGB",(128,128),(20,100,160)).save(fixture,format="JPEG")
        files={"file":("synthetic-fixture.jpg",fixture.getvalue(),"image/jpeg")}
        with TestClient(app) as client:
            health=client.get("/health")
            assert health.status_code==200
            assert health.json()["model_trained"], health.json()
            first=client.post("/analyze",files=files,data={"claim_id":"smoke-a","image_id":"a"}); first.raise_for_status()
            second=client.post("/analyze",files=files,data={"claim_id":"smoke-b","image_id":"b"}); second.raise_for_status()
            assert second.json()["damage_analysis_available"]
            assert second.json()["fraud_score"] is None
            match=next(x for x in second.json()["fraud_indicators"] if x["code"]=="duplicate_image")
            assert match["evidence"]["matches"][0]["claim_id"]=="smoke-a"
            annotated=client.post("/detect",files=files); annotated.raise_for_status()
            assert annotated.content.startswith(b"\x89PNG")
            saliency=client.post("/saliency",files=files); saliency.raise_for_status()
            report={"checkpoint_loaded":True,"actual_inference_completed":True,
                    "actual_ml_api_and_persistent_match":True,"annotated_png":True,
                    "saliency_route_responded":True,"fixture":"synthetic uniform image",
                    "accuracy_evaluated":False,"network_listener_tested":False}
            (ROOT/"var/vision-smoke.json").write_text(json.dumps(report,indent=2))
            print(json.dumps(report,indent=2))
if __name__=="__main__":main()
