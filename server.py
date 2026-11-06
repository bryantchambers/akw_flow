#!/usr/bin/env python3
"""Read-only Angkor research inventory. Run with python3.11 server.py --port 9090."""
import argparse
import json
import mimetypes
import shutil
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
WEB = ROOT / 'web'


def catalog():
    data = json.loads((WEB / 'catalog.json').read_text())
    manifest = json.loads((ASSETS / 'metadata/acquisition_manifest.json').read_text())
    records = {r['id']: r for r in manifest}
    pages = {r['path']: r.get('pages') for r in json.loads((ASSETS / 'metadata/pdf_validation.json').read_text())}
    def artifact(key):
        r = records.get(key, {})
        path = r.get('path', '')
        local = ASSETS / path
        available = bool(path and r.get('status') == 'available' and local.is_file())
        return {'id': key, 'available': available, 'url': '/assets/' + path if available else None,
                'path': path, 'source_url': r.get('source_url'), 'bytes': local.stat().st_size if available else None,
                'pages': pages.get(path), 'sha256': r.get('sha256'), 'retrieved': r.get('retrieved_utc')}
    for r in data['resources']:
        r['artifact'] = artifact(r['id'])
        r['related_artifacts'] = [artifact(k) for k in r.get('related', [])]
    acquired = [r for r in manifest if r.get('status') == 'available' and (ASSETS / r['path']).is_file()]
    data['stats'] = {'pdfs': sum(r['path'].endswith('.pdf') for r in acquired),
                     'supplements': sum(r['path'].endswith('.docx') for r in acquired),
                     'source_archives': sum(r['path'].endswith('.zip') for r in acquired),
                     'geospatial_datasets': 0, 'hydraulic_projects': 0,
                     'total_bytes': sum((ASSETS / r['path']).stat().st_size for r in acquired),
                     'resources': len(data['resources']),
                     'critical_needs': sum(r['priority'] == 'Critical' for r in data['needs'])}
    data['generated_utc'] = datetime.now(timezone.utc).isoformat()
    return data


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond(False)

    def do_HEAD(self):
        self.respond(True)

    def respond(self, head):
        path = unquote(urlsplit(self.path).path)
        if path in ('/api/catalog', '/healthz'):
            try:
                result = catalog() if path == '/api/catalog' else {'status': 'ok', 'service': 'angkor-research-inventory'}
                body = json.dumps(result, ensure_ascii=False).encode()
            except (OSError, ValueError) as exc:
                self.send_error(500, 'Inventory files could not be read')
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if not head:
                self.wfile.write(body)
            return
        if path in ('/', '/index.html', '/style.css', '/app.js'):
            file = WEB / ('index.html' if path == '/' else path.lstrip('/'))
            attachment = False
        elif path.startswith('/assets/'):
            file = (ASSETS / path[len('/assets/'):]).resolve()
            if not file.is_relative_to(ASSETS.resolve()):
                self.send_error(403)
                return
            attachment = file.suffix.lower() not in ('.pdf', '.json', '.txt', '.md')
        else:
            self.send_error(404)
            return
        if not file.is_file():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(file.stat().st_size))
        self.send_header('X-Content-Type-Options', 'nosniff')
        if attachment:
            self.send_header('Content-Disposition', 'attachment; filename="' + file.name.replace('"', '') + '"')
        self.end_headers()
        if not head:
            try:
                with file.open('rb') as stream:
                    shutil.copyfileobj(stream, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=9090)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'Angkor inventory listening on http://{args.host}:{args.port}', flush=True)
    server.serve_forever()
