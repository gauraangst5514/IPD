"""
Dataset Preparation Script

Downloads and organizes car damage datasets into the folder structure
expected by the training script.

Supported sources:
1. Kaggle datasets (requires kaggle CLI configured)
2. Manual setup with your own images

Usage:
    python -m ml.training.prepare_data --source kaggle
    python -m ml.training.prepare_data --source manual --input_dir /path/to/raw/images

After running, your data directory will look like:
    data/car_damage/
    ├── train/
    │   ├── minor_scratch/
    │   ├── minor_dent/
    │   ├── moderate_scratch/
    │   ├── moderate_dent/
    │   ├── moderate_crack/
    │   ├── moderate_bumper/
    │   ├── severe_dent/
    │   ├── severe_crack/
    │   ├── severe_shatter/
    │   └── no_damage/
    └── val/
        └── (same structure, ~20% of data)
"""

import os
import shutil
import random
import argparse
from pathlib import Path


DATA_ROOT = Path("data/car_damage")
CLASSES = [
    "no_damage",
    "minor_scratch",
    "minor_dent",
    "moderate_scratch",
    "moderate_dent",
    "moderate_crack",
    "moderate_bumper",
    "severe_dent",
    "severe_crack",
    "severe_shatter",
    "severe_bumper",
    "severe_panel",
]


def create_directory_structure():
    """Create the expected folder structure."""
    for split in ["train", "val"]:
        for cls in CLASSES:
            (DATA_ROOT / split / cls).mkdir(parents=True, exist_ok=True)
    print(f"✅ Created directory structure at {DATA_ROOT}")


def download_kaggle_dataset():
    """
    Download car damage dataset from Kaggle.

    Requires:
        pip install kaggle
        ~/.kaggle/kaggle.json with your API key

    Popular datasets:
        - "lplenern/car-damage-severity"  (damage severity: minor/moderate/severe)
        - "anujms/car-damage-detection"   (damaged vs whole)
    """
    print("📥 Downloading dataset from Kaggle...")
    print("   Make sure you have:")
    print("   1. pip install kaggle")
    print("   2. ~/.kaggle/kaggle.json configured")
    print("")

    try:
        os.system("kaggle datasets download -d lplenern/car-damage-severity -p data/raw/kaggle_severity --unzip")
        print("✅ Downloaded car-damage-severity dataset")
    except Exception as e:
        print(f"⚠️  Kaggle download failed: {e}")
        print("   You can manually download from:")
        print("   https://www.kaggle.com/datasets/lplenern/car-damage-severity")
        return False

    try:
        os.system("kaggle datasets download -d anujms/car-damage-detection -p data/raw/kaggle_detection --unzip")
        print("✅ Downloaded car-damage-detection dataset")
    except Exception:
        pass

    return True


def organize_severity_dataset(raw_dir: str = "data/raw/kaggle_severity"):
    """
    Organize the Kaggle car-damage-severity dataset.

    This dataset typically has:
        minor/
        moderate/
        severe/
    """
    raw_path = Path(raw_dir)
    if not raw_path.exists():
        print(f"⚠️  Raw directory not found: {raw_dir}")
        return

    # Map severity folders to our classes
    severity_mapping = {
        "minor": ["minor_scratch", "minor_dent"],  # We'll randomly assign type
        "moderate": ["moderate_dent", "moderate_scratch", "moderate_crack"],
        "severe": ["severe_dent", "severe_crack", "severe_bumper"],
    }

    for severity_folder in raw_path.iterdir():
        if not severity_folder.is_dir():
            continue

        severity = severity_folder.name.lower()
        if severity not in severity_mapping:
            continue

        target_classes = severity_mapping[severity]
        images = [f for f in severity_folder.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")]

        # Shuffle and split 80/20
        random.shuffle(images)
        split_idx = int(len(images) * 0.8)
        train_images = images[:split_idx]
        val_images = images[split_idx:]

        # Distribute across target classes
        for i, img in enumerate(train_images):
            target_class = target_classes[i % len(target_classes)]
            dest = DATA_ROOT / "train" / target_class / img.name
            shutil.copy2(img, dest)

        for i, img in enumerate(val_images):
            target_class = target_classes[i % len(target_classes)]
            dest = DATA_ROOT / "val" / target_class / img.name
            shutil.copy2(img, dest)

    print(f"✅ Organized severity dataset into {DATA_ROOT}")


def organize_detection_dataset(raw_dir: str = "data/raw/kaggle_detection"):
    """
    Organize the Kaggle car-damage-detection dataset.

    This dataset typically has:
        damaged/
        whole/ (undamaged)
    """
    raw_path = Path(raw_dir)
    if not raw_path.exists():
        return

    # Handle 'whole' / 'not damaged' images
    for folder_name in ["whole", "not_damaged", "undamaged"]:
        folder = raw_path / folder_name
        if not folder.exists():
            continue

        images = [f for f in folder.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
        random.shuffle(images)
        split_idx = int(len(images) * 0.8)

        for img in images[:split_idx]:
            shutil.copy2(img, DATA_ROOT / "train" / "no_damage" / img.name)
        for img in images[split_idx:]:
            shutil.copy2(img, DATA_ROOT / "val" / "no_damage" / img.name)

    print(f"✅ Organized detection dataset")


def organize_manual_dataset(input_dir: str):
    """
    Organize a manually collected dataset.

    Expected input structure (flexible):
        input_dir/
        ├── damaged/    OR  scratch/  OR  minor/
        │   └── *.jpg       └── *.jpg     └── *.jpg
        └── undamaged/
            └── *.jpg
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"⚠️  Input directory not found: {input_dir}")
        return

    for folder in input_path.iterdir():
        if not folder.is_dir():
            continue

        folder_name = folder.name.lower()
        images = [f for f in folder.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]

        if not images:
            continue

        # Determine target class
        if folder_name in ("whole", "undamaged", "no_damage", "clean"):
            target_class = "no_damage"
        elif "_" in folder_name:
            target_class = folder_name if folder_name in CLASSES else "moderate_dent"
        elif folder_name in ("minor", "moderate", "severe"):
            target_class = f"{folder_name}_dent"
        elif folder_name in ("scratch", "dent", "crack", "bumper", "panel", "shatter"):
            target_class = f"moderate_{folder_name}"
        else:
            target_class = "moderate_dent"
            print(f"  ⚠️  Unknown folder '{folder_name}', mapping to '{target_class}'")

        # Split and copy
        random.shuffle(images)
        split_idx = int(len(images) * 0.8)

        for img in images[:split_idx]:
            dest = DATA_ROOT / "train" / target_class / img.name
            shutil.copy2(img, dest)
        for img in images[split_idx:]:
            dest = DATA_ROOT / "val" / target_class / img.name
            shutil.copy2(img, dest)

        print(f"  📂 {folder_name} → {target_class} ({len(images)} images)")


def print_dataset_stats():
    """Print statistics about the prepared dataset."""
    print(f"\n{'='*50}")
    print("📊 Dataset Statistics")
    print(f"{'='*50}")

    for split in ["train", "val"]:
        split_dir = DATA_ROOT / split
        if not split_dir.exists():
            continue

        total = 0
        print(f"\n  {split.upper()}:")
        for cls_dir in sorted(split_dir.iterdir()):
            if cls_dir.is_dir():
                count = len([f for f in cls_dir.iterdir() if f.is_file()])
                if count > 0:
                    print(f"    {cls_dir.name:25s} {count:5d} images")
                total += count
        print(f"    {'TOTAL':25s} {total:5d} images")

    print(f"\n{'='*50}")


def create_sample_dataset():
    """
    Create a tiny sample dataset with placeholder images for testing.

    This lets you verify the training pipeline works before downloading
    a real dataset.
    """
    print("🧪 Creating sample dataset for pipeline testing...")

    from PIL import Image
    import numpy as np

    create_directory_structure()

    for split in ["train", "val"]:
        for cls in CLASSES:
            num_images = 20 if split == "train" else 5

            for i in range(num_images):
                # Create a random colored image (simulating variety)
                color = np.random.randint(50, 200, size=3)
                img_array = np.full((224, 224, 3), color, dtype=np.uint8)

                # Add some noise to simulate real images
                noise = np.random.randint(-20, 20, size=(224, 224, 3))
                img_array = np.clip(img_array.astype(int) + noise, 0, 255).astype(np.uint8)

                img = Image.fromarray(img_array)
                img.save(DATA_ROOT / split / cls / f"sample_{i:04d}.jpg")

    print(f"✅ Sample dataset created at {DATA_ROOT}")
    print("   ⚠️  These are RANDOM images — only for testing the pipeline!")
    print("   Replace with real data before actual training.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare training dataset")
    parser.add_argument(
        "--source",
        choices=["kaggle", "manual", "sample"],
        default="sample",
        help="Data source: kaggle (download), manual (organize existing), sample (tiny test set)",
    )
    parser.add_argument("--input_dir", type=str, default=None, help="Input directory for manual mode")
    args = parser.parse_args()

    # Always create directory structure
    create_directory_structure()

    if args.source == "kaggle":
        success = download_kaggle_dataset()
        if success:
            organize_severity_dataset()
            organize_detection_dataset()
    elif args.source == "manual":
        if not args.input_dir:
            print("❌ --input_dir required for manual mode")
            exit(1)
        organize_manual_dataset(args.input_dir)
    elif args.source == "sample":
        create_sample_dataset()

    print_dataset_stats()
    print("\n✅ Dataset preparation complete!")
    print(f"   Next step: python -m ml.training.train --data_dir {DATA_ROOT}")
