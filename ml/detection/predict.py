"""
Single Image Prediction — Detection Pipeline

Test the trained YOLOv8 detector on a single image and get the full
assessment: detected damages, severity, cost estimate, and fraud signals.

Usage:
    python -m ml.detection.predict --image path/to/car.jpg
    python -m ml.detection.predict --image car.jpg --vehicle_make bmw --region mumbai --save_annotated out.png
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ml.detection.detector import DamageDetector
from ml.cost.estimator import CostEstimationEngine
from ml.fraud.image_forensics import ImageForensics


def predict(
    image_path: str,
    weights: str = "ml/weights/detection/cardd_yolov8/weights/best.pt",
    vehicle_make: str = "hyundai",
    vehicle_year: int = 2022,
    region: str = "mumbai",
    save_annotated: str = None,
):
    """Run the full detection-based prediction pipeline on one image."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    detector = DamageDetector(weights_path=weights)
    cost_engine = CostEstimationEngine()
    forensics = ImageForensics()

    # Detect
    result = detector.detect(image_bytes)

    # Cost
    cost = cost_engine.estimate(
        damage_type=result["primary_damage_type"],
        severity=result["severity"],
        vehicle_make=vehicle_make,
        vehicle_year=vehicle_year,
        region=region,
    ) if result["damage_detected"] and result["severity"] else None

    # Fraud
    fraud = forensics.full_analysis(image_bytes)

    # Output
    print(f"\n{'='*60}")
    print(f"🔍 DAMAGE ASSESSMENT")
    print(f"{'='*60}")
    print(f"\n  Image: {image_path}")
    print(f"  Vehicle: {vehicle_make.title()} ({vehicle_year}) | Region: {region.title()}")

    print(f"\n  🚗 Detected Damage ({result['num_instances']} instances):")
    if result["detections"]:
        for d in result["detections"]:
            print(f"    • {d['label']:15s} conf={d['confidence']*100:.1f}%  bbox={d['bbox']}")
    else:
        print("    (none detected)")

    print(f"\n  📊 Estimated severity: {(result['severity'] or 'not assessed').upper()}")
    r = result["severity_reasoning"]
    if "total_area_coverage" in r:
        print(f"    Area coverage: {r['total_area_coverage']*100:.1f}%")
        print(f"    Largest damage: {r['largest_damage_area']*100:.1f}%")
        print(f"    Most severe type: {r['most_severe_type']}")

    if cost:
        print(f"\n  Indicative cost band: ₹{cost.min_cost:,.0f} – ₹{cost.max_cost:,.0f}")
        print(f"    Parts ₹{cost.breakdown['parts']:,.0f} | "
              f"Labour ₹{cost.breakdown['labour']:,.0f} | "
              f"Paint ₹{cost.breakdown['paint']:,.0f}")
    else:
        print("\n  Repair cost: not estimated")

    print("\n  Evidence indicators (fraud probability not estimated):")
    for item in fraud["fraud_indicators"]:
        print(f"    {item['code']}: {item['status']} — {item['detail']}")
    if fraud["metadata_flags"]:
        print(f"    Flags: {', '.join(fraud['metadata_flags'])}")

    print(f"\n{'='*60}")

    # Save annotated image
    if save_annotated and result.get("damage_analysis_available", False):
        with open(save_annotated, "wb") as f:
            f.write(result["annotated_image"])
        print(f"  💾 Annotated image saved to: {save_annotated}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict damage on a single image")
    parser.add_argument("--image", type=str, required=True)
    parser.add_argument("--weights", type=str, default="ml/weights/detection/cardd_yolov8/weights/best.pt")
    parser.add_argument("--vehicle_make", type=str, default="hyundai")
    parser.add_argument("--vehicle_year", type=int, default=2022)
    parser.add_argument("--region", type=str, default="mumbai")
    parser.add_argument("--save_annotated", type=str, default=None)
    args = parser.parse_args()

    predict(
        image_path=args.image,
        weights=args.weights,
        vehicle_make=args.vehicle_make,
        vehicle_year=args.vehicle_year,
        region=args.region,
        save_annotated=args.save_annotated,
    )
