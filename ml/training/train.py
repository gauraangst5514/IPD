"""
Training Script for IntelliClaim Damage Classifier

Usage:
    python -m ml.training.train --data_dir data/car_damage --epochs 30 --batch_size 16

Or with the convenience script:
    python train_model.py
"""

import argparse
import os
import time
from pathlib import Path
from typing import Optional

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from ml.damage.model import DamageClassifier
from ml.training.dataset import create_dataloaders


class MultiTaskLoss(nn.Module):
    """
    Combined loss for multi-task damage classification.

    Weighted sum of:
    - Binary cross-entropy for damage detection
    - Cross-entropy for damage type classification
    - Cross-entropy for severity classification

    Severity and type losses are only computed for damaged images.
    """

    def __init__(self, damage_weight: float = 1.0, type_weight: float = 1.0, severity_weight: float = 1.5):
        super().__init__()
        self.damage_weight = damage_weight
        self.type_weight = type_weight
        self.severity_weight = severity_weight  # Severity matters most for cost estimation

        self.bce_loss = nn.BCELoss()
        self.ce_loss = nn.CrossEntropyLoss()

    def forward(self, outputs: dict[str, torch.Tensor], targets: dict[str, torch.Tensor]) -> dict[str, torch.Tensor]:
        # Damage detection loss (binary)
        damage_loss = self.bce_loss(
            outputs["damage_present"].squeeze(),
            targets["damage_present"],
        )

        # Only compute type/severity loss for damaged images
        damage_mask = targets["damage_present"] > 0.5
        if damage_mask.sum() > 0:
            type_loss = self.ce_loss(
                outputs["damage_type"][damage_mask],
                targets["damage_type"][damage_mask],
            )
            severity_loss = self.ce_loss(
                outputs["severity"][damage_mask],
                targets["severity"][damage_mask],
            )
        else:
            type_loss = torch.tensor(0.0, device=damage_loss.device)
            severity_loss = torch.tensor(0.0, device=damage_loss.device)

        total_loss = (
            self.damage_weight * damage_loss
            + self.type_weight * type_loss
            + self.severity_weight * severity_loss
        )

        return {
            "total": total_loss,
            "damage": damage_loss,
            "type": type_loss,
            "severity": severity_loss,
        }


def compute_accuracy(outputs: dict[str, torch.Tensor], targets: dict[str, torch.Tensor]) -> dict[str, float]:
    """Compute accuracy for each task."""
    with torch.no_grad():
        # Damage detection accuracy
        damage_preds = (outputs["damage_present"].squeeze() > 0.5).float()
        damage_acc = (damage_preds == targets["damage_present"]).float().mean().item()

        # Type and severity accuracy (only on damaged images)
        damage_mask = targets["damage_present"] > 0.5
        if damage_mask.sum() > 0:
            type_preds = outputs["damage_type"][damage_mask].argmax(dim=1)
            type_acc = (type_preds == targets["damage_type"][damage_mask]).float().mean().item()

            severity_preds = outputs["severity"][damage_mask].argmax(dim=1)
            severity_acc = (severity_preds == targets["severity"][damage_mask]).float().mean().item()
        else:
            type_acc = 0.0
            severity_acc = 0.0

    return {"damage_acc": damage_acc, "type_acc": type_acc, "severity_acc": severity_acc}


def train_one_epoch(
    model: DamageClassifier,
    dataloader: DataLoader,
    criterion: MultiTaskLoss,
    optimizer: torch.optim.Optimizer,
    device: str,
) -> dict[str, float]:
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    total_damage_acc = 0.0
    total_type_acc = 0.0
    total_severity_acc = 0.0
    num_batches = 0

    for images, targets in dataloader:
        images = images.to(device)
        targets = {k: v.to(device) for k, v in targets.items()}

        # Forward pass
        outputs = model(images)
        losses = criterion(outputs, targets)

        # Backward pass
        optimizer.zero_grad()
        losses["total"].backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()

        # Track metrics
        acc = compute_accuracy(outputs, targets)
        total_loss += losses["total"].item()
        total_damage_acc += acc["damage_acc"]
        total_type_acc += acc["type_acc"]
        total_severity_acc += acc["severity_acc"]
        num_batches += 1

    return {
        "loss": total_loss / num_batches,
        "damage_acc": total_damage_acc / num_batches,
        "type_acc": total_type_acc / num_batches,
        "severity_acc": total_severity_acc / num_batches,
    }


@torch.no_grad()
def validate(
    model: DamageClassifier,
    dataloader: DataLoader,
    criterion: MultiTaskLoss,
    device: str,
) -> dict[str, float]:
    """Validate the model."""
    model.eval()
    total_loss = 0.0
    total_damage_acc = 0.0
    total_type_acc = 0.0
    total_severity_acc = 0.0
    num_batches = 0

    for images, targets in dataloader:
        images = images.to(device)
        targets = {k: v.to(device) for k, v in targets.items()}

        outputs = model(images)
        losses = criterion(outputs, targets)
        acc = compute_accuracy(outputs, targets)

        total_loss += losses["total"].item()
        total_damage_acc += acc["damage_acc"]
        total_type_acc += acc["type_acc"]
        total_severity_acc += acc["severity_acc"]
        num_batches += 1

    return {
        "loss": total_loss / max(num_batches, 1),
        "damage_acc": total_damage_acc / max(num_batches, 1),
        "type_acc": total_type_acc / max(num_batches, 1),
        "severity_acc": total_severity_acc / max(num_batches, 1),
    }


def train(
    data_dir: str,
    output_dir: str = "ml/weights",
    epochs: int = 30,
    batch_size: int = 16,
    learning_rate: float = 1e-4,
    num_workers: int = 4,
    device: str = "auto",
    resume_from: Optional[str] = None,
):
    """
    Full training loop.

    Args:
        data_dir: Root directory containing train/ and val/ subdirectories
        output_dir: Where to save model weights
        epochs: Number of training epochs
        batch_size: Batch size (reduce if OOM)
        learning_rate: Initial learning rate
        num_workers: DataLoader workers
        device: "auto", "cuda", "mps", or "cpu"
        resume_from: Path to checkpoint to resume from
    """
    # Setup device
    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"
    print(f"🖥️  Using device: {device}")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Create dataloaders
    train_dir = os.path.join(data_dir, "train")
    val_dir = os.path.join(data_dir, "val")

    if not os.path.exists(train_dir):
        raise FileNotFoundError(
            f"Training directory not found: {train_dir}\n"
            f"Expected structure:\n"
            f"  {data_dir}/\n"
            f"    train/\n"
            f"      minor_scratch/\n"
            f"      moderate_dent/\n"
            f"      severe_crack/\n"
            f"      ...\n"
            f"    val/\n"
            f"      (same structure)\n\n"
            f"Run 'python -m ml.training.prepare_data' to download and set up a dataset."
        )

    train_loader, val_loader = create_dataloaders(
        train_dir, val_dir, batch_size=batch_size, num_workers=num_workers
    )
    print(f"📊 Train: {len(train_loader.dataset)} samples, Val: {len(val_loader.dataset)} samples")

    # Create model
    model = DamageClassifier(pretrained=True)
    model = model.to(device)

    # Resume from checkpoint
    start_epoch = 0
    if resume_from and os.path.exists(resume_from):
        checkpoint = torch.load(resume_from, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        start_epoch = checkpoint.get("epoch", 0)
        print(f"📂 Resumed from checkpoint: {resume_from} (epoch {start_epoch})")

    # Loss, optimizer, scheduler
    criterion = MultiTaskLoss(severity_weight=1.5)
    optimizer = AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    # Training loop
    best_val_severity_acc = 0.0
    print(f"\n{'='*60}")
    print(f"🚀 Starting training for {epochs} epochs")
    print(f"{'='*60}\n")

    for epoch in range(start_epoch, epochs):
        epoch_start = time.time()

        # Train
        train_metrics = train_one_epoch(model, train_loader, criterion, optimizer, device)

        # Validate
        val_metrics = validate(model, val_loader, criterion, device)

        # Step scheduler
        scheduler.step()

        # Logging
        epoch_time = time.time() - epoch_start
        print(
            f"Epoch {epoch+1:3d}/{epochs} ({epoch_time:.1f}s) | "
            f"Train Loss: {train_metrics['loss']:.4f} | "
            f"Val Loss: {val_metrics['loss']:.4f} | "
            f"Val Damage Acc: {val_metrics['damage_acc']:.3f} | "
            f"Val Type Acc: {val_metrics['type_acc']:.3f} | "
            f"Val Severity Acc: {val_metrics['severity_acc']:.3f}"
        )

        # Save best model (based on severity accuracy — our most important metric)
        if val_metrics["severity_acc"] > best_val_severity_acc:
            best_val_severity_acc = val_metrics["severity_acc"]
            save_path = os.path.join(output_dir, "best_model.pth")
            torch.save(
                {
                    "epoch": epoch + 1,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                    "val_metrics": val_metrics,
                    "train_metrics": train_metrics,
                },
                save_path,
            )
            print(f"  ✅ New best model saved! (severity_acc: {best_val_severity_acc:.3f})")

        # Save periodic checkpoint
        if (epoch + 1) % 10 == 0:
            checkpoint_path = os.path.join(output_dir, f"checkpoint_epoch_{epoch+1}.pth")
            torch.save(
                {
                    "epoch": epoch + 1,
                    "model_state_dict": model.state_dict(),
                    "optimizer_state_dict": optimizer.state_dict(),
                },
                checkpoint_path,
            )

    # Save final model
    final_path = os.path.join(output_dir, "final_model.pth")
    torch.save({"model_state_dict": model.state_dict(), "epoch": epochs}, final_path)

    print(f"\n{'='*60}")
    print(f"🏁 Training complete!")
    print(f"   Best severity accuracy: {best_val_severity_acc:.3f}")
    print(f"   Models saved to: {output_dir}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train IntelliClaim Damage Classifier")
    parser.add_argument("--data_dir", type=str, default="data/car_damage", help="Dataset root directory")
    parser.add_argument("--output_dir", type=str, default="ml/weights", help="Output directory for weights")
    parser.add_argument("--epochs", type=int, default=30, help="Number of epochs")
    parser.add_argument("--batch_size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--workers", type=int, default=4, help="DataLoader workers")
    parser.add_argument("--device", type=str, default="auto", help="Device: auto/cuda/mps/cpu")
    parser.add_argument("--resume", type=str, default=None, help="Checkpoint to resume from")

    args = parser.parse_args()

    train(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        num_workers=args.workers,
        device=args.device,
        resume_from=args.resume,
    )
