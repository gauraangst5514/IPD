"""
Damage Detection & Severity Classification Model

Uses EfficientNet-B4 with transfer learning for:
1. Binary damage detection (damaged / not damaged)
2. Damage type classification (scratch, dent, crack, shatter, bumper, panel)
3. Severity scoring (minor, moderate, severe)
"""

import torch
import torch.nn as nn
from torchvision import models


class DamageClassifier(nn.Module):
    """
    Multi-task model for vehicle damage assessment.

    Outputs:
        - damage_present: Binary (damaged or not)
        - damage_type: 6-class classification
        - severity: 3-class classification
    """

    NUM_DAMAGE_TYPES = 6  # scratch, dent, crack, shatter, bumper, panel
    NUM_SEVERITY_LEVELS = 3  # minor, moderate, severe

    DAMAGE_TYPES = ["scratch", "dent", "crack", "shatter", "bumper", "panel"]
    SEVERITY_LEVELS = ["minor", "moderate", "severe"]

    def __init__(self, pretrained: bool = True):
        super().__init__()

        # Backbone: EfficientNet-B4 (good balance of accuracy vs speed)
        weights = models.EfficientNet_B4_Weights.DEFAULT if pretrained else None
        self.backbone = models.efficientnet_b4(weights=weights)

        # Get the feature dimension from EfficientNet
        in_features = self.backbone.classifier[1].in_features

        # Remove original classifier
        self.backbone.classifier = nn.Identity()

        # Shared feature layer
        self.shared_fc = nn.Sequential(
            nn.Linear(in_features, 512),
            nn.ReLU(),
            nn.Dropout(0.3),
        )

        # Task-specific heads
        self.damage_head = nn.Sequential(
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Linear(128, 1),  # Binary: damaged or not
        )

        self.type_head = nn.Sequential(
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Linear(128, self.NUM_DAMAGE_TYPES),
        )

        self.severity_head = nn.Sequential(
            nn.Linear(512, 128),
            nn.ReLU(),
            nn.Linear(128, self.NUM_SEVERITY_LEVELS),
        )

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        features = self.backbone(x)
        shared = self.shared_fc(features)

        damage_logit = self.damage_head(shared)
        type_logits = self.type_head(shared)
        severity_logits = self.severity_head(shared)

        return {
            "damage_present": torch.sigmoid(damage_logit),
            "damage_type": type_logits,
            "severity": severity_logits,
        }

    def predict(self, x: torch.Tensor) -> dict:
        """Run inference and return human-readable results."""
        self.eval()
        with torch.no_grad():
            outputs = self.forward(x)

        damage_prob = outputs["damage_present"].item()
        damage_type_idx = outputs["damage_type"].argmax(dim=1).item()
        severity_idx = outputs["severity"].argmax(dim=1).item()

        return {
            "damage_detected": damage_prob > 0.5,
            "damage_confidence": round(damage_prob, 4),
            "damage_type": self.DAMAGE_TYPES[damage_type_idx],
            "damage_type_confidence": round(
                torch.softmax(outputs["damage_type"], dim=1).max().item(), 4
            ),
            "severity": self.SEVERITY_LEVELS[severity_idx],
            "severity_confidence": round(
                torch.softmax(outputs["severity"], dim=1).max().item(), 4
            ),
        }
