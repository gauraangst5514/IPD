"""
Damage Detector — Inference Wrapper

Wraps the trained YOLOv8 model and combines its output with the severity
estimator to produce a full damage assessment.

This is the primary inference entry point used by the ML service.
"""

import io
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

from ml.detection.severity import SeverityEstimator, DamageInstance


DEFAULT_WEIGHTS = "ml/weights/detection/cardd_yolov8/weights/best.pt"

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

    def __init__(self, weights_path: str = DEFAULT_WEIGHTS, device: str = "auto", conf: float = 0.25):
        from ultralytics import YOLO

        self.conf = conf
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

        # Load model — fall back to pretrained if no fine-tuned weights exist
        if Path(weights_path).exists():
            self.model = YOLO(weights_path)
            self.trained = True
            print(f"✅ Loaded fine-tuned CarDD model: {weights_path}")
        else:
            self.model = YOLO("yolov8s.pt")
            self.trained = False
            print(f"⚠️  No fine-tuned weights at {weights_path}. Using base YOLOv8 "
                  f"(will not detect car damage correctly until trained).")

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

        # Run inference
        results = self.model.predict(
            source=np.array(image),
            conf=self.conf,
            device=self.device,
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

        # Generate annotated image (boxes drawn)
        annotated_bytes = self._annotate(result)

        return {
            "damage_detected": len(instances) > 0,
            "num_instances": len(instances),
            "detections": detections_out,
            "severity": severity_result.severity,
            "severity_score": severity_result.score,
            "severity_reasoning": severity_result.reasoning,
            "primary_damage_type": primary_type,
            "annotated_image": annotated_bytes,
        }

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
