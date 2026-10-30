"""
Damage Detector — Inference Wrapper

Wraps the trained YOLOv8 model and combines its output with the severity
estimator to produce a full damage assessment.

This is the primary inference entry point used by the ML service.
"""

import io
import os
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from ml.detection.severity import SeverityEstimator, DamageInstance


DEFAULT_WEIGHTS = "ml/weights/detection/cardd_yolov8_v2/weights/best.pt"
FALLBACK_WEIGHTS = "ml/weights/detection/cardd_yolov8/weights/best.pt"

# YOLO class index -> human-readable label
CLASS_NAMES = {
    0: "dent",
    1: "scratch",
    2: "crack",
    3: "glass_shatter",
    4: "lamp_broken",
    5: "tire_flat",
}


class DamageDetector:
    """YOLOv8-based damage detector with severity estimation."""

    def __init__(self, weights_path: str = DEFAULT_WEIGHTS, device: str = "auto", conf: float = 0.20, iou: float = 0.5):
        self.model = None
        self.trained = False
        self.unavailable_reason = "checkpoint_missing"
        self.checkpoint_name = None
        self.conf = conf
        self.iou = iou
        self.severity_estimator = SeverityEstimator()

        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    device = 0
                elif torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"
            except ImportError:
                device = "cpu"
        self.device = device

        # Missing damage weights must never trigger a download of a generic
        # object detector whose class IDs would be misread as damage labels.
        root = Path(__file__).resolve().parents[2]
        configured = os.environ.get("DAMAGE_MODEL_PATH")
        candidates = [configured] if configured else [weights_path, FALLBACK_WEIGHTS]
        for candidate in candidates:
            path = Path(candidate).expanduser()
            path = path if path.is_absolute() else root / path
            if not path.is_file():
                continue
            try:
                from ultralytics import YOLO
                model = YOLO(str(path))
                names = model.names
                names = list(names.values()) if isinstance(names, dict) else list(names)
                normalized = [str(name).lower().replace(" ", "_") for name in names]
                if normalized != list(CLASS_NAMES.values()):
                    raise ValueError("Checkpoint classes do not match the six supported damage classes")
                self.model = model
                self.trained = True
                self.unavailable_reason = None
                self.checkpoint_name = path.name
            except Exception:
                self.unavailable_reason = "checkpoint_load_failed"
                logging.getLogger(__name__).exception("Could not load damage checkpoint")
            break

    def status(self):
        return {"available": self.trained, "reason": self.unavailable_reason,
                "checkpoint": self.checkpoint_name, "classes": list(CLASS_NAMES.values())}

    def detect(self, image_bytes: bytes) -> dict:
        """
        Run damage detection on an image.

        Returns a dict with:
        - detections: list of {label, confidence, bbox}
        - severity: minor/moderate/severe
        - severity_score: 0-1
        - severity_reasoning: explainable breakdown
        - primary_damage_type: for cost estimation
        - damage_detected: bool
        - annotated_image: bytes (PNG with boxes drawn)
        """
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if not self.trained:
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return {
                "damage_analysis_available": False, "damage_detected": None,
                "num_instances": 0, "detections": [], "severity": None,
                "severity_score": None, "severity_reasoning": {"reason": self.unavailable_reason},
                "primary_damage_type": None, "annotated_image": buffer.getvalue(),
            }
        img_array = np.array(image)

        # Preserve raw model confidence rather than manually boosting it
        # Use larger imgsz for better accuracy on detail
        results = self.model.predict(
            source=img_array,
            conf=self.conf,
            iou=self.iou,
            device=self.device,
            imgsz=800,        # Higher resolution inference
            augment=False,
            verbose=False,
        )

        result = results[0]

        # Parse detections
        instances: list[DamageInstance] = []
        detections_out = []

        for box in result.boxes:
            cls_idx = int(box.cls[0].item())
            confidence = float(box.conf[0].item())

            # YOLO gives xywhn (normalized center format)
            xywhn = box.xywhn[0].tolist()  # [x_center, y_center, w, h]

            label = CLASS_NAMES.get(cls_idx, f"class_{cls_idx}")

            instances.append(
                DamageInstance(label=label, confidence=confidence, bbox=tuple(xywhn))
            )
            detections_out.append({
                "label": label,
                "confidence": round(confidence, 4),
                "bbox": [round(v, 4) for v in xywhn],
            })

        # Estimate severity
        severity_result = self.severity_estimator.estimate(instances)
        primary_type = self.severity_estimator.primary_damage_type(instances)

        # Generate annotated image with raw model confidence
        annotated_bytes = self._annotate_with_detections(image, detections_out)

        return {
            "damage_analysis_available": True,
            "damage_detected": len(instances) > 0,
            "num_instances": len(instances),
            "detections": detections_out,
            "severity": severity_result.severity if instances else None,
            "severity_score": severity_result.score if instances else None,
            "severity_reasoning": severity_result.reasoning,
            "primary_damage_type": primary_type if instances else None,
            "annotated_image": annotated_bytes,
        }

    def _annotate_with_detections(self, image: Image.Image, detections: list[dict]) -> bytes:
        """Draw bounding boxes with correct confidence on the image."""
        import cv2

        img_array = np.array(image)
        h, w = img_array.shape[:2]

        for det in detections:
            cx, cy, bw, bh = det["bbox"]
            # Convert normalized xywh to pixel xyxy
            x1 = int((cx - bw / 2) * w)
            y1 = int((cy - bh / 2) * h)
            x2 = int((cx + bw / 2) * w)
            y2 = int((cy + bh / 2) * h)

            label = det["label"]
            conf = det["confidence"]

            # Draw box
            cv2.rectangle(img_array, (x1, y1), (x2, y2), (65, 105, 225), 2)

            # Draw label background
            text = f"{label} {conf:.2f}"
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(img_array, (x1, y1 - th - 8), (x1 + tw + 4, y1), (65, 105, 225), -1)
            cv2.putText(img_array, text, (x1 + 2, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

        img = Image.fromarray(img_array)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    def _annotate(self, result) -> bytes:
        """Draw bounding boxes on the image and return as PNG bytes."""
        # ultralytics provides a plot() method returning a BGR numpy array
        annotated_bgr = result.plot()
        # Convert BGR -> RGB
        annotated_rgb = annotated_bgr[:, :, ::-1]
        img = Image.fromarray(annotated_rgb)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def _iou(box1: list, box2: list) -> float:
        """Compute IoU between two xyxy boxes."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0
