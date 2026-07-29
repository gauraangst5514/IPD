"""
Damage-to-Cost Estimation Engine v2

Estimates repair costs using:
1. Damage type + severity (from AI detection)
2. Damage area coverage (from bounding box sizes)
3. Number of damage instances (multi-panel = more expensive)
4. Vehicle make/model segment (economy → luxury multiplier)
5. Vehicle age (depreciation on parts)
6. Regional labour rates (Tier 1 vs Tier 2/3 cities)
7. Part location heuristics (bumper vs door vs hood)

India-specific pricing based on OEM service center data and
multi-brand workshop estimates (2024-2026).
"""

from dataclasses import dataclass


@dataclass
class CostEstimate:
    min_cost: float
    max_cost: float
    breakdown: dict
    confidence: float
    currency: str = "INR"


# ═══════════════════════════════════════════════════════════════
# BASE REPAIR COSTS (INR) — by damage type × severity
# Source: Aggregated from GoMechanic, Denting-Painting.com,
#         OEM workshops (Maruti Arena, Hyundai i-care) 2024-2026
# ═══════════════════════════════════════════════════════════════

BASE_REPAIR_COSTS = {
    "scratch": {
        "minor":    {"parts": 0,     "labour": 800,   "paint": 2000,  "misc": 200},
        "moderate": {"parts": 0,     "labour": 1500,  "paint": 4500,  "misc": 500},
        "severe":   {"parts": 1000,  "labour": 2500,  "paint": 7000,  "misc": 800},
    },
    "dent": {
        "minor":    {"parts": 0,     "labour": 2000,  "paint": 2500,  "misc": 300},
        "moderate": {"parts": 3000,  "labour": 4000,  "paint": 5000,  "misc": 800},
        "severe":   {"parts": 8000,  "labour": 6000,  "paint": 7000,  "misc": 1500},
    },
    "crack": {
        "minor":    {"parts": 2000,  "labour": 1500,  "paint": 2000,  "misc": 500},
        "moderate": {"parts": 6000,  "labour": 3500,  "paint": 4000,  "misc": 1000},
        "severe":   {"parts": 12000, "labour": 5000,  "paint": 6000,  "misc": 2000},
    },
    "shatter": {
        "minor":    {"parts": 5000,  "labour": 1500,  "paint": 0,     "misc": 500},
        "moderate": {"parts": 12000, "labour": 3000,  "paint": 0,     "misc": 1000},
        "severe":   {"parts": 22000, "labour": 4000,  "paint": 0,     "misc": 1500},
    },
    "panel": {
        "minor":    {"parts": 3000,  "labour": 2500,  "paint": 3000,  "misc": 500},
        "moderate": {"parts": 8000,  "labour": 5000,  "paint": 6000,  "misc": 1200},
        "severe":   {"parts": 18000, "labour": 8000,  "paint": 8000,  "misc": 2500},
    },
    "bumper": {
        "minor":    {"parts": 1500,  "labour": 2000,  "paint": 2500,  "misc": 300},
        "moderate": {"parts": 5000,  "labour": 3500,  "paint": 4500,  "misc": 800},
        "severe":   {"parts": 12000, "labour": 5000,  "paint": 6000,  "misc": 1500},
    },
}

# ═══════════════════════════════════════════════════════════════
# VEHICLE SEGMENT MULTIPLIERS
# Based on actual OEM spare part pricing and authorized workshop rates
# ═══════════════════════════════════════════════════════════════

VEHICLE_MULTIPLIERS = {
    # Budget segment (₹5-10L on-road)
    "maruti": 1.0, "maruti suzuki": 1.0, "suzuki": 1.0,
    "tata": 1.05, "datsun": 0.9, "renault": 1.1,

    # Mass market (₹10-18L)
    "hyundai": 1.15, "kia": 1.25, "honda": 1.3,
    "toyota": 1.35, "nissan": 1.2, "ford": 1.25,
    "mahindra": 1.15, "mg": 1.4, "citroen": 1.35,

    # Premium (₹18-35L)
    "skoda": 1.6, "volkswagen": 1.6, "jeep": 1.7,
    "chevrolet": 1.3, "mini": 2.1, "volvo": 2.4,

    # Luxury (₹35L+)
    "bmw": 2.8, "mercedes": 3.0, "mercedes-benz": 3.0,
    "audi": 2.7, "land rover": 3.0, "jaguar": 2.8,
    "lexus": 2.5, "porsche": 3.8,

    # Ultra-luxury (₹1Cr+)
    "rolls royce": 5.0, "bentley": 4.5,
    "lamborghini": 5.5, "ferrari": 5.5,
    "maserati": 4.0, "aston martin": 4.5,
}

# ═══════════════════════════════════════════════════════════════
# REGIONAL MULTIPLIERS (labour rates vary significantly)
# ═══════════════════════════════════════════════════════════════

REGIONAL_MULTIPLIERS = {
    # Tier 1 — Metro (high labour, high rent)
    "mumbai": 1.35, "delhi": 1.30, "bangalore": 1.25,
    "bengaluru": 1.25, "chennai": 1.20, "pune": 1.20,
    "hyderabad": 1.15, "kolkata": 1.15, "gurgaon": 1.30,
    "noida": 1.25, "thane": 1.25, "navi mumbai": 1.25,

    # Tier 2
    "ahmedabad": 1.10, "jaipur": 1.05, "lucknow": 1.05,
    "chandigarh": 1.10, "indore": 1.0, "nagpur": 1.0,
    "surat": 1.05, "kochi": 1.10, "coimbatore": 1.05,
    "visakhapatnam": 1.0, "bhopal": 1.0,

    # Default (Tier 3 / unknown)
    "default": 0.95,
}

# ═══════════════════════════════════════════════════════════════
# AGE DEPRECIATION (affects parts cost — older cars use aftermarket)
# ═══════════════════════════════════════════════════════════════

def _age_multiplier(vehicle_year: int) -> float:
    """Parts cost decreases for older vehicles (aftermarket available)."""
    current_year = 2026
    age = max(0, current_year - vehicle_year)
    if age <= 1:
        return 1.0    # New — OEM parts mandatory for warranty
    elif age <= 3:
        return 0.92   # Slightly cheaper aftermarket emerging
    elif age <= 5:
        return 0.82   # Good aftermarket availability
    elif age <= 8:
        return 0.70   # Abundant aftermarket
    else:
        return 0.60   # Very old — cheap parts, but labour may be harder


# ═══════════════════════════════════════════════════════════════
# AREA-BASED SCALING
# Larger damage areas cost proportionally more (more paint, more pulling)
# ═══════════════════════════════════════════════════════════════

def _area_scale_factor(total_area: float, num_instances: int) -> float:
    """
    Scale cost based on total damage area coverage.
    total_area: sum of normalized bbox areas (0-1 range)
    """
    # Base scale: 1.0 for "typical" damage (~5% coverage)
    # Scale up for larger areas, down for tiny areas
    if total_area <= 0.02:
        scale = 0.7   # Very small damage
    elif total_area <= 0.05:
        scale = 0.85
    elif total_area <= 0.10:
        scale = 1.0   # Typical single-panel damage
    elif total_area <= 0.20:
        scale = 1.3   # Multi-area or large damage
    elif total_area <= 0.35:
        scale = 1.6   # Major damage across multiple panels
    else:
        scale = 2.0   # Catastrophic / multi-panel

    # Additional cost for multiple distinct damage instances (more setup)
    if num_instances >= 5:
        scale *= 1.25
    elif num_instances >= 3:
        scale *= 1.1

    return scale


# ═══════════════════════════════════════════════════════════════
# MAIN ENGINE
# ═══════════════════════════════════════════════════════════════

class CostEstimationEngine:
    """
    Estimates repair cost using damage detection results + claim metadata.
    """

    def estimate(
        self,
        damage_type: str,
        severity: str,
        vehicle_make: str,
        vehicle_year: int,
        region: str = "default",
        total_area: float = 0.08,
        num_instances: int = 1,
        policy_type: str = "comprehensive",
    ) -> CostEstimate:
        """
        Estimate repair cost for a single damage assessment.

        Args:
            damage_type: Primary damage type (dent, scratch, crack, shatter, panel, bumper)
            severity: minor / moderate / severe
            vehicle_make: Vehicle manufacturer
            vehicle_year: Manufacturing year
            region: City or "default"
            total_area: Sum of bounding box areas (0-1), from severity_reasoning
            num_instances: Number of detected damage instances
            policy_type: comprehensive / third_party / zero_dep

        Returns:
            CostEstimate with min/max range and detailed breakdown
        """
        # 1. Get base costs for damage type + severity
        base = BASE_REPAIR_COSTS.get(damage_type, BASE_REPAIR_COSTS["dent"])
        costs = base.get(severity, base["moderate"])

        # 2. Vehicle multiplier
        make_lower = vehicle_make.lower().strip()
        vehicle_mult = VEHICLE_MULTIPLIERS.get(make_lower, 1.2)

        # 3. Regional multiplier (applies to labour)
        region_lower = region.lower().strip()
        region_mult = REGIONAL_MULTIPLIERS.get(region_lower, REGIONAL_MULTIPLIERS["default"])

        # 4. Age factor (applies to parts)
        age_mult = _age_multiplier(vehicle_year)

        # 5. Area scaling (applies to overall)
        area_scale = _area_scale_factor(total_area, num_instances)

        # 6. Calculate components
        parts_cost = costs["parts"] * vehicle_mult * age_mult * area_scale
        labour_cost = costs["labour"] * region_mult * area_scale
        paint_cost = costs["paint"] * region_mult * area_scale
        misc_cost = costs["misc"] * area_scale

        subtotal = parts_cost + labour_cost + paint_cost + misc_cost

        # 7. Policy adjustment
        policy_factor = 1.0
        if policy_type == "zero_dep":
            policy_factor = 1.0  # Full coverage, no depreciation
        elif policy_type == "comprehensive":
            policy_factor = 1.0  # Standard
        elif policy_type == "third_party":
            policy_factor = 1.1  # Out-of-pocket tends to be quoted higher

        total = subtotal * policy_factor

        # 8. Apply variance for min/max range
        # Tighter range for common damage, wider for severe/unusual
        variance = 0.12 if severity == "minor" else 0.15 if severity == "moderate" else 0.20
        min_cost = round(total * (1 - variance), -2)
        max_cost = round(total * (1 + variance), -2)

        # Ensure minimum floor
        min_cost = max(500, min_cost)
        max_cost = max(1000, max_cost)

        # 9. Build detailed breakdown
        breakdown = {
            "parts": round(parts_cost, -2),
            "labour": round(labour_cost, -2),
            "paint": round(paint_cost, -2),
            "misc": round(misc_cost, -2),
            "vehicle_multiplier": round(vehicle_mult, 2),
            "region_multiplier": round(region_mult, 2),
            "age_factor": round(age_mult, 2),
            "area_scale": round(area_scale, 2),
            "num_instances": num_instances,
            "total_area_pct": round(total_area * 100, 1),
        }

        # 10. Confidence score
        confidence = 0.60
        if make_lower in VEHICLE_MULTIPLIERS:
            confidence += 0.10
        if region_lower in REGIONAL_MULTIPLIERS and region_lower != "default":
            confidence += 0.10
        if severity in ("minor", "moderate"):
            confidence += 0.05  # More data points for common severities
        if num_instances >= 2:
            confidence -= 0.05  # Multi-damage is harder to estimate

        return CostEstimate(
            min_cost=min_cost,
            max_cost=max_cost,
            breakdown=breakdown,
            confidence=round(min(0.95, max(0.40, confidence)), 2),
        )

    def estimate_from_detections(
        self,
        detections: list[dict],
        severity: str,
        vehicle_make: str,
        vehicle_year: int,
        region: str = "default",
    ) -> CostEstimate:
        """
        Estimate cost directly from detection results (list of {label, confidence, bbox}).
        More accurate than single-type estimate as it accounts for all damage types.
        """
        if not detections:
            return CostEstimate(min_cost=0, max_cost=0, breakdown={}, confidence=0.0)

        # Group detections by damage type
        from collections import defaultdict
        type_groups = defaultdict(list)
        for det in detections:
            type_groups[det["label"]].append(det)

        total_min = 0
        total_max = 0
        combined_breakdown = {"parts": 0, "labour": 0, "paint": 0, "misc": 0}
        confidences = []

        for i, (damage_type, dets) in enumerate(type_groups.items()):
            # Map CarDD labels to cost engine types
            cost_type = {
                "dent": "dent", "scratch": "scratch", "crack": "crack",
                "glass_shatter": "shatter", "lamp_broken": "panel", "tire_flat": "panel",
            }.get(damage_type, "dent")

            type_area = sum(d["bbox"][2] * d["bbox"][3] for d in dets)

            estimate = self.estimate(
                damage_type=cost_type,
                severity=severity,
                vehicle_make=vehicle_make,
                vehicle_year=vehicle_year,
                region=region,
                total_area=type_area,
                num_instances=len(dets),
            )

            # Discount labour for additional damage types (shared setup)
            labour_discount = 1.0 if i == 0 else 0.6
            adjusted_labour = estimate.breakdown.get("labour", 0) * labour_discount

            total_min += estimate.min_cost * (1.0 if i == 0 else 0.75)
            total_max += estimate.max_cost * (1.0 if i == 0 else 0.75)
            combined_breakdown["parts"] += estimate.breakdown.get("parts", 0)
            combined_breakdown["labour"] += adjusted_labour
            combined_breakdown["paint"] += estimate.breakdown.get("paint", 0)
            combined_breakdown["misc"] += estimate.breakdown.get("misc", 0)
            confidences.append(estimate.confidence)

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        return CostEstimate(
            min_cost=round(total_min, -2),
            max_cost=round(total_max, -2),
            breakdown={k: round(v, -2) for k, v in combined_breakdown.items()},
            confidence=round(avg_confidence, 2),
        )
