import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
from app.services.invoice import parse_invoice

class InvoiceTests(unittest.TestCase):
    def test_unparsed_invoice_has_no_fabricated_items(self):
        result = parse_invoice("Nothing can be extracted")
        self.assertFalse(result["available"])
        self.assertEqual(result["lines"], [])
        self.assertEqual(result["indicators"], [])

    def test_arithmetic_difference_is_reviewable_not_a_fraud_verdict(self):
        result = parse_invoice("Paint | 2 | 100.50\nBumper | 1 | 500\nInvoice total: 800")
        self.assertEqual(result["calculated_subtotal"],701)
        self.assertEqual(result["declared_total"],800)
        self.assertEqual(result["indicators"][0]["status"],"review")
        self.assertNotIn("fraud_score",result)

    def test_equal_total_does_not_fabricate_discrepancy(self):
        result = parse_invoice("Repair | 2 | 1,500\nInvoice total: 3000")
        self.assertEqual(result["indicators"],[])

@unittest.skipUnless(importlib.util.find_spec("numpy"), "Install development dependencies")
class ModelTests(unittest.TestCase):
    def test_split_is_disjoint_and_exhaustive(self):
        from scripts.train_tabular import split_indices
        groups=split_indices([0]*75+[1]*25)
        self.assertEqual(set().union(*map(set,groups)),set(range(100)))
        for a,b in [(0,1),(0,2),(1,2)]:
            self.assertFalse(set(groups[a]) & set(groups[b]))

    def test_preprocessing_does_not_learn_test_category(self):
        from ml.tabular.model import fit_schema, encode
        row={"incident_severity":"Minor Damage","insured_hobbies":"reading",
             "incident_type":"Parked Car","total_claim_amount":1,
             "vehicle_claim":1,"umbrella_limit":0,"policy_annual_premium":100}
        schema=fit_schema([row])
        heldout={**row,"insured_hobbies":"unseen","total_claim_amount":9000000}
        encode([heldout],schema)
        self.assertNotIn("unseen",schema["categories"]["insured_hobbies"])
        self.assertEqual(schema["numeric"]["total_claim_amount"]["mean"],1)

    def test_shown_explanation_reconstructs_model_score(self):
        import math
        from ml.tabular.model import TabularModel
        row={"incident_severity":"Minor Damage","incident_type":"Parked Car","insured_hobbies":"reading",
             "total_claim_amount":6200,"vehicle_claim":4100,"umbrella_limit":0,"policy_annual_premium":1120}
        result=TabularModel().assess(row)
        self.assertTrue(result["available"])
        logit=result["intercept_log_odds"]+sum(c["log_odds"] for c in result["contributions"])
        self.assertAlmostEqual(result["model_score"],1/(1+math.exp(-logit)),places=7)

    def test_unknown_categories_and_missing_fields_are_unavailable(self):
        from ml.tabular.model import TabularModel
        row={"incident_severity":"Minor Damage","incident_type":"Parked Car","insured_hobbies":"reading",
             "total_claim_amount":6200,"vehicle_claim":4100,"umbrella_limit":0,"policy_annual_premium":1120}
        row["insured_hobbies"]="unknown-value"
        self.assertFalse(TabularModel().assess(row)["available"])
        self.assertFalse(TabularModel().assess({})["available"])

    def test_graph_neighbors_only_reference_training_records(self):
        import numpy as np
        from ml.tabular.graph import neighbors
        reference=np.array([[0.,0.],[1.,1.],[2.,2.]])
        query=np.array([[100.,100.]])
        adjacency=neighbors(query,reference,k=2)
        self.assertEqual(adjacency.shape,(1,3))
        self.assertAlmostEqual(float(adjacency.sum()),1.)
        self.assertEqual(adjacency[0,0],0)

    def test_occlusion_tracks_the_same_detection(self):
        from PIL import Image
        from ml.explainability.occlusion import occlusion_saliency
        stream=io.BytesIO(); Image.new("RGB",(32,32),(120,80,20)).save(stream,format="PNG")
        class Detector:
            calls=0
            def detect(self,content):
                self.calls+=1
                # A high confidence unrelated object must not explain the selected target.
                target={"label":"dent","confidence":.8,"bbox":[.1,.1,.1,.1]}
                return {"damage_analysis_available":True,"detections":[target] if self.calls==1 else
                        [{"label":"dent","confidence":.99,"bbox":[.9,.9,.1,.1]}]}
        detector=Detector()
        result=occlusion_saliency(detector,stream.getvalue(),grid=2)
        self.assertEqual(detector.calls,5)
        self.assertAlmostEqual(result["score_drops"][0][0],.8,places=6)
        self.assertTrue(result["image"].startswith(b"\x89PNG"))

if __name__=="__main__": unittest.main()
