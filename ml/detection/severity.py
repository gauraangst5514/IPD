"""
Severity Estimation from Detection Results

CarDD provides damage *type* labels but not *severity*. We derive severity
(minor / moderate / severe) from the detection output using an explainable,
rule-based heuristic.

Signals used:
1. Total damage area coverage (sum of bounding-box areas / image area)
2. Number of distinct damage instances
3. Damage type weighting (some damage is inherently more severe)
4. Largest single damage area

This is explainable and defensible — an assessor can understand exactly
why a claim was scored a certain severity.
"""

from dataclasses import dataclass


# Some damage types are inherently more severe than others.
# A glass shatter or tire flat is structurally significant; a scratch is cosmetic.
DAMAGE_TYPE_SEVERITY_WEIGHT = {
    "dent": 1.0,
    "scratch": 0.6,        # mostly cosmetic
    "crack": 1.3,
    "glass_shatter": 1.6,  # safety-critical
    "glass shatter": 1.6,
    "lamp_broken": 1.4,    # safety + electronics
    "lamp broken": 1.4,
    "tire_flat": 1.5,      # safety-critical, immobilizing
    "tire flat": 1.5,
}


@dataclass
class DamageInstance:
    """A single detected damage region."""
    label: str
    confidence: float
    # Normalized bounding box [x_center, y_center, width, height]
    bbox: tuple

    @property
    def area(self) -> float:
        """Normalized area (fraction of image)."""
        _, _, w, h = self.bbox
        return w * h


@dataclass
class SeverityResult:
    severity: str | None  # minor / moderate / severe
    score: float   # 0.0 - 1.0 raw severity score
    reasoning: dict  # explainable breakdown


class SeverityEstimator:
    """
    Estimates overall claim severity from a set of detected damage instances.
    """

    # Thresholds for final severity classification.
    # NOTE: bounding-box areas are naturally small (a single damage instance
    # rarely exceeds ~25% of the image), so thresholds are tuned accordingly.
    # These can be re-calibrated on the real validation set after training by
    # inspecting the distribution of severity scores.
    MINOR_THRESHOLD = 0.08
    SEVERE_THRESHOLD = 0.25

    def estimate(self, detections: list[DamageInstance]) -> SeverityResult:
        """
        Compute severity from a list of detected damage instances.

        Returns a SeverityResult with the level, raw score, and reasoning.
        """
        if not detections:
            return SeverityResult(
                severity=None,
                score=0.0,
                reasoning={"note": "No damage detected"},
            )

        # Signal 1: Total area coverage
        total_area = sum(d.area for d in detections)
        # Cap at 1.0 (boxes can overlap)
        total_area = min(total_area, 1.0)

        # Signal 2: Largest single damage
        max_area = max(d.area for d in detections)

        # Signal 3: Instance count factor
        num_instances = len(detections)
        count_factor = min(num_instances / 5.0, 1.0)  # saturates at 5 instances

        # Signal 4: Damage-type weighting (use the most severe type present)
        max_type_weight = max(
            DAMAGE_TYPE_SEVERITY_WEIGHT.get(d.label, 1.0) for d in detections
        )

        # Combine signals into a weighted severity score
        # Area is the dominant factor; type weight amplifies; count adds a bit.
        area_component = 0.5 * total_area + 0.3 * max_area
        score = (area_component * max_type_weight) + (0.2 * count_factor)
        score = min(score, 1.0)

        # Classify
        if score < self.MINOR_THRESHOLD:
            severity = "minor"
        elif score < self.SEVERE_THRESHOLD:
            severity = "moderate"
        else:
            severity = "severe"

        # Build explainable reasoning
        reasoning = {
            "total_area_coverage": round(total_area, 4),
            "largest_damage_area": round(max_area, 4),
            "num_damage_instances": num_instances,
            "most_severe_type": max(
                detections, key=lambda d: DAMAGE_TYPE_SEVERITY_WEIGHT.get(d.label, 1.0)
            ).label,
            "type_weight_applied": round(max_type_weight, 2),
            "raw_score": round(score, 4),
            "thresholds": {
                "minor_below": self.MINOR_THRESHOLD,
                "severe_above": self.SEVERE_THRESHOLD,
            },
        }

        return SeverityResult(severity=severity, score=round(score, 4), reasoning=reasoning)

    # Maps CarDD damage categories -> cost engine damage types
    # Preserve canonical damage labels through pricing and persistence.
    CARDD_TO_COST_TYPE = {
        "dent": "dent",
        "scratch": "scratch",
        "crack": "crack",
        "glass_shatter": "glass_shatter",
        "glass shatter": "glass_shatter",
        "lamp_broken": "lamp_broken",
        "lamp broken": "lamp_broken",
        "tire_flat": "tire_flat",
        "tire flat": "tire_flat",
    }

    def primary_damage_type(self, detections: list[DamageInstance]) -> str | None:
        """
        Determine the primary damage type for cost estimation.

        Returns the cost-engine damage type with the largest total area.
        """
        if not detections:
            return None

        # Sum area by type
        type_areas: dict[str, float] = {}
        for d in detections:
            type_areas[d.label] = type_areas.get(d.label, 0.0) + d.area

        primary = max(type_areas, key=type_areas.get)
        return self.CARDD_TO_COST_TYPE.get(primary, "dent")
