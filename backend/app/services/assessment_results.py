"""Aggregate available damage results without manufacturing missing values."""
from collections import Counter


def aggregate_damage(results):
    damage = [r for r in results if r.get("damage_analysis_available", True)
              and r.get("severity") in {"minor", "moderate", "severe"}
              and r.get("primary_damage_type")]
    order = {"minor": 1, "moderate": 2, "severe": 3}
    detections = [d for r in results if r.get("damage_analysis_available", True)
                  for d in r.get("detections", [])]
    confidences = [d["confidence"] for d in detections if isinstance(d.get("confidence"), (int, float))]
    costs = [r for r in damage if isinstance(r.get("cost_estimate_min"), (int, float))
             and isinstance(r.get("cost_estimate_max"), (int, float))]
    highest_cost = max(costs, key=lambda r: r["cost_estimate_max"]) if costs else None
    return {
        "severity": max((r["severity"] for r in damage), key=order.get) if damage else None,
        "primary_damage_type": Counter(r["primary_damage_type"] for r in damage).most_common(1)[0][0] if damage else None,
        "confidence": sum(confidences) / len(confidences) if confidences else None,
        "cost_min": max(r["cost_estimate_min"] for r in costs) if costs else None,
        "cost_max": highest_cost["cost_estimate_max"] if highest_cost else None,
        "cost_breakdown": highest_cost.get("cost_breakdown") if highest_cost else None,
        "detections": detections,
    }
