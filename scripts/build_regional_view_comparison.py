#!/usr/bin/env python3
"""Compare saved runs over the pilot footprint without altering either simulation."""
import json,sys
from pathlib import Path
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/private/regional_native'
PILOT=ROOT/'assets/private/terrain_flow/terrain_flow.json'


def state(path):return {'size':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns}

def build(output_directory=None):
    global OUT
    if output_directory is not None:OUT=Path(output_directory).resolve()
    pilot=json.loads(PILOT.read_text());regional=json.loads((OUT/'manifest.json').read_text())
    cfg=pilot['parameters'];x,y=cfg['center_utm_m'];half=cfg['extent_m']/2
    rp=regional['parameters']
    pilot_forcing=('Prescribed '+cfg['boundary_hydrograph']['side']+'-boundary water-level hydrograph') if cfg.get('boundary_hydrograph') else 'No prescribed inlet hydrograph'
    regional_forcing=('Configured stage boundaries' if rp.get('stage_boundaries') else 'Closed perimeter; no inlet hydrograph')+f"; rainfall {rp.get('rainfall_mm_hr',0):g} mm/hour"
    comparison={}
    for key in ('initial','final'):
        with rasterio.open(OUT/(key+'.tif')) as src:
            w=from_bounds(x-half,y-half,x+half,y+half,src.transform).round_offsets().round_lengths()
            h=src.read(1,window=w);valid=h>=0
            row={'water_volume_m3':float(h[valid].sum(dtype=np.float64)*.25),'wet_area_above_1mm_m2':float((valid&(h>.001)).sum()*.25),'maximum_depth_m':float(h[valid].max())}
            if key=='final':row['native_faces_above_1e_minus5_m3_s']=int((np.abs(src.read((2,3),window=w)*.5)>1e-5).sum())
            comparison[key]=row
    togeo=Transformer.from_crs(32648,4326,always_xy=True)
    points=[togeo.transform(xx,yy) for xx in (x-half,x+half) for yy in (y-half,y+half)]
    result={'pilot_bounds_lonlat':[[min(p[1] for p in points),min(p[0] for p in points)],[max(p[1] for p in points),max(p[0] for p in points)]],'pilot':{'spacing_m':cfg['grid_spacing_m'],'duration_s':cfg['duration_s'],'initial_stage_m':pilot['initial_stage_m'],
            'initial_water_volume_m3':pilot['budget']['initial_volume_m3'],'final_water_volume_m3':pilot['budget']['final_volume_m3'],
            'final_wet_cell_area_m2':sum(n['storage_area_m2'] for n,h in zip(pilot['nodes'],pilot['frames'][-1]['depth_m']) if h>.001),
            'initialization':f"Local mapped-terrain percentile {cfg['initial_water_stage_percentile']:g} + {cfg['initial_water_depth_above_mapped_bed_m']:g} m",'forcing':pilot_forcing},
        'regional':{'spacing_m':regional['solver_spacing_m'],'duration_s':regional['parameters']['duration_s'],
            'initialization':('Separate storage percentile levels; constant depth on conduits' if rp.get('initialization')=='separate_storage_and_conduits' else f"Minimum terrain of each connected mapped-water component + {rp['initial_mapped_water_depth_m']:g} m"),
            'forcing':regional_forcing,'pilot_footprint':comparison},
        'center_utm_m':[x,y],'extent_m':cfg['extent_m'],'warning':'These are different scenarios and times. This comparison diagnoses visibility and initialization; it is not a spatial convergence test. Wet areas use different cell/storage representations.',
        'source_states':{str(path.relative_to(ROOT)):state(path) for path in (PILOT,OUT/'manifest.json',OUT/'initial.tif',OUT/'final.tif')}}
    target=OUT/'view_comparison.json';tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(result,indent=2));tmp.replace(target)
    print(json.dumps(result,indent=2));return result

if __name__=='__main__':build()
