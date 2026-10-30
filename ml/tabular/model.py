"""Portable learned baseline, with exact additive log-odds explanations.

No fraud-score fusion. Fit preprocessing on training records only. The bundled
public benchmark is not evidence of performance on an insurer's population.
"""
import json
import math
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "ml/weights/tabular/model.json"
CATEGORICAL = ["incident_severity", "insured_hobbies", "incident_type"]
NUMERIC = ["total_claim_amount", "vehicle_claim", "umbrella_limit", "policy_annual_premium"]
FEATURES = CATEGORICAL + NUMERIC


def sigmoid(values):
    return 1 / (1 + np.exp(-np.clip(values, -35, 35)))


def fit_schema(rows):
    return {
        "categories": {key: sorted({str(row[key]) for row in rows}) for key in CATEGORICAL},
        "numeric": {key: {"mean": float(np.mean([float(r[key]) for r in rows])),
                          "scale": max(float(np.std([float(r[key]) for r in rows])), 1.0)}
                    for key in NUMERIC},
    }


def encode(rows, schema):
    names = ["intercept"] + [key + "=" + value for key in CATEGORICAL
                             for value in schema["categories"][key]] + NUMERIC
    matrix = []
    for row in rows:
        values = [1.0]
        for key in CATEGORICAL:
            values += [float(str(row[key]) == value) for value in schema["categories"][key]]
        for key in NUMERIC:
            value = float(row[key])
            if not math.isfinite(value):
                raise ValueError("Numeric fields must be finite")
            stats = schema["numeric"][key]
            values.append((value - stats["mean"]) / stats["scale"])
        matrix.append(values)
    return np.asarray(matrix), names


def train(rows, labels):
    schema = fit_schema(rows)
    x, names = encode(rows, schema)
    y = np.asarray(labels, dtype=float)
    weights = np.zeros(x.shape[1])
    # Actual prevalence is preserved. No oversampling or class weight distortion.
    for _ in range(2500):
        regularization = 0.01 * weights
        regularization[0] = 0
        weights -= 0.1 * (x.T @ (sigmoid(x @ weights) - y) / len(y) + regularization)
    return {"schema": schema, "weights": weights.tolist(), "feature_names": names,
            "model_type": "l2_logistic_regression", "version": 1}


def predict(model, rows):
    x, _ = encode(rows, model["schema"])
    return sigmoid(x @ np.asarray(model["weights"]))


class TabularModel:
    def __init__(self, path=MODEL_PATH):
        self.path = Path(path)

    def status(self):
        if not self.path.is_file():
            return {"available": False, "reason": "run_scripts_train_tabular"}
        model = json.loads(self.path.read_text())
        return {"available": True, "method": model["model_type"],
                "metrics": model.get("metrics"), "research_only": True,
                "warning": "Public benchmark; calibration and insurer transfer are unverified."}

    def assess(self, fields):
        if not self.path.is_file():
            return {"available": False, "reason": "Model has not been trained"}
        missing = [key for key in FEATURES if fields.get(key) is None or fields.get(key) == ""]
        if missing:
            return {"available": False, "missing_fields": missing}
        model = json.loads(self.path.read_text())
        unknown = [key for key in CATEGORICAL
                   if str(fields[key]) not in model["schema"]["categories"][key]]
        if unknown:
            return {"available": False, "reason": "Unseen category", "fields": unknown}
        x, names = encode([fields], model["schema"])
        contributions = x[0] * np.asarray(model["weights"])
        return {"available": True, "method": model["model_type"], "research_only": True,
                "model_score": float(sigmoid(np.sum(contributions))),
                "score_meaning": "Uncalibrated public-benchmark classifier output; not a verified claim fraud probability.",
                "intercept_log_odds": float(contributions[0]),
                "contributions": sorted([
                    {"feature": name, "log_odds": float(value)}
                    for name, value in zip(names[1:], contributions[1:]) if abs(value) > 1e-10
                ], key=lambda item: abs(item["log_odds"]), reverse=True),
                "explanation": "Contributions plus intercept equal the model log-odds; they are associations, not causes."}
