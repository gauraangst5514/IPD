# Dataset Setup for IntelliClaim

## Quick Start (3 options)

### Option 1: Kaggle API (Recommended — Automated)

```bash
# 1. Install kaggle
pip install kaggle

# 2. Get your API key
#    Go to https://www.kaggle.com/settings → API → Create New Token
#    This downloads kaggle.json

# 3. Place credentials
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json

# 4. Download datasets
python data/download_dataset.py --method kaggle

# 5. Augment (balances classes)
python data/augment_dataset.py --target_per_class 400

# 6. Train!
python train_model.py --train --epochs 30
```

### Option 2: Manual Download (No API needed)

1. Download these datasets from Kaggle (free account required):
   - **Primary**: https://www.kaggle.com/datasets/lplenern/car-damage-severity-dataset
   - **Secondary** (optional): https://www.kaggle.com/datasets/anujms/car-damage-detection

2. Extract the zip files:
   ```bash
   mkdir -p data/raw/severity
   unzip ~/Downloads/car-damage-severity-dataset.zip -d data/raw/severity/
   
   # Optional
   mkdir -p data/raw/detection
   unzip ~/Downloads/car-damage-detection.zip -d data/raw/detection/
   ```

3. Organize into training structure:
   ```bash
   python data/download_dataset.py --method manual --input_dir data/raw/severity
   python data/download_dataset.py --method manual --input_dir data/raw/detection
   ```

4. Augment and train:
   ```bash
   python data/augment_dataset.py --target_per_class 400
   python train_model.py --train --epochs 30
   ```

### Option 3: Your Own Images

If you have your own car damage photos (e.g., from insurance company data):

1. Organize them into folders by severity:
   ```
   my_images/
   ├── minor/       (light scratches, small scuffs)
   ├── moderate/    (dents, deeper scratches, cracked bumpers)
   ├── severe/      (major damage, shattered glass, crushed panels)
   └── no_damage/   (clean/undamaged cars — optional but helpful)
   ```

2. Run:
   ```bash
   python data/download_dataset.py --method manual --input_dir my_images/
   python data/augment_dataset.py --target_per_class 300
   python train_model.py --train --epochs 30
   ```

## Dataset Details

### Expected Structure After Setup

```
data/car_damage/
├── train/              (80% of data)
│   ├── no_damage/      (undamaged reference images)
│   ├── minor_scratch/  (light scratches)
│   ├── minor_dent/     (very small dents)
│   ├── moderate_scratch/ (visible scratches)
│   ├── moderate_dent/  (noticeable dents)
│   ├── moderate_crack/ (bumper cracks, small panel cracks)
│   ├── moderate_bumper/(bumper damage)
│   ├── severe_dent/    (large dents, deformation)
│   ├── severe_crack/   (large cracks, structural damage)
│   ├── severe_shatter/ (broken glass, windshield)
│   ├── severe_bumper/  (destroyed bumper)
│   └── severe_panel/   (entire panel damaged)
└── val/                (20% of data)
    └── (same structure)
```

### Recommended Minimum Sizes

| Quality Level | Images per class | Total | Training Time |
|--------------|-----------------|-------|---------------|
| Quick test   | 50              | ~600  | ~10 min       |
| Decent demo  | 200             | ~2400 | ~45 min       |
| Production   | 500+            | ~6000 | ~2-3 hours    |

### Image Requirements

- Format: JPG, PNG, WebP
- Minimum size: 224×224 pixels (will be resized to 380×380)
- No text overlays, watermarks, or collages
- Single car per image preferred
- Various angles welcome (front, side, rear, close-up)

## Augmentation

The augmentation script creates realistic variations:
- Horizontal flips
- Brightness changes (simulates time of day)
- Contrast variation
- Slight rotations (imperfect photo angles)
- Color jitter (different phone cameras)
- Blur (motion/focus issues)
- Random crops (different framing)

## Notes

- The `data/raw/` directory is gitignored — raw downloads won't be committed
- The `data/car_damage/` directory is also gitignored — it can be large
- Model weights are saved to `ml/weights/` (also gitignored)
- To share your trained model, upload `ml/weights/best_model.pth` separately
