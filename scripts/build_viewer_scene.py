#!/usr/bin/env python3
"""Prepare actual Copernicus terrain and an uncalibrated D8 area-accumulation screening layer.
Requires numpy and rasterio. No rainfall, discharge, bacterial model, or canal routing is inferred.
"""
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import rasterio
from rasterio.merge import merge

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'assets/data/context'
BBOX = [103.6, 13.2, 104.2, 13.8]


def accumulate(z, dx, dy, cell_area):
    h, w = z.shape
    downstream = np.full((h, w), -1, dtype=np.int32)
    best = np.zeros((h, w), dtype=np.float32)
    indexes = np.arange(h*w, dtype=np.int32).reshape(h, w)
    for dr, dc in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
        r = slice(max(0,-dr), min(h,h-dr)); c = slice(max(0,-dc), min(w,w-dc))
        nr = slice(max(0,dr), min(h,h+dr)); nc = slice(max(0,dc), min(w,w+dc))
        slope = (z[r,c] - z[nr,nc]) / math.hypot(dr*dy,dc*dx)
        mask = slope > best[r,c]
        best[r,c][mask] = slope[mask]
        downstream[r,c][mask] = indexes[nr,nc][mask]
    receiver = downstream.ravel()
    area = np.full(z.size, cell_area, dtype=np.float64)
    for index in np.argsort(z.ravel())[::-1]:
        target = receiver[index]
        if target >= 0: area[target] += area[index]
    sinks = receiver < 0
    assert np.isclose(area[sinks].sum(), z.size*cell_area, rtol=1e-8)
    return area.reshape(z.shape), receiver, int(sinks.sum())


def main():
    paths = sorted(DATA.glob('Copernicus*.tif'))
    if len(paths) != 2: raise RuntimeError('Acquire the two context tiles first')
    sources = [rasterio.open(p) for p in paths]
    for src in sources:
        assert src.crs.to_epsg() == 4326 and src.width == 3600 and src.height == 3600, 'Unexpected source grid'
        assert np.allclose(src.res, [1/3600, 1/3600]), 'Unexpected source spacing'
    array, transform = merge(sources, bounds=BBOX)
    for src in sources: src.close()
    z = array[0]
    assert np.isfinite(z).all()
    west, south, east, north = BBOX
    latitude = (north+south)/2
    dx = 6371000 * math.cos(math.radians(latitude)) * math.radians(transform.a)
    dy = 6371000 * math.radians(-transform.e)
    area, receiver, sink_count = accumulate(z, dx, dy, dx*dy/1e6)
    stride = 9
    height, width = math.ceil(z.shape[0]/stride), math.ceil(z.shape[1]/stride)
    terrain=[]; screen=[]
    for r in range(height):
        for c in range(width):
            patch = (slice(r*stride,min((r+1)*stride,z.shape[0])),slice(c*stride,min((c+1)*stride,z.shape[1])))
            terrain.append(round(float(z[patch].mean()),2))
            screen.append(round(float(area[patch].max()),5))
    hot=[]
    for idx in np.argsort(area.ravel())[::-1]:
        r,c = divmod(int(idx),z.shape[1]); lon,lat=transform*(c+.5,r+.5)
        if all(math.hypot((lon-p['lon'])*math.cos(math.radians(latitude)),lat-p['lat'])*111320 > 1800 for p in hot):
            hot.append({'id':len(hot)+1,'lon':lon,'lat':lat,'value':round(float(area[r,c]),3),'elevation_m':round(float(z[r,c]),2),'domain_boundary':r in (0,z.shape[0]-1) or c in (0,z.shape[1]-1)})
        if len(hot)==10:break
    osm_path=DATA/'osm_water_context.geojson'
    osm=json.loads(osm_path.read_text()) if osm_path.exists() else {'type':'FeatureCollection','features':[]}
    raw=json.loads((DATA/'osm_water_raw.json').read_text()) if (DATA/'osm_water_raw.json').exists() else {}
    scene={'generated_utc':datetime.now(timezone.utc).isoformat(), 'bbox_wsen':BBOX,
      'fence_description':'Provisional rectangular search area; not an archaeological boundary or delineated catchment.',
      'width':width,'height':height,'grid_bbox_wsen':[west+(east-west)/width/2,south+(north-south)/height/2,east-(east-west)/width/2,north-(north-south)/height/2],'elevation_m':terrain,'screening_area_km2':screen,
      'terrain':{'source':'Copernicus GLO-30 Public (AWS 2021 release)','horizontal_crs':'EPSG:4326',
        'vertical_reference':'EGM2008 orthometric height, metres (product documentation)',
        'native_pixel_metres_approx':[dx,dy],'display_pixel_metres_approx':[dx*stride,dy*stride],
        'aggregation':'Mean elevation and maximum contributing area within each 9×9 native-pixel display cell.',
        'min_m':float(z.min()),'max_m':float(z.max()),
        'source_url':'https://registry.opendata.aws/copernicus-dem/'},
      'screening':{'method':'D8 steepest-descent contributing area','metric':'Upstream contributing area','unit':'km²',
        'status':'Exploratory terrain screening; not calibrated flow or bacterial output',
        'assumptions':['Uniform unit area contribution; no rainfall or runoff coefficient specified.',
          'Strictly downhill routing on the modern DSM; no pit filling or flat resolution.',
          'Canals, controls, storage, infiltration and sediment transport are not represented.',
          'Upstream supply outside the fence is omitted; mapped hotspots depend on the selected domain.',
          'Local sinks retain contributing area. This is not water depth, discharge, residence time or bacterial concentration.'],
        'native_cells':int(z.size),'local_sinks':sink_count,'mass_balance_check':'Sum of contributing area at all sinks equals total domain pixel area.'},
      'waterways':osm,'osm_snapshot':raw.get('osm3s',{}).get('timestamp_osm_base'),
      'osm_attribution':'© OpenStreetMap contributors, ODbL 1.0; modern features, historical status unverified.',
      'hotspots':hot,'model_outputs':[],
      'landmarks':[{'name':'Angkor Wat','lon':103.86699,'lat':13.41247},{'name':'Angkor Thom','lon':103.859,'lat':13.445},{'name':'West Baray','lon':103.802,'lat':13.434}]}
    dest=DATA/'viewer_scene.json';dest.write_text(json.dumps(scene,separators=(',',':'))+'\n')
    provenance={'generated_utc':scene['generated_utc'],'script':'scripts/build_viewer_scene.py',
      'source_files':[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths],
      'scene_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'native_shape':list(z.shape),'display_shape':[height,width],
      'modern_water_features':len(osm['features']),'screening':scene['screening']}
    (DATA/'viewer_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(json.dumps({'scene':str(dest),'bytes':dest.stat().st_size,'native_shape':list(z.shape),'display_shape':[height,width],'waterways':len(osm['features']),'hotspots':hot[:2]},indent=2),flush=True)


if __name__=='__main__':main()
