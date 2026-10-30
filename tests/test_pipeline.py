import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from ml.pipeline import AssessmentPipeline

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services.assessment_results import aggregate_damage


def damage_result(available=True, detected=True):
    return {
        "damage_analysis_available": available,
        "damage_detected": detected if available else None,
        "num_instances": 1 if available and detected else 0,
        "detections": [{"label": "scratch", "confidence": 0.82, "bbox": [0.5, 0.5, 0.2, 0.2]}] if available and detected else [],
        "severity": "minor" if available and detected else None,
        "severity_score": 0.05 if available and detected else None,
        "severity_reasoning": {"total_area_coverage": 0.04},
        "primary_damage_type": "scratch" if available and detected else None,
    }


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.detector = Mock(trained=True)
        self.detector.status.return_value = {"available": True}
        self.detector.detect.return_value = damage_result()
        self.forensics = Mock()
        self.forensics.full_analysis.return_value = {"fraud_indicators": [
            {"code": "duplicate_image", "status": "review", "detail": "Match", "evidence": {"matches": [{"claim_id": "old"}]}}]}
        self.cost = Mock()
        self.cost.estimate.return_value = SimpleNamespace(min_cost=1000, max_cost=2000, breakdown={"parts": 500})
        self.text = Mock()
        self.text.check_all.return_value = {"flags": [], "details": {}}
        self.pipeline = AssessmentPipeline(self.detector, self.forensics, self.cost, self.text)

    def test_normal_assessment_preserves_evidence_and_raw_model_confidence(self):
        result = self.pipeline.analyze(b"fixture", description="door scratch")
        self.assertEqual(result["detections"][0]["confidence"], 0.82)
        self.assertEqual(result["cost_estimate_min"], 1000)
        self.assertEqual(result["severity_method"], "area_heuristic")
        self.assertTrue(result["review_required"])
        self.assertIsNone(result["fraud_score"])

    def test_missing_detector_does_not_generate_severity_or_cost(self):
        self.detector.trained = False
        self.detector.detect.return_value = damage_result(False)
        result = self.pipeline.analyze(b"fixture", description="scratch")
        self.assertIsNone(result["damage_detected"])
        self.assertIsNone(result["severity"])
        self.assertIsNone(result["cost_estimate_min"])
        self.cost.estimate.assert_not_called()
        self.text.check_all.assert_not_called()
        self.assertTrue(result["review_required"])

    def test_no_visible_damage_does_not_become_minor_with_a_price(self):
        self.detector.detect.return_value = damage_result(detected=False)
        result = self.pipeline.analyze(b"fixture")
        self.assertFalse(result["damage_detected"])
        self.assertIsNone(result["severity"])
        self.assertIsNone(result["cost_estimate_max"])

    def test_detector_failure_does_not_discard_matching_history(self):
        self.detector.detect.side_effect = RuntimeError("inference unavailable")
        with self.assertLogs("ml.pipeline", level="ERROR"):
            result = self.pipeline.analyze(b"fixture")
        self.assertFalse(result["damage_analysis_available"])
        self.assertIn("duplicate_image", result["fraud_flags"])

    def test_cost_failure_preserves_damage_and_reuse(self):
        self.cost.estimate.side_effect = RuntimeError("cost unavailable")
        with self.assertLogs("ml.pipeline", level="ERROR"):
            result = self.pipeline.analyze(b"fixture")
        self.assertTrue(result["damage_detected"])
        self.assertIsNone(result["cost_estimate_max"])
        self.assertIn("duplicate_image", result["fraud_flags"])

    def test_text_failure_preserves_other_components(self):
        self.text.check_all.side_effect = RuntimeError("text unavailable")
        with self.assertLogs("ml.pipeline", level="ERROR"):
            result = self.pipeline.analyze(b"fixture", description="scratch")
        self.assertTrue(result["damage_detected"])
        self.assertEqual(next(i for i in result["fraud_indicators"] if i["code"] == "description_consistency")["status"], "unavailable")

    def test_forensics_failure_preserves_damage(self):
        self.forensics.full_analysis.side_effect = RuntimeError("evidence unavailable")
        with self.assertLogs("ml.pipeline", level="ERROR"):
            result = self.pipeline.analyze(b"fixture")
        self.assertTrue(result["damage_detected"])
        self.assertFalse(result["checks_complete"])

    def test_unbuilt_models_are_explicitly_unavailable(self):
        result = self.pipeline.analyze(b"fixture")
        status = {i["code"]: i["status"] for i in result["fraud_indicators"]}
        self.assertEqual(status["tamper_detection"], "unavailable")
        self.assertEqual(status["damage_reidentification"], "unavailable")


class DamageAggregationTests(unittest.TestCase):
    def test_all_unavailable_has_no_fabricated_damage_price_or_confidence(self):
        summary = aggregate_damage([damage_result(False)])
        for field in ("severity", "primary_damage_type", "cost_min", "cost_max", "confidence"):
            self.assertIsNone(summary[field])

    def test_uses_detection_confidence_not_severity_score(self):
        result = damage_result()
        result.update(cost_estimate_min=1000, cost_estimate_max=2000)
        summary = aggregate_damage([result, damage_result(False)])
        self.assertEqual(summary["confidence"], 0.82)
        self.assertEqual(summary["cost_max"], 2000)

    def test_empty_result_is_unassessed(self):
        self.assertIsNone(aggregate_damage([])["severity"])


if __name__ == "__main__":
    unittest.main()
