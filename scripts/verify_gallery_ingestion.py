"""Live local assessor ingestion/duplicate/authorization smoke; no credentials in output.

Adds one deterministic generated test image to the mutable demonstration gallery.
"""
import io
import json
import os
from pathlib import Path
import httpx
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]

def main():
    url = os.environ.get('BACKEND_URL', 'http://127.0.0.1:8010') + '/api/v1'
    accounts = json.loads((ROOT / 'var/demo_accounts.json').read_text())
    image = Image.fromarray(np.random.default_rng(20261030).integers(0, 256, (48, 64, 3), dtype=np.uint8))
    stream = io.BytesIO(); image.save(stream, format='PNG')
    files = {'file': ('restart-check-without-extension', stream.getvalue(), 'image/png')}
    report = {}
    with httpx.Client(trust_env=False, timeout=240) as client:
        for role in ('claimant', 'assessor'):
            account = accounts[role]
            login = client.post(url + '/auth/login', data={'username': account['email'], 'password': account['password']})
            login.raise_for_status()
            headers = {'Authorization': 'Bearer ' + login.json()['access_token']}
            if role == 'claimant':
                for endpoint in ('/intelligence/retrieval/gallery/add', '/intelligence/retrieval/stats'):
                    response = client.post(url + endpoint, headers=headers, files=files) if endpoint.endswith('/add') else client.get(url + endpoint, headers=headers)
                    assert response.status_code == 403, response.status_code
                report['claimant_denied'] = True
                continue
            invalid = client.post(url + '/intelligence/retrieval/gallery/add', headers=headers, files={'file': ('invalid.png', b'invalid', 'image/png')})
            assert invalid.status_code == 422, invalid.status_code
            report['invalid_image_status'] = invalid.status_code
            first = client.post(url + '/intelligence/retrieval/gallery/add', headers=headers, files=files)
            first.raise_for_status(); first = first.json()
            assert first['image_id'].endswith('.png'), first
            second = client.post(url + '/intelligence/retrieval/gallery/add', headers=headers, files=files)
            second.raise_for_status(); second = second.json()
            assert second['added'] is False and second['reason'] == 'duplicate_image', second
            assert first['gallery_size'] == second['gallery_size'], second
            stats = client.get(url + '/intelligence/retrieval/stats', headers=headers)
            stats.raise_for_status(); stats = stats.json()
            assert stats['gallery_size'] == second['gallery_size']
            assert stats['model_loaded']
            report.update(first_ingestion=first, duplicate_detected=True, stats_consistent=True)
    (ROOT / 'research/results/gallery_ingestion_verification.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
