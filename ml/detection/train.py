"""
YOLOv8 Training Script for CarDD Damage Detection

Trains a YOLOv8 object detection model to localize and classify the 6 CarDD
damage categories. Uses transfer learning from COCO-pretrained weights.

Usage:
    python -m ml.detection.train --epochs 50
    python -m ml.detection.train --epochs 100 --model yolov8m.pt --batch 16
    python -m ml.detection.train --epochs 30 --device mps   # Apple Silicon

Model sizes (speed vs accuracy tradeoff):
    yolov8n.pt  - nano (fastest, lowest accuracy) - good for CPU/demo
    yolov8s.pt  - small (balanced) - RECOMMENDED for this project
    yolov8m.pt  - medium (slower, more accurate)
    yolov8l.pt  - large
"""

import argparse
import os
from pathlib import Path

DATA_YAML = Path("data/cardd_yolo/data.yaml")
OUTPUT_DIR = Path("ml/weights/detection").resolve()


def train(
    model_size: str = "yolov8s.pt",
    epochs: int = 50,
    batch: int = 16,
    imgsz: int = 640,
    device: str = "auto",
    patience: int = 20,
    resume: bool = False,
):
    """
    Train YOLOv8 on the CarDD dataset.

    Args:
        model_size: Pretrained model to start from (yolov8n/s/m/l.pt)
        epochs: Number of training epochs
        batch: Batch size (reduce if out of memory)
        imgsz: Input image size
        device: "auto", "cuda", "mps", "cpu", or device index
        patience: Early stopping patience (epochs without improvement)
        resume: Resume from last checkpoint
    """
    from ultralytics import YOLO

    if not DATA_YAML.exists():
        raise FileNotFoundError(
            f"Dataset config not found: {DATA_YAML}\n"
            f"Run: python -m ml.detection.prepare_cardd"
        )

    # Resolve device
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

    print(f"{'='*60}")
    print(f"🚀 Training YOLOv8 on CarDD")
    print(f"{'='*60}")
    print(f"   Model:   {model_size}")
    print(f"   Epochs:  {epochs}")
    print(f"   Batch:   {batch}")
    print(f"   Device:  {device}")
    print(f"   Data:    {DATA_YAML}")
    print(f"{'='*60}\n")

    # Load pretrained model
    model = YOLO(model_size)

    # Train
    results = model.train(
        data=str(DATA_YAML.resolve()),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        patience=patience,
        resume=resume,
        project=str(OUTPUT_DIR),
        name="cardd_yolov8",
        exist_ok=True,
        # Augmentation (CarDD-appropriate)
        hsv_h=0.015,      # hue
        hsv_s=0.7,        # saturation
        hsv_v=0.4,        # brightness
        degrees=10.0,     # rotation (cars photographed at slight angles)
        translate=0.1,
        scale=0.5,
        fliplr=0.5,       # horizontal flip
        mosaic=1.0,       # mosaic augmentation
        # Optimizer
        optimizer="auto",
        lr0=0.01,
        verbose=True,
    )

    # The best model is saved automatically
    best_path = OUTPUT_DIR / "cardd_yolov8" / "weights" / "best.pt"
    print(f"\n{'='*60}")
    print(f"🏁 Training complete!")
    print(f"   Best model: {best_path}")
    print(f"{'='*60}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLOv8 on CarDD")
    parser.add_argument("--model", type=str, default="yolov8s.pt", help="Pretrained model")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--patience", type=int, default=20)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    train(
        model_size=args.model,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        patience=args.patience,
        resume=args.resume,
    )
