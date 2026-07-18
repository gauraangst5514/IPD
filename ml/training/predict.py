"""
Single Image Prediction Script

Test a trained model on a single image and get full results
including damage type, severity, cost estimate, and fraud analysis.

Usage:
    python -m ml.training.predict --image path/to/car_image.jpg
    python -m ml.training.predict --image path/to/car_image.jpg --vehicle_make hyundai --region mumbai
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import torch
from PIL import Image
from torchvision import transforms

from ml.damage.model import DamageClassifier
from ml.cost.estimator import CostEstimationEngine
from ml.fraud.image_forensics import ImageForensics


def predict(
    image_path: str,
    weights_path: str = "ml/weights/best_model.pth",
    vehicle_make: str = "hyundai",
    vehicle_year: int = 2022,
    region: str = "mumbai",
    device: str = "auto",
):
    """Run full prediction pipeline on a single image."""

    if device == "auto":
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

    # Load model
    model = DamageClassifier(pretrained=False)
    if os.path.exists(weights_path):
        checkpoint = torch.load(weights_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        print(f"✅ Loaded trained weights from {weights_path}")
    else:
        print(f"⚠️  No weights at {weights_path}, using pretrained backbone (untrained heads)")

    model = model.to(device)
    model.eval()

    # Load and preprocess image
    image = Image.open(image_path).convert("RGB")
    transform = transforms.Compose([
        transforms.Resize((380, 380)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    input_tensor = transform(image).unsqueeze(0).to(device)

    # Run damage prediction
    result = model.predict(input_tensor)

    # Run cost estimation
    cost_engine = CostEstimationEngine()
    cost_estimate = cost_engine.estimate(
        damage_type=result["damage_type"],
        severity=result["severity"],
        vehicle_make=vehicle_make,
        vehicle_year=vehicle_year,
        region=region,
    )

    # Run fraud analysis
    forensics = ImageForensics()
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    fraud_result = forensics.full_analysis(image_bytes, claim_id="test")

    # Print results
    print(f"\n{'='*60}")
    print(f"🔍 PREDICTION RESULTS")
    print(f"{'='*60}")
    print(f"\n  Image: {image_path}")
    print(f"  Vehicle: {vehicle_make.title()} ({vehicle_year})")
    print(f"  Region: {region.title()}")

    print(f"\n  🚗 Damage Assessment:")
    print(f"    Damage Detected: {'✅ Yes' if result['damage_detected'] else '❌ No'}")
    print(f"    Confidence: {result['damage_confidence']*100:.1f}%")
    print(f"    Damage Type: {result['damage_type'].title()} ({result['damage_type_confidence']*100:.1f}%)")
    print(f"    Severity: {result['severity'].title()} ({result['severity_confidence']*100:.1f}%)")

    print(f"\n  💰 Cost Estimate:")
    print(f"    Range: ₹{cost_estimate.min_cost:,.0f} – ₹{cost_estimate.max_cost:,.0f}")
    print(f"    Parts: ₹{cost_estimate.breakdown['parts']:,.0f}")
    print(f"    Labour: ₹{cost_estimate.breakdown['labour']:,.0f}")
    print(f"    Paint: ₹{cost_estimate.breakdown['paint']:,.0f}")
    print(f"    Confidence: {cost_estimate.confidence*100:.0f}%")

    print(f"\n  🕵️ Fraud Analysis:")
    print(f"    Manipulation Score: {fraud_result['overall_manipulation_score']*100:.1f}%")
    print(f"    EXIF Present: {'✅' if fraud_result['exif_analysis']['has_exif'] else '❌'}")
    print(f"    Suspicious: {'⚠️  Yes' if fraud_result['exif_analysis']['suspicious'] else '✅ No'}")
    if fraud_result['metadata_flags']:
        print(f"    Flags: {', '.join(fraud_result['metadata_flags'])}")
    print(f"    Duplicate: {'⚠️  Yes' if fraud_result['duplicate_check']['is_duplicate'] else '✅ No'}")

    print(f"\n{'='*60}")

    return {
        "damage": result,
        "cost": {
            "min": cost_estimate.min_cost,
            "max": cost_estimate.max_cost,
            "breakdown": cost_estimate.breakdown,
        },
        "fraud": fraud_result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict damage for a single image")
    parser.add_argument("--image", type=str, required=True, help="Path to image")
    parser.add_argument("--weights", type=str, default="ml/weights/best_model.pth")
    parser.add_argument("--vehicle_make", type=str, default="hyundai")
    parser.add_argument("--vehicle_year", type=int, default=2022)
    parser.add_argument("--region", type=str, default="mumbai")
    parser.add_argument("--device", type=str, default="auto")
    args = parser.parse_args()

    predict(
        image_path=args.image,
        weights_path=args.weights,
        vehicle_make=args.vehicle_make,
        vehicle_year=args.vehicle_year,
        region=args.region,
        device=args.device,
    )
