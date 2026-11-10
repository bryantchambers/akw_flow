#!/usr/bin/env python3
"""Regional source-feature graph followed by non-overlapping hydraulic cells.
Geometry-derived contact is a preliminary scenario, not verified historic flow.
"""
import argparse,collections,hashlib,json,math,sys
from pathlib import Path
import numpy as np
import shapefile,rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
from shapely import make_valid,STRtree,union_all,transform
from shapely.geometry import shape,box,mapping,LineString
from shapely.ops import nearest_points
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.model import simulate
from hydraulics.channel_review import connection_enabled,feature_incision,interface_manning
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/regional_network'

def polygons(g):
    if g.geom_type=='Polygon':yield g
    elif hasattr(g,'geoms'):
        for part in g.geoms:yield from polygons(part)

def components(ids,edges):
    adj={n:set() for n in ids}
    for e in edges:adj[e['from']].add(e['to']);adj[e['to']].add(e['from'])
    seen=set();sizes=[]
    for n in adj:
        if n in seen:continue
        todo=[n];seen.add(n);count=0
        while todo:
            a=todo.pop();count+=1
            for b in adj[a]-seen:seen.add(b);todo.append(b)
        sizes.append(count)
    return sorted(sizes,reverse=True)

def feature_contacts(features,gap):
    tree=STRtree([f['geom'] for f in features]);edges=[]
    for i,f in enumerate(features):
        for j in tree.query(f['geom'],predicate='dwithin',distance=gap):
            j=int(j)
            if j<=i:continue
            other=features[j];d=f['geom'].distance(other['geom']);a,b=nearest_points(f['geom'],other['geom'])
            edges.append({'id':f['id']+'__'+other['id'],'from':f['id'],'to':other['id'],
                          'gap_m':float(d),'status':'geometric_contact_unverified' if d<1e-7 else 'proposed_gap_requires_review',
                          'connection_xy_m':[[a.x,a.y],[b.x,b.y]]})
    return edges

def partition(features,spacing,min_area):
    """Priority ownership removes overlapping mapped water storage once only."""
    geoms=[f['geom'] for f in features];tree=STRtree(geoms);cells=[];excluded=[]
    for i,f in enumerate(features):
        earlier=[geoms[int(j)] for j in tree.query(f['geom'],predicate='intersects') if int(j)<i]
        owned=make_valid(f['geom'].difference(union_all(earlier))) if earlier else f['geom']
        for k,part in enumerate(polygons(owned)):
            pieces=[]
            if f['kind']=='Pond':pieces=[('storage'+str(k),part)]
            else:
                x0,y0,x1,y1=part.bounds
                for row in range(math.floor(y0/spacing),math.floor(y1/spacing)+1):
                    for col in range(math.floor(x0/spacing),math.floor(x1/spacing)+1):
                        cut=part.intersection(box(col*spacing,row*spacing,(col+1)*spacing,(row+1)*spacing))
                        for j,g in enumerate(polygons(cut)):pieces.append((f'{k}r{row}c{col}p{j}',g))
            for suffix,g in pieces:
                if g.area<min_area:
                    excluded.append({'source_id':f['id'],'area_m2':g.area,'reason':'below_minimum_cell_area'});continue
                cells.append({'id':f['id']+'|'+suffix,'source_id':f['id'],'kind':f['kind'],'geom':g})
    return cells,excluded

def shared_interfaces(cells):
    tree=STRtree([c['geom'] for c in cells]);edges=[]
    for i,c in enumerate(cells):
        for j in tree.query(c['geom'],predicate='intersects'):
            j=int(j)
            if j<=i:continue
            b=cells[j];width=c['geom'].boundary.intersection(b['geom'].boundary).length
            if width<1e-5:continue
            axy=c['geom'].centroid;bxy=b['geom'].centroid
            length=max(1.,axy.distance(bxy))
            edges.append({'id':c['id']+'__'+b['id'],'from':c['id'],'to':b['id'],'length_m':length,
                          'width_m':float(width),'connection_status':'shared_water_geometry_unverified'})
    return edges

def sample_bed(src,g):
    bounds=g.bounds;clip=g.intersection(box(*src.bounds))
    if clip.is_empty:return None
    window=from_bounds(*clip.bounds,src.transform).round_offsets().round_lengths()
    if window.width<1 or window.height<1:return None
    # Bound sampling work per storage polygon; approximately uniform spatial sampling.
    h=min(256,max(1,int(window.height)));w=min(256,max(1,int(window.width)))
    values=src.read(1,window=window,out_shape=(h,w),masked=True)
    tf=src.window_transform(window)*rasterio.Affine.scale(window.width/w,window.height/h)
    inside=geometry_mask([mapping(clip)],out_shape=(h,w),transform=tf,invert=True)
    valid=inside&~np.ma.getmaskarray(values)&np.isfinite(values.data)
    if not valid.any():return None
    coverage=float(valid.sum()/max(1,inside.sum()))
    return float(np.percentile(values.data[valid],20)),coverage

def build(config):
    gap=float(config['candidate_gap_m']);spacing=float(config['reach_cell_size_m']);minarea=float(config['minimum_cell_area_m2'])
    if not 0<=gap<=500 or not math.isfinite(gap) or not 25<=spacing<=500 or not minarea>0:raise ValueError('Invalid extraction settings')
    base=ROOT/'assets/private/humanum_danish_edna';features=[]
    for name in ['angkor_center_features','angkor_center_lineartraces']:
        for rec in shapefile.Reader(str(base/name)).iterShapeRecords():
            code=int(rec.record['TYPE'])
            if name.endswith('features') and code not in [1,2,4]:continue
            if name.endswith('lineartraces') and code!=2:continue
            g=make_valid(shape(rec.shape.__geo_interface__))
            kind={1:'Pond',2:'Canal',4:'Temple Moat'}[code] if name.endswith('features') else 'Water'
            if kind=='Water':g=g.buffer(float(config['water_trace_width_m'])/2)
            features.append({'id':name+':'+str(rec.record['FID']),'kind':kind,'geom':g})
    features.sort(key=lambda f:({'Water':0,'Canal':1,'Temple Moat':2,'Pond':3}[f['kind']],f['id']))
    print('Building feature contacts',len(features),flush=True)
    if len({f['id'] for f in features})!=len(features):raise ValueError('Duplicate source feature IDs')
    if any(not math.isfinite(float(t)) or not 0<=float(t)<=gap for t in config['sensitivity_gap_m']):raise ValueError('Sensitivity distances must lie within candidate_gap_m')
    contacts=feature_contacts(features,gap);rejected=set(config['rejected_links']);accepted=set(config['accepted_gap_links'])
    known={e['id'] for e in contacts}
    if (rejected|accepted)-known:raise ValueError('Review references unknown feature link')
    review_path=ROOT/'assets/private/channel_review/reviews.json'
    reviews=json.loads(review_path.read_text()) if review_path.exists() else {'revision':0,'links':{},'features':{}}
    if set(reviews['links'])-known:raise ValueError('Saved reviews reference missing feature links; reconcile before rebuilding')
    if set(reviews['features'])-{f['id'] for f in features}:raise ValueError('Saved reach assumptions reference missing features')
    for edge in contacts:
        decision=reviews['links'].get(edge['id'],{}).get('decision')
        edge['review_decision']=decision
        edge['scenario_enabled']=connection_enabled(edge,accepted,rejected,reviews['links'])
    sizes={str(t):components([f['id'] for f in features],[e for e in contacts if e['gap_m']<=t]) for t in config['sensitivity_gap_m']}
    with rasterio.open(base/'dtm_angkor_center.tif') as src:
        terrain_footprint=box(*src.bounds)
    clipped=[{**f,'geom':make_valid(f['geom'].intersection(terrain_footprint))} for f in features]
    print('Partitioning mapped water',flush=True);cells,excluded=partition(clipped,spacing,minarea)
    for f,c in zip(features,clipped):
        missing=f['geom'].area-c['geom'].area
        if missing>1e-5:excluded.append({'source_id':f['id'],'area_m2':missing,'reason':'outside_terrain_footprint'})
    if len(cells)>int(config['maximum_cells']):raise ValueError('Cell limit exceeded; increase reach cell size')
    with rasterio.open(base/'dtm_angkor_center.tif') as src:
        kept=[];nodes=[];togeo=Transformer.from_crs(32648,4326,always_xy=True)
        for cell in cells:
            bed=sample_bed(src,cell['geom'])
            if bed is None:
                excluded.append({'source_id':cell['source_id'],'cell_id':cell['id'],'area_m2':cell['geom'].area,'reason':'no_valid_terrain_sample'});continue
            bed,coverage=bed
            if coverage<float(config.get('minimum_terrain_sample_coverage',.8)):
                excluded.append({'source_id':cell['source_id'],'cell_id':cell['id'],'area_m2':cell['geom'].area,'reason':'insufficient_valid_terrain_samples'});continue
            kept.append(cell);g=cell['geom'];point=g.representative_point()
            nodes.append({'id':cell['id'],'source_id':cell['source_id'],'kind':cell['kind'],
                          'coordinates':list(togeo.transform(point.x,point.y)),
                          'geometry':mapping(transform(g,togeo.transform,interleaved=False)),'geometry_projected':mapping(g),
                          'terrain_sample_coverage_fraction':coverage,'bed_elevation_m':bed-feature_incision(reviews['features'],cell['source_id'],config['bed_incision_m']),'storage_area_m2':float(g.area)})
    cells=kept;print('Building cell interfaces',len(cells),flush=True);edges=shared_interfaces(cells)
    allowed_pairs={frozenset((e['from'],e['to'])) for e in contacts if e['scenario_enabled']}
    source_ids={c['id']:c['source_id'] for c in cells}
    edges=[e for e in edges if source_ids[e['from']]==source_ids[e['to']] or frozenset((source_ids[e['from']],source_ids[e['to']])) in allowed_pairs]
    byfeature=collections.defaultdict(list)
    for i,c in enumerate(cells):byfeature[c['source_id']].append(i)
    cell_by_id={c['id']:c for c in cells}
    for link in contacts:
        if not link['scenario_enabled'] or link['gap_m']<1e-7:continue
        aa=byfeature[link['from']];bb=byfeature[link['to']]
        if not aa or not bb:continue
        i,j=min(((a,b) for a in aa for b in bb),key=lambda ij:cells[ij[0]]['geom'].distance(cells[ij[1]]['geom']))
        a,b=cells[i],cells[j];length=max(1.,a['geom'].centroid.distance(b['geom'].centroid))
        edges.append({'id':'reviewed_gap:'+link['id'],'from':a['id'],'to':b['id'],'length_m':length,'width_m':float(config['water_trace_width_m']),'connection_status':'explicitly_accepted_gap_assumed_width'})
    for edge in edges:
        source_a=source_ids[edge['from']];source_b=source_ids[edge['to']]
        reviewed_n=interface_manning(reviews['features'],source_a,source_b,config['roughness']['manning_n'])
        if reviewed_n is not None:edge['reviewed_manning_n']=reviewed_n
    scenario={k:config[k] for k in ['duration_s','dt_max_s','output_interval_s','initial_depth_m','max_steps','roughness','groundwater']}
    scenario['edge_overrides']={e['id']:{'manning_n':e['reviewed_manning_n']} for e in edges if 'reviewed_manning_n' in e}
    if scenario['groundwater'].get('enabled'):raise ValueError('Regional groundwater footprint requires separate column parameterization; use pilot groundwater controls')
    network={'nodes':nodes,'edges':edges,'assumptions':['Feature graph covers supplied water inventory, not all historical Angkor or both barays.',
        'Mapped geometry contacts are provisional; gap links disabled until explicitly accepted.',
        'Ponds are lumped storage; canals and moats subdivided into geometry-clipped cells.',
        'Overlapping water polygons assigned once: Water trace, Canal, Moat, Pond priority.',
        'Present sampled terrain minus assumed incision is not surveyed bathymetry.',
        'No rainfall or inflow/outflow forcing in this closed short conservation scenario.',
        'Junctions, banks, gates and weirs need review; contact does not prove historical connection.']}
    print('Running short regional scenario',len(nodes),len(edges),flush=True)
    simulation=simulate(network,scenario)
    frames=[{'time_s':s['time_s'],'depth_m':[v/n['storage_area_m2'] for v,n in zip(s['volumes_m3'],nodes)],'flows_m3_s':s['flows_m3_s']} for s in simulation['samples']]
    feature_nodes=[{'id':f['id'],'kind':f['kind'],'coordinates':list(togeo.transform(f['geom'].representative_point().x,f['geom'].representative_point().y)),'area_m2':f['geom'].area} for f in features]
    for e in contacts:e['connection_coordinates']=[list(togeo.transform(*p)) for p in e['connection_xy_m']]
    graph={'review_revision':reviews['revision'],'nodes':feature_nodes,'edges':contacts,'sensitivity_component_sizes':sizes,'status':'Source-feature contact graph; proposals are not established channels'}
    summary={'review_revision':reviews['revision'],'feature_assumptions':reviews['features'],'source_counts':dict(collections.Counter(f['kind'] for f in features)),'feature_nodes':len(features),'feature_links':len(contacts),
        'enabled_feature_links':sum(e['scenario_enabled'] for e in contacts),'cell_nodes':len(nodes),'cell_links':len(edges),
        'excluded_area_m2':sum(x['area_m2'] for x in excluded),'represented_water_area_m2':sum(n['storage_area_m2'] for n in nodes),
        'cell_components':components([n['id'] for n in nodes],edges),'excluded':excluded,'budget':simulation['budget'],
        'parameters':config,'source_provenance':{'dtm':next(r for r in json.loads((base/'acquisition_manifest.json').read_text())['records'] if r['filename']=='dtm_angkor_center.tif'),
        'source_features':'Original FIDs retained; QGIS classes mapped by TYPE'},'assumptions':network['assumptions']}
    payload={'status':f"Regional preliminary hydraulic cells; uncalibrated closed {float(config['duration_s']):g}-second demonstration",'nodes':[{k:v for k,v in n.items() if k!='geometry_projected'} for n in nodes],'edges':edges,'frames':frames,'budget':simulation['budget'],'parameters':config,'assumptions':network['assumptions'],'summary':summary}
    OUT.mkdir(parents=True,exist_ok=True)
    for name,obj in [('feature_graph.json',graph),('cell_network.json',network),('simulation.json',simulation),('regional_flow.json',payload),('manifest.json',summary)]:
        p=OUT/(name+'.tmp');p.write_text(json.dumps(obj,allow_nan=False));p.replace(OUT/name)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['excluded','cell_components','source_provenance','assumptions','parameters']}))
    return payload
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',type=Path,default=ROOT/'configs/regional_network.json');args=p.parse_args();build(json.loads(args.config.read_text()))
