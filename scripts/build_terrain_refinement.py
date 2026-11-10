#!/usr/bin/env python3
"""Same-domain 10 m / 5 m pilot comparison and native-terrain connectivity screening."""
import argparse, copy, json, sys, hashlib
from pathlib import Path
import numpy as np
import rasterio, shapefile
from rasterio.features import rasterize
from rasterio.windows import Window
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.build_terrain_flow import build, ROOT
from hydraulics.terrain_review import disconnected_pools, aggregate_nested
OUT=ROOT/'assets/private/terrain_refinement'


def audit(payload,manifest):
    grid=manifest['grid'];factor=grid['native_factor'];count=grid['cols'];tf=rasterio.Affine(*grid['transform'])
    h=count*factor
    with rasterio.open(manifest['source']) as src:
        row,col=src.index(tf.c,tf.f)
        z=src.read(1,window=Window(col,row,h,h),masked=True).filled(np.nan).astype(float)*payload['parameters']['elevation_scale_to_m']
    shapes=[]
    for rec in shapefile.Reader(str(ROOT/'assets/private/humanum_danish_edna/angkor_center_features')).iterShapeRecords():
        if rec.record['TYPE'] in (3,7):shapes.append((rec.shape.__geo_interface__,1))
    banks=rasterize(shapes,out_shape=z.shape,transform=tf,fill=0).astype(bool)
    stages=[payload['initial_stage_m']+offset for offset in (0.,.75,1.5)]
    flagged=[];counts=[0]*len(stages);area=[0.]*len(stages)
    for i,flat in enumerate(grid['valid_flat_indices']):
        r,c=divmod(flat,count);patch=z[r*factor:(r+1)*factor,c*factor:(c+1)*factor]
        pools=[disconnected_pools(patch,stage) for stage in stages]
        split=[p['pool_count']>1 for p in pools]
        for j,yes in enumerate(split):
            if yes:counts[j]+=1;area[j]+=pools[j]['secondary_pool_area_m2']
        bank=bool(banks[r*factor:(r+1)*factor,c*factor:(c+1)*factor].any())
        if not any(split):continue
        mid=factor//2;profile_x=patch[mid,:].tolist();profile_y=patch[:,mid].tolist()
        flagged.append({'cell_index':i,'id':payload['nodes'][i]['id'],'geometry':payload['nodes'][i]['geometry'],
            'mapped_bank_or_raised_overlap':bank,'stages_m':stages,'pools':pools,
            'simulated_wet':payload['maximum_depth_m'][i]>.001,
            'priority':'mapped_barrier_and_disconnected_pools' if bank else 'disconnected_subcell_pools',
            'native_cross_sections':{'distance_m':((np.arange(factor)+.5)*.5).tolist(),'west_to_east_m':profile_x,'north_to_south_m':profile_y},
            'score':max(p['secondary_pool_area_m2'] for p in pools)*(2 if bank else 1)})
    flagged.sort(key=lambda x:(x['simulated_wet'],x['mapped_bank_or_raised_overlap'],x['score']),reverse=True)
    return {'screening_stages_m':stages,'counts_by_stage':counts,'secondary_pool_area_m2_by_stage':area,
        'flagged_cells':len(flagged),'simulated_wet_flag_count':sum(f['simulated_wet'] for f in flagged),'mapped_barrier_overlap_count':sum(f['mapped_bank_or_raised_overlap'] for f in flagged),
        'review_queue':flagged,'minimum_pool_area_m2':1.,'note':'Native four-neighbour wet patches at uniform screening levels. Multiple pools within one model cell indicate possible premature mixing. This is a flag, not proof of a bank or failed flow.'}


def gauge(payload,manifest):
    tf=rasterio.Affine(*manifest['grid']['transform']);dx=payload['parameters']['grid_spacing_m'];count=manifest['grid']['cols']
    # Transect lies on a 10 m grid line and therefore also on the nested 5 m grid.
    north=tf.f;target=north-200
    ids=[]
    for i,e in enumerate(payload['edges']):
        suffix=e['from'].split(':')[-1];r,c=map(int,suffix[1:].split('c'))
        to=e['to'].split(':')[-1];rr,cc=map(int,to[1:].split('c'))
        x=tf.c+(c+.5)*dx
        if rr==r+1 and abs(north-(r+1)*dx-target)<1e-6 and tf.c+230<=x<tf.c+380:ids.append(i)
    if not ids:raise ValueError('No transect faces')
    cumulative=0.;series=[];last=0.
    for f in payload['frames']:
        mean=sum(f['preceding_interval_mean_flows_m3_s'][i] for i in ids)
        cumulative+=mean*(f['time_s']-last);last=f['time_s']
        series.append({'time_s':last,'flow_m3_s':sum(f['flows_m3_s'][i] for i in ids),'net_volume_m3':cumulative})
    return {'name':'Canal cross-section · positive southward','projected_y_m':target,'projected_x_span_m':[tf.c+230,tf.c+380],
        'face_count':len(ids),'series':series,'note':'Diagnostic transect across the canal corridor; not a verified structure or outlet.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reuse',action='store_true');args=parser.parse_args()
    cfg=json.loads((ROOT/'configs/terrain_flow.json').read_text())
    if cfg.get('terrain_modifications') or cfg.get('face_controls'):raise ValueError('Study requires unmodified geometry; create an explicit study for altered terrain')
    cfg['initialization']='native_mapped_water_volume'
    cfg['maximum_cells']=20000
    # Pin one equal-width inlet band inside ANG_F_09042, excluding unrelated boundary ponds.
    with rasterio.open(ROOT/'assets/private/humanum_danish_edna/dtm_angkor_center.tif') as src:
        row,col=src.index(cfg['center_utm_m'][0]-cfg['extent_m']/2,cfg['center_utm_m'][1]+cfg['extent_m']/2)
        x0,_=src.transform*(col,row)
    cfg['boundary_hydrograph']['mapped_water_only']=False
    cfg['boundary_hydrograph']['coordinate_span_m']=[x0+330,x0+340]
    results=[];manifests=[];audits=[];gauges=[]
    for spacing in (10,5):
        scenario=copy.deepcopy(cfg);scenario['grid_spacing_m']=spacing;directory=OUT/f'{spacing}m'
        if args.reuse:
            payload=json.loads((directory/'terrain_flow.json').read_text())
            if payload['parameters']!=scenario:raise ValueError('Cached scenario differs; rebuild required')
        else:payload=build(scenario,directory)
        manifest=json.loads((directory/'manifest.json').read_text())
        source=Path(manifest['source'])
        if source.stat().st_size!=manifest['source_size_bytes'] or source.stat().st_mtime_ns!=manifest['source_modified_ns']:
            raise ValueError('Source terrain changed; rebuild required')
        results.append(payload);manifests.append(manifest);audits.append(audit(payload,manifest));gauges.append(gauge(payload,manifest))
    if manifests[0]['grid']['transform']!=manifests[1]['grid']['transform']:raise ValueError('Native footprints do not match')
    frames=aggregate_nested(*results);final=frames[-1];diff=np.array(final['depth_difference_m']);a=np.array(results[0]['frames'][-1]['depth_m']);b=np.array(final['fine_depth_m'])
    wet=(a>.001)|(b>.001)
    summary={'final_depth_rmse_all_cells_m':float(np.sqrt(np.mean(diff**2))),
        'final_depth_rmse_wet_union_m':float(np.sqrt(np.mean(diff[wet]**2))) if wet.any() else 0.,
        'final_depth_max_absolute_difference_m':float(abs(diff).max()),
        'initial_volume_difference_m3':results[1]['budget']['initial_volume_m3']-results[0]['budget']['initial_volume_m3'],
        'final_volume_difference_m3':results[1]['budget']['final_volume_m3']-results[0]['budget']['final_volume_m3'],
        'wet_support_agreement_fraction':float(np.mean((a>.001)==(b>.001))),
        'conclusion':'Two-resolution sensitivity study; no spatial convergence or site validation claim.'}
    artifact={'version':1,'description':'Same-domain, matched-native-volume initialization and same 10 m inlet band. Original pilot preserved.',
        'coarse_file':'terrain_review_10m.json','fine_file':'terrain_review_5m.json',
        'summary':summary,'frames':frames,'coarse_nodes':results[0]['nodes'],
        'audits':{f'{s}m':a for s,a in zip((10,5),audits)},'gauges':{f'{s}m':g for s,g in zip((10,5),gauges)},
        'runs':{f'{s}m':{'cells':len(p['nodes']),'budget':p['budget'],'tracer_budget':p['tracer_budget'],'steps':p['steps']} for s,p in zip((10,5),results)},
        'limits':['Hypothetical forcing and unverified vertical metadata/bathymetry.','Uniform 5 m refinement does not enforce bank alignment or prove accuracy.',
            '32 storage quantiles on both meshes; spatial and storage-compression effects are combined.','Compare study 10 m against study 5 m; initialization and inlet differ from original pilot.'],
        'source_state':{k:manifests[0][k] for k in ('source','source_size_bytes','source_modified_ns')},
        'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    OUT.mkdir(parents=True,exist_ok=True);target=OUT/'review.json';temp=OUT/'review.json.tmp';temp.write_text(json.dumps(artifact,allow_nan=False,separators=(',',':')));temp.replace(target)
    (OUT/'summary.json').write_text(json.dumps({**summary,'audits':{s:{k:v for k,v in a.items() if k!='review_queue'} for s,a in artifact['audits'].items()},'gauges':artifact['gauges'],'runs':artifact['runs'],'limits':artifact['limits']},indent=2))
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
