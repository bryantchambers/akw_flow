"""Allowlisted local GIS derivatives, scoped to the selected verified case."""
import json,math
from pathlib import Path
from functools import lru_cache
from .water_case import active_directory,case_directory
from shapely.geometry import shape
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/water_system'
LAYERS={'reaches','nodes','waterbodies','ports','cross_sections'}
DOWNLOADS={'water_network.gpkg':'application/geopackage+sqlite3',**{name+'.geojson':'application/geo+json' for name in LAYERS},
    'scenario_summary.json':'application/json','diagnosis.pdf':'application/pdf','depth_flux_native.tif':'image/tiff','terrain_native.tif':'image/tiff'}


def scope(case=None):
    model=case_directory(case)
    network=model/'network'
    if (network/'coupling.json').exists():return model,network
    if model.resolve()!=active_directory().resolve():raise FileNotFoundError('Scenario network is not ready')
    return model,OUT


def coupling_current(coupling,model=None):
    if not coupling:return False
    model=model if model is not None else active_directory()
    if model.name!=coupling.get('model_directory','hydraulics'):return False
    manifest=model/'manifest.json'
    if not manifest.exists() or json.loads(manifest.read_text()).get('status')!='complete':return False
    for name,expected in coupling['model_source_state'].items():
        f=model/name
        if not f.exists() or {'size':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns}!=expected:return False
    return True


def status(case=None):
    model,network=scope(case);result={'case':model.name}
    for name in ('network_manifest','network_verification','preflight'):
        p=OUT/(name+'.json');result[name]=json.loads(p.read_text()) if p.exists() else None
    for name,path in [('coupling',network/'coupling.json'),('acceptance',model/'acceptance.json' if network!=OUT else OUT/'acceptance.json'),('scenario_summary',model/'scenario_summary.json')]:
        result[name]=json.loads(path.read_text()) if path.exists() else None
    if result['coupling'] and not coupling_current(result['coupling'],model):result['coupling']=None
    return result


@lru_cache(maxsize=16)
def load(path,mtime):
    data=json.loads(Path(path).read_text())
    return data,[(shape(f['geometry']).bounds,f) for f in data['features']]


def layer(name,bounds=None,case=None):
    if name not in LAYERS:raise ValueError('Unknown water-network layer')
    model,network=scope(case);file=network/(name+'.geojson')
    data,features=load(str(file),file.stat().st_mtime_ns)
    cp=network/'coupling.json';coupled=json.loads(cp.read_text()) if cp.exists() else None
    if name=='reaches' and coupled and not coupling_current(coupled,model):
        features=[(b,{**f,'properties':{**f['properties'],'flow_direction':0,'discharge_m3_s':None,'flow_status':'Hydraulic case changed; flux integration pending'}}) for b,f in features]
        data={'type':'FeatureCollection','features':[f for _,f in features]}
    if bounds is None:return data
    if len(bounds)!=4 or not all(math.isfinite(v) for v in bounds):raise ValueError('Invalid bounds')
    w,s,e,n=bounds
    if not -180<=w<e<=180 or not -85<=s<n<=85:raise ValueError('Invalid bounds')
    return {'type':'FeatureCollection','features':[f for (a,b,c,d),f in features if a<=e and c>=w and b<=n and d>=s]}


def download(name,case=None):
    if name not in DOWNLOADS:raise FileNotFoundError('Unknown GIS derivative')
    model,network=scope(case)
    if name=='diagnosis.pdf':
        if network!=OUT:raise FileNotFoundError('The baseline diagnosis PDF is not a rainfall scenario report')
        file=ROOT/'knowledge/Fixed-terrain model/Fixed-terrain rebuild diagnosis.pdf'
    elif name=='scenario_summary.json':file=model/name
    else:file=model/'final.tif' if name=='depth_flux_native.tif' else model/'terrain.tif' if name=='terrain_native.tif' else network/name
    if name=='depth_flux_native.tif':
        manifest=model/'manifest.json'
        if not manifest.exists() or json.loads(manifest.read_text()).get('status')!='complete':raise FileNotFoundError('Native hydraulic export not ready')
    if not file.is_file():raise FileNotFoundError('GIS derivative not ready')
    return file,DOWNLOADS[name]
