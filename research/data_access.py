"""Frozen original test subset; live ingested images never enter evaluation."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def generali_test_paths():
    manifest=json.loads((ROOT/'research/data/generali_test_manifest.json').read_text())
    folder=ROOT/'data/raw/generali/extracted/paper/test_papers_2.1.0_for_repo'
    paths=[]
    for row in manifest['images']:
        p=folder/row['name']
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError(f'Missing or altered benchmark image: {row["name"]}')
        paths.append(p)
    return paths
