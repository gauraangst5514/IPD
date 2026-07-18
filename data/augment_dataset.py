#!/usr/bin/env python3
"""
Dataset Augmentation & Balancing Script

After downloading the base dataset, this script:
1. Balances classes (oversamples minority classes via augmentation)
2. Generates additional augmented versions for robustness
3. Verifies image integrity (removes corrupt files)
4. Prints a final report

Usage:
    python data/augment_dataset.py
    python data/augment_dataset.py --target_per_class 500
"""

import argparse
import os
import sys
from pathlib import Path
from collections import Counter

from PIL import Image, ImageEnhance, ImageFilter
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_ROOT = Path("data/car_damage")


def verify_images(data_dir: Path) -> int:
    """Remove corrupt or unreadable images."""
    removed = 0
    for img_path in data_dir.rglob("*"):
        if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp", ".bmp"):
            continue
        try:
            img = Image.open(img_path)
            img.verify()
        except Exception:
            print(f"  ⚠️  Removing corrupt image: {img_path}")
            img_path.unlink()
            removed += 1
    return removed


def count_per_class(split_dir: Path) -> dict:
    """Count images per class."""
    counts = {}
    for cls_dir in sorted(split_dir.iterdir()):
        if cls_dir.is_dir():
            count = len([f for f in cls_dir.iterdir() if f.is_file()])
            if count > 0:
                counts[cls_dir.name] = count
    return counts


def augment_image(image: Image.Image, aug_type: int) -> Image.Image:
    """
    Apply one of several augmentation types to an image.
    
    This creates realistic variations that the model might see in claims:
    - Different lighting conditions
    - Slightly different angles (rotation)
    - Weather effects (blur for rain)
    - Phone camera quality variation
    """
    if aug_type == 0:
        # Horizontal flip
        return image.transpose(Image.FLIP_LEFT_RIGHT)
    elif aug_type == 1:
        # Brightness variation (simulates different time of day)
        factor = np.random.uniform(0.6, 1.4)
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(factor)
    elif aug_type == 2:
        # Contrast variation
        factor = np.random.uniform(0.7, 1.3)
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)
    elif aug_type == 3:
        # Slight rotation (simulates imperfect photo angle)
        angle = np.random.uniform(-15, 15)
        return image.rotate(angle, fillcolor=(128, 128, 128), expand=False)
    elif aug_type == 4:
        # Color jitter (different phone cameras)
        factor = np.random.uniform(0.8, 1.2)
        enhancer = ImageEnhance.Color(image)
        return enhancer.enhance(factor)
    elif aug_type == 5:
        # Slight blur (simulates motion/focus issues)
        return image.filter(ImageFilter.GaussianBlur(radius=1))
    elif aug_type == 6:
        # Sharpen (some phones auto-sharpen)
        return image.filter(ImageFilter.SHARPEN)
    elif aug_type == 7:
        # Crop and resize (simulates different framing)
        w, h = image.size
        crop_pct = np.random.uniform(0.8, 0.95)
        new_w, new_h = int(w * crop_pct), int(h * crop_pct)
        left = np.random.randint(0, w - new_w)
        top = np.random.randint(0, h - new_h)
        cropped = image.crop((left, top, left + new_w, top + new_h))
        return cropped.resize((w, h), Image.LANCZOS)
    else:
        return image


def balance_classes(split_dir: Path, target_per_class: int):
    """
    Balance classes by augmenting minority classes.
    
    Only augments classes that have fewer than target_per_class images.
    Never removes images from majority classes.
    """
    counts = count_per_class(split_dir)
    if not counts:
        print("  No classes found to balance")
        return

    print(f"\n  Current class distribution:")
    for cls, count in sorted(counts.items()):
        bar = "█" * min(50, count // 5)
        print(f"    {cls:25s} {count:4d} {bar}")

    print(f"\n  Target per class: {target_per_class}")
    total_augmented = 0

    for cls_dir in sorted(split_dir.iterdir()):
        if not cls_dir.is_dir():
            continue

        existing = [f for f in cls_dir.iterdir() if f.is_file()]
        current_count = len(existing)

        if current_count >= target_per_class or current_count == 0:
            continue

        need = target_per_class - current_count
        print(f"  📈 Augmenting '{cls_dir.name}': {current_count} → {target_per_class} (+{need})")

        augmented = 0
        while augmented < need:
            # Pick a random source image
            source_img_path = existing[augmented % len(existing)]
            
            try:
                img = Image.open(source_img_path).convert("RGB")
                
                # Apply random augmentation
                aug_type = augmented % 8
                aug_img = augment_image(img, aug_type)
                
                # Save augmented image
                aug_filename = f"aug_{aug_type}_{source_img_path.stem}_{augmented:04d}.jpg"
                aug_path = cls_dir / aug_filename
                aug_img.save(aug_path, "JPEG", quality=90)
                
                augmented += 1
                total_augmented += 1
            except Exception as e:
                print(f"    ⚠️  Failed to augment {source_img_path}: {e}")
                augmented += 1  # Skip to avoid infinite loop

    print(f"\n  ✅ Created {total_augmented} augmented images")


def main():
    parser = argparse.ArgumentParser(description="Augment and balance training dataset")
    parser.add_argument(
        "--target_per_class", type=int, default=300,
        help="Target number of images per class (default: 300)"
    )
    parser.add_argument(
        "--verify_only", action="store_true",
        help="Only verify image integrity, don't augment"
    )
    args = parser.parse_args()

    print("\n" + "="*60)
    print("🔧 Dataset Augmentation & Balancing")
    print("="*60)

    train_dir = DATA_ROOT / "train"
    val_dir = DATA_ROOT / "val"

    if not train_dir.exists():
        print(f"\n❌ Training directory not found: {train_dir}")
        print("   Run data/download_dataset.py first!")
        return

    # Step 1: Verify images
    print("\n📋 Step 1: Verifying image integrity...")
    removed_train = verify_images(train_dir)
    removed_val = verify_images(val_dir)
    print(f"  Removed {removed_train + removed_val} corrupt images")

    if args.verify_only:
        return

    # Step 2: Balance training set
    print(f"\n📋 Step 2: Balancing training classes (target: {args.target_per_class} per class)...")
    balance_classes(train_dir, args.target_per_class)

    # Step 3: Print final stats
    print(f"\n📋 Step 3: Final dataset statistics")
    for split_name, split_dir in [("TRAIN", train_dir), ("VAL", val_dir)]:
        counts = count_per_class(split_dir)
        total = sum(counts.values())
        print(f"\n  {split_name}: {total} images across {len(counts)} classes")
        for cls, count in sorted(counts.items()):
            print(f"    {cls:25s} {count:4d}")

    print(f"\n{'='*60}")
    print("✅ Dataset augmentation complete!")
    print(f"   Next: python train_model.py --train --epochs 30")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
