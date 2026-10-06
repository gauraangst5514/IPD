"""Image analysis and projections. Database leases live in processing_jobs."""
import asyncio
import base64
import binascii
from collections import Counter
import httpx
from shared.contracts import AnalysisResult
from app.models.claim import ClaimStatus, DamageType, SeverityLevel
from app.services.storage import get_storage_service
from app.services.ml_client import get_ml_client

DAMAGE_TYPE_MAP = {kind.value: kind for kind in DamageType}
SEVERITY_MAP = {level.value: level for level in SeverityLevel}


def _extract_region(location):
    value = (location or '').lower()
    cities = ['mumbai', 'delhi', 'bangalore', 'bengaluru', 'chennai', 'pune', 'hyderabad',
              'kolkata', 'ahmedabad', 'jaipur', 'lucknow', 'surat', 'indore', 'nagpur', 'thane']
    return next((city for city in cities if city in value), 'default')


async def analyze_image(image, claim, *, storage, client, artifact_suffix):
    """Return a safe outcome; transient failures never become successful assessments."""
    evidence = image['duplicate_evidence']
    payload = {'image_id': image['id'], 'result': None, 'error': None,
               'annotation_error': None, 'heatmap_key': None, 'duplicate_evidence': evidence}
    try:
        content = await asyncio.to_thread(storage.download_image, image['key'])
        analysis = await client.analyze_image(
            image_bytes=content, vehicle_make=claim['make'], vehicle_year=claim['year'],
            region=_extract_region(claim['location']), claim_id=claim['id'],
            description=claim['description'] or '', registration_number=claim['registration'],
        )
        result = AnalysisResult.model_validate(analysis).model_dump()
        annotation = result.pop('annotated_image_base64', None)
        result['checks'] = [c for c in result['checks'] if c['id'] != 'duplicate']
        result['checks'].append({
            'id': 'duplicate', 'method': 'sha256_exact_v1',
            'status': 'unavailable' if not evidence['available'] else 'flagged' if evidence['match_count'] else 'passed',
            'detail': 'Exact-file reuse in this customer’s images; not a fraud verdict' if evidence['match_count'] else 'No exact match within this customer’s stored images' if evidence['available'] else 'File hash unavailable',
        })
        payload['result'] = result
        if annotation:
            try:
                raw = base64.b64decode(annotation, validate=True)
                if len(raw) > 10 * 1024 * 1024:
                    raise ValueError('Annotation too large')
                payload['heatmap_key'] = await asyncio.to_thread(
                    storage.upload_heatmap, raw, claim['id'], image['id'] + '-' + artifact_suffix,
                )
            except Exception:  # Optional previews must not invalidate successful analysis.
                payload['annotation_error'] = 'annotation_unavailable'
        else:
            payload['annotation_error'] = 'annotation_unavailable'
    except (httpx.HTTPError, ValueError, OSError, RuntimeError, TimeoutError):
        payload['error'] = 'analysis_unavailable'
    return payload


def aggregate_checks(results):
    keys = sorted({check['id'] for result in results for check in result['checks']})
    ranking = {'flagged': 5, 'inconclusive': 4, 'unavailable': 3, 'passed': 2, 'not_applicable': 1}
    checks = []
    for key in keys:
        values = [check for result in results for check in result['checks'] if check['id'] == key]
        chosen = max(values, key=lambda check: ranking[check['status']])
        checks.append({**chosen, 'images_checked': len(values)})
    return checks


def project(claim, images_by_id, outcomes):
    """Update the current projection only after the caller has fenced the attempt."""
    for field in ('damage_type', 'severity', 'confidence_score', 'detector_confidence', 'severity_score',
                  'estimated_cost_min', 'estimated_cost_max', 'cost_breakdown', 'fraud_risk_score',
                  'fraud_flags', 'detections', 'analysis_outcome', 'checks'):
        setattr(claim, field, None)
    results = []
    for outcome in outcomes:
        image = images_by_id[outcome['image_id']]
        for field in ('damage_type', 'severity', 'confidence', 'detector_confidence', 'severity_score',
                      'damage_detected', 'is_manipulated', 'manipulation_score', 'heatmap_url', 'analysis_outcome', 'checks'):
            setattr(image, field, None)
        image.duplicate_evidence = outcome['duplicate_evidence']
        image.is_duplicate = bool(outcome['duplicate_evidence']['match_count'])
        image.processing_error = outcome['error']
        image.annotation_error = outcome['annotation_error']
        image.processing_status = 'failed' if outcome['error'] else 'completed'
        result = outcome['result']
        if result is None:
            continue
        results.append(result)
        image.analysis_outcome = result['outcome']
        image.damage_detected = result['damage_detected']
        image.damage_type = DAMAGE_TYPE_MAP.get(result['primary_damage_type'])
        image.severity = SEVERITY_MAP.get(result['severity'])
        image.detector_confidence = result['detector_confidence']
        image.severity_score = result['severity_score']
        image.checks = result['checks']
        image.heatmap_url = outcome['heatmap_key']
        image.manipulation_score = result['manipulation_score']
        image.is_manipulated = None  # Heuristic flags cannot establish image tampering.
    if not results:
        claim.status = ClaimStatus.PROCESSING_FAILED
        return
    damaged = [result for result in results if result['damage_detected']]
    if damaged:
        claim.damage_type = DAMAGE_TYPE_MAP[Counter(r['primary_damage_type'] for r in damaged).most_common(1)[0][0]]
        claim.severity = max((SEVERITY_MAP[r['severity']] for r in damaged), key=lambda level: {'minor': 0, 'moderate': 1, 'severe': 2}[level.value])
        scores = [r['detector_confidence'] for r in damaged if r['detector_confidence'] is not None]
        claim.detector_confidence = sum(scores) / len(scores) if scores else None
        severity_scores = [r['severity_score'] for r in damaged if r['severity_score'] is not None]
        claim.severity_score = max(severity_scores) if severity_scores else None
        priced = [r for r in damaged if r['cost_estimate_max'] is not None]
        if priced:
            best = max(priced, key=lambda r: r['cost_estimate_max'])
            claim.estimated_cost_min = best['cost_estimate_min']
            claim.estimated_cost_max = best['cost_estimate_max']
            claim.cost_breakdown = {**best['cost_breakdown'], 'aggregation': 'max_image_heuristic',
                                    'limitation': 'Not a sum of unique repair operations across views'}
    claim.analysis_outcome = 'damage_detected' if damaged else 'no_visible_damage'
    if any(r['outcome'] == 'insufficient_evidence' for r in results):
        claim.analysis_outcome = 'insufficient_evidence'
    claim.fraud_risk_score = max(r['fraud_score'] for r in results)
    claim.fraud_flags = {flag: True for r in results for flag in r['fraud_flags']}
    claim.checks = aggregate_checks(results)
    claim.detections = [{**d, 'image_id': outcome['image_id']} for outcome in outcomes
                        if outcome['result'] for d in outcome['result']['detections']]
    if len(results) != len(outcomes) or claim.analysis_outcome == 'insufficient_evidence':
        claim.status = ClaimStatus.PARTIAL_PROCESSING
    else:
        claim.status = ClaimStatus.FLAGGED if claim.fraud_risk_score > .7 else ClaimStatus.AWAITING_REVIEW
