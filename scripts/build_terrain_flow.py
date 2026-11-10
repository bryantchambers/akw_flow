#!/usr/bin/env python3
"""Private fixed-terrain 2D pilot. Explicit scenario edits; no blanket channel burning."""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import rasterio
import shapefile
from rasterio.features import rasterize
from rasterio.windows import Window
from pyproj import Transformer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hydraulics.terrain import simulate, stage_from_volume
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/private/terrain_flow'


def build(config, output_directory=None):
    out = Path(output_directory) if output_directory is not None else OUT
    base = ROOT / 'assets/private/humanum_danish_edna'
    spacing = float(config['grid_spacing_m']); extent = float(config['extent_m'])
    if not np.isfinite([spacing,extent]).all() or spacing < 1 or extent <= 0: raise ValueError('Invalid grid')
    with rasterio.open(base/'dtm_angkor_center.tif') as src:
        if src.crs.to_epsg() != 32648 or src.res != (.5,.5): raise ValueError('Expected native 0.5 m EPSG:32648 terrain')
        factor = round(spacing/.5); count = round(extent/spacing)
        if not np.isclose(factor*.5,spacing) or not np.isclose(count*spacing,extent) or count**2 > config['maximum_cells']:
            raise ValueError('Extent must divide spacing; cell limit applies')
        x,y = config['center_utm_m']; row,col = src.index(x-extent/2,y+extent/2)
        h = count*factor
        if min(row,col)<0 or row+h>src.height or col+h>src.width: raise ValueError('Pilot outside terrain coverage')
        tf = src.window_transform(Window(col,row,h,h))
        raw = src.read(1,window=Window(col,row,h,h),masked=True).filled(np.nan).astype(float)
        scale=float(config.get('elevation_scale_to_m',1))
        if not np.isfinite(scale) or scale<=0:raise ValueError('Elevation scale must be positive and finite')
        raw *= scale
    z = raw.copy()
    edits = config.get('terrain_modifications', [])
    for edit in edits:
        # Each polygon is a documented fixed scenario: opening, crest or channel-bed reconstruction.
        if not edit.get('evidence') or edit.get('mode') not in ('set','lower','raise'): raise ValueError('Document every terrain edit and mode')
        mask = rasterize([(edit['geometry_projected'],1)],out_shape=z.shape,transform=tf,fill=0).astype(bool)
        val = float(edit['elevation_m'])
        if not np.isfinite(val): raise ValueError('Nonfinite edit')
        if edit['mode']=='set': z[mask]=val
        elif edit['mode']=='lower': z[mask]=np.minimum(z[mask],val)
        else: z[mask]=np.maximum(z[mask],val)
    shapes=[]
    for rec in shapefile.Reader(str(base/'angkor_center_features')).iterShapeRecords():
        if rec.record['TYPE'] in (1,2,4): shapes.append((rec.shape.__geo_interface__,int(rec.record['TYPE'])))
    water = rasterize(shapes,out_shape=z.shape,transform=tf,fill=0).astype(bool)
    patches = z.reshape(count,factor,count,factor).transpose(0,2,1,3).reshape(count*count,-1)
    valid = np.isfinite(patches).all(axis=1)
    indices = np.where(valid)[0]; lookup=np.full(count*count,-1,int);lookup[indices]=np.arange(len(indices))
    if not len(indices): raise ValueError('No fully supported terrain cells')
    samples = int(config.get('storage_samples',32))
    if not 4 <= samples <= factor**2: raise ValueError('Invalid storage sample count')
    zz = np.quantile(patches[valid],np.linspace(0,1,samples),axis=1).T
    water_fraction = water.reshape(count,factor,count,factor).mean(axis=(1,3)).ravel()[valid]
    a=[];b=[];profiles=[];geometries=[]
    togeo = Transformer.from_crs(32648,4326,always_xy=True)
    nodes=[]
    for flat in indices:
        r,c=divmod(int(flat),count);i=lookup[flat]
        corners=[tf*(cc*factor,rr*factor) for cc,rr in [(c,r),(c+1,r),(c+1,r+1),(c,r+1),(c,r)]]
        center=tf*((c+.5)*factor,(r+.5)*factor)
        nodes.append({'id':f'terrain:r{r}c{c}','coordinates':list(togeo.transform(*center)),
            'geometry':{'type':'Polygon','coordinates':[[list(togeo.transform(*xy)) for xy in corners]]},
            'bed_elevation_m':float(zz[i,0]),'storage_area_m2':spacing**2,'water_fraction':float(water_fraction[i])})
        for dr,dc in ((0,1),(1,0)):
            rr,cc=r+dr,c+dc
            if rr>=count or cc>=count or lookup[rr*count+cc]<0: continue
            j=lookup[rr*count+cc]
            if dc:
                k=(c+1)*factor
                prof=np.maximum(z[r*factor:(r+1)*factor,k-1],z[r*factor:(r+1)*factor,k])
                points=[tf*(k,r*factor),tf*(k,(r+1)*factor)]
            else:
                k=(r+1)*factor
                prof=np.maximum(z[k-1,c*factor:(c+1)*factor],z[k,c*factor:(c+1)*factor])
                points=[tf*(c*factor,k),tf*((c+1)*factor,k)]
            a.append(int(i));b.append(int(j));profiles.append(prof.tolist())
            geometries.append({'type':'LineString','coordinates':[list(togeo.transform(*xy)) for xy in points]})
    controls=config.get('face_controls', [])
    controlled={}
    for control in controls:
        if not control.get('evidence'):raise ValueError('Face controls require evidence / scenario rationale')
        face=int(control['face_index'])
        if face<0 or face>=len(profiles) or face in controlled:raise ValueError('Unknown or repeated face control')
        values=np.asarray(control['profile_elevations_m'],float)
        if values.shape!=(factor,) or not np.isfinite(values).all():raise ValueError('Face control must supply one elevation per native strip')
        profiles[face]=values.tolist();controlled[face]=control
    mesh={'terrain_samples_m':zz.tolist(),'face_profiles_m':profiles,'face_from':a,'face_to':b,'cell_area_m2':spacing**2,'spacing_m':spacing}
    scenario=dict(config)
    wetvals=z[water & np.isfinite(z)]
    if not len(wetvals): raise ValueError('No mapped water in pilot')
    initial_level=float(np.percentile(wetvals,config['initial_water_stage_percentile']))+config['initial_water_depth_above_mapped_bed_m']
    # Optional mesh-independent initial water volume, aggregated from native mapped pixels.
    initialization = config.get('initialization', 'cell_stage')
    if initialization == 'native_mapped_water_volume':
        native_volume = np.where(water, np.maximum(initial_level-z,0), 0)*.25
        volumes = native_volume.reshape(count,factor,count,factor).sum(axis=(1,3)).ravel()[valid]
        scenario['initial_stage_m'] = stage_from_volume(volumes,zz,spacing**2).tolist()
    elif initialization == 'cell_stage':
        scenario['initial_stage_m']=np.where(water_fraction>0,initial_level,zz[:,0]).tolist()
    else: raise ValueError('Unknown initialization mode')
    boundary=config.get('boundary_hydrograph')
    if boundary:
        side=boundary['side']
        if side not in ('north','south','east','west'):raise ValueError('Invalid boundary side')
        span=boundary.get('coordinate_span_m')
        if span is not None and (len(span)!=2 or not np.isfinite(span).all() or not span[0]<span[1]):raise ValueError('Boundary coordinate span must have finite increasing limits')
        ids=[]
        for i,flat in enumerate(indices):
            r,c=divmod(int(flat),count)
            on={'north':r==0,'south':r==count-1,'west':c==0,'east':c==count-1}[side]
            center=tf*((c+.5)*factor,(r+.5)*factor)
            span=boundary.get('coordinate_span_m')
            along=center[0] if side in ('north','south') else center[1]
            in_span=span is None or float(span[0]) <= along < float(span[1])
            if on and in_span and (not boundary.get('mapped_water_only',True) or water_fraction[i]>.05):ids.append(i)
        if not ids:raise ValueError('No selected boundary cells')
        scenario['stage_boundaries']=[{'cells':ids,'series':[[t,initial_level+offset] for t,offset in boundary['stage_offsets_m']], 'tracer_concentration':boundary.get('tracer_concentration',0)}]
    print(f'Solving {len(nodes)} terrain cells, {len(a)} faces; initial stage {initial_level:.3f}',flush=True)
    result=simulate(mesh,scenario)
    edges=[{'id':f'face:{i}','from':nodes[aa]['id'],'to':nodes[bb]['id'],'face_geometry':geometries[i],
        'control':controlled.get(i),'crest_min_m':min(profiles[i]),'crest_max_m':max(profiles[i]),'length_m':spacing,'width_m':spacing} for i,(aa,bb) in enumerate(zip(a,b))]
    payload={'version':2,'model':'Fixed-terrain 2D subgrid local-inertial pilot','status':'Hypothetical forcing; uncalibrated. Fixed geometry, no erosion. Closed perimeter except explicit stage cells.',
        'nodes':nodes,'edges':edges,'parameters':config,'initial_stage_m':initial_level,**result,
        'assumptions':['0.5 m DTM; vertical metres provisional; bathymetry unverified.',
            'No blanket mapped-water incision. Geometry edits are explicit fixed scenarios.',
            'All terrain cells included, not only mapped water. Invalid terrain is impermeable.',
            'Quantile-compressed storage; native 0.5 m strips along faces, maximum of two adjacent pixels.',
            'One stage per cell; unresolved subcell barriers may require refinement.',
            'Local-inertial approximation omits advective momentum; not validated for rapid breach flows.',
            'Conservative unit tracer, no pathogen kinetics. Rain and groundwater inflow have zero tracer.',
            'Infiltration carries dissolved tracer out; no soil tracer or regional aquifer simulation.']}
    out.mkdir(parents=True,exist_ok=True)
    target=out/'terrain_flow.json'
    temporary=out/'terrain_flow.json.tmp'
    temporary.write_text(json.dumps(payload,allow_nan=False,separators=(',',':')))
    temporary.replace(target)
    (out/'mesh.json').write_text(json.dumps(mesh,allow_nan=False,separators=(',',':')))
    manifest={'model':payload['model'],'config':config,'cells':len(nodes),'faces':len(edges),'excluded_no_data_cells':int((~valid).sum()),'boundary_cells':scenario.get('stage_boundaries',[]),
        'budget':result['budget'],'tracer_budget':result['tracer_budget'],'steps':result['steps'],'limiter_steps':result['limiter_steps'],
        'grid':{'rows':count,'cols':count,'native_factor':factor,'transform':list(tf)[:6],'valid_flat_indices':indices.tolist()},'source':str(base/'dtm_angkor_center.tif'),'source_size_bytes':(base/'dtm_angkor_center.tif').stat().st_size,
        'source_modified_ns':(base/'dtm_angkor_center.tif').stat().st_mtime_ns,'assumptions':payload['assumptions'],
        'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'solver_sha256':hashlib.sha256((ROOT/'hydraulics/terrain.py').read_bytes()).hexdigest()}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({'budget':result['budget'],'tracer_budget':result['tracer_budget'],'steps':result['steps']}),flush=True)
    return payload

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--config',default=str(ROOT/'configs/terrain_flow.json'));args=parser.parse_args()
    build(json.loads(Path(args.config).read_text()))
