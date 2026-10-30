import hashlib
from contextlib import closing
import importlib.util
import io
import multiprocessing
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ml.fraud.image_history import ImageHistory
from ml.fraud.evidence import indicator, summarize


def fingerprint(value):
    return hashlib.sha256(value.encode()).hexdigest()


def simultaneous_register(path, claim, queue):
    history = ImageHistory(path)
    result = history.check_and_register(claim, claim, fingerprint("same"), "0" * 16, "1" * 16)
    queue.put(bool(result["matches"]))


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "history.sqlite3"
        self.history = ImageHistory(self.path)

    def register(self, claim="A", sha="same", phash="0" * 16, dhash="1" * 16):
        return self.history.check_and_register(claim, "image-" + claim, fingerprint(sha), phash, dhash)

    def test_survives_new_service_instance(self):
        self.register()
        restarted = ImageHistory(self.path)
        result = restarted.check_and_register("B", "b-image", fingerprint("same"), "0" * 16, "1" * 16)
        self.assertEqual(result["matches"][0]["claim_id"], "A")
        self.assertEqual(result["matches"][0]["image_id"], "image-A")
        self.assertEqual(result["matches"][0]["match_type"], "exact_file")

    def test_same_claim_retry_is_not_duplicate_and_is_idempotent(self):
        self.register()
        self.assertEqual(self.register()["matches"], [])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM image_history").fetchone()[0], 1)

    def test_retains_all_claims_instead_of_overwriting_first_owner(self):
        for claim in ("A", "B", "C"):
            self.register(claim)
        self.assertEqual({m["claim_id"] for m in self.register("D")["matches"]}, {"A", "B", "C"})

    def test_near_match_requires_both_hashes(self):
        self.register()
        candidate = self.register("B", "changed bytes", "0" * 15 + "1", "1" * 15 + "0")
        self.assertEqual(candidate["matches"][0]["match_type"], "perceptual_candidate")
        self.assertEqual(candidate["matches"][0]["phash_distance"], 1)
        self.assertEqual(self.register("C", "different", "f" * 16, "1" * 16)["matches"], [])

    def test_anonymous_call_does_not_pollute_history(self):
        self.assertEqual(self.register("")["status"], "unavailable")
        self.assertEqual(self.register("A")["matches"], [])

    def test_simultaneous_processes_observe_each_other(self):
        context = multiprocessing.get_context("spawn")
        queue = context.Queue()
        processes = [context.Process(target=simultaneous_register, args=(str(self.path), c, queue)) for c in ("A", "B")]
        for process in processes:
            process.start()
        results = [queue.get(timeout=20) for _ in processes]
        for process in processes:
            process.join(timeout=20)
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(sorted(results), [False, True])
        queue.close()


class IndicatorTests(unittest.TestCase):
    def test_missing_metadata_is_unavailable_without_review_or_probability(self):
        result = summarize([indicator("image_metadata", "unavailable", "Absent")])
        self.assertIsNone(result["fraud_score"])
        self.assertFalse(result["checks_complete"])
        self.assertFalse(result["review_required"])
        self.assertEqual(result["fraud_flags"], [])

    def test_observation_requests_review_without_classifying_fraud(self):
        result = summarize([indicator("duplicate_image", "review", "Match", {"claim_id": "A"})])
        self.assertTrue(result["review_required"])
        self.assertIsNone(result["fraud_score"])
        self.assertNotIn("is_fraud", result)


HAS_IMAGING = all(importlib.util.find_spec(m) for m in ("PIL", "numpy", "imagehash", "exifread"))


@unittest.skipUnless(HAS_IMAGING, "Install tests/requirements.txt for real-image regression tests")
class ImageRegressionTests(unittest.TestCase):
    def setUp(self):
        from PIL import Image
        from ml.fraud.image_forensics import ImageForensics
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "history.sqlite3"
        self.forensics = ImageForensics(self.path)
        image = Image.new("RGB", (64, 64), (30, 100, 170))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        self.image = buffer.getvalue()

    def test_real_jpeg_without_exif_never_receives_fraud_score(self):
        result = self.forensics.full_analysis(self.image, "A", "image-A")
        self.assertFalse(result["exif_analysis"]["has_exif"])
        self.assertIsNone(result["overall_manipulation_score"])
        self.assertIsNone(result["fraud_score"])
        self.assertEqual(result["fraud_flags"], [])
        self.assertFalse(result["review_required"])

    def test_real_file_matches_after_restart(self):
        from ml.fraud.image_forensics import ImageForensics
        self.forensics.full_analysis(self.image, "A", "image-A")
        result = ImageForensics(self.path).full_analysis(self.image, "B", "image-B")
        self.assertTrue(result["review_required"])
        self.assertEqual(result["duplicate_check"]["matches"][0]["claim_id"], "A")

    def test_editing_software_tag_is_information_not_fraud(self):
        with patch("ml.fraud.image_forensics.exifread.process_file", return_value={"Image Software": "Photoshop"}):
            result = self.forensics.full_analysis(self.image, "A")
        self.assertEqual(result["exif_analysis"]["status"], "informational")
        self.assertEqual(result["fraud_flags"], [])

    def test_unparseable_metadata_does_not_become_fraud(self):
        with patch("ml.fraud.image_forensics.exifread.process_file", side_effect=ValueError("bad exif")):
            result = self.forensics.full_analysis(self.image, "A")
        self.assertEqual(result["exif_analysis"]["status"], "unavailable")
        self.assertFalse(result["review_required"])

    def test_history_failure_is_unavailable_not_clear(self):
        with patch.object(self.forensics.history, "check_and_register", side_effect=sqlite3.OperationalError("busy")):
            result = self.forensics.full_analysis(self.image, "A")
        self.assertIsNone(result["duplicate_check"]["is_duplicate"])
        self.assertFalse(result["checks_complete"])
        self.assertEqual(result["duplicate_check"]["status"], "unavailable")

    def test_invalid_image_is_not_reported_as_authentic(self):
        result = self.forensics.full_analysis(b"not an image", "A")
        self.assertEqual(result["duplicate_check"]["status"], "unavailable")
        self.assertIsNone(result["fraud_score"])


if __name__ == "__main__":
    unittest.main()
