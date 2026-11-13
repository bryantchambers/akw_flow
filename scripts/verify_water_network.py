#!/usr/bin/env python3
"""Independent GIS readback, reach/node topology and source coverage audit."""
import json,sys,time
from pathlib import Path
import numpy as np,pyogrio,rasterio
from pyogrio.raw import read
from shapely import from_wkb
from shapely.geometry import shape
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.build_water_network import OUT,BASE


def verify():
    m=json.loads((OUT/'network_manifest.json').read_text());layers=pyogrio.list_layers(OUT/'water_network.gpkg');counts={}
    for name,kind in layers:
        info=pyogrio.read_info(OUT/'water_network.gpkg',layer=name)
        if info['crs']!='EPSG:32648':raise ValueError('Wrong vector CRS')
        meta,fids,geometry,fields=read(OUT/'water_network.gpkg',layer=name)
        geometries=from_wkb(geometry)
        if not all(g.is_valid and not g.is_empty for g in geometries):raise ValueError('Invalid/empty GIS geometry')
        counts[name]=info['features']
        if counts[name]!=len(geometry):raise ValueError('GIS record readback mismatch')
    nodes={f['properties']['id']:f for f in json.loads((OUT/'nodes.geojson').read_text())['features']}
    reaches=json.loads((OUT/'reaches.geojson').read_text())['features'];degree={k:0 for k in nodes};togeo=Transformer.from_crs(32648,4326,always_xy=True)
    for f in reaches:
        p=f['properties'];a=p['from_node'];b=p['to_node']
        if a not in nodes or b not in nodes:raise ValueError('Dangling reach node reference')
        for key,coordinate in ((a,f['geometry']['coordinates'][0]),(b,f['geometry']['coordinates'][-1])):
            if not np.allclose(coordinate,nodes[key]['geometry']['coordinates'],rtol=0,atol=1e-10):raise ValueError('Reach geometry does not meet its node')
        if not p['source_ids']:raise ValueError('Reach missing source lineage')
        degree[a]+=1;degree[b]+=1
        if nodes[a]['properties']['component_id']!=p['component_id'] or nodes[b]['properties']['component_id']!=p['component_id']:raise ValueError('Component mismatch')
    for key,f in nodes.items():
        p=f['properties']
        if degree[key]!=p['degree']:raise ValueError('Node degree mismatch')
    with rasterio.open(BASE/'dtm_angkor_center.tif') as terrain:
        for f in nodes.values():
            p=f['properties'];expected=togeo.transform(*(terrain.transform @ (p['col']+.5,p['row']+.5)))
            if not np.allclose(expected,f['geometry']['coordinates'],rtol=0,atol=1e-10):raise ValueError('Node does not lie on native raster center')
    for filename,state in m['source_files'].items():
        f=BASE/filename
        if {'size':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns}!=state:raise ValueError('Extraction source changed')
    report={'status':'passed','gis_layers':counts,'native_node_locations_verified':len(nodes),'reach_endpoint_and_degree_checks':len(reaches),'geometric_components':m['components'],'cycle_rank':len(reaches)-len(nodes)+m['components'],
        'interpretation':'Geometry/topology/export acceptance only. Disconnected components remain disconnected; mapped contacts are not verified spillway crests. Hydraulic connectivity is governed by native cell-face bed elevations and evolving water levels.'}
    (OUT/'network_verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return report

if __name__=='__main__':verify()
