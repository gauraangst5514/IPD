"""
CarDD Dataset Preparation for YOLOv8

Downloads the CarDD dataset from Hugging Face and converts it from
FiftyOne/COCO format into YOLOv8 detection format.

CarDD categories (6):
    0: dent
    1: scratch
    2: crack
    3: glass shatter
    4: lamp broken
    5: tire flat

Output structure (YOLOv8 format):
    data/cardd_yolo/
    ├── data.yaml
    ├── images/
    │   ├── train/
    │   ├── val/
    │   └── test/
    └── labels/
        ├── train/
        ├── val/
        └── test/

Each label file (e.g., 000001.txt) contains one line per damage instance:
    <class_id> <x_center> <y_center> <width> <height>   (all normalized 0-1)

Usage:
    python -m ml.detection.prepare_cardd
    python -m ml.detection.prepare_cardd --max_images 200   # quick test subset
"""

import argparse
import json
import os
import random
import shutil
from pathlib import Path
from typing import Optional

HF_REPO = "harpreetsahota/CarDD"

# CarDD category name -> YOLO class index
CATEGORY_TO_IDX = {
    "dent": 0,
    "scratch": 1,
    "crack": 2,
    "glass shatter": 3,
    "lamp broken": 4,
    "tire flat": 5,
}
IDX_TO_CATEGORY = {v: k for k, v in CATEGORY_TO_IDX.items()}

DATA_ROOT = Path("data/cardd_yolo")
RAW_ROOT = Path("data/raw/cardd_hf")


def download_dataset(max_images: Optional[int] = None):
    """
    Download CarDD from Hugging Face Hub.

    Downloads the full snapshot (images + samples.json annotations).
    """
    from huggingface_hub import snapshot_download

    print(f"📥 Downloading CarDD from Hugging Face ({HF_REPO})...")
    print("   This is ~1.5 GB and may take several minutes on first run.")

    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    # Download the dataset repo snapshot
    snapshot_download(
        repo_id=HF_REPO,
        repo_type="dataset",
        local_dir=str(RAW_ROOT),
        allow_patterns=["data/*.jpg", "data/*.png", "samples.json", "metadata.json"],
    )

    print(f"✅ Downloaded to {RAW_ROOT}")


def fiftyone_bbox_to_yolo(bbox: list) -> tuple:
    """
    Convert FiftyOne bounding box to YOLO format.

    FiftyOne format: [x_top_left, y_top_left, width, height]  (normalized 0-1)
    YOLO format:     [x_center, y_center, width, height]       (normalized 0-1)
    """
    x_tl, y_tl, w, h = bbox
    x_center = x_tl + w / 2.0
    y_center = y_tl + h / 2.0
    return x_center, y_center, w, h


def convert_to_yolo(
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    max_images: Optional[int] = None,
    seed: int = 42,
):
    """
    Convert the downloaded FiftyOne dataset to YOLOv8 format with train/val/test split.
    """
    samples_path = RAW_ROOT / "samples.json"
    if not samples_path.exists():
        raise FileNotFoundError(
            f"samples.json not found at {samples_path}. Run download first."
        )

    print("📖 Loading annotations...")
    with open(samples_path) as f:
        data = json.load(f)
    samples = data["samples"]

    # Filter to samples whose image actually exists
    valid_samples = []
    for s in samples:
        img_path = RAW_ROOT / s["filepath"]
        if img_path.exists():
            valid_samples.append(s)

    print(f"   {len(valid_samples)}/{len(samples)} images present on disk")

    # Optionally subset for quick testing
    random.seed(seed)
    random.shuffle(valid_samples)
    if max_images:
        valid_samples = valid_samples[:max_images]
        print(f"   Using subset of {len(valid_samples)} images")

    # Split
    n = len(valid_samples)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    splits = {
        "train": valid_samples[:n_train],
        "val": valid_samples[n_train : n_train + n_val],
        "test": valid_samples[n_train + n_val :],
    }

    # Create output directories
    for split in ["train", "val", "test"]:
        (DATA_ROOT / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATA_ROOT / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Process each split
    for split, split_samples in splits.items():
        print(f"\n🔄 Processing {split} split ({len(split_samples)} images)...")
        instances = 0

        for s in split_samples:
            src_img = RAW_ROOT / s["filepath"]
            img_name = Path(s["filepath"]).name
            stem = Path(img_name).stem

            # Copy image
            dst_img = DATA_ROOT / "images" / split / img_name
            if not dst_img.exists():
                shutil.copy2(src_img, dst_img)

            # Write YOLO label file
            label_lines = []
            detections = s.get("detections", {}).get("detections", [])
            for det in detections:
                label = det["label"]
                if label not in CATEGORY_TO_IDX:
                    continue
                cls_idx = CATEGORY_TO_IDX[label]
                x_c, y_c, w, h = fiftyone_bbox_to_yolo(det["bounding_box"])
                # Clamp to [0, 1]
                x_c, y_c = min(max(x_c, 0), 1), min(max(y_c, 0), 1)
                w, h = min(max(w, 0), 1), min(max(h, 0), 1)
                label_lines.append(f"{cls_idx} {x_c:.6f} {y_c:.6f} {w:.6f} {h:.6f}")
                instances += 1

            label_path = DATA_ROOT / "labels" / split / f"{stem}.txt"
            with open(label_path, "w") as lf:
                lf.write("\n".join(label_lines))

        print(f"   ✅ {len(split_samples)} images, {instances} instances")

    # Write data.yaml
    write_data_yaml()
    print_stats()


def write_data_yaml():
    """Write the YOLOv8 data.yaml config file."""
    yaml_content = f"""# CarDD Dataset — YOLOv8 config
# Auto-generated by prepare_cardd.py

path: {DATA_ROOT.resolve()}
train: images/train
val: images/val
test: images/test

# Classes (6 damage categories)
nc: 6
names:
  0: dent
  1: scratch
  2: crack
  3: glass_shatter
  4: lamp_broken
  5: tire_flat
"""
    yaml_path = DATA_ROOT / "data.yaml"
    with open(yaml_path, "w") as f:
        f.write(yaml_content)
    print(f"\n✅ Wrote {yaml_path}")


def print_stats():
    """Print dataset statistics."""
    print(f"\n{'='*60}")
    print("📊 CarDD YOLO Dataset Statistics")
    print(f"{'='*60}")

    for split in ["train", "val", "test"]:
        img_dir = DATA_ROOT / "images" / split
        label_dir = DATA_ROOT / "labels" / split
        if not img_dir.exists():
            continue

        num_images = len(list(img_dir.glob("*")))

        # Count instances per category
        from collections import Counter
        cat_counts = Counter()
        for label_file in label_dir.glob("*.txt"):
            with open(label_file) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        cls_idx = int(line.split()[0])
                        cat_counts[IDX_TO_CATEGORY[cls_idx]] += 1

        print(f"\n  {split.upper()}: {num_images} images")
        for cat, cnt in cat_counts.most_common():
            print(f"    {cat:15s} {cnt}")

    print(f"\n{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare CarDD dataset for YOLOv8")
    parser.add_argument("--max_images", type=int, default=None, help="Limit images (for testing)")
    parser.add_argument("--skip_download", action="store_true", help="Skip download, only convert")
    parser.add_argument("--train_ratio", type=float, default=0.8)
    parser.add_argument("--val_ratio", type=float, default=0.1)
    args = parser.parse_args()

    if not args.skip_download:
        download_dataset(max_images=args.max_images)

    convert_to_yolo(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        max_images=args.max_images,
    )

    print("\n✅ CarDD preparation complete!")
    print("   Next: python -m ml.detection.train --epochs 50")
