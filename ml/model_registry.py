"""Status and inference for the actual installed artifacts; no generic fallback."""
import importlib.util
import logging
from pathlib import Path
from ml.tabular.model import TabularModel
from ml.tabular.graph import GraphModel

def status(pipeline):
    from ml.fraud.plate_reader import status as plate_status
    return {
        **(pipeline.capabilities() if pipeline else {}),
        "tabular_classifier": TabularModel().status(),
        "graph_baseline": GraphModel().status(),
        "plate_reader": plate_status(),
    }

def assess_structured(fields):
    try:
        tabular=TabularModel().assess(fields)
    except Exception:
        logging.exception("Tabular inference failed")
        tabular={"available":False,"reason":"inference_failed"}
    try:
        graph=GraphModel().assess(fields) if tabular.get("available") else {
            "available":False,"reason":"complete_supported_fields_required"}
    except Exception:
        logging.exception("Graph inference failed")
        graph={"available":False,"reason":"inference_failed"}
    return {**tabular,"graph_baseline":graph}
