"""
Grad-CAM Heatmap Generation

Produces class-discriminative heatmaps showing which regions of the image
influenced the model's damage classification decision.
"""

import io
import numpy as np
import torch
from PIL import Image
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from torchvision import transforms

from ml.damage.model import DamageClassifier


class GradCAMExplainer:
    """Generate visual explanations for damage predictions."""

    def __init__(self, model: DamageClassifier, device: str = "cpu"):
        self.model = model.to(device)
        self.model.eval()
        self.device = device

        # Target the last conv layer of EfficientNet backbone
        # EfficientNet-B4's last features block
        self.target_layer = self.model.backbone.features[-1]

    def generate_heatmap(
        self,
        image_bytes: bytes,
        target_task: str = "severity",  # "damage_type" or "severity"
    ) -> tuple[bytes, np.ndarray]:
        """
        Generate Grad-CAM heatmap for the given image.

        Args:
            image_bytes: Raw image bytes
            target_task: Which output head to explain

        Returns:
            Tuple of (heatmap_overlay_bytes, raw_cam_array)
        """
        # Load and preprocess
        original_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        original_image_resized = original_image.resize((380, 380))

        # Normalize for model
        transform = transforms.Compose([
            transforms.Resize((380, 380)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])
        input_tensor = transform(original_image).unsqueeze(0).to(self.device)

        # Create a wrapper that returns the target output
        class TaskWrapper(torch.nn.Module):
            def __init__(self, model, task):
                super().__init__()
                self.model = model
                self.task = task

            def forward(self, x):
                outputs = self.model(x)
                if self.task == "severity":
                    return outputs["severity"]
                elif self.task == "damage_type":
                    return outputs["damage_type"]
                else:
                    return outputs["damage_present"]

        wrapped_model = TaskWrapper(self.model, target_task)
        target_layers = [self.target_layer]

        # Generate CAM
        cam = GradCAM(model=wrapped_model, target_layers=target_layers)
        grayscale_cam = cam(input_tensor=input_tensor, targets=None)
        grayscale_cam = grayscale_cam[0, :]  # First image in batch

        # Create overlay
        rgb_image = np.array(original_image_resized).astype(np.float32) / 255.0
        heatmap_overlay = show_cam_on_image(rgb_image, grayscale_cam, use_rgb=True)

        # Convert to bytes
        overlay_image = Image.fromarray(heatmap_overlay)
        buffer = io.BytesIO()
        overlay_image.save(buffer, format="PNG")
        heatmap_bytes = buffer.getvalue()

        return heatmap_bytes, grayscale_cam
