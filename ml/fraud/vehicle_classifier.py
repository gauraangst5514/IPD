"""
Vehicle Make Classifier

Uses a fine-tuned EfficientNet-B0 on Stanford Cars to predict the make
of the vehicle in an image. Used for cross-checking against the claimed
vehicle make on the insurance claim.

Weights: ml/weights/vehicle_make/vehicle_make_classifier.pt
"""

import io
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_PATH = ROOT / 'weights/vehicle_make/vehicle_make_classifier.pt'
HF_MODEL_PATH = ROOT / 'weights/vehicle_make_hf'


class VehicleMakeClassifier:
    """Classify vehicle make from an image."""

    def __init__(self):
        self.model = None
        self.idx_to_make = None
        self.transform = None
        self.device = None
        self.loaded = False

        self.processor = None
        self.method = 'efficientnet_stanford_cars'
        self.unavailable_reason = 'checkpoint_missing'
        if (HF_MODEL_PATH / 'model.safetensors').exists():
            self._load_hf_model()
        elif WEIGHTS_PATH.exists():
            self._load_model()
        else:
            print(f"⚠️  Vehicle make classifier weights not found at {WEIGHTS_PATH}")
            print(f"   Run notebooks/train_vehicle_classifier_kaggle.ipynb to train.")

    def _load_hf_model(self):
        try:
            import torch
            from transformers import AutoImageProcessor, AutoModelForImageClassification
            self.processor = AutoImageProcessor.from_pretrained(HF_MODEL_PATH, local_files_only=True,use_fast=False)
            self.model = AutoModelForImageClassification.from_pretrained(
                HF_MODEL_PATH, local_files_only=True, use_safetensors=True).eval()
            self.device = torch.device('cpu')
            self.idx_to_make = {int(k): str(v) for k,v in self.model.config.id2label.items()}
            if not self.idx_to_make or any(v.startswith('LABEL_') for v in self.idx_to_make.values()):
                raise ValueError('Classifier must have explicit vehicle-make labels')
            self.method = 'pretrained_vit_vehicle_make'
            self.loaded = True
            self.unavailable_reason = None
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Vehicle model could not load')
            self.loaded = False
            self.unavailable_reason = 'checkpoint_load_failed'

    def status(self):
        return {'available': self.loaded, 'method': self.method,
                'reason': self.unavailable_reason,
                'supported_makes': sorted(set(self.idx_to_make.values())) if self.loaded else [],
                'limitation': 'Pretrained visual make suggestion; confidence is uncalibrated. Close-up damage photos and unsupported makes may be inconclusive.'}

    def _load_model(self):
        """Load the trained classifier."""
        try:
            import torch
            import timm
            from torchvision import transforms

            # Determine device
            if torch.cuda.is_available():
                self.device = torch.device("cuda")
            elif torch.backends.mps.is_available():
                self.device = torch.device("mps")
            else:
                self.device = torch.device("cpu")

            # Load checkpoint
            checkpoint = torch.load(WEIGHTS_PATH, map_location=self.device, weights_only=True)

            # Build model
            num_classes = checkpoint["num_classes"]
            model_name = checkpoint.get("model_name", "efficientnet_b0")
            self.model = timm.create_model(model_name, pretrained=False, num_classes=num_classes)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.model.to(self.device)
            self.model.eval()

            # Class mapping
            self.idx_to_make = checkpoint["idx_to_make"]
            # Convert string keys back to int if needed
            if isinstance(list(self.idx_to_make.keys())[0], str):
                self.idx_to_make = {int(k): v for k, v in self.idx_to_make.items()}

            # Transform
            mean = checkpoint.get("normalize_mean", [0.485, 0.456, 0.406])
            std = checkpoint.get("normalize_std", [0.229, 0.224, 0.225])
            input_size = checkpoint.get("input_size", 224)

            self.transform = transforms.Compose([
                transforms.Resize((input_size + 32, input_size + 32)),
                transforms.CenterCrop(input_size),
                transforms.ToTensor(),
                transforms.Normalize(mean=mean, std=std),
            ])

            self.loaded = True
            print(f"✅ Vehicle make classifier loaded ({num_classes} makes)")

        except Exception as e:
            print(f"⚠️  Failed to load vehicle make classifier: {e}")
            self.loaded = False

    def predict(self, image_bytes: bytes, top_k: int = 3) -> dict:
        """
        Predict the vehicle make from image bytes.

        Returns:
            {
                "predicted_make": "bmw",
                "confidence": 0.87,
                "top_predictions": [("bmw", 0.87), ("audi", 0.05), ("mercedes", 0.03)],
            }
        """
        if not self.loaded:
            return {"predicted_make": None, "confidence": 0.0, "top_predictions": []}

        import torch

        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            input_tensor = (self.processor(images=image, return_tensors='pt')['pixel_values']
                            if self.processor else self.transform(image).unsqueeze(0)).to(self.device)

            with torch.no_grad():
                output = self.model(input_tensor)
                logits = output.logits if self.processor else output
                probs = torch.softmax(logits, dim=1)
                top_probs, top_indices = probs.topk(min(top_k, len(self.idx_to_make)), dim=1)

            top_predictions = [
                (self.idx_to_make[idx.item()], prob.item())
                for idx, prob in zip(top_indices[0], top_probs[0])
            ]

            return {
                "predicted_make": top_predictions[0][0],
                "confidence": top_predictions[0][1],
                "top_predictions": top_predictions,
            }
        except Exception as e:
            print(f"⚠️  Vehicle make prediction failed: {e}")
            return {"predicted_make": None, "confidence": 0.0, "top_predictions": []}

    def verify_make(self, image_bytes: bytes, claimed_make: str, threshold: float = 0.7) -> dict:
        """
        Verify if the vehicle in the image matches the claimed make.

        Returns:
            {
                "match": True/False/None (None = inconclusive),
                "claimed_make": "rolls royce",
                "detected_make": "bmw",
                "confidence": 0.87,
                "flag": "vehicle_make_mismatch" or None,
                "detail": "Claimed Rolls Royce but image shows BMW (87% confidence)"
            }
        """
        if not self.loaded:
            return {"match": None, "flag": None, "detail": "Classifier not available"}

        if not claimed_make or self._normalize_make(claimed_make) not in {
                self._normalize_make(make) for make in self.idx_to_make.values()}:
            return {'match': None, 'flag': None, 'detail': 'Claimed make is outside this model vocabulary.',
                    'supported_makes': sorted(set(self.idx_to_make.values()))}
        prediction = self.predict(image_bytes)

        if prediction["confidence"] < threshold:
            # Not confident enough to make a determination
            return {
                "match": None,
                "claimed_make": claimed_make,
                "detected_make": prediction["predicted_make"],
                "confidence": prediction["confidence"],
                "flag": None,
                "detail": f"Low confidence prediction ({prediction['confidence']:.0%}), inconclusive",
            }

        # Normalize make names for comparison
        claimed_normalized = self._normalize_make(claimed_make)
        detected_normalized = self._normalize_make(prediction["predicted_make"])

        # If the claimed make is an Indian-only brand not in the classifier,
        # don't flag a mismatch — the classifier simply can't verify it.
        if claimed_normalized in self.INDIAN_ONLY_MAKES:
            return {
                "match": None,
                "claimed_make": claimed_make,
                "detected_make": prediction["predicted_make"],
                "confidence": prediction["confidence"],
                "flag": None,
                "detail": f"Indian make '{claimed_make}' not in classifier training data, skipping verification",
            }

        # Check if they match (with aliases)
        is_match = self._makes_match(claimed_normalized, detected_normalized)

        if is_match:
            return {
                "match": True,
                "claimed_make": claimed_make,
                "detected_make": prediction["predicted_make"],
                "confidence": prediction["confidence"],
                "flag": None,
                "detail": None,
            }
        else:
            return {
                "match": False,
                "claimed_make": claimed_make,
                "detected_make": prediction["predicted_make"],
                "confidence": prediction["confidence"],
                "flag": "vehicle_make_mismatch",
                "detail": (
                    f"Claimed {claimed_make.title()} but image shows "
                    f"{prediction['predicted_make'].title()} "
                    f"(model score {prediction['confidence']:.0%}; verify manually)"
                ),
            }

    def _normalize_make(self, make: str) -> str:
        """Normalize make name for comparison."""
        make = make.lower().strip()
        # Common aliases including Indian makes
        aliases = {
            # Standard aliases
            "rolls-royce": "rolls royce",
            "rolls": "rolls royce",
            "royce": "rolls royce",
            "merc": "mercedes-benz",
            "mercedes": "mercedes-benz",
            "benz": "mercedes-benz",
            "vw": "volkswagen",
            "chevy": "chevrolet",
            "land rover": "land rover",
            "landrover": "land rover",
            "aston": "aston martin",
            # Indian makes
            "maruti": "suzuki",
            "maruti suzuki": "suzuki",
            "tata": "tata",
            "tata motors": "tata",
            "mahindra": "mahindra",
            "mahindra & mahindra": "mahindra",
            "m&m": "mahindra",
            "mg": "mg",
            "mg motor": "mg",
            "mg motors": "mg",
            "kia": "kia",
            "kia motors": "kia",
            "skoda": "skoda",
            "škoda": "skoda",
            "renault": "renault",
            "citroen": "citroen",
            "citroën": "citroen",
            "force motors": "force",
            "ashok leyland": "ashok leyland",
            "eicher": "eicher",
            "tvs": "tvs",
            "hero": "hero",
            "bajaj": "bajaj",
            "royal enfield": "royal enfield",
        }
        return aliases.get(make, make)

    # Indian makes not in the Stanford Cars classifier — if claimed make is one
    # of these and classifier can't identify it, we should not flag as mismatch.
    INDIAN_ONLY_MAKES = {
        "tata", "mahindra", "force", "ashok leyland", "eicher",
        "tvs", "hero", "bajaj", "royal enfield",
    }

    def _makes_match(self, make1: str, make2: str) -> bool:
        """Check if two normalized makes refer to the same brand."""
        if make1 == make2:
            return True
        # Check if one contains the other
        if make1 in make2 or make2 in make1:
            return True

        # Known equivalent groups (brands that share design language)
        equivalent_groups = [
            {"suzuki", "maruti"},                          # Maruti Suzuki
            {"mercedes-benz", "maybach"},                  # Mercedes group
        ]
        for group in equivalent_groups:
            if make1 in group and make2 in group:
                return True

        return False
