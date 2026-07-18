#!/usr/bin/env python3
"""
IntelliClaim Model Training — One-command convenience script.

Usage:
    # Step 1: Prepare sample data (for testing pipeline)
    python train_model.py --prepare sample

    # Step 1 (alt): Prepare from Kaggle
    python train_model.py --prepare kaggle

    # Step 1 (alt): Prepare from your own images
    python train_model.py --prepare manual --input_dir /path/to/your/images

    # Step 2: Train the model
    python train_model.py --train

    # Step 3: Evaluate
    python train_model.py --evaluate

    # All steps at once (sample data)
    python train_model.py --all
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    parser = argparse.ArgumentParser(description="IntelliClaim Model Training")
    parser.add_argument("--prepare", choices=["sample", "kaggle", "manual"], help="Prepare dataset")
    parser.add_argument("--input_dir", type=str, help="Input directory for manual preparation")
    parser.add_argument("--train", action="store_true", help="Train the model")
    parser.add_argument("--evaluate", action="store_true", help="Evaluate the model")
    parser.add_argument("--all", action="store_true", help="Run all steps (prepare sample + train + evaluate)")

    # Training params
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch_size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument("--data_dir", type=str, default="data/car_damage")
    parser.add_argument("--output_dir", type=str, default="ml/weights")

    args = parser.parse_args()

    if not any([args.prepare, args.train, args.evaluate, args.all]):
        parser.print_help()
        print("\n💡 Quick start:")
        print("   python train_model.py --all          # Full pipeline with sample data")
        print("   python train_model.py --prepare kaggle  # Use real Kaggle data")
        return

    if args.all:
        args.prepare = "sample"
        args.train = True
        args.evaluate = True

    # Step 1: Prepare data
    if args.prepare:
        print("\n" + "="*60)
        print("📦 STEP 1: Preparing dataset...")
        print("="*60 + "\n")

        from ml.training.prepare_data import (
            create_directory_structure,
            create_sample_dataset,
            download_kaggle_dataset,
            organize_severity_dataset,
            organize_detection_dataset,
            organize_manual_dataset,
            print_dataset_stats,
        )

        create_directory_structure()

        if args.prepare == "sample":
            create_sample_dataset()
        elif args.prepare == "kaggle":
            success = download_kaggle_dataset()
            if success:
                organize_severity_dataset()
                organize_detection_dataset()
        elif args.prepare == "manual":
            if not args.input_dir:
                print("❌ --input_dir required for manual mode")
                return
            organize_manual_dataset(args.input_dir)

        print_dataset_stats()

    # Step 2: Train
    if args.train:
        print("\n" + "="*60)
        print("🚀 STEP 2: Training model...")
        print("="*60 + "\n")

        from ml.training.train import train

        train(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.lr,
            device=args.device,
        )

    # Step 3: Evaluate
    if args.evaluate:
        print("\n" + "="*60)
        print("📊 STEP 3: Evaluating model...")
        print("="*60 + "\n")

        weights_path = os.path.join(args.output_dir, "best_model.pth")
        if not os.path.exists(weights_path):
            print(f"⚠️  No trained model found at {weights_path}")
            print("   Run training first: python train_model.py --train")
            return

        from ml.training.evaluate import evaluate
        evaluate(weights_path, args.data_dir, args.device)


if __name__ == "__main__":
    main()
