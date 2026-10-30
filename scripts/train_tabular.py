"""Reproducible split-first baseline using teammate's seven tabular features."""
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
from ml.tabular.model import train, predict, MODEL_PATH, FEATURES


def split_indices(labels, seed=42):
    rng = random.Random(seed)
    splits = [[], [], []]
    for label in [0, 1]:
        indices = [i for i, value in enumerate(labels) if value == label]
        rng.shuffle(indices)
        a, b = int(len(indices) * .6), int(len(indices) * .8)
        for target, subset in zip(splits, [indices[:a], indices[a:b], indices[b:]]):
            target.extend(subset)
    return splits


def metrics(y, p, threshold):
    y, p = np.asarray(y), np.asarray(p)
    pred = p >= threshold
    tp, fp = int(sum(pred & (y == 1))), int(sum(pred & (y == 0)))
    fn, tn = int(sum(~pred & (y == 1))), int(sum(~pred & (y == 0)))
    order = np.argsort(-p, kind="stable")
    # AP grouped by tied scores.
    positive, average_precision = int(sum(y)), 0.
    for score in sorted(set(p), reverse=True):
        selected = p >= score
        count = int(sum((p == score) & (y == 1)))
        average_precision += count / max(positive, 1) * float(sum(y[selected]) / sum(selected))
    auc = float(np.mean([(a > b) + .5 * (a == b) for a in p[y == 1] for b in p[y == 0]]))
    return {"n": len(y), "prevalence": float(np.mean(y)), "pr_auc_average_precision": average_precision,
            "roc_auc": auc, "brier_score": float(np.mean((p-y)**2)),
            "precision": tp/max(tp+fp, 1), "recall": tp/max(tp+fn, 1),
            "confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
            "threshold": threshold, "precision_at_20": float(np.mean(y[order[:20]]))}


def main():
    source = ROOT / "data/teammate/insurance_claims.csv"
    with source.open() as stream:
        rows = list(csv.DictReader(stream))
    labels = [int(row["fraud_reported"] == "Y") for row in rows]
    train_ids, val_ids, test_ids = split_indices(labels)
    # Exact feature-vector overlap across partitions is reported, never hidden.
    fingerprints = [tuple(row[key] for key in FEATURES) for row in rows]
    model = train([rows[i] for i in train_ids], [labels[i] for i in train_ids])
    val_y = np.array([labels[i] for i in val_ids])
    val_p = predict(model, [rows[i] for i in val_ids])
    candidates = sorted(set(float(x) for x in val_p))
    def f1(t):
        pred = val_p >= t
        tp = sum(pred & (val_y == 1))
        return 2*tp/max(sum(pred) + sum(val_y), 1)
    threshold = max(candidates, key=f1)
    model["metrics"] = metrics([labels[i] for i in test_ids],
                               predict(model, [rows[i] for i in test_ids]), threshold)
    model["threshold"] = threshold
    model["data_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    model["split"] = {"seed": 42, "train": train_ids, "validation": val_ids, "test": test_ids}
    model["validation_metrics"] = metrics(val_y, val_p, threshold)
    model["feature_overlap_train_test"] = len({fingerprints[i] for i in train_ids} &
                                             {fingerprints[i] for i in test_ids})
    model["limitations"] = [
        "Random-row public benchmark only; no prospective or insurer validation.",
        "Garage and claimant IDs excluded: construction/provenance unverified.",
        "Preprocessing and gradient fitting use training rows only.",
        "Threshold selected on validation; test used once for reporting.",
        "Model output uncalibrated. No causal or automatic denial interpretation.",
        "Seven features inherited from teammate; selection was not independently validated."]
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(model, indent=2))
    report = ROOT / "docs/TABULAR_EVALUATION.json"
    report.write_text(json.dumps({k:v for k,v in model.items()
                                  if k not in {"weights", "schema", "feature_names"}}, indent=2))
    print(json.dumps(model["metrics"], indent=2))


if __name__ == "__main__":
    main()
