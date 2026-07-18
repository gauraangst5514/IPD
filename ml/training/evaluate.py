"""
Model Evaluation Script

Evaluates a trained model on the validation set and generates:
- Per-class accuracy
- Confusion matrix
- Sample predictions with confidence scores

Usage:
    python -m ml.training.evaluate --weights ml/weights/best_model.pth --data_dir data/car_damage
"""

import argparse
import os
from collections import defaultdict

import torch
from torch.utils.data import DataLoader
from torchvision import transforms

from ml.damage.model import DamageClassifier
from ml.training.dataset import CarDamageDataset


def evaluate(weights_path: str, data_dir: str, device: str = "auto"):
    """Run full evaluation on validation set."""

    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    print(f"🖥️  Device: {device}")
    print(f"📂 Weights: {weights_path}")
    print(f"📁 Data: {data_dir}")

    # Load model
    model = DamageClassifier(pretrained=False)
    checkpoint = torch.load(weights_path, map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model = model.to(device)
    model.eval()

    if "val_metrics" in checkpoint:
        print(f"\n📊 Training metrics at save time:")
        for k, v in checkpoint["val_metrics"].items():
            print(f"   {k}: {v:.4f}")

    # Load validation data
    val_transform = transforms.Compose([
        transforms.Resize((380, 380)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    val_dir = os.path.join(data_dir, "val")
    dataset = CarDamageDataset(val_dir, transform=val_transform)
    dataloader = DataLoader(dataset, batch_size=16, shuffle=False, num_workers=4)

    # Run evaluation
    damage_correct = 0
    damage_total = 0
    type_correct = 0
    type_total = 0
    severity_correct = 0
    severity_total = 0

    # Per-class tracking
    severity_per_class = defaultdict(lambda: {"correct": 0, "total": 0})
    type_per_class = defaultdict(lambda: {"correct": 0, "total": 0})

    with torch.no_grad():
        for images, targets in dataloader:
            images = images.to(device)
            outputs = model(images)

            # Damage detection
            damage_preds = (outputs["damage_present"].squeeze() > 0.5).float().cpu()
            damage_correct += (damage_preds == targets["damage_present"]).sum().item()
            damage_total += len(targets["damage_present"])

            # Type & severity (only damaged images)
            mask = targets["damage_present"] > 0.5
            if mask.sum() > 0:
                type_preds = outputs["damage_type"][mask].argmax(dim=1).cpu()
                type_targets = targets["damage_type"][mask]
                type_correct += (type_preds == type_targets).sum().item()
                type_total += mask.sum().item()

                severity_preds = outputs["severity"][mask].argmax(dim=1).cpu()
                severity_targets = targets["severity"][mask]
                severity_correct += (severity_preds == severity_targets).sum().item()
                severity_total += mask.sum().item()

                # Per-class
                for pred, target in zip(severity_preds, severity_targets):
                    cls_name = DamageClassifier.SEVERITY_LEVELS[target.item()]
                    severity_per_class[cls_name]["total"] += 1
                    if pred == target:
                        severity_per_class[cls_name]["correct"] += 1

                for pred, target in zip(type_preds, type_targets):
                    cls_name = DamageClassifier.DAMAGE_TYPES[target.item()]
                    type_per_class[cls_name]["total"] += 1
                    if pred == target:
                        type_per_class[cls_name]["correct"] += 1

    # Print results
    print(f"\n{'='*60}")
    print("📊 EVALUATION RESULTS")
    print(f"{'='*60}")

    print(f"\n  Overall Accuracy:")
    print(f"    Damage Detection: {damage_correct}/{damage_total} = {damage_correct/max(damage_total,1)*100:.1f}%")
    print(f"    Damage Type:      {type_correct}/{type_total} = {type_correct/max(type_total,1)*100:.1f}%")
    print(f"    Severity:         {severity_correct}/{severity_total} = {severity_correct/max(severity_total,1)*100:.1f}%")

    print(f"\n  Per-Class Severity Accuracy:")
    for cls in DamageClassifier.SEVERITY_LEVELS:
        stats = severity_per_class[cls]
        acc = stats["correct"] / max(stats["total"], 1) * 100
        print(f"    {cls:12s}: {stats['correct']:4d}/{stats['total']:4d} = {acc:.1f}%")

    print(f"\n  Per-Class Damage Type Accuracy:")
    for cls in DamageClassifier.DAMAGE_TYPES:
        stats = type_per_class[cls]
        acc = stats["correct"] / max(stats["total"], 1) * 100
        print(f"    {cls:12s}: {stats['correct']:4d}/{stats['total']:4d} = {acc:.1f}%")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate trained model")
    parser.add_argument("--weights", type=str, default="ml/weights/best_model.pth")
    parser.add_argument("--data_dir", type=str, default="data/car_damage")
    parser.add_argument("--device", type=str, default="auto")
    args = parser.parse_args()

    evaluate(args.weights, args.data_dir, args.device)
