#!/usr/bin/env python3
"""
Dataset Download & Setup for IntelliClaim

This script handles downloading and organizing car damage datasets.

=== RECOMMENDED APPROACH ===

The best dataset for this project is the Kaggle "Car Damage Severity" dataset.
Here's how to set it up:

Option A: Via Kaggle API (automated)
    1. Create a Kaggle account at https://www.kaggle.com
    2. Go to Settings → API → Create New Token (downloads kaggle.json)
    3. Place it at ~/.kaggle/kaggle.json
    4. Run: pip install kaggle
    5. Run: python data/download_dataset.py --method kaggle

Option B: Manual Download (no API needed)
    1. Go to https://www.kaggle.com/datasets/lplenern/car-damage-severity-dataset
    2. Click "Download" (sign in required, but free)
    3. Extract the zip to data/raw/severity/
    4. Run: python data/download_dataset.py --method manual --input_dir data/raw/severity

Option C: Multiple Datasets Combined
    1. Download severity dataset (above)
    2. Also download: https://www.kaggle.com/datasets/anujms/car-damage-detection
       (gives you "damaged" vs "not damaged" — useful for the binary classification head)
    3. Extract both to data/raw/
    4. Run: python data/download_dataset.py --method combine

=== DATASET DETAILS ===

Primary: "Car Damage Severity Dataset" by lplenern
    - 3 classes: minor, moderate, severe
    - ~1500 images total
    - Good quality, varied angles

Secondary: "Car Damage Detection" by anujms
    - 2 classes: damaged, whole
    - ~900 images
    - Adds negative examples (undamaged cars)

After setup, the directory structure will be:
    data/car_damage/
    ├── train/ (80%)
    │   ├── no_damage/
    │   ├── minor_scratch/
    │   ├── minor_dent/
    │   ├── moderate_scratch/
    │   ├── moderate_dent/
    │   ├── moderate_crack/
    │   ├── moderate_bumper/
    │   ├── severe_dent/
    │   ├── severe_crack/
    │   ├── severe_shatter/
    │   ├── severe_bumper/
    │   └── severe_panel/
    └── val/ (20%)
        └── (same structure)
"""

import argparse
import os
import sys
import shutil
import random
import subprocess
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_ROOT = Path("data/car_damage")
RAW_ROOT = Path("data/raw")

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

# Kaggle dataset identifiers
KAGGLE_DATASETS = {
    "severity": "lplenern/car-damage-severity-dataset",
    "detection": "anujms/car-damage-detection",
    "severity_v2": "prajwalbhamere/car-damage-severity-dataset",
}


def create_directory_structure():
    """Create the training directory structure."""
    for split in ["train", "val"]:
        for cls in CLASSES:
            (DATA_ROOT / split / cls).mkdir(parents=True, exist_ok=True)
    print("✅ Created directory structure")


def install_kaggle_cli():
    """Install kaggle CLI if not present."""
    try:
        import kaggle  # noqa: F401
        return True
    except ImportError:
        print("📦 Installing kaggle CLI...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "kaggle"], 
                      capture_output=True)
        return True


def check_kaggle_auth():
    """Check if Kaggle API credentials are configured."""
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if not kaggle_json.exists():
        print("\n" + "="*60)
        print("⚠️  Kaggle API credentials not found!")
        print("="*60)
        print("\nTo set up Kaggle API access:")
        print("  1. Go to https://www.kaggle.com/settings")
        print("  2. Scroll to 'API' section")
        print("  3. Click 'Create New Token'")
        print("  4. This downloads kaggle.json")
        print(f"  5. Move it to: {kaggle_json}")
        print(f"  6. Run: chmod 600 {kaggle_json}")
        print("\nAlternatively, use --method manual after downloading manually.")
        print("="*60 + "\n")
        return False
    return True


def download_kaggle(dataset_key: str = "severity"):
    """Download dataset from Kaggle."""
    if not check_kaggle_auth():
        return False

    install_kaggle_cli()

    dataset_id = KAGGLE_DATASETS[dataset_key]
    output_dir = RAW_ROOT / f"kaggle_{dataset_key}"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📥 Downloading {dataset_id}...")
    result = subprocess.run(
        ["kaggle", "datasets", "download", "-d", dataset_id, "-p", str(output_dir), "--unzip"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        # Try with python -m kaggle
        result = subprocess.run(
            [sys.executable, "-m", "kaggle", "datasets", "download", "-d", dataset_id, 
             "-p", str(output_dir), "--unzip"],
            capture_output=True, text=True,
        )

    if result.returncode != 0:
        print(f"❌ Download failed: {result.stderr}")
        print(f"\nTry manually downloading from:")
        print(f"   https://www.kaggle.com/datasets/{dataset_id}")
        return False

    print(f"✅ Downloaded to {output_dir}")
    return True


def find_image_dirs(root: Path) -> dict:
    """
    Recursively find directories containing images and categorize them.
    Returns dict mapping category -> list of image paths.
    """
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    categories = {}

    for dirpath, dirnames, filenames in os.walk(root):
        images = [
            Path(dirpath) / f for f in filenames 
            if Path(f).suffix.lower() in image_extensions
        ]
        if images:
            dir_name = Path(dirpath).name.lower()
            categories[dir_name] = images

    return categories


def organize_severity_data(raw_dir: Path):
    """
    Organize a severity-based dataset (minor/moderate/severe folders).
    
    Handles various folder structures found in Kaggle datasets.
    """
    print(f"\n📂 Scanning {raw_dir} for image directories...")
    categories = find_image_dirs(raw_dir)

    if not categories:
        print(f"  ⚠️  No images found in {raw_dir}")
        return 0

    print(f"  Found directories: {list(categories.keys())}")
    total_organized = 0

    # Map found directories to our target classes
    for dir_name, images in categories.items():
        target_classes = map_directory_to_classes(dir_name)
        if not target_classes:
            print(f"  ⏭️  Skipping '{dir_name}' (unrecognized)")
            continue

        # Shuffle and split
        random.shuffle(images)
        split_idx = int(len(images) * 0.8)
        train_images = images[:split_idx]
        val_images = images[split_idx:]

        # Copy to target directories
        for i, img in enumerate(train_images):
            target_class = target_classes[i % len(target_classes)]
            dest = DATA_ROOT / "train" / target_class / img.name
            if not dest.exists():
                shutil.copy2(img, dest)
                total_organized += 1

        for i, img in enumerate(val_images):
            target_class = target_classes[i % len(target_classes)]
            dest = DATA_ROOT / "val" / target_class / img.name
            if not dest.exists():
                shutil.copy2(img, dest)
                total_organized += 1

        print(f"  ✅ '{dir_name}' → {target_classes} ({len(images)} images)")

    return total_organized


def map_directory_to_classes(dir_name: str) -> Optional[list]:
    """Map a found directory name to our target classification classes."""
    dir_name = dir_name.lower().strip()

    # Direct severity mapping
    severity_map = {
        "minor": ["minor_scratch", "minor_dent"],
        "moderate": ["moderate_dent", "moderate_scratch", "moderate_crack", "moderate_bumper"],
        "severe": ["severe_dent", "severe_crack", "severe_bumper", "severe_panel"],
    }

    # Direct type mapping
    type_map = {
        "scratch": ["minor_scratch", "moderate_scratch"],
        "dent": ["minor_dent", "moderate_dent", "severe_dent"],
        "crack": ["moderate_crack", "severe_crack"],
        "shatter": ["severe_shatter"],
        "bumper": ["moderate_bumper", "severe_bumper"],
        "panel": ["severe_panel"],
    }

    # No damage
    no_damage_names = {"whole", "undamaged", "no_damage", "not_damaged", "pristine", "clean", "intact"}

    # Combined labels (e.g., "minor_scratch")
    if dir_name in CLASSES:
        return [dir_name]

    if dir_name in severity_map:
        return severity_map[dir_name]

    if dir_name in type_map:
        return type_map[dir_name]

    if dir_name in no_damage_names:
        return ["no_damage"]

    # Handle "damaged" generically
    if dir_name in ("damaged", "damage"):
        return ["moderate_dent", "moderate_scratch", "severe_dent"]

    # Training/test/val split names - skip these, look inside
    if dir_name in ("train", "training", "test", "testing", "val", "validation", "data", "images"):
        return None

    return None


def organize_detection_data(raw_dir: Path):
    """Organize a binary detection dataset (damaged/whole)."""
    return organize_severity_data(raw_dir)


def print_dataset_stats():
    """Print statistics about the prepared dataset."""
    print(f"\n{'='*60}")
    print("📊 DATASET STATISTICS")
    print(f"{'='*60}")

    total_all = 0
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
        total_all += total

    print(f"\n  {'GRAND TOTAL':27s} {total_all:5d} images")
    print(f"{'='*60}")

    if total_all == 0:
        print("\n⚠️  No images found! Make sure you've downloaded the dataset.")
        print("   See instructions at the top of this file.")

    return total_all


def main():
    parser = argparse.ArgumentParser(
        description="Download and organize car damage dataset for IntelliClaim",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python data/download_dataset.py --method kaggle
  python data/download_dataset.py --method manual --input_dir data/raw/my_images
  python data/download_dataset.py --method manual --input_dir ~/Downloads/car-damage-severity-dataset
        """,
    )
    parser.add_argument(
        "--method",
        choices=["kaggle", "manual", "combine"],
        default="kaggle",
        help="Download method",
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        default=None,
        help="Input directory containing images (for manual method)",
    )
    parser.add_argument(
        "--dataset",
        choices=["severity", "detection", "severity_v2", "all"],
        default="all",
        help="Which Kaggle dataset to download",
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("🚗 IntelliClaim Dataset Preparation")
    print("="*60 + "\n")

    # Create directory structure
    create_directory_structure()

    if args.method == "kaggle":
        # Download from Kaggle
        if args.dataset == "all":
            datasets_to_download = ["severity", "detection"]
        else:
            datasets_to_download = [args.dataset]

        for ds in datasets_to_download:
            success = download_kaggle(ds)
            if success:
                raw_dir = RAW_ROOT / f"kaggle_{ds}"
                organize_severity_data(raw_dir)

    elif args.method == "manual":
        if not args.input_dir:
            print("❌ --input_dir is required for manual method")
            print("\nUsage:")
            print("  1. Download dataset manually from Kaggle")
            print("  2. Extract the zip file")
            print("  3. Run: python data/download_dataset.py --method manual --input_dir /path/to/extracted/folder")
            return

        input_path = Path(args.input_dir)
        if not input_path.exists():
            print(f"❌ Directory not found: {args.input_dir}")
            return

        organize_severity_data(input_path)

    elif args.method == "combine":
        # Organize all raw data directories
        if RAW_ROOT.exists():
            for raw_subdir in RAW_ROOT.iterdir():
                if raw_subdir.is_dir():
                    print(f"\nProcessing: {raw_subdir}")
                    organize_severity_data(raw_subdir)

    # Print final stats
    total = print_dataset_stats()

    if total > 0:
        print(f"\n✅ Dataset ready! Start training with:")
        print(f"   python train_model.py --train --data_dir data/car_damage")
        print(f"\n   Or for full pipeline:")
        print(f"   python train_model.py --train --epochs 30 --batch_size 16 --device auto")
    else:
        print(f"\n📋 SETUP INSTRUCTIONS:")
        print(f"{'='*60}")
        print(f"\n  Option 1 - Kaggle API (Recommended):")
        print(f"    1. pip install kaggle")
        print(f"    2. Get API token from https://www.kaggle.com/settings")
        print(f"    3. Save to ~/.kaggle/kaggle.json")
        print(f"    4. Run: python data/download_dataset.py --method kaggle")
        print(f"\n  Option 2 - Manual Download:")
        print(f"    1. Go to: https://www.kaggle.com/datasets/lplenern/car-damage-severity-dataset")
        print(f"    2. Download and extract the zip")
        print(f"    3. Run: python data/download_dataset.py --method manual --input_dir <extracted_folder>")
        print(f"\n  Option 3 - Use your own images:")
        print(f"    1. Organize images into folders: minor/ moderate/ severe/ (and optionally no_damage/)")
        print(f"    2. Run: python data/download_dataset.py --method manual --input_dir <your_folder>")
        print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
