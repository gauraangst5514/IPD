"""Claim assessment orchestration with explicit per-component availability.

Dependencies are injected so evidence routing can be tested independently of
model packages, remote downloads and model weights.
"""
from ml.fraud.evidence import indicator, summarize


class AssessmentPipeline:
    def __init__(self, detector, forensics, cost_engine, consistency_checker,
                 vehicle_classifier=None, plate_check=None, tamper_detector=None, retrieval_engine=None):
        self.detector = detector
        self.forensics = forensics
        self.cost_engine = cost_engine
        self.consistency_checker = consistency_checker
        self.vehicle_classifier = vehicle_classifier
        self.plate_check = plate_check
        self.tamper_detector = tamper_detector
        self.retrieval_engine = retrieval_engine

    def capabilities(self):
        return {
            "damage_detection": self.detector.status(),
            "image_reuse": {"available": True, "method": "sha256_phash_dhash"},
            "text_consistency": {"available": True, "method": "keyword_baseline"},
            "vehicle_make": self.vehicle_classifier.status() if self.vehicle_classifier and hasattr(self.vehicle_classifier, "status") else {"available": bool(self.vehicle_classifier and self.vehicle_classifier.loaded)},
            "tamper_detection": self.tamper_detector.status() if self.tamper_detector else {"available": False, "reason": "checkpoint_missing"},
            "damage_reidentification": {"available": self.retrieval_engine is not None, "method": "OSNet_historical_candidates",
                "limitation": "Retrieves visually related photographs; physical-damage identity requires human review."},
            "saliency": {"available": self.detector.trained, "method": "occlusion_sensitivity"},
            "fraud_probability": {"available": False, "reason": "no_validated_calibrated_claim_probability"},
        }

    def analyze(self, image_bytes, claim_id="", image_id="", vehicle_make="",
                vehicle_year=2022, region="default", description="", registration_number=""):
        # A model failure must not discard independent image evidence.
        try:
            damage = self.detector.detect(image_bytes)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Damage inference failed")
            damage = {
                "damage_analysis_available": False, "damage_detected": None,
                "num_instances": 0, "detections": [], "severity": None,
                "severity_score": None, "severity_reasoning": {"reason": "inference_failed"},
                "primary_damage_type": None,
            }
        available = damage.get("damage_analysis_available", self.detector.trained)
        try:
            fraud = self.forensics.full_analysis(image_bytes, claim_id=claim_id, image_id=image_id)
            indicators = list(fraud["fraud_indicators"])
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Image evidence analysis failed")
            indicators = [indicator("image_evidence", "unavailable",
                "Photograph evidence checks could not be completed; damage assessment is shown separately.")]
        if not available:
            indicators.append(indicator("damage_model", "unavailable",
                "Damage inference is unavailable; severity and cost have not been estimated.",
                self.detector.status()))
        cost = None
        if available and damage["damage_detected"] and damage["severity"]:
            try:
                cost = self.cost_engine.estimate(
                    damage_type=damage["primary_damage_type"], severity=damage["severity"],
                    vehicle_make=vehicle_make, vehicle_year=vehicle_year, region=region,
                    total_area=damage["severity_reasoning"].get("total_area_coverage", 0),
                    num_instances=damage["num_instances"])
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Cost estimate failed")
                indicators.append(indicator("repair_cost", "unavailable", "Repair cost could not be estimated."))
        consistency_available = available and bool(description.strip()) and bool(damage["detections"])
        if consistency_available:
            try:
                consistency = self.consistency_checker.check_all(
                    claimed_make=vehicle_make, claimed_description=description,
                    detected_damage_type=damage["primary_damage_type"],
                    detected_severity=damage["severity"], detected_instances=damage["detections"],
                    image_bytes=image_bytes)
                for code in consistency["flags"]:
                    indicators.append(indicator(code, "review",
                        consistency.get("details", {}).get(code, "Claim and image discrepancy needs review.")))
                if not consistency["flags"]:
                    indicators.append(indicator("description_consistency", "not_observed",
                        "No discrepancy identified by keyword checks; this does not establish genuineness."))
            except Exception:
                import logging
                logging.getLogger(__name__).exception("Text consistency check failed")
                indicators.append(indicator("description_consistency", "unavailable",
                    "The narrative could not be checked; other evidence is retained."))
        else:
            indicators.append(indicator("description_consistency", "unavailable",
                "A narrative, available trained detector and visible damage are needed for this check."))
        try:
            vehicle = (self.vehicle_classifier.verify_make(image_bytes, vehicle_make)
                       if self.vehicle_classifier else {"match": None})
        except Exception:
            vehicle = {"match": None, "detail": "Vehicle verification could not be completed."}
        try:
            plate = (self.plate_check(image_bytes, registration_number)
                     if self.plate_check else {"match": None})
        except Exception:
            plate = {"match": None, "detail": "Plate verification could not be completed."}
        for code, result in [("vehicle_make_mismatch", vehicle), ("plate_number_mismatch", plate)]:
            match = result.get("match")
            indicators.append(indicator(code,
                "unavailable" if match is None else "not_observed" if match else "review",
                result.get("detail") or (
                    "Verification unavailable or inconclusive." if match is None else
                    "No mismatch observed." if match else "Vehicle evidence differs from the claim; verify manually."),
                result))
        if self.tamper_detector:
            try:
                tamper=self.tamper_detector.analyze(image_bytes)
            except Exception:
                tamper={'available':False,'reason':'inference_failed'}
            indicators.append(indicator('tamper_detection', 'informational' if tamper.get('available') else 'unavailable',
                'Pretrained forensic model output requires expert review; no authenticity verdict.', tamper))
        else:
            indicators.append(indicator('tamper_detection','unavailable','Photograph tampering was not assessed.'))
        if self.retrieval_engine:
            try:
                retrieval=self.retrieval_engine.search(image_bytes,k=3)
                # Persist identifiers and evidence, not repeated full thumbnails.
                evidence={k:v for k,v in retrieval.items() if k!='candidates'}
                evidence['candidates']=[{k:v for k,v in row.items() if k!='thumbnail'} for row in retrieval['candidates']]
                indicators.append(indicator('damage_reidentification','informational',
                    'Historical photographic candidates for investigator review; physical identity is not established.',evidence))
            except Exception:
                indicators.append(indicator('damage_reidentification','unavailable','Historical photograph retrieval could not complete.'))
        else:
            indicators.append(indicator('damage_reidentification','unavailable','Physical-damage recurrence was not assessed.'))
        return {
            "damage_analysis_available": bool(available),
            "damage_detected": damage["damage_detected"],
            "num_instances": damage["num_instances"], "detections": damage["detections"],
            "severity": damage["severity"], "severity_score": damage["severity_score"],
            "severity_reasoning": damage["severity_reasoning"],
            "severity_method": "area_heuristic" if damage["severity"] else None,
            "primary_damage_type": damage["primary_damage_type"],
            "cost_estimate_min": cost.min_cost if cost else None,
            "cost_estimate_max": cost.max_cost if cost else None,
            "cost_breakdown": cost.breakdown if cost else {},
            "cost_method": "indicative_rules" if cost else None,
            "component_status": self.capabilities(),
            **summarize(indicators),
        }
