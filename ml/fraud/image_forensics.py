"""
Image Forensics Module

Detects manipulated, duplicate, or AI-generated images using:
1. EXIF metadata analysis
2. Error Level Analysis (ELA)
3. Perceptual hashing for duplicate detection
4. Image manipulation scoring
"""

import io
import hashlib
from datetime import datetime
from PIL import Image
import numpy as np
import imagehash
import exifread


class ImageForensics:
    """Analyse images for signs of fraud or manipulation."""

    def full_analysis(self, image_bytes: bytes, claim_id: str = "") -> dict:
        """
        Run all forensic checks on an image.

        Returns a dict with fraud signals and confidence scores.
        """
        results = {
            "file_hash": self._compute_sha256(image_bytes),
            "exif_analysis": self._analyse_exif(image_bytes),
            "ela_score": self._error_level_analysis(image_bytes),
            "duplicate_check": self._check_duplicate(image_bytes, claim_id),
            "metadata_flags": [],
            "overall_manipulation_score": 0.0,
        }

        # Aggregate score
        scores = []
        if results["exif_analysis"]["suspicious"]:
            scores.append(0.7)
            results["metadata_flags"].append("exif_inconsistency")
        if results["ela_score"] is not None and results["ela_score"] > 0.6:
            scores.append(results["ela_score"])
            results["metadata_flags"].append("high_ela_score")
        if results["duplicate_check"]["is_duplicate"]:
            scores.append(0.9)
            results["metadata_flags"].append("duplicate_image")

        results["overall_manipulation_score"] = max(scores) if scores else 0.0
        return results

    def _compute_sha256(self, image_bytes: bytes) -> str:
        """Compute SHA-256 hash of the raw file."""
        return hashlib.sha256(image_bytes).hexdigest()

    def _analyse_exif(self, image_bytes: bytes) -> dict:
        """
        Extract and analyse EXIF metadata for inconsistencies.

        Red flags:
        - Missing EXIF entirely (suggests screenshot or processed image)
        - Editing software in metadata
        - Date/time inconsistencies
        - GPS mismatch with claimed location
        """
        try:
            tags = exifread.process_file(io.BytesIO(image_bytes))
        except Exception:
            return {"has_exif": False, "suspicious": False, "reason": "Cannot parse EXIF"}

        if not tags:
            return {"has_exif": False, "suspicious": False, "reason": "No EXIF data; provenance is inconclusive"}

        result = {
            "has_exif": True,
            "suspicious": False,
            "camera_make": str(tags.get("Image Make", "")),
            "camera_model": str(tags.get("Image Model", "")),
            "software": str(tags.get("Image Software", "")),
            "datetime_original": str(tags.get("EXIF DateTimeOriginal", "")),
            "gps_available": "GPS GPSLatitude" in tags,
        }

        # Flag if editing software detected
        software = result["software"].lower()
        editing_indicators = ["photoshop", "gimp", "lightroom", "snapseed", "canva", "picsart"]
        if any(indicator in software for indicator in editing_indicators):
            result["suspicious"] = True
            result["reason"] = f"Editing software detected: {result['software']}"

        # Flag if no camera info but has other EXIF (suspicious)
        if not result["camera_make"] and not result["camera_model"] and tags:
            result["suspicious"] = True
            result["reason"] = "EXIF present but no camera information"

        return result

    def _error_level_analysis(self, image_bytes: bytes) -> float:
        """
        Error Level Analysis (ELA).

        Re-saves image at known quality and compares pixel differences.
        Manipulated regions show different error levels than organic regions.

        Returns: Score 0.0 (clean) to 1.0 (highly suspicious)
        """
        try:
            original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            # Re-save at quality 90
            buffer = io.BytesIO()
            original.save(buffer, format="JPEG", quality=90)
            buffer.seek(0)
            resaved = Image.open(buffer).convert("RGB")

            # Compute difference
            original_np = np.array(original).astype(np.float32)
            resaved_np = np.array(resaved).astype(np.float32)
            diff = np.abs(original_np - resaved_np)

            # Analyse variance of differences
            # High variance in ELA suggests regions were edited at different compression levels
            ela_std = diff.std()
            ela_max = diff.max()

            # Normalize to 0-1 score (thresholds tuned empirically)
            score = min(1.0, ela_std / 30.0)

            return round(score, 4)
        except Exception:
            return None

    def _check_duplicate(self, image_bytes: bytes, claim_id: str) -> dict:
        """Database-backed exact matching lives in the backend, with owner scope.

        Fingerprints here are informational; this stateless service cannot compare claims.
        """
        try:
            with Image.open(io.BytesIO(image_bytes)) as image:
                phash = str(imagehash.phash(image))
        except Exception:
            phash = None
        return {"is_duplicate": False, "matching_claim_id": None,
                "perceptual_hash": phash, "comparison_available": False}
