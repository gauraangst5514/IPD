"""Extract image evidence without inferring fraud from metadata or JPEG error."""
import hashlib
import io
import logging
import sqlite3

from PIL import Image
import numpy as np
import imagehash
import exifread

from ml.fraud.evidence import indicator, summarize
from ml.fraud.image_history import ImageHistory

logger = logging.getLogger(__name__)


class ImageForensics:
    def __init__(self, history_path=None, history=None):
        self.history = history if history is not None else ImageHistory(history_path)

    def full_analysis(self, image_bytes: bytes, claim_id: str = "", image_id: str = "") -> dict:
        exif = self._analyse_exif(image_bytes)
        ela = self._error_level_analysis(image_bytes)
        duplicate = self._check_duplicate(image_bytes, claim_id, image_id)
        indicators = [indicator("image_metadata", exif["status"], exif["reason"], exif)]
        indicators.append(indicator(
            "jpeg_recompression_difference", "informational" if ela is not None else "unavailable",
            "JPEG recompression difference is a diagnostic, not proof of editing or fraud.",
            {"difference_std": ela},
        ))
        if duplicate["status"] == "checked":
            matched = bool(duplicate["matches"])
            indicators.append(indicator(
                "duplicate_image", "review" if matched else "not_observed",
                "Image matches found in other claims; inspect resubmission context." if matched
                else "No matching image found in the indexed claim history.",
                duplicate,
            ))
        else:
            indicators.append(indicator("duplicate_image", "unavailable",
                "Image history check could not be completed; request manual review.", duplicate))
        summary = summarize(indicators)
        return {
            "file_hash": hashlib.sha256(image_bytes).hexdigest(),
            "exif_analysis": exif, "ela_difference_std": ela,
            "duplicate_check": duplicate, "metadata_flags": summary["fraud_flags"],
            "overall_manipulation_score": None,  # compatibility; no invented score
            **summary,
        }

    def _analyse_exif(self, image_bytes: bytes) -> dict:
        try:
            tags = exifread.process_file(io.BytesIO(image_bytes))
        except Exception:
            return {"status": "unavailable", "has_exif": False,
                    "reason": "EXIF could not be parsed; no fraud inference is made."}
        if not tags:
            return {"status": "unavailable", "has_exif": False,
                    "reason": "EXIF metadata is absent; export and messaging can remove metadata."}
        return {
            "status": "informational", "has_exif": True,
            "reason": "Metadata extracted; presence and software tags do not establish authenticity.",
            "camera_make": str(tags.get("Image Make", "")),
            "camera_model": str(tags.get("Image Model", "")),
            "software": str(tags.get("Image Software", "")),
            "datetime_original": str(tags.get("EXIF DateTimeOriginal", "")),
            "gps_available": "GPS GPSLatitude" in tags,
        }

    def _error_level_analysis(self, image_bytes: bytes):
        try:
            with Image.open(io.BytesIO(image_bytes)) as source:
                original = source.convert("RGB")
            buffer = io.BytesIO()
            original.save(buffer, format="JPEG", quality=90)
            buffer.seek(0)
            with Image.open(buffer) as source:
                resaved = source.convert("RGB")
            diff = np.abs(np.array(original).astype(np.float32) - np.array(resaved).astype(np.float32))
            return round(float(diff.std()), 4)
        except Exception:
            return None

    def _check_duplicate(self, image_bytes: bytes, claim_id: str, image_id: str = "") -> dict:
        try:
            with Image.open(io.BytesIO(image_bytes)) as source:
                image = source.convert("RGB")
            result = self.history.check_and_register(
                claim_id, image_id, hashlib.sha256(image_bytes).hexdigest(),
                str(imagehash.phash(image)), str(imagehash.dhash(image)),
            )
            matches = result["matches"]
            return {**result, "is_duplicate": bool(matches) if result["status"] == "checked" else None,
                    "matching_claim_id": matches[0]["claim_id"] if matches else None}
        except (sqlite3.Error, OSError):
            logger.exception("Image history unavailable")
            return {"status": "unavailable", "reason": "history_unavailable", "matches": [], "is_duplicate": None}
        except Exception:
            logger.exception("Could not fingerprint image")
            return {"status": "unavailable", "reason": "image_unreadable", "matches": [], "is_duplicate": None}
