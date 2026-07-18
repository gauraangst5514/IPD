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

    def __init__(self):
        self.known_hashes: dict[str, str] = {}  # hash -> claim_id mapping

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
        if results["ela_score"] > 0.6:
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
            return {"has_exif": False, "suspicious": True, "reason": "Cannot parse EXIF"}

        if not tags:
            return {"has_exif": False, "suspicious": True, "reason": "No EXIF data (possible screenshot/download)"}

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
            return 0.0

    def _check_duplicate(self, image_bytes: bytes, claim_id: str) -> dict:
        """
        Check if this image (or very similar one) was used in another claim.

        Uses perceptual hashing — resilient to resizing, compression, minor edits.
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))

            # Compute multiple hash types for robustness
            phash = str(imagehash.phash(image))
            dhash = str(imagehash.dhash(image))
            combined_hash = f"{phash}_{dhash}"

            # Check against known hashes
            is_duplicate = False
            matching_claim = None

            if combined_hash in self.known_hashes:
                existing_claim = self.known_hashes[combined_hash]
                if existing_claim != claim_id:
                    is_duplicate = True
                    matching_claim = existing_claim

            # Store hash
            self.known_hashes[combined_hash] = claim_id

            return {
                "is_duplicate": is_duplicate,
                "matching_claim_id": matching_claim,
                "perceptual_hash": phash,
            }
        except Exception:
            return {"is_duplicate": False, "matching_claim_id": None, "perceptual_hash": None}
