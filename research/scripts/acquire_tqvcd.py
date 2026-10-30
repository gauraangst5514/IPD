"""Fetch pinned public examples; audit content duplicates before any splitting."""
import concurrent.futures, hashlib, json, pathlib, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]
manifest = json.loads((ROOT/'research/data/tqvcd_manifest.json').read_text())
revision = manifest['tree_sha']
def fetch(entry):
    path = entry['path']
    target = ROOT/'data/raw/tqvcd'/path
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        url = f'https://raw.githubusercontent.com/{manifest["repository"]}/{revision}/{path}'
        data = urllib.request.urlopen(url, timeout=45).read()
        blob = hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
        if blob != entry['git_blob_sha']:
            raise ValueError(f'Integrity mismatch: {path}')
        target.write_bytes(data)
    data = target.read_bytes()
    blob = hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
    if blob != entry['git_blob_sha']:
        raise ValueError(f'Cached integrity mismatch: {path}')
    return {'path':path,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(fetch, manifest['files']))
    groups = {}
    for row in records:
        groups.setdefault(row['sha256'], []).append(row['path'])
    report = {'scope':manifest['scope'],'images':len(records),'unique_images':len(groups),
              'exact_duplicate_groups':[v for v in groups.values() if len(v)>1],
              'warning':'Classification examples; no same-physical-damage identities. Group duplicates before splitting. License unresolved; do not redistribute.',
              'records':records}
    out=ROOT/'research/results'; out.mkdir(exist_ok=True)
    (out/'tqvcd_audit.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='records'},indent=2))
