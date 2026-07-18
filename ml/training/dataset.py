"""
Dataset Module for Vehicle Damage Classification

Supports two dataset structures:

1. Folder-based (easiest to set up):
   data/
   ├── train/
   │   ├── minor_scratch/
   │   ├── minor_dent/
   │   ├── moderate_scratch/
   │   ├── moderate_dent/
   │   ├── moderate_crack/
   │   ├── severe_dent/
   │   ├── severe_crack/
   │   ├── severe_shatter/
   │   └── no_damage/
   └── val/
       └── (same structure)

2. CSV-based (more flexible):
   data/images/  (all images in one folder)
   data/labels.csv  (columns: filename, damage_type, severity)

The label encodes BOTH damage type and severity:
  - "minor_scratch" → severity=minor, type=scratch
  - "severe_dent" → severity=severe, type=dent
  - "no_damage" → severity=none, type=none
"""

import os
import csv
from pathlib import Path
from typing import Optional

import torch
from torch.utils.data import Dataset, DataLoader
from PIL import Image
from torchvision import transforms

from ml.damage.model import DamageClassifier


# === Label Mapping ===
DAMAGE_TYPES = DamageClassifier.DAMAGE_TYPES  # ["scratch", "dent", "crack", "shatter", "bumper", "panel"]
SEVERITY_LEVELS = DamageClassifier.SEVERITY_LEVELS  # ["minor", "moderate", "severe"]


def parse_folder_label(folder_name: str) -> dict:
    """
    Parse a folder name like 'moderate_dent' into damage type and severity.

    Returns:
        {
            "damage_present": 1 or 0,
            "damage_type_idx": int (index into DAMAGE_TYPES),
            "severity_idx": int (index into SEVERITY_LEVELS),
        }
    """
    folder_name = folder_name.lower().strip()

    if folder_name in ("no_damage", "undamaged", "whole", "clean"):
        return {"damage_present": 0, "damage_type_idx": 0, "severity_idx": 0}

    # Try parsing as "severity_type" format
    parts = folder_name.split("_", 1)
    if len(parts) == 2:
        severity_str, type_str = parts
        if severity_str in SEVERITY_LEVELS and type_str in DAMAGE_TYPES:
            return {
                "damage_present": 1,
                "damage_type_idx": DAMAGE_TYPES.index(type_str),
                "severity_idx": SEVERITY_LEVELS.index(severity_str),
            }

    # Try parsing as just damage type (default to moderate)
    if folder_name in DAMAGE_TYPES:
        return {
            "damage_present": 1,
            "damage_type_idx": DAMAGE_TYPES.index(folder_name),
            "severity_idx": 1,  # default moderate
        }

    # Try parsing as just severity (default to dent)
    if folder_name in SEVERITY_LEVELS:
        return {
            "damage_present": 1,
            "damage_type_idx": 1,  # default dent
            "severity_idx": SEVERITY_LEVELS.index(folder_name),
        }

    # Fallback: treat as damaged, moderate dent
    print(f"⚠️  Unknown label folder: '{folder_name}', defaulting to moderate_dent")
    return {"damage_present": 1, "damage_type_idx": 1, "severity_idx": 1}


class CarDamageDataset(Dataset):
    """
    PyTorch Dataset for car damage images.

    Loads images from a folder-based directory structure.
    """

    def __init__(
        self,
        root_dir: str,
        transform: Optional[transforms.Compose] = None,
        max_samples_per_class: Optional[int] = None,
    ):
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.samples: list[tuple[str, dict]] = []

        if not self.root_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {root_dir}")

        # Walk through class folders
        for class_folder in sorted(self.root_dir.iterdir()):
            if not class_folder.is_dir():
                continue

            label = parse_folder_label(class_folder.name)
            count = 0

            for img_file in class_folder.iterdir():
                if img_file.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
                    self.samples.append((str(img_file), label))
                    count += 1
                    if max_samples_per_class and count >= max_samples_per_class:
                        break

        print(f"📁 Loaded {len(self.samples)} samples from {root_dir}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        img_path, label = self.samples[idx]

        # Load image
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"⚠️  Failed to load {img_path}: {e}")
            # Return a blank image on failure
            image = Image.new("RGB", (380, 380), (128, 128, 128))

        if self.transform:
            image = self.transform(image)

        # Convert labels to tensors
        targets = {
            "damage_present": torch.tensor(label["damage_present"], dtype=torch.float32),
            "damage_type": torch.tensor(label["damage_type_idx"], dtype=torch.long),
            "severity": torch.tensor(label["severity_idx"], dtype=torch.long),
        }

        return image, targets


class CSVCarDamageDataset(Dataset):
    """
    Dataset loaded from a CSV file.

    CSV format:
        filename,damage_type,severity
        img001.jpg,dent,moderate
        img002.jpg,scratch,minor
        img003.jpg,none,none
    """

    def __init__(
        self,
        csv_path: str,
        images_dir: str,
        transform: Optional[transforms.Compose] = None,
    ):
        self.images_dir = Path(images_dir)
        self.transform = transform
        self.samples: list[tuple[str, dict]] = []

        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = row["filename"]
                damage_type = row.get("damage_type", "dent").lower()
                severity = row.get("severity", "moderate").lower()

                img_path = str(self.images_dir / filename)
                if not os.path.exists(img_path):
                    continue

                if damage_type in ("none", "no_damage", ""):
                    label = {"damage_present": 0, "damage_type_idx": 0, "severity_idx": 0}
                else:
                    type_idx = DAMAGE_TYPES.index(damage_type) if damage_type in DAMAGE_TYPES else 1
                    sev_idx = SEVERITY_LEVELS.index(severity) if severity in SEVERITY_LEVELS else 1
                    label = {"damage_present": 1, "damage_type_idx": type_idx, "severity_idx": sev_idx}

                self.samples.append((img_path, label))

        print(f"📁 Loaded {len(self.samples)} samples from CSV: {csv_path}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        img_path, label = self.samples[idx]

        try:
            image = Image.open(img_path).convert("RGB")
        except Exception:
            image = Image.new("RGB", (380, 380), (128, 128, 128))

        if self.transform:
            image = self.transform(image)

        targets = {
            "damage_present": torch.tensor(label["damage_present"], dtype=torch.float32),
            "damage_type": torch.tensor(label["damage_type_idx"], dtype=torch.long),
            "severity": torch.tensor(label["severity_idx"], dtype=torch.long),
        }

        return image, targets


def create_dataloaders(
    train_dir: str,
    val_dir: str,
    batch_size: int = 16,
    num_workers: int = 4,
    max_samples_per_class: Optional[int] = None,
) -> tuple[DataLoader, DataLoader]:
    """
    Create training and validation DataLoaders.

    Uses standard augmentation for training and simple resize for validation.
    """
    train_transform = transforms.Compose([
        transforms.Resize((400, 400)),
        transforms.RandomCrop((380, 380)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2, hue=0.1),
        transforms.RandomAffine(degrees=0, translate=(0.1, 0.1), scale=(0.9, 1.1)),
        transforms.RandomPerspective(distortion_scale=0.2, p=0.3),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        transforms.RandomErasing(p=0.1),
    ])

    val_transform = transforms.Compose([
        transforms.Resize((380, 380)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    train_dataset = CarDamageDataset(
        train_dir, transform=train_transform, max_samples_per_class=max_samples_per_class
    )
    val_dataset = CarDamageDataset(val_dir, transform=val_transform)

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )

    return train_loader, val_loader
