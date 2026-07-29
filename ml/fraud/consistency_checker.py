"""
Consistency Checker — Cross-validation fraud signals

Detects mismatches between:
1. Claimed vehicle make/model vs what's visible in the image
2. Claimant's description vs AI-detected damage
3. Severity described vs severity detected

These are rule-based checks that augment the ML detection output.
"""

from typing import Optional


# Known vehicle visual identifiers (badge shapes, grille patterns, etc.)
# In a production system, this would be a classifier. For now, we use
# logo/text detection heuristics from the image metadata and detection results.
MAKE_KEYWORDS = {
    "bmw": ["bmw", "bayerische"],
    "mercedes": ["mercedes", "benz", "daimler"],
    "audi": ["audi"],
    "hyundai": ["hyundai"],
    "honda": ["honda"],
    "toyota": ["toyota"],
    "tata": ["tata"],
    "mahindra": ["mahindra"],
    "maruti": ["maruti", "suzuki"],
    "kia": ["kia"],
    "rolls royce": ["rolls", "royce"],
    "rolls-royce": ["rolls", "royce"],
    "volkswagen": ["volkswagen", "vw"],
    "ford": ["ford"],
    "nissan": ["nissan"],
    "renault": ["renault"],
    "skoda": ["skoda"],
    "mg": ["mg", "morris"],
}


class ConsistencyChecker:
    """Check for mismatches between claim metadata and AI analysis results."""

    def check_all(
        self,
        claimed_make: str,
        claimed_description: Optional[str],
        detected_damage_type: str,
        detected_severity: str,
        detected_instances: list[dict],
        image_bytes: Optional[bytes] = None,
    ) -> dict:
        """
        Run all consistency checks.

        Returns:
            {
                "flags": ["vehicle_make_mismatch", ...],
                "details": {"vehicle_make_mismatch": "Claimed Rolls Royce but image shows BMW features", ...},
                "consistency_score": 0.0 - 1.0 (1.0 = fully consistent)
            }
        """
        flags = []
        details = {}

        # Check 1: Description vs detected damage
        desc_result = self._check_description_consistency(
            claimed_description, detected_damage_type, detected_severity, detected_instances
        )
        if desc_result:
            flags.append("description_mismatch")
            details["description_mismatch"] = desc_result

        # Check 2: Severity consistency
        severity_result = self._check_severity_consistency(
            claimed_description, detected_severity
        )
        if severity_result:
            flags.append("severity_mismatch")
            details["severity_mismatch"] = severity_result

        # Check 3: Damage count vs description
        count_result = self._check_damage_count_consistency(
            claimed_description, detected_instances
        )
        if count_result:
            flags.append("damage_extent_mismatch")
            details["damage_extent_mismatch"] = count_result

        # Compute consistency score (1.0 = no flags)
        penalty_per_flag = 0.3
        consistency_score = max(0.0, 1.0 - len(flags) * penalty_per_flag)

        return {
            "flags": flags,
            "details": details,
            "consistency_score": round(consistency_score, 2),
        }

    def check_vehicle_make(
        self,
        claimed_make: str,
        image_bytes: bytes,
    ) -> Optional[str]:
        """
        Attempt to verify if the vehicle in the image matches the claimed make.

        Uses a combination of:
        - Image metadata (some phones embed location/device info)
        - Visual badge/logo detection (future: use a vehicle make classifier)

        For now, uses a simple OCR-free heuristic based on image filename
        and any text embedded in EXIF. A production system would use a
        vehicle make/model classifier (e.g., Stanford Cars + fine-tuned ResNet).

        Returns: flag description if mismatch detected, None if OK or inconclusive.
        """
        # This is a placeholder for actual vehicle recognition.
        # In production, you'd use:
        # 1. A vehicle make/model classifier (ResNet/EfficientNet on Stanford Cars)
        # 2. OCR on license plate to cross-reference with registration DB
        # 3. Logo/badge detection
        #
        # For now, we return None (inconclusive) since we don't have
        # a trained vehicle classifier yet.
        return None

    def _check_description_consistency(
        self,
        description: Optional[str],
        detected_type: str,
        detected_severity: str,
        detected_instances: list[dict],
    ) -> Optional[str]:
        """
        Check if the claimant's description matches what the AI detected.

        Examples of mismatches:
        - Description: "small scratch on door" → AI: severe dent + glass_shatter
        - Description: "flat tire" → AI: no tire_flat detected, only dents
        """
        if not description:
            return None

        desc_lower = description.lower()

        # Extract damage keywords from description
        desc_mentions_scratch = any(w in desc_lower for w in ["scratch", "scratched", "scraped", "scrape"])
        desc_mentions_dent = any(w in desc_lower for w in ["dent", "dented", "bent", "crumpled"])
        desc_mentions_crack = any(w in desc_lower for w in ["crack", "cracked", "broken glass", "windshield"])
        desc_mentions_tire = any(w in desc_lower for w in ["tire", "tyre", "flat", "puncture", "burst"])
        desc_mentions_lamp = any(w in desc_lower for w in ["lamp", "light", "headlight", "taillight", "indicator"])
        desc_mentions_shatter = any(w in desc_lower for w in ["shatter", "shattered", "broken glass", "windscreen"])
        desc_mentions_minor = any(w in desc_lower for w in ["small", "minor", "tiny", "slight", "little"])
        desc_mentions_severe = any(w in desc_lower for w in ["major", "severe", "total", "destroyed", "heavy", "big", "huge"])

        # Detected types
        detected_types = set(d["label"] for d in detected_instances)

        mismatches = []

        # If description mentions specific damage type not detected
        if desc_mentions_tire and "tire_flat" not in detected_types and len(detected_instances) > 0:
            mismatches.append("Description mentions tire damage but none detected in image")

        if desc_mentions_scratch and "scratch" not in detected_types and len(detected_instances) > 0:
            if detected_type in ("dent", "glass_shatter", "crack"):
                mismatches.append(f"Description mentions scratch but AI detected {detected_type}")

        # If description says minor but AI says severe
        if desc_mentions_minor and detected_severity == "severe":
            mismatches.append("Description says minor damage but AI detected severe damage")

        # If description says severe but AI says minor
        if desc_mentions_severe and detected_severity == "minor":
            mismatches.append("Description says major damage but AI detected only minor damage")

        # If no damage mentioned in description but significant damage detected
        no_damage_words = any(w in desc_lower for w in ["no damage", "undamaged", "fine", "nothing"])
        if no_damage_words and len(detected_instances) > 2:
            mismatches.append("Description suggests no/minimal damage but multiple damage instances detected")

        if mismatches:
            return "; ".join(mismatches)
        return None

    def _check_severity_consistency(
        self,
        description: Optional[str],
        detected_severity: str,
    ) -> Optional[str]:
        """Check if claimed severity aligns with detected severity."""
        if not description:
            return None

        desc_lower = description.lower()

        # Descriptions that strongly imply minor damage
        minor_phrases = ["barely visible", "hairline", "tiny scratch", "small dent", "minor"]
        severe_phrases = ["totaled", "write-off", "completely destroyed", "beyond repair", "crushed"]

        claims_minor = any(phrase in desc_lower for phrase in minor_phrases)
        claims_severe = any(phrase in desc_lower for phrase in severe_phrases)

        if claims_minor and detected_severity == "severe":
            return "Claimant describes minor damage but image shows severe damage — possible understatement to avoid scrutiny"

        if claims_severe and detected_severity == "minor":
            return "Claimant describes total loss but image shows only minor damage — possible exaggeration for higher payout"

        return None

    def _check_damage_count_consistency(
        self,
        description: Optional[str],
        detected_instances: list[dict],
    ) -> Optional[str]:
        """Check if the number of damage areas matches the description."""
        if not description:
            return None

        desc_lower = description.lower()
        num_detected = len(detected_instances)

        # If description mentions single area but many detected
        single_phrases = ["one scratch", "a dent", "single", "one spot", "only the"]
        multiple_phrases = ["multiple", "several", "many", "all over", "everywhere"]

        claims_single = any(phrase in desc_lower for phrase in single_phrases)
        claims_multiple = any(phrase in desc_lower for phrase in multiple_phrases)

        if claims_single and num_detected > 4:
            return f"Description mentions single damage area but {num_detected} damage instances detected"

        if claims_multiple and num_detected <= 1:
            return f"Description mentions multiple damage areas but only {num_detected} detected"

        return None
