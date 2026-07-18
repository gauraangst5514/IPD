"""
Image preprocessing pipeline for damage detection.
"""

import io
from PIL import Image
import torch
from torchvision import transforms


# Standard preprocessing for EfficientNet-B4 (input size 380x380)
INFERENCE_TRANSFORM = transforms.Compose([
    transforms.Resize((380, 380)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])

# Training augmentation
TRAIN_TRANSFORM = transforms.Compose([
    transforms.Resize((400, 400)),
    transforms.RandomCrop((380, 380)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomRotation(degrees=15),
    transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
    transforms.RandomAffine(degrees=0, translate=(0.1, 0.1)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    ),
])


def preprocess_image(image_bytes: bytes, mode: str = "inference") -> torch.Tensor:
    """
    Preprocess raw image bytes into a model-ready tensor.

    Args:
        image_bytes: Raw image file bytes
        mode: "inference" or "train"

    Returns:
        Tensor of shape (1, 3, 380, 380)
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    transform = INFERENCE_TRANSFORM if mode == "inference" else TRAIN_TRANSFORM
    tensor = transform(image)

    # Add batch dimension
    return tensor.unsqueeze(0)


def preprocess_pil_image(image: Image.Image) -> torch.Tensor:
    """Preprocess a PIL Image directly."""
    image = image.convert("RGB")
    tensor = INFERENCE_TRANSFORM(image)
    return tensor.unsqueeze(0)
