#!/usr/bin/env python3
"""Check revised regional initialization and a native pilot-window relaxation first."""
import json,sys,time
from pathlib import Path
import numpy as np,rasterio
from rasterio.windows import from_bounds
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.water_initialization import initialize_mapped_water
from hydraulics.native_grid import simulate
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/water_system';BASE=ROOT/'assets/private/humanum_danish_edna'


def check():
    c=json.loads((ROOT/'configs/water_system.json').read_text());pilot=json.loads((ROOT/'assets/private/terrain_flow/terrain_flow.json').read_text())
    with rasterio.open(BASE/'dtm_angkor_center.tif') as src:
        z=src.read(1);z[(z==src.nodata)|~np.isfinite(z)]=np.nan;tf=src.transform
    h,initialization=initialize_mapped_water(z,tf,BASE,c)
    x,y=pilot['parameters']['center_utm_m'];extent=pilot['parameters']['extent_m'];half=extent/2
    w=from_bounds(x-half,y-half,x+half,y+half,tf).round_offsets().round_lengths();sl=np.s_[int(w.row_off):int(w.row_off+w.height),int(w.col_off):int(w.col_off+w.width)]
    zz=z[sl].copy();hh=h[sl].copy();del z,h
    p={**c,'duration_s':5,'threads':2};r=simulate(zz,hh,p,initial_concentration=np.ones_like(hh))
    maxv=0.;deepfr=0;wetfaces=0;maxdeepv=0.;maxdeepfr=0.
    for axis,q in ((1,r['qx_per_width']),(0,r['qy_per_width'])):
        a=np.s_[:,:-1] if axis==1 else np.s_[:-1,:];b=np.s_[:,1:] if axis==1 else np.s_[1:,:]
        depth=np.maximum(zz[a]+r['momentum_depth'][a],zz[b]+r['momentum_depth'][b])-np.maximum(zz[a],zz[b]);flux=q[a]
        valid=np.isfinite(depth)&(depth>1e-6);velocity=np.divide(flux,depth,out=np.zeros_like(flux),where=valid);maxv=max(maxv,float(abs(velocity).max()))
        deep=valid&(depth>=.01);wetfaces+=int(deep.sum());fr=abs(velocity[deep])/np.sqrt(9.80665*depth[deep]);deepfr+=int((fr>1).sum())
        if deep.any():maxdeepv=max(maxdeepv,float(abs(velocity[deep]).max()));maxdeepfr=max(maxdeepfr,float(fr.max()))
    if not np.isfinite(r['depth']).all() or (r['depth']<0).any():raise ValueError('Invalid native pilot state')
    if abs(r['budget']['residual_m3'])>1e-7*max(1.,r['budget']['initial_volume_m3']):raise ValueError('Pilot conservation failure')
    report={'implementation_status':'passed','scenario':'Revised cross-section stage initialization; 5 s native relaxation over original pilot footprint, closed crop boundary (not pilot hydrograph)',
        'shape':list(zz.shape),'spacing_m':.5,'initial_water_volume_m3':float(hh.sum()*.25),'initial_wet_area_m2':float((hh>.001).sum()*.25),
        'final_water_volume_m3':r['budget']['final_volume_m3'],'maximum_face_velocity_m_s':maxv,'faces_depth_at_least_1cm':wetfaces,'faces_froude_over_1_at_depth_at_least_1cm':deepfr,'maximum_deep_face_velocity_m_s':maxdeepv,'maximum_deep_face_froude':maxdeepfr,
        'budget':r['budget'],'tracer_budget':r['tracer_budget'],'regional_initialization':{k:v for k,v in initialization.items() if k!='storage_bodies'},'scientific_validation':'not validated; any supercritical faces require momentum/regime review'}
    np.savez_compressed(OUT/'native_pilot_preflight.npz',terrain=zz,initial_depth=hh,final_depth=r['depth'],qx=r['qx_per_width'],qy=r['qy_per_width'])
    (OUT/'preflight.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return report

if __name__=='__main__':check()
