#!/usr/bin/env python3
"""Mapped-water finite-volume storage grid, hypothetical bathymetry; private pilot."""
import json,sys,math
from pathlib import Path
import numpy as np
import rasterio,shapefile
from rasterio.features import rasterize
from rasterio.transform import from_origin
from rasterio.windows import Window
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.model import simulate
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/private/humanum_flow'


def build(config):
    def number(key,minimum=0,strict=False):
        x=float(config[key])
        if not math.isfinite(x) or x<minimum or strict and x==minimum:raise ValueError('Invalid '+key)
        return x
    spacing=number('grid_spacing_m',0,True);fraction=number('minimum_wet_fraction',0,True)
    if spacing<2 or fraction>1:raise ValueError('Use spacing >=2 m and fraction <=1')
    incision=number('bed_incision_m');tracewidth=number('water_trace_width_m',0,True)
    base=ROOT/'assets/private/humanum_danish_edna';pilot=json.loads((ROOT/'assets/private/humanum_channels/balanced_network.json').read_text())
    row,col=pilot['provenance']['window_row_col'];h,w=pilot['provenance']['window_shape']
    with rasterio.open(base/'dtm_angkor_center.tif') as src:
        win=Window(col,row,w,h);z=src.read(1,window=win,masked=True).astype(float).filled(np.nan);tf=src.window_transform(win)
    shapes=[]
    for name in ['angkor_center_features','angkor_center_lineartraces']:
        reader=shapefile.Reader(str(base/name))
        for rec in reader.iterShapeRecords():
            typ=int(rec.record['TYPE'])
            if name.endswith('features') and typ not in (1,2,4):continue
            if name.endswith('lineartraces') and typ!=2:continue
            shapes.append((rec.shape.__geo_interface__,1 if name.endswith('features') else 2))
    polygon=rasterize([(g,1) for g,k in shapes if k==1],out_shape=z.shape,transform=tf,fill=0).astype(bool)
    lines=rasterize([(g,1) for g,k in shapes if k==2],out_shape=z.shape,transform=tf,fill=0).astype(bool)
    from scipy.ndimage import distance_transform_edt
    wet=polygon.copy()
    if lines.any():wet |= distance_transform_edt(~lines,sampling=.5)<=tracewidth/2
    wet &= np.isfinite(z)
    factor=round(spacing/.5)
    if not np.isclose(factor*.5,spacing):raise ValueError('Spacing must be a multiple of 0.5 m')
    if h%factor or w%factor:raise ValueError('Spacing must divide pilot dimensions')
    height,width=h//factor,w//factor;nodes=[];cells={};togeo=Transformer.from_crs(32648,4326,always_xy=True)
    for r in range(height):
        for c in range(width):
            patch=wet[r*factor:(r+1)*factor,c*factor:(c+1)*factor];f=float(patch.mean())
            if f<fraction:continue
            values=z[r*factor:(r+1)*factor,c*factor:(c+1)*factor][patch]
            identifier=f'r{r}c{c}';x,y=tf*((c+.5)*factor,(r+.5)*factor)
            corners=[tf*(cc*factor,rr*factor) for cc,rr in [(c,r),(c+1,r),(c+1,r+1),(c,r+1),(c,r)]]
            node={'id':identifier,'bed_elevation_m':float(np.percentile(values,20))-incision+float(config.get('node_bed_offsets_m',{}).get(identifier,0)),
                  'storage_area_m2':float(patch.sum())*.25,'coordinates':list(togeo.transform(x,y)),
                  'geometry':{'type':'Polygon','coordinates':[[list(togeo.transform(*xy)) for xy in corners]]},'wet_fraction':f}
            cells[r,c]=len(nodes);nodes.append(node)
    if not nodes or len(nodes)>1000:raise ValueError('Pilot requires 1..1000 wet cells; coarsen grid if necessary')
    edges=[]
    for (r,c),i in cells.items():
        for dr,dc in [(1,0),(0,1)]:
            if (r+dr,c+dc) not in cells:continue
            # Require wet pixels touching across the shared cell interface.
            if dr:
                a=wet[(r+1)*factor-1,c*factor:(c+1)*factor];b=wet[(r+1)*factor,c*factor:(c+1)*factor]
            else:
                a=wet[r*factor:(r+1)*factor,(c+1)*factor-1];b=wet[r*factor:(r+1)*factor,(c+1)*factor]
            contact=float(np.sum(a&b))*.5
            if not contact:continue
            j=cells[r+dr,c+dc];edges.append({'id':nodes[i]['id']+'_'+nodes[j]['id'],'from':nodes[i]['id'],'to':nodes[j]['id'],'length_m':spacing,'width_m':contact})
    external=config.get('external_node_flows_m3_s',{})
    if set(external)-{n['id'] for n in nodes}:raise ValueError('External flow references unknown cell')
    scenario={k:config[k] for k in ['duration_s','dt_max_s','output_interval_s','initial_depth_m','roughness','edge_overrides','max_steps']}
    rain=number('rainfall_mm_hr')/1000/3600
    scenario['groundwater']=config.get('groundwater',{'enabled':False})
    scenario['external_flows_m3_s']=[rain*n['storage_area_m2']+float(external.get(n['id'],0)) for n in nodes]
    network={'nodes':nodes,'edges':edges,'assumptions':['Mapped-water pilot only; closed boundaries except explicitly configured sources/sinks.','Cells are lumped water storage; multiple subcell components may be conflated.','20th percentile current terrain minus assumed incision is not measured bathymetry.','Interface widths derive from rasterized mapping, not surveyed wetted cross sections.','Banks, gates, culverts and overflow structures are not resolved.','Diffusion-wave closure omits inertia; rapid waves and supercritical flows require a fuller solver.']}
    result=simulate(network,scenario)
    frames=[]
    for sample in result['samples']:
        frames.append({'time_s':sample['time_s'],'depth_m':[v/n['storage_area_m2'] for v,n in zip(sample['volumes_m3'],nodes)],'flows_m3_s':sample['flows_m3_s'],**{k:sample[k] for k in ('groundwater_head_m','surface_to_groundwater_m3_s') if k in sample}})
    payload={'status':'Hypothetical mapped-water pilot; not calibrated historical flow','nodes':nodes,'edges':edges,'frames':frames,'budget':result['budget'],'groundwater_budget':result.get('groundwater_budget'),'parameters':config,'assumptions':network['assumptions']}
    OUT.mkdir(parents=True,exist_ok=True)
    for name,data in [('network.json',network),('scenario.json',scenario),('simulation.json',result),('flow_model.json',payload)]:
        temporary=OUT/(name+'.tmp')
        temporary.write_text(json.dumps(data,allow_nan=False))
        temporary.replace(OUT/name)
    return payload
if __name__=='__main__':
    p=build(json.loads((ROOT/'configs/humanum_flow.json').read_text()));print(json.dumps({'nodes':len(p['nodes']),'edges':len(p['edges']),'budget':p['budget']}))
