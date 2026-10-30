"""Inductive GraphSAGE benchmark over feature-neighbour relationships.

These edges mean similar public tabular records, not collusion. Teammate's
unverified claimant/garage identifiers and test-selected checkpoint are excluded.
"""
import json
from pathlib import Path
import numpy as np
from ml.tabular.model import MODEL_PATH, encode, TabularModel

GRAPH_PATH = MODEL_PATH.with_name("graph.json")

def neighbors(query, reference, k=8):
    distances = ((query[:,None,:]-reference[None,:,:])**2).sum(axis=2)
    adjacency = np.zeros_like(distances)
    nearest = np.argsort(distances, axis=1)[:,:min(k,len(reference))]
    np.put_along_axis(adjacency, nearest, 1 / nearest.shape[1], axis=1)
    return adjacency

def build_model(features):
    import torch
    class Network(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.first = torch.nn.Linear(features*2, 24)
            self.second = torch.nn.Linear(48, 1)
        def forward(self, reference, adjacency, query, query_adj):
            hidden_ref = torch.relu(self.first(torch.cat([reference,adjacency @ reference], dim=1)))
            hidden_query = torch.relu(self.first(torch.cat([query,query_adj @ reference], dim=1)))
            return self.second(torch.cat([hidden_query, query_adj @ hidden_ref], dim=1)).squeeze(1)
    return Network()

class GraphModel:
    def status(self):
        import importlib.util
        return {"available": GRAPH_PATH.exists() and importlib.util.find_spec("torch") is not None,
                "method": "inductive_graphsage_feature_neighbors", "research_only": True,
                "edge_meaning": "Similar benchmark feature vectors; not a fraud-ring graph"}
    def assess(self, fields):
        if not self.status()["available"]:
            return {"available": False, "reason": "Run scripts/train_graph.py with vision dependencies installed"}
        check = TabularModel().assess(fields)
        if not check["available"]:
            return check
        import torch
        artifact = json.loads(GRAPH_PATH.read_text())
        query, _ = encode([fields], artifact["schema"])
        reference = np.array(artifact["reference"])
        query_adj = neighbors(query, reference)
        model = build_model(reference.shape[1])
        model.load_state_dict({k:torch.tensor(v) for k,v in artifact["state"].items()})
        model.eval()
        with torch.no_grad():
            logits = model(torch.tensor(reference,dtype=torch.float32),
                torch.tensor(neighbors(reference,reference),dtype=torch.float32),
                torch.tensor(query,dtype=torch.float32),torch.tensor(query_adj,dtype=torch.float32))
            score = torch.sigmoid(logits)[0].item()
        return {"available": True, "model_score": score, **self.status(),
                "score_meaning": "Uncalibrated public-benchmark graph classifier; not evidence of a fraud ring.",
                "metrics": artifact["metrics"]}
