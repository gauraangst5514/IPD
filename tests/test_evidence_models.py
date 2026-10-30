import io
import unittest
from unittest.mock import patch
from PIL import Image
from ml.fraud.plate_reader import extract_plates_from_text, check_plate_match
from ml.fraud.vehicle_classifier import VehicleMakeClassifier

class EvidenceModelTests(unittest.TestCase):
    def test_ocr_confusion_only_changes_digit_positions(self):
        self.assertIn('MH02AB1234',extract_plates_from_text('MHOZAB1234'))
        self.assertIn('MH02AB1234',extract_plates_from_text('MH 02 AB 1234'))
        self.assertEqual(extract_plates_from_text('NO PLATE VISIBLE'),[])

    def test_no_readable_plate_is_inconclusive(self):
        with patch('ml.fraud.plate_reader.read_plate_evidence',return_value={'plates':[],'raw_text':[]}):
            result=check_plate_match(b'fixture','MH02AB1234')
        self.assertIsNone(result['match']);self.assertIsNone(result['flag'])

    def test_unsupported_vehicle_make_is_inconclusive(self):
        model=object.__new__(VehicleMakeClassifier);model.loaded=True;model.idx_to_make={0:'Toyota'}
        result=model.verify_make(b'fixture','Tata')
        self.assertIsNone(result['match']);self.assertIsNone(result['flag'])

    def test_different_manufacturers_are_not_equivalent(self):
        model=object.__new__(VehicleMakeClassifier)
        self.assertFalse(model._makes_match('volkswagen','skoda'))

    def test_restricted_checkpoint_does_not_allow_arbitrary_globals(self):
        import pickle
        from ml.safe_checkpoint import RestrictedUnpickler
        with self.assertRaises(pickle.UnpicklingError):
            RestrictedUnpickler(io.BytesIO()).find_class('os','system')
