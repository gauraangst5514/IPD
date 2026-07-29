# Model Training Improvements

## What Changed (Old → New)

| Parameter | Current (old) | New (notebook) | Why |
|-----------|--------------|----------------|-----|
| Model | YOLOv8n/s (nano/small) | YOLOv8m (medium) | 3x more parameters, better feature extraction for overlapping damage |
| Input size | 640px | 800px | Captures small cracks/scratches that get lost at lower resolution |
| Epochs | 50 | 150 (patience 30) | More time to converge, early stopping prevents overfitting |
| Optimizer | SGD (auto) | AdamW | Smoother convergence for fine-tuning pretrained models |
| Learning rate | 0.01 | 0.001 with cosine decay to 0.00001 | Lower LR avoids destroying pretrained features |
| Warmup | 3 epochs (default) | 5 epochs | Gentler start, less instability |
| Mixup | Off | 0.15 | Blends images together, forces model to learn robust features |
| Copy-paste | Off | 0.1 | Pastes damage instances from one image onto another — synthetic data expansion |
| Shear | Off | 5.0° | Simulates photos taken at slight angles |
| Scale variation | 0.5 | 0.5 | Same — already good for multi-size damage |
| close_mosaic | 10 (default) | 15 | Disables mosaic augmentation for last 15 epochs — cleaner fine-tuning on real images |
| Box loss weight | 7.5 (default) | 7.5 | Kept high — localization accuracy matters |
| DFL weight | 1.5 (default) | 1.5 | Distribution focal loss for tighter boxes |

## Expected Impact

- Confidence scores: 0.3–0.67 → 0.5–0.85
- Fewer missed detections on severe/multi-damage scenes
- Tighter bounding boxes around actual damage areas
- Better at distinguishing overlapping damage types (dent vs crack in same area)

---

## How to Train on Kaggle (Works After Closing Laptop)

Kaggle notebooks run on their servers — once you hit "Run All", it keeps running even if you close your laptop, disconnect from WiFi, or shut down your machine.

### Steps

1. **Zip your dataset**
   ```bash
   cd /Users/gauraangthakkar/IPD
   zip -r cardd_yolo.zip data/cardd_yolo/images data/cardd_yolo/labels data/cardd_yolo/data.yaml
   ```

2. **Upload dataset to Kaggle**
   - Go to https://www.kaggle.com/datasets → New Dataset
   - Upload `cardd_yolo.zip`, name it `cardd-yolo`
   - Click Create

3. **Create the notebook**
   - Go to https://www.kaggle.com/code → New Notebook
   - File → Import Notebook → upload `notebooks/train_cardd_kaggle.ipynb`
   - Right panel → Add Data → search `cardd-yolo` → Add
   - Settings → Accelerator → **GPU T4 x2**
   - Settings → Persistence → **Files** (saves output even if session disconnects)

4. **Run and close your laptop**
   - Click **Run All** (or Ctrl+Shift+Enter)
   - **Turn on "Save & Run All (Commit)"** — this submits the notebook as a background job
   - You can now close your laptop. Kaggle runs it server-side.
   - Training takes ~1.5 hours for YOLOv8m / 150 epochs / 800px

5. **Check results later**
   - Come back to https://www.kaggle.com/code → Your Work
   - Click your notebook → check if the run completed (green checkmark)
   - Go to the **Output** tab → download `best_cardd_yolov8m.pt`

6. **Replace weights in your project**
   ```bash
   cp ~/Downloads/best_cardd_yolov8m.pt ml/weights/detection/cardd_yolov8/weights/best.pt
   ```

7. **Restart ML service** — it will pick up the new model automatically on next start

### Key Point: "Save & Run All" vs "Run All"

| Action | What happens | Can close laptop? |
|--------|-------------|-------------------|
| Run All | Runs interactively in browser | ❌ Stops if you close tab |
| Save & Run All (Commit) | Submits as background job | ✅ Runs server-side, close laptop freely |

Always use **"Save & Run All (Commit)"** if you want to close your laptop. Find it under the "Save Version" button (top right) → select "Save & Run All" → click Save.
