#!/usr/bin/env python3
"""Acquire provisional modern context for Angkor; not historical hydraulic geometry."""
import hashlib
import subprocess
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/data/context'
BBOX = [103.6, 13.2, 104.2, 13.8]  # west, south, east, north; provisional rectangle, not a watershed
UA = 'QModel-Angkor-context-research/1.0'


def fetch(url, path, body=None, content_type=None):
    headers = {'User-Agent': UA}
    if content_type:
        headers['Content-Type'] = content_type
    if path.exists() and path.suffix == '.tif':
        content = path.read_bytes()
        return {'path': str(path.relative_to(ROOT / 'assets')), 'source_url': url,
                'retrieved_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(), 'cached_download': True}
    with urlopen(Request(url, data=body, headers=headers), timeout=120) as response:
        content = response.read()
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_bytes(content)
    temporary.replace(path)
    return {'path': str(path.relative_to(ROOT / 'assets')), 'source_url': url,
            'retrieved_utc': datetime.now(timezone.utc).isoformat(), 'bytes': len(content),
            'sha256': hashlib.sha256(content).hexdigest()}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    def checkpoint():
        (OUT / 'provenance.json').write_text(json.dumps({'working_bbox_wsen': BBOX, 'scope': 'Provisional context rectangle, not a delineated watershed.', 'records': records}, indent=2) + '\n')
    search = {'collections': ['cop-dem-glo-30'], 'bbox': BBOX, 'limit': 10}
    stac_path = OUT / 'copernicus_stac.json'
    fetch('https://earth-search.aws.element84.com/v1/search', stac_path,
          json.dumps(search).encode(), 'application/json')
    stac = json.loads(stac_path.read_text())
    for item in stac['features']:
        asset = item['assets']['data']['href']
        url = asset.replace('s3://copernicus-dem-30m/', 'https://copernicus-dem-30m.s3.amazonaws.com/')
        record = fetch(url, OUT / (item['id'] + '.tif'))
        record.update(dataset='copernicus_glo30', kind='surface_elevation', interpretation='Modern regional context; not canal bathymetry or medieval terrain.')
        records.append(record)
        checkpoint()
        print('Downloaded', record['path'], record['bytes'], flush=True)
    subprocess.run([sys.executable, str(ROOT/'scripts/extract_osm_context.py'), '--download'], check=True)


if __name__ == '__main__':
    main()
