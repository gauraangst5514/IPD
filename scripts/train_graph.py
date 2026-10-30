"""Train/validation/test-separated inductive graph baseline; no test selection."""
import csv
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import torch
from ml.tabular.model import MODEL_PATH, encode
from ml.tabular.graph import GRAPH_PATH, neighbors, build_model
from scripts.train_tabular import metrics

def main():
    torch.set_num_threads(2)
    torch.manual_seed(42)
    baseline = json.loads(MODEL_PATH.read_text())
    with (ROOT/"data/teammate/insurance_claims.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    indices = baseline["split"]
    def batch(part):
        selected = [rows[i] for i in indices[part]]
        x,_ = encode(selected, baseline["schema"])
        return x, np.array([int(row["fraud_reported"]=="Y") for row in selected])
    train_x, train_y = batch("train")
    val_x, val_y = batch("validation")
    test_x, test_y = batch("test")
    def tensor(x): return torch.tensor(x,dtype=torch.float32)
    reference, adjacency = tensor(train_x), tensor(neighbors(train_x,train_x))
    model = build_model(train_x.shape[1])
    optimizer = torch.optim.Adam(model.parameters(),lr=.005,weight_decay=.01)
    loss_fn = torch.nn.BCEWithLogitsLoss()
    best_loss, best, patience = float("inf"), None, 0
    val_adj = tensor(neighbors(val_x,train_x))
    for epoch in range(500):
        model.train(); optimizer.zero_grad()
        logits = model(reference,adjacency,reference,adjacency)
        loss = loss_fn(logits,tensor(train_y)); loss.backward(); optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = loss_fn(model(reference,adjacency,tensor(val_x),val_adj),tensor(val_y)).item()
        if validation_loss < best_loss - 1e-5:
            best_loss = validation_loss
            best = {k:v.detach().clone() for k,v in model.state_dict().items()}
            patience = 0
        else:
            patience += 1
        if patience >= 50: break
    model.load_state_dict(best); model.eval()
    with torch.no_grad():
        validation_scores = torch.sigmoid(model(reference,adjacency,tensor(val_x),val_adj)).numpy()
    def f1(t):
        pred=validation_scores>=t
        return 2*sum(pred & (val_y==1))/max(sum(pred)+sum(val_y),1)
    threshold = max(sorted(set(float(p) for p in validation_scores)),key=f1)
    with torch.no_grad():
        scores = torch.sigmoid(model(reference,adjacency,tensor(test_x),tensor(neighbors(test_x,train_x)))).numpy()
    report = {"metrics":metrics(test_y,scores,threshold),"selected_by":"validation_bce",
              "epochs_run":epoch+1,"edge_semantics":"8 nearest training feature vectors",
              "limitations":baseline["limitations"] + ["Feature-neighbour graph only; not tested for collusion or recurrent physical damage."]}
    artifact = {**report,"schema":baseline["schema"],"reference":train_x.tolist(),
                "state":{k:v.tolist() for k,v in best.items()},"data_sha256":baseline["data_sha256"]}
    GRAPH_PATH.write_text(json.dumps(artifact))
    (ROOT/"docs/GRAPH_EVALUATION.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=="__main__": main()
