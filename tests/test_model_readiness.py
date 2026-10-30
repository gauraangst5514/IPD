import importlib.util
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HAS_IMAGING = all(importlib.util.find_spec(m) for m in ("PIL", "numpy"))


@unittest.skipUnless(HAS_IMAGING, "Install tests/requirements.txt for checkpoint readiness tests")
class ModelReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        from PIL import Image
        buffer = io.BytesIO()
        Image.new("RGB", (64, 64), "blue").save(buffer, format="JPEG")
        self.image = buffer.getvalue()

    def test_missing_checkpoint_never_downloads_or_labels_generic_objects(self):
        from ml.detection.detector import DamageDetector
        yolo = Mock()
        with patch.dict(os.environ, {"DAMAGE_MODEL_PATH": str(Path(self.tmp.name) / "missing.pt")}), \
             patch.dict("sys.modules", {"ultralytics": SimpleNamespace(YOLO=yolo)}):
            detector = DamageDetector(device="cpu")
            result = detector.detect(self.image)
        yolo.assert_not_called()
        self.assertFalse(result["damage_analysis_available"])
        self.assertIsNone(result["damage_detected"])
        self.assertIsNone(result["severity"])
        self.assertEqual(result["detections"], [])

    def test_incompatible_checkpoint_classes_are_rejected(self):
        from ml.detection.detector import DamageDetector
        checkpoint = Path(self.tmp.name) / "object-model.pt"
        checkpoint.touch()
        yolo = Mock(return_value=SimpleNamespace(names={0: "person", 1: "car"}))
        with patch.dict(os.environ, {"DAMAGE_MODEL_PATH": str(checkpoint)}), \
             patch.dict("sys.modules", {"ultralytics": SimpleNamespace(YOLO=yolo)}), \
             self.assertLogs("ml.detection.detector", level="ERROR"):
            detector = DamageDetector(device="cpu")
        self.assertFalse(detector.trained)
        self.assertEqual(detector.status()["reason"], "checkpoint_load_failed")

    def test_actual_detector_wrapper_keeps_raw_confidence(self):
        from ml.detection.detector import DamageDetector, CLASS_NAMES
        checkpoint = Path(self.tmp.name) / "damage.pt"
        checkpoint.touch()
        box = SimpleNamespace(cls=[SimpleNamespace(item=lambda: 1)],
            conf=[SimpleNamespace(item=lambda: 0.8)],
            xywhn=[SimpleNamespace(tolist=lambda: [0.5, 0.5, 0.2, 0.2])])
        model = Mock()
        model.names = CLASS_NAMES
        model.predict.return_value = [SimpleNamespace(boxes=[box])]
        with patch.dict(os.environ, {"DAMAGE_MODEL_PATH": str(checkpoint)}), \
             patch.dict("sys.modules", {"ultralytics": SimpleNamespace(YOLO=Mock(return_value=model))}):
            detector = DamageDetector(device="cpu")
            with patch.object(detector, "_annotate_with_detections", return_value=b"overlay"):
                result = detector.detect(self.image)
        self.assertTrue(result["damage_analysis_available"])
        self.assertEqual(result["detections"][0]["confidence"], 0.8)
        self.assertEqual(model.predict.call_count, 1)


if __name__ == "__main__":
    unittest.main()
