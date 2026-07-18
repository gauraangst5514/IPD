#!/bin/bash
# Download car damage datasets from GitHub repositories
# These don't require any API keys or authentication

set -e

echo "====================================="
echo "🚗 Downloading Car Damage Datasets"
echo "====================================="
echo ""

DATA_DIR="data/raw"
mkdir -p "$DATA_DIR"

# Dataset 1: Insurance Car Damage Categorisation (3 categories: pristine, fender_bender, write_off)
echo "📥 [1/2] Downloading InsuranceCarDamageCategorsation..."
if [ ! -d "$DATA_DIR/github_insurance" ]; then
    git clone --depth 1 https://github.com/MarkWoolnough/InsuranceCarDamageCategorsation.git "$DATA_DIR/github_insurance" 2>/dev/null || {
        echo "  ⚠️  Git clone failed. Trying wget..."
        mkdir -p "$DATA_DIR/github_insurance"
        wget -q "https://github.com/MarkWoolnough/InsuranceCarDamageCategorsation/archive/refs/heads/master.zip" -O "$DATA_DIR/github_insurance.zip"
        unzip -q "$DATA_DIR/github_insurance.zip" -d "$DATA_DIR/github_insurance"
        rm "$DATA_DIR/github_insurance.zip"
    }
    echo "  ✅ Downloaded"
else
    echo "  ⏭️  Already exists, skipping"
fi

# Dataset 2: Car Damage Detection (binary: damaged vs whole)
echo "📥 [2/2] Downloading car-damage-detection-peltarion..."
if [ ! -d "$DATA_DIR/github_peltarion" ]; then
    git clone --depth 1 https://github.com/politecat314/car-damage-detection-peltarion.git "$DATA_DIR/github_peltarion" 2>/dev/null || {
        echo "  ⚠️  Git clone failed. Trying wget..."
        mkdir -p "$DATA_DIR/github_peltarion"
        wget -q "https://github.com/politecat314/car-damage-detection-peltarion/archive/refs/heads/main.zip" -O "$DATA_DIR/github_peltarion.zip"
        unzip -q "$DATA_DIR/github_peltarion.zip" -d "$DATA_DIR/github_peltarion"
        rm "$DATA_DIR/github_peltarion.zip"
    }
    echo "  ✅ Downloaded"
else
    echo "  ⏭️  Already exists, skipping"
fi

echo ""
echo "====================================="
echo "📂 Raw data downloaded to: $DATA_DIR/"
echo ""
echo "Next steps:"
echo "  1. Organize: python data/download_dataset.py --method combine"
echo "  2. Augment:  python data/augment_dataset.py --target_per_class 300"
echo "  3. Train:    python train_model.py --train --epochs 30"
echo "====================================="
