# Training on Kaggle

## Steps

### 1. Zip your dataset for upload
```bash
cd /Users/gauraangthakkar/IPD
zip -r cardd_yolo.zip data/cardd_yolo/images data/cardd_yolo/labels data/cardd_yolo/data.yaml
```

### 2. Upload to Kaggle
- Go to https://www.kaggle.com/datasets → New Dataset
- Upload `cardd_yolo.zip`
- Name it `cardd-yolo`

### 3. Create a Notebook
- New Notebook → Import `train_cardd_kaggle.ipynb`
- Add your dataset (right panel → Add Data → search "cardd-yolo")
- Set Accelerator to **GPU T4 x2** (Settings → Accelerator)
- Run all cells

### 4. Download weights
- After training completes, go to Output tab
- Download `best_cardd_yolov8m.pt`
- Place it at: `ml/weights/detection/cardd_yolov8/weights/best.pt`

## Expected Time
| Model | Epochs | Image Size | Kaggle T4 | Mac M1/M2 (MPS) |
|-------|--------|-----------|-----------|-----------------|
| YOLOv8s | 150 | 800 | ~50 min | ~5-7 hours |
| YOLOv8m | 150 | 800 | ~1.5 hr | ~8-12 hours |

## What's Improved
- **YOLOv8m** instead of nano — much better at detecting small/overlapping damage
- **800px input** — captures more detail than 640px
- **150 epochs** with patience 30 — better convergence
- **Stronger augmentation** — mosaic, mixup, copy-paste, higher scale variation
- **AdamW optimizer** with cosine LR decay — smoother training
- **close_mosaic=15** — disables mosaic last 15 epochs for final fine-tuning
