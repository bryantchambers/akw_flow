#!/usr/bin/env python3
"""Angkor research dashboard with local review and simulation endpoints. Run with the GIS Python environment on port 9090."""
import argparse
import json
import mimetypes
import os
import shutil
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / 'assets'
WEB = ROOT / 'web'
FLOW_LOCK = threading.Lock()


def catalog():
    data = json.loads((WEB / 'catalog.json').read_text())
    manifest = json.loads((ASSETS / 'metadata/acquisition_manifest.json').read_text())
    records = {r['id']: r for r in manifest}
    context = ASSETS / 'data/context/provenance.json'
    if context.is_file():
        entries = json.loads(context.read_text()).get('records', [])
        for entry in entries:
            key = 'copernicus_context' if entry.get('dataset') == 'copernicus_glo30' else 'osm_context'
            records[key] = dict(entry, status='available', path=entry.get('derived_path', entry['path']), sha256=entry.get('derived_sha256', entry['sha256']))
    topsar = ASSETS / 'data/context/topsar/acquisition.json'
    if topsar.is_file():
        entry = json.loads(topsar.read_text())
        records['topsar_raw'] = dict(entry, status='available', path='data/context/topsar/ts1260_c.demi2')
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
    topsar_ready = all((ASSETS / path).is_file() for path in ('data/context/topsar/viewer_topsar_detail.json','data/context/topsar/viewer_topsar_overview.json','data/context/topsar/conversion_provenance.json'))
    data['stats'] = {'pdfs': sum(r['path'].endswith('.pdf') for r in acquired),
                     'supplements': sum(r['path'].endswith('.docx') for r in acquired),
                     'source_archives': sum(r['path'].endswith('.zip') for r in acquired),
                     'geospatial_datasets': 0, 'context_datasets': sum(k in records and (ASSETS / records[k]['path']).is_file() for k in ('copernicus_context','osm_context')) + int(topsar_ready), 'hydraulic_projects': 0,
                     'total_bytes': sum((ASSETS / r['path']).stat().st_size for r in acquired),
                     'resources': len(data['resources']),
                     'critical_needs': sum(r['priority'] == 'Critical' for r in data['needs'])}
    data['generated_utc'] = datetime.now(timezone.utc).isoformat()
    return data


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.respond(False)

    def do_POST(self):
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            self.send_error(403, 'Cross-origin writes are not allowed')
            return
        if urlsplit(self.path).path in ('/api/channel-review/save', '/api/channel-review/profile', '/api/channel-review/rebuild', '/api/channel-review/screen'):
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 100000:
                    raise ValueError('Review request must be 1..100000 bytes')
                request = json.loads(self.rfile.read(size))
                if not isinstance(request, dict):
                    raise ValueError('Use a JSON object')
                from hydraulics.channel_review import save, profile, screen
                if urlsplit(self.path).path.endswith('/rebuild'):
                    if not FLOW_LOCK.acquire(blocking=False):raise ValueError('Another scenario is running')
                    try:
                        from scripts.build_regional_network import build
                        result=build(json.loads((ROOT/'configs/regional_network.json').read_text()))
                    finally:
                        FLOW_LOCK.release()
                elif urlsplit(self.path).path.endswith('/screen'):
                    result = screen(request)
                else:
                    result = save(request) if urlsplit(self.path).path.endswith('/save') else profile(request)
                body = json.dumps(result, allow_nan=False).encode()
                status = 200
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                body = json.dumps({'error':str(exc)}).encode()
                status = 400
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if urlsplit(self.path).path not in ('/api/transport/simulate','/api/channel-flow/simulate','/api/terrain-flow/simulate'):
            self.send_error(404)
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 2_000_000:
                raise ValueError('Request must be 1 byte to 2 MB')
            config = json.loads(self.rfile.read(size))
            if not isinstance(config, dict) or len(config.get('cells', [])) > 500:
                raise ValueError('Use an object with at most 500 cells')
            config['max_steps'] = min(int(config.get('max_steps', 10000)), 10000)
            from transport.core import simulate
            if urlsplit(self.path).path == '/api/channel-flow/simulate':
                from scripts.build_humanum_flow import build
                if not FLOW_LOCK.acquire(blocking=False):
                    raise ValueError('A flow scenario is already running; try again after it finishes')
                try:
                    result = build(config)
                finally:
                    FLOW_LOCK.release()
            elif urlsplit(self.path).path == '/api/terrain-flow/simulate':
                from scripts.build_terrain_flow import build
                if float(config.get('duration_s',900)) > 86400 or float(config.get('duration_s',900))/float(config.get('output_interval_s',60)) > 200 or int(config.get('maximum_cells',10000)) > 10000:
                    raise ValueError('Terrain pilot limited to 10000 cells, one day and 200 output intervals')
                if not FLOW_LOCK.acquire(blocking=False):raise ValueError('A flow scenario is already running')
                try:
                    result = build(config)
                finally:
                    FLOW_LOCK.release()
            else:
                result = simulate(config)
            body = json.dumps(result, allow_nan=False).encode()
            status = 200
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            body = json.dumps({'error': str(exc)}).encode()
            status = 400
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def do_HEAD(self):
        self.respond(True)

    def water_network_response(self, head):
        from hydraulics import water_network_view as view
        parsed=urlsplit(self.path);query=parse_qs(parsed.query);parts=parsed.path.split('/')
        try:
            if len(parts)==5 and parts[3]=='download':
                file,mime=view.download(unquote(parts[4]),query.get('case',[None])[0])
                # Open before fstat: an atomic GeoPackage replacement must not
                # change the file between Content-Length and streamed content.
                with file.open('rb') as source:
                    size=os.fstat(source.fileno()).st_size
                    self.send_response(200);self.send_header('Content-Type',mime)
                    self.send_header('Content-Disposition','attachment; filename="'+file.name+'"')
                    self.send_header('Content-Length',str(size));self.send_header('Cache-Control','no-store');self.end_headers()
                    if not head:
                        try:shutil.copyfileobj(source,self.wfile,1024*1024)
                        except (BrokenPipeError,ConnectionResetError):pass
                return
            if parsed.path=='/api/water-network/status':result=view.status(query.get('case',[None])[0])
            elif len(parts)==5 and parts[3]=='layers':
                bounds=[float(v) for v in query['bounds'][0].split(',')] if 'bounds' in query else None
                result=view.layer(parts[4],bounds,query.get('case',[None])[0])
            else:raise FileNotFoundError('Unknown water-system derivative')
            body=json.dumps(result,allow_nan=False).encode();code=200
        except (FileNotFoundError,KeyError):body=json.dumps({'error':'Water-system derivative not ready'}).encode();code=404
        except (ValueError,TypeError) as exc:body=json.dumps({'error':str(exc)}).encode();code=400
        self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers()
        if not head:self.wfile.write(body)

    def regional_native_response(self, head):
        from hydraulics import regional_view as view
        from hydraulics.water_case import case_directory
        query=parse_qs(urlsplit(self.path).query)
        try:directory=case_directory(query.get('case',[None])[0])
        except (ValueError,FileNotFoundError) as exc:
            body=json.dumps({'error':str(exc)}).encode();self.send_response(400 if isinstance(exc,ValueError) else 404)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers()
            if not head:self.wfile.write(body)
            return
        token=view.CASE_DIRECTORY.set(directory)
        try:self._regional_native_response(head)
        finally:view.CASE_DIRECTORY.reset(token)

    def _regional_native_response(self, head):
        import re
        from hydraulics import regional_view as view
        parsed=urlsplit(self.path);path=parsed.path;query=parse_qs(parsed.query)
        content_type='application/json; charset=utf-8'
        try:
            if path=='/api/regional-native/status':result=view.status()
            elif path=='/api/regional-native/cells':
                result=view.cells([float(v) for v in query.get('bounds',[''])[0].split(',')],query.get('snapshot',['final'])[0])
            elif path=='/api/regional-native/point':
                result=view.point(float(query.get('lon',[''])[0]),float(query.get('lat',[''])[0]),query.get('snapshot',['final'])[0])
            elif path=='/api/regional-native/faces':
                from hydraulics.regional_faces import faces
                bounds=[float(v) for v in query.get('bounds',[''])[0].split(',')]
                result=faces(bounds,query.get('snapshot',['final'])[0],float(query.get('minimum_q',['0.00001'])[0]),query.get('include_idle',['false'])[0]=='true')
            elif path=='/api/regional-native/comparison':
                from hydraulics.regional_view import comparison
                result=comparison()
            elif path=='/api/regional-native/vectors':
                bounds=[float(v) for v in query.get('bounds',[''])[0].split(',')]
                result=view.vectors(bounds,query.get('snapshot',['final'])[0])
            else:
                match=re.fullmatch(r'/api/regional-native/tiles/(height|hillshade|depth|tracer)/(initial|final)/(\d+)/(\d+)/(\d+)\.png',path)
                if not match:raise FileNotFoundError('Unknown regional derivative')
                layer,snapshot,z,x,y=match.groups();result=view.tile(layer,snapshot,int(z),int(x),int(y));content_type='image/png'
            body=result if isinstance(result,bytes) else json.dumps(result,allow_nan=False).encode()
            status=200
        except FileNotFoundError:
            body=json.dumps({'error':'Requested regional derivative is not available yet'}).encode();status=404
        except (ValueError,TypeError,OverflowError) as exc:
            body=json.dumps({'error':str(exc)}).encode();status=400
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers()
        if not head:self.wfile.write(body)

    def respond(self, head):
        if urlsplit(self.path).path=='/api/rainfall-scenarios/status':
            from hydraulics.rainfall_scenarios import status
            body=json.dumps(status(),allow_nan=False).encode();self.send_response(200)
            self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers()
            if not head:self.wfile.write(body)
            return
        if urlsplit(self.path).path.startswith('/api/water-network/'):
            self.water_network_response(head)
            return
        if urlsplit(self.path).path.startswith('/api/regional-native/'):
            self.regional_native_response(head)
            return
        path = unquote(urlsplit(self.path).path)
        if path == '/api/channel-review/workspace':
            from hydraulics.channel_review import workspace
            body=json.dumps(workspace(),allow_nan=False).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            if not head:self.wfile.write(body)
            return
        if path in ('/api/catalog', '/healthz', '/api/transport/models'):
            try:
                if path == '/api/transport/models':
                    from transport.core import get_models
                    result = get_models()
                else:
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
        if path.startswith('/api/channel-inspector/'):
            name = path.rsplit('/', 1)[-1]
            if name not in {'inspector.json', 'overview_height.png', 'overview_depression.png', 'detail_height.png', 'detail_depression.png', 'flow_model.json', 'feature_graph.json', 'regional_flow.json', 'regional_manifest.json', 'terrain_flow.json', 'terrain_review_10m.json', 'terrain_review_5m.json', 'terrain_review.json'}:
                self.send_error(404)
                return
            if name in ('terrain_review_10m.json','terrain_review_5m.json','terrain_review.json'):
                base = ASSETS / 'private/terrain_refinement'
                file = base / 'review.json' if name == 'terrain_review.json' else base / ('10m' if name == 'terrain_review_10m.json' else '5m') / 'terrain_flow.json'
            elif name == 'terrain_flow.json':
                file = ASSETS / 'private/terrain_flow/terrain_flow.json'
            elif name in ('feature_graph.json','regional_flow.json','regional_manifest.json'):
                file = ASSETS / 'private/regional_network' / ('manifest.json' if name == 'regional_manifest.json' else name)
            else:
                file = ASSETS / ('private/humanum_flow' if name == 'flow_model.json' else 'private/channel_inspector') / name
            attachment = False
        elif path == '/regional-terrain':
            file = WEB / 'regional-terrain.html'
            attachment = False
        elif path == '/channel-inspector':
            file = WEB / 'channel-inspector.html'
            attachment = False
        elif path == '/transport-model':
            file = WEB / 'transport.html'
            attachment = False
        elif path == '/model-view':
            file = WEB / 'viewer.html'
            attachment = False
        elif path in ('/', '/index.html') or path.endswith(('.css', '.js', '.json', '.txt')) and not path.startswith('/assets/'):
            file = (WEB / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
            if not file.is_relative_to(WEB.resolve()):
                self.send_error(403)
                return
            attachment = False
        elif path.startswith('/assets/'):
            file = (ASSETS / path[len('/assets/'):]).resolve()
            if not file.is_relative_to(ASSETS.resolve()):
                self.send_error(403)
                return
            if file.is_relative_to((ASSETS / 'private').resolve()):
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
    # Initialize scientific C extensions before concurrent first requests.
    from hydraulics import regional_view,water_network_view,regional_faces
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'Angkor inventory listening on http://{args.host}:{args.port}', flush=True)
    server.serve_forever()
