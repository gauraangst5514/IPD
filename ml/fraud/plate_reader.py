"""
License Plate Reader Module

Reads Indian license plates from vehicle images using EasyOCR (optional).
Falls back to returning empty results if EasyOCR is not installed.

Indian plate format: XX-00-XX-0000
Examples: MH02AB1234, DL7CQ1234, KA01MH9999

Cross-references detected plate with the claimed vehicle's registration number
to detect plate_number_mismatch fraud.
"""

import re
from typing import Optional

# Indian license plate regex pattern
# Format: 2 letters (state) + 1-2 digits (district) + 0-3 letters (series) + 4 digits (number)
INDIAN_PLATE_PATTERN = re.compile(
    r"[A-Z]{2}\s*\d{1,2}\s*[A-Z]{0,3}\s*\d{4}"
)

# Try to import easyocr - gracefully handle if not installed
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# Module-level reader instance (lazy loaded)
_reader = None


def _get_reader():
    """Lazy-load EasyOCR reader to avoid startup overhead."""
    global _reader
    if _reader is None and EASYOCR_AVAILABLE:
        _reader = easyocr.Reader(["en"], gpu=False)
    return _reader


def normalize_plate(plate: str) -> str:
    """
    Normalize a plate number by removing spaces, hyphens, and converting to uppercase.
    MH 02 AB 1234 -> MH02AB1234
    MH-02-AB-1234 -> MH02AB1234
    """
    return re.sub(r"[\s\-]", "", plate.upper().strip())


def extract_plates_from_text(text: str) -> list[str]:
    """Extract Indian license plate patterns from arbitrary text."""
    matches = INDIAN_PLATE_PATTERN.findall(text.upper())
    # Normalize each match
    return [normalize_plate(m) for m in matches]


def read_plates_from_image(image_bytes: bytes) -> list[str]:
    """
    Attempt to read license plate numbers from an image.

    Uses EasyOCR if available, otherwise returns empty list.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, etc.)

    Returns:
        List of detected Indian license plate numbers (normalized).
    """
    if not EASYOCR_AVAILABLE:
        return []

    reader = _get_reader()
    if reader is None:
        return []

    try:
        # EasyOCR can read from bytes via numpy array
        import numpy as np
        from PIL import Image
        import io

        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)

        # Run OCR
        results = reader.readtext(image_np, detail=0)

        # Combine all detected text and search for plate patterns
        all_text = " ".join(results)
        plates = extract_plates_from_text(all_text)

        return plates

    except Exception as e:
        print(f"⚠️  Plate reader error: {e}")
        return []


def check_plate_match(
    image_bytes: bytes,
    claimed_registration: str,
) -> dict:
    """
    Detect plates in an image and check against the claimed registration number.

    Args:
        image_bytes: Raw image bytes
        claimed_registration: The vehicle's registered plate number from the database

    Returns:
        {
            "detected_plates": list of plates found in image,
            "claimed_plate": normalized claimed registration,
            "match": True/False/None (None if no plates detected),
            "flag": "plate_number_mismatch" or None
        }
    """
    detected_plates = read_plates_from_image(image_bytes)
    claimed_normalized = normalize_plate(claimed_registration) if claimed_registration else ""

    if not detected_plates or not claimed_normalized:
        # Cannot determine match - no plates detected or no claimed plate
        return {
            "detected_plates": detected_plates,
            "claimed_plate": claimed_normalized,
            "match": None,
            "flag": None,
        }

    # Check if any detected plate matches the claimed registration
    match_found = any(
        plate == claimed_normalized for plate in detected_plates
    )

    return {
        "detected_plates": detected_plates,
        "claimed_plate": claimed_normalized,
        "match": match_found,
        "flag": "plate_number_mismatch" if not match_found else None,
    }
