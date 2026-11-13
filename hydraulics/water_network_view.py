"""Allowlisted local GIS derivatives for the rebuilt water-system model."""
import json,math
from pathlib import Path
from functools import lru_cache
from .water_case import active_directory
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/water_system'
LAYERS={'reaches','nodes','waterbodies','ports','cross_sections'}
DOWNLOADS={'water_network.gpkg':'application/geopackage+sqlite3',**{name+'.geojson':'application/geo+json' for name in LAYERS},
    'diagnosis.pdf':'application/pdf','depth_flux_native.tif':'image/tiff','terrain_native.tif':'image/tiff'}


def coupling_current(coupling):
    if not coupling:return False
    model=OUT/coupling.get('model_directory','hydraulics')
    if model.resolve()!=active_directory().resolve():return False
    manifest=model/'manifest.json'
    if not manifest.exists() or json.loads(manifest.read_text()).get('status')!='complete':return False
    for name,expected in coupling['model_source_state'].items():
        f=model/name
        if not f.exists() or {'size':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns}!=expected:return False
    return True


def status():
    result={name:json.loads((OUT/(name+'.json')).read_text()) if (OUT/(name+'.json')).exists() else None for name in ('network_manifest','coupling','acceptance','network_verification','preflight')}
    if result['coupling'] and not coupling_current(result['coupling']):result['coupling']=None
    return result


@lru_cache(maxsize=10)
def load(name,mtime):
    data=json.loads((OUT/(name+'.geojson')).read_text())
    return data,[(shape(f['geometry']).bounds,f) for f in data['features']]


def layer(name,bounds=None):
    if name not in LAYERS:raise ValueError('Unknown water-network layer')
    file=OUT/(name+'.geojson')
    data,features=load(name,file.stat().st_mtime_ns)
    # A geometry cache must never preserve invalidated directions from an older hydraulic case.
    cp=OUT/'coupling.json'
    coupled=json.loads(cp.read_text()) if cp.exists() else None
    if name=='reaches' and coupled and not coupling_current(coupled):
        features=[(b,{**f,'properties':{**f['properties'],'flow_direction':0,'discharge_m3_s':None,'flow_status':'Hydraulic case changed; flux integration pending'}}) for b,f in features]
        data={'type':'FeatureCollection','features':[f for _,f in features]}
    if bounds is None:return data
    if len(bounds)!=4 or not all(math.isfinite(v) for v in bounds):raise ValueError('Invalid bounds')
    w,s,e,n=bounds
    if not -180<=w<e<=180 or not -85<=s<n<=85:raise ValueError('Invalid bounds')
    return {'type':'FeatureCollection','features':[f for (a,b,c,d),f in features if a<=e and c>=w and b<=n and d>=s]}


def download(name):
    if name not in DOWNLOADS:raise FileNotFoundError('Unknown GIS derivative')
    if name=='diagnosis.pdf':
        file=ROOT/'knowledge/Fixed-terrain model/Fixed-terrain rebuild diagnosis.pdf'
        if not file.is_file():raise FileNotFoundError('Diagnosis report not ready')
        return file,DOWNLOADS[name]
    model=active_directory()
    file=model/'final.tif' if name=='depth_flux_native.tif' else model/'terrain.tif' if name=='terrain_native.tif' else OUT/name
    if name=='depth_flux_native.tif':
        manifest=model/'manifest.json'
        if not manifest.exists() or json.loads(manifest.read_text()).get('status')!='complete':raise FileNotFoundError('Native hydraulic export not ready')
    if not file.is_file():raise FileNotFoundError('GIS derivative not ready')
    return file,DOWNLOADS[name]
