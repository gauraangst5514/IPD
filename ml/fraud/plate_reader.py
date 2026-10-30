"""Offline English OCR with confidence-gated Indian registration candidates."""
import importlib.util
import os
import re
import threading
from pathlib import Path

MODEL_DIR=Path(os.environ.get('OCR_MODEL_DIR',str(Path(__file__).resolve().parents[1]/'weights/ocr')))
EASYOCR_AVAILABLE=importlib.util.find_spec('easyocr') is not None
INDIAN_PLATE_PATTERN=re.compile(r'(?<![A-Z0-9])[A-Z]{2}\s*\d{1,2}\s*[A-Z]{0,3}\s*\d{4}(?![A-Z0-9])')
_reader=None
_lock=threading.RLock()
_reader_error=None


def status():
    ready=EASYOCR_AVAILABLE and all((MODEL_DIR/name).is_file() for name in ('craft_mlt_25k.pth','english_g2.pth'))
    return {'available':ready and _reader_error is None,'method':'easyocr_offline',
            'reason':_reader_error or (None if ready else 'package_or_weights_missing'),
            'limitation':'English OCR and Indian registration patterns; no readable plate is inconclusive.'}


def _get_reader():
    global _reader, _reader_error
    with _lock:
        if _reader is None and status()['available']:
            try:
                import easyocr
                _reader=easyocr.Reader(['en'],gpu=False,model_storage_directory=str(MODEL_DIR),download_enabled=False,verbose=False)
            except Exception:
                _reader_error='weights_load_failed'
        return _reader


def normalize_plate(plate):
    return re.sub(r'[\s\-]', '',plate.upper().strip())


def extract_plates_from_text(text):
    strict=[normalize_plate(m) for m in INDIAN_PLATE_PATTERN.findall(text.upper())]
    # Preserve letter positions; fix common OCR glyph confusions only where
    # Indian registrations require digits. These remain reviewable candidates.
    pattern=re.compile(r'(?<![A-Z0-9])([A-Z]{2})\s*([0-9OQIZSB]{1,2})\s*([A-Z]{0,3})\s*([0-9OQIZSB]{4})(?![A-Z0-9])')
    digits=str.maketrans({'O':'0','Q':'0','I':'1','Z':'2','S':'5','B':'8'})
    for state,district,series,number in pattern.findall(text.upper()):
        strict.append(state+district.translate(digits)+series+number.translate(digits))
    return list(dict.fromkeys(strict))


def read_plate_evidence(image_bytes):
    reader=_get_reader()
    if reader is None:return {'plates':[],'raw_text':[]}
    from ml.image_input import open_upload
    import numpy as np
    with open_upload(image_bytes) as image:
        image=image.convert('RGB');image.thumbnail((1600,1600));array=np.array(image)
    with _lock:
        rows=reader.readtext(array,detail=1)
    # Low-confidence text must not create a mismatched-registration flag.
    text=[str(row[1]) for row in rows if float(row[2])>=.6]
    candidates=[]
    for line in [*text, ' '.join(text)]: candidates.extend(extract_plates_from_text(line))
    return {'plates':list(dict.fromkeys(candidates)),'raw_text':[{'text':str(row[1]),'confidence':float(row[2])} for row in rows]}


def read_plates_from_image(image_bytes):
    return read_plate_evidence(image_bytes)['plates']


def check_plate_match(image_bytes, claimed_registration):
    evidence=read_plate_evidence(image_bytes)
    detected=evidence['plates']
    claimed=normalize_plate(claimed_registration) if claimed_registration else ''
    match=any(plate==claimed for plate in detected) if detected and claimed else None
    return {'detected_plates':detected,'raw_ocr_text':evidence['raw_text'],'claimed_plate':claimed,'match':match,
            'flag':'plate_number_mismatch' if match is False else None,
            'detail':'No readable high-confidence registration; inconclusive.' if match is None else None,
            'method':'easyocr_offline','normalization':'Common OCR glyph confusions corrected only in digit positions; confirm the original photograph.','score_type':'uncalibrated_ocr_confidence'}
