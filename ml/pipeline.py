"""Assemble explicit evidence statuses without inventing labels or confidence."""
import base64
import io
from PIL import Image
from shared.contracts import AnalysisResult, CheckResult


def check(key, status, detail, method='heuristic'):
    return CheckResult(id=key, status=status, detail=detail, method=method)


def analyze(image_bytes, *, detector, forensics, cost_engine, consistency_checker,
            vehicle_classifier, plate_check, vehicle_make, vehicle_year, region,
            claim_id='', description='', registration_number=''):
    detection = detector.detect(image_bytes)
    detections = detection['detections']
    found = bool(detections)
    severity = detection['severity'] if found else None
    primary = detection['primary_damage_type'] if found else None
    # No detection is evidence of no visible damage, not proof that the car is undamaged.
    cost = cost_engine.estimate(
        damage_type=primary, severity=severity, vehicle_make=vehicle_make,
        vehicle_year=vehicle_year, region=region,
        total_area=detection['severity_reasoning'].get('total_area_coverage', 0),
        num_instances=len(detections),
    ) if found else None
    checks = []
    flags = []
    manipulation = None
    if forensics is None:
        checks.extend([check('exif', 'unavailable', 'Metadata analysis unavailable'),
                       check('ela', 'unavailable', 'Image consistency analysis unavailable')])
    else:
        try:
            forensic = forensics.full_analysis(image_bytes, claim_id=claim_id)
            exif = forensic['exif_analysis']
            exif_state = 'inconclusive' if not exif.get('has_exif') else 'flagged' if exif.get('suspicious') else 'passed'
            checks.append(check('exif', exif_state, 'Metadata absent or unreadable' if exif_state == 'inconclusive' else 'Metadata heuristic completed'))
            ela = forensic.get('ela_score')
            checks.append(check('ela', 'unavailable' if ela is None else 'flagged' if ela > .6 else 'passed',
                                'Compression consistency heuristic; not proof of tampering'))
            manipulation = forensic['overall_manipulation_score'] if ela is not None or exif.get('has_exif') else None
            flags.extend(forensic['metadata_flags'])
        except (ValueError, OSError, RuntimeError):
            checks.extend([check('exif', 'unavailable', 'Metadata analysis failed'),
                           check('ela', 'unavailable', 'Image consistency analysis failed')])
    # The API supplies a database-backed, owner-scoped duplicate result.
    checks.append(check('duplicate', 'unavailable', 'Exact-file comparison is performed by the claims API', 'sha256_exact_v1'))
    consistency_bonus = 0.0
    if not description.strip() or not found:
        for key in ('description', 'severity'):
            checks.append(check(key, 'inconclusive', 'Description and visible damage are needed for this check'))
    else:
        result = consistency_checker.check_all(
            claimed_make=vehicle_make, claimed_description=description,
            detected_damage_type=primary, detected_severity=severity,
            detected_instances=detections, image_bytes=image_bytes,
        )
        flags.extend(result['flags'])
        consistency_bonus = (1 - result['consistency_score']) * .6
        for key in ('description', 'severity'):
            flagged = f'{key}_mismatch' in result['flags']
            checks.append(check(key, 'flagged' if flagged else 'passed',
                                result.get('details', {}).get(f'{key}_mismatch', 'Keyword consistency heuristic completed')))
    vehicle = vehicle_classifier.verify_make(image_bytes, vehicle_make)
    state = 'unavailable' if not vehicle_classifier.loaded else 'inconclusive' if vehicle.get('match') is None else 'passed' if vehicle['match'] else 'flagged'
    checks.append(check('vehicle_make', state, vehicle.get('detail') or 'Vehicle make comparison completed', 'classifier'))
    if vehicle.get('flag'):
        flags.append(vehicle['flag'])
    plate = plate_check(image_bytes, registration_number)
    plate_state = plate.get('status', 'inconclusive')
    checks.append(check('plate', plate_state, plate.get('detail') or 'Plate comparison inconclusive', 'ocr'))
    if plate.get('flag'):
        flags.append(plate['flag'])
    score = max(manipulation or 0, consistency_bonus, .8 if vehicle.get('match') is False else 0,
                .7 if plate.get('flag') else 0)
    annotation = None
    if detection.get('annotated_image'):
        with Image.open(io.BytesIO(detection['annotated_image'])) as preview:
            preview.thumbnail((1600, 1600))
            output = io.BytesIO()
            preview.convert('RGB').save(output, format='PNG')
            annotation = base64.b64encode(output.getvalue()).decode('ascii')
    return AnalysisResult(
        outcome='damage_detected' if found else 'no_visible_damage',
        damage_detected=found, detections=detections, severity=severity,
        severity_score=detection['severity_score'] if found else None,
        detector_confidence=sum(d['confidence'] for d in detections) / len(detections) if found else None,
        primary_damage_type=primary,
        cost_estimate_min=cost.min_cost if cost else None,
        cost_estimate_max=cost.max_cost if cost else None,
        cost_breakdown={**cost.breakdown, 'method': 'provisional_heuristic', 'aggregation': 'primary_damage_type'} if cost else {},
        severity_reasoning=detection['severity_reasoning'], fraud_score=score,
        manipulation_score=manipulation, fraud_flags=sorted(set(flags)), checks=checks,
        model_provenance=detector.provenance, annotated_image_base64=annotation,
    )
