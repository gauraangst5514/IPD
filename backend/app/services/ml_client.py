"""
ML Service Client

Makes HTTP calls to the separate ML inference service (ml/serve.py)
to analyze images for damage, severity, cost, and fraud.
"""

import httpx
from typing import Optional

from app.core.config import get_settings

settings = get_settings()

ML_TIMEOUT = 120.0  # ML inference can be slow on CPU


class MLServiceClient:
    """HTTP client for the ML inference service."""

    def __init__(self):
        self.base_url = settings.ML_SERVICE_URL

    async def analyze_image(
        self,
        image_bytes: bytes,
        filename: str = "image.jpg",
        vehicle_make: str = "hyundai",
        vehicle_year: int = 2022,
        region: str = "mumbai",
        claim_id: str = "",
        description: str = "",
        registration_number: str = "",
    ) -> dict:
        """
        Send an image to the ML service for full analysis.

        Returns the AnalysisResponse from the ML service:
        {
            "damage_detected": bool,
            "num_instances": int,
            "detections": [...],
            "severity": "minor" | "moderate" | "severe",
            "severity_score": float,
            "severity_reasoning": dict,
            "primary_damage_type": str,
            "cost_estimate_min": float,
            "cost_estimate_max": float,
            "cost_breakdown": dict,
            "fraud_score": float,
            "fraud_flags": [...]
        }
        """
        async with httpx.AsyncClient(timeout=ML_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/analyze",
                files={"file": (filename, image_bytes, "image/jpeg")},
                data={
                    "vehicle_make": vehicle_make,
                    "vehicle_year": str(vehicle_year),
                    "region": region,
                    "claim_id": claim_id,
                    "description": description,
                    "registration_number": registration_number,
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_annotated_image(self, image_bytes: bytes, filename: str = "image.jpg") -> bytes:
        """Get the annotated image (boxes drawn) from the ML service."""
        async with httpx.AsyncClient(timeout=ML_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/detect",
                files={"file": (filename, image_bytes, "image/jpeg")},
            )
            response.raise_for_status()
            return response.content

    async def health_check(self) -> dict:
        """Check if ML service is alive."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.json()
        except Exception as e:
            return {"status": "unreachable", "error": str(e)}


# Singleton
_ml_client = None


def get_ml_client() -> MLServiceClient:
    global _ml_client
    if _ml_client is None:
        _ml_client = MLServiceClient()
    return _ml_client
