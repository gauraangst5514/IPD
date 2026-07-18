"""
Damage-to-Cost Estimation Engine

THE MOAT: Maps damage type + severity + vehicle model + region → estimated repair cost.

This is what makes IntelliClaim useful to insurers. Detection alone is academic.
Cost estimation is money.

Architecture:
- Rule-based baseline using industry pricing data
- Adjustments for vehicle make/model (luxury vs economy)
- Regional cost multipliers (Mumbai vs Indore)
- Policy type adjustments (zero-dep vs standard)
"""

from dataclasses import dataclass


@dataclass
class CostEstimate:
    min_cost: float
    max_cost: float
    breakdown: dict
    confidence: float
    currency: str = "INR"


# === PRICING DATA (India-specific) ===
# Base costs by damage type and severity (in INR)
# Source: Industry estimates, OEM service center data
BASE_REPAIR_COSTS = {
    "scratch": {
        "minor": {"parts": 0, "labour": 500, "paint": 1500},
        "moderate": {"parts": 0, "labour": 1000, "paint": 3500},
        "severe": {"parts": 500, "labour": 2000, "paint": 6000},
    },
    "dent": {
        "minor": {"parts": 0, "labour": 1500, "paint": 2000},
        "moderate": {"parts": 2000, "labour": 3000, "paint": 4000},
        "severe": {"parts": 5000, "labour": 5000, "paint": 6000},
    },
    "crack": {
        "minor": {"parts": 1000, "labour": 1000, "paint": 1500},
        "moderate": {"parts": 4000, "labour": 2500, "paint": 3000},
        "severe": {"parts": 8000, "labour": 4000, "paint": 5000},
    },
    "shatter": {  # glass damage
        "minor": {"parts": 3000, "labour": 1000, "paint": 0},
        "moderate": {"parts": 8000, "labour": 2000, "paint": 0},
        "severe": {"parts": 15000, "labour": 3000, "paint": 0},
    },
    "bumper": {
        "minor": {"parts": 1000, "labour": 1500, "paint": 2000},
        "moderate": {"parts": 4000, "labour": 2500, "paint": 3500},
        "severe": {"parts": 8000, "labour": 4000, "paint": 5000},
    },
    "panel": {
        "minor": {"parts": 2000, "labour": 2000, "paint": 3000},
        "moderate": {"parts": 6000, "labour": 4000, "paint": 5000},
        "severe": {"parts": 12000, "labour": 6000, "paint": 7000},
    },
}

# Vehicle segment multipliers (luxury cars cost more to repair)
VEHICLE_MULTIPLIERS = {
    # Economy segment
    "maruti": 1.0,
    "hyundai": 1.1,
    "tata": 1.0,
    "renault": 1.1,
    "kia": 1.2,
    "honda": 1.3,
    "toyota": 1.3,
    # Premium segment
    "skoda": 1.5,
    "volkswagen": 1.5,
    "mg": 1.4,
    "jeep": 1.6,
    # Luxury segment
    "bmw": 2.5,
    "mercedes": 2.8,
    "audi": 2.5,
    "land rover": 2.8,
    "volvo": 2.3,
    "porsche": 3.5,
    "jaguar": 2.6,
}

# Regional multipliers (Tier 1 cities cost more)
REGIONAL_MULTIPLIERS = {
    "mumbai": 1.3,
    "delhi": 1.25,
    "bangalore": 1.2,
    "chennai": 1.15,
    "pune": 1.15,
    "hyderabad": 1.1,
    "kolkata": 1.1,
    "ahmedabad": 1.05,
    # Default for Tier 2/3
    "default": 1.0,
}

# Age depreciation (older cars have cheaper parts in some cases)
AGE_ADJUSTMENTS = {
    0: 1.0,   # Brand new
    1: 1.0,
    2: 0.95,
    3: 0.90,
    4: 0.85,
    5: 0.80,
    6: 0.75,
    7: 0.70,
}


class CostEstimationEngine:
    """
    Estimates repair cost based on:
    - Damage type and severity
    - Vehicle make, model, year
    - Region
    - Policy type
    """

    def estimate(
        self,
        damage_type: str,
        severity: str,
        vehicle_make: str,
        vehicle_year: int,
        region: str = "default",
        policy_type: str = "comprehensive",
    ) -> CostEstimate:
        """
        Estimate repair cost.

        Returns min/max range to account for uncertainty.
        """
        # Get base costs
        base = BASE_REPAIR_COSTS.get(damage_type, BASE_REPAIR_COSTS["dent"])
        severity_costs = base.get(severity, base["moderate"])

        # Apply vehicle multiplier
        make_lower = vehicle_make.lower()
        vehicle_mult = VEHICLE_MULTIPLIERS.get(make_lower, 1.2)

        # Apply regional multiplier
        region_lower = region.lower()
        region_mult = REGIONAL_MULTIPLIERS.get(region_lower, REGIONAL_MULTIPLIERS["default"])

        # Apply age adjustment
        current_year = 2026
        vehicle_age = max(0, min(7, current_year - vehicle_year))
        age_mult = AGE_ADJUSTMENTS.get(vehicle_age, 0.70)

        # Calculate component costs
        parts_cost = severity_costs["parts"] * vehicle_mult * age_mult
        labour_cost = severity_costs["labour"] * region_mult
        paint_cost = severity_costs["paint"] * region_mult

        total = parts_cost + labour_cost + paint_cost

        # Apply variance for min/max range (±15%)
        min_cost = round(total * 0.85, -2)  # Round to nearest 100
        max_cost = round(total * 1.15, -2)

        breakdown = {
            "parts": round(parts_cost, -2),
            "labour": round(labour_cost, -2),
            "paint": round(paint_cost, -2),
            "vehicle_multiplier": vehicle_mult,
            "region_multiplier": region_mult,
            "age_adjustment": age_mult,
        }

        # Confidence based on how specific our data is
        confidence = 0.7  # Base confidence
        if make_lower in VEHICLE_MULTIPLIERS:
            confidence += 0.1
        if region_lower in REGIONAL_MULTIPLIERS:
            confidence += 0.1

        return CostEstimate(
            min_cost=max(500, min_cost),  # Floor at ₹500
            max_cost=max(1000, max_cost),
            breakdown=breakdown,
            confidence=round(confidence, 2),
        )

    def estimate_multi_damage(
        self,
        damages: list[dict],
        vehicle_make: str,
        vehicle_year: int,
        region: str = "default",
    ) -> CostEstimate:
        """
        Estimate cost for multiple damage areas on same vehicle.

        Applies a discount factor for combined repairs (labour reuse).
        """
        if not damages:
            return CostEstimate(min_cost=0, max_cost=0, breakdown={}, confidence=0.0)

        total_min = 0
        total_max = 0
        combined_breakdown = {"parts": 0, "labour": 0, "paint": 0}

        for i, damage in enumerate(damages):
            estimate = self.estimate(
                damage_type=damage["type"],
                severity=damage["severity"],
                vehicle_make=vehicle_make,
                vehicle_year=vehicle_year,
                region=region,
            )

            # Discount labour for additional repairs (shared setup time)
            labour_discount = 1.0 if i == 0 else 0.7
            adjusted_breakdown = estimate.breakdown.copy()
            adjusted_breakdown["labour"] *= labour_discount

            total_min += estimate.min_cost * (1.0 if i == 0 else 0.85)
            total_max += estimate.max_cost * (1.0 if i == 0 else 0.85)
            combined_breakdown["parts"] += adjusted_breakdown["parts"]
            combined_breakdown["labour"] += adjusted_breakdown["labour"]
            combined_breakdown["paint"] += adjusted_breakdown["paint"]

        return CostEstimate(
            min_cost=round(total_min, -2),
            max_cost=round(total_max, -2),
            breakdown=combined_breakdown,
            confidence=0.65,
        )
