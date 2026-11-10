"""Local review ledger and terrain profiles; no automatic archaeological acceptance."""
import copy,hashlib,json,math,threading
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import rasterio,shapefile
from shapely import make_valid
from shapely.geometry import shape,LineString,Point
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[1]
STORE=ROOT/'assets/private/channel_review/reviews.json'
LOCK=threading.RLock()
CACHE={}


def graph():
    p=ROOT/'assets/private/regional_network/feature_graph.json';stamp=p.stat().st_mtime_ns
    if CACHE.get('stamp')!=stamp:
        b=p.read_bytes();g=json.loads(b);CACHE.update(stamp=stamp,graph=g,hash=hashlib.sha256(b).hexdigest())
    return CACHE['graph']


def state():
    with LOCK:
        data=json.loads(STORE.read_text()) if STORE.exists() else {'revision':0,'links':{},'features':{},'history':[]}
        graph();data['current_graph_sha256']=CACHE['hash'];return data


def save(request):
    with LOCK:
        data=state()
        if type(request.get('expected_revision')) is not int or request['expected_revision']!=data['revision']:raise ValueError('Review revision changed; reload before saving')
        if request.get('graph_sha256')!=data['current_graph_sha256']:raise ValueError('Network changed; reload before saving')
        category=request['category'];identifier=request['id'];g=graph()
        if category not in ('links','features'):raise ValueError('Unknown review category')
        known={x['id'] for x in g['edges' if category=='links' else 'nodes']}
        if identifier not in known:raise ValueError('Unknown source ID')
        record={}
        for key in ('reviewer','notes','evidence','period'):
            value=request.get(key,'')
            if not isinstance(value,str) or len(value)>4000:raise ValueError('Invalid review text')
            record[key]=value
        if category=='links':
            decision=request.get('decision')
            if decision not in ('accepted','rejected','unresolved'):raise ValueError('Invalid review decision')
            if decision=='accepted' and (not record['evidence'].strip() or not record['notes'].strip()):raise ValueError('Accepted links require evidence and a rationale')
            record['decision']=decision
        else:
            guide=request.get('guide_coordinates')
            if guide is not None:
                if not isinstance(guide,list) or not 2<=len(guide)<=100:raise ValueError('Saved guide needs 2..100 vertices')
                for point in guide:
                    if not isinstance(point,list) or len(point)!=2 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in point) or abs(point[0])>180 or abs(point[1])>90:raise ValueError('Invalid saved guide')
                record['guide_coordinates']=guide
                record['guide_method']=str(request.get('guide_method','user_supplied'))[:200]
            for key in ('incision_m','manning_n'):
                value=request.get(key)
                if value is not None:
                    value=float(value)
                    if not math.isfinite(value) or value<0 or key=='manning_n' and value<=0:raise ValueError('Invalid '+key)
                record[key]=value
            for key,value_key in [('incision_range_m','incision_m'),('manning_range','manning_n')]:
                values=request.get(key)
                if values is not None:
                    if not isinstance(values,list) or len(values)!=2:raise ValueError('Range requires two values')
                    values=list(map(float,values))
                    if not all(math.isfinite(v) and (v>0 if key=='manning_range' else v>=0) for v in values) or values[0]>values[1]:raise ValueError('Invalid '+key)
                    value=record[value_key]
                    if value is not None and not values[0]<=value<=values[1]:raise ValueError('Selected value lies outside range')
                record[key]=values
        record['updated_utc']=datetime.now(timezone.utc).isoformat();record['graph_sha256']=data['current_graph_sha256']
        old=data[category].get(identifier);data['revision']+=1;data[category][identifier]=record
        data['history'].append({'revision':data['revision'],'category':category,'id':identifier,'before':old,'after':copy.deepcopy(record)})
        STORE.parent.mkdir(parents=True,exist_ok=True,mode=0o700);tmp=STORE.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');tmp.chmod(0o600);tmp.replace(STORE)
        return data


def geometry(identifier):
    if 'geometry' not in CACHE:
        geoms={}
        for name in ('angkor_center_features','angkor_center_lineartraces'):
            for r in shapefile.Reader(str(ROOT/'assets/private/humanum_danish_edna'/name)).iterShapeRecords():
                if name.endswith('features') and int(r.record['TYPE']) not in (1,2,4):continue
                if name.endswith('lineartraces') and int(r.record['TYPE'])!=2:continue
                geoms[name+':'+str(r.record['FID'])]=make_valid(shape(r.shape.__geo_interface__))
        CACHE['geometry']=geoms
    if identifier not in CACHE['geometry']:raise ValueError('Unknown water feature')
    return CACHE['geometry'][identifier]


def sampled_line(src,line,spacing=.5,max_samples=4096):
    n=min(max_samples,max(2,math.ceil(line.length/spacing)+1));stations=np.linspace(0,line.length,n)
    points=[line.interpolate(float(t)) for t in stations]
    values=[]
    for p,v in zip(points,src.sample([(p.x,p.y) for p in points],masked=True)):
        value=float(v[0]) if not np.ma.is_masked(v[0]) else float('nan')
        if not src.bounds.left<=p.x<src.bounds.right or not src.bounds.bottom<p.y<=src.bounds.top:value=float('nan')
        values.append(value if math.isfinite(value) and value!=src.nodata else None)
    return {'station_m':stations.tolist(),'elevation_m':values,'xy_m':[[p.x,p.y] for p in points],
            'sample_spacing_m':line.length/(n-1),'valid_fraction':sum(v is not None for v in values)/n}


def profile(request):
    identifier=request['feature_id'];g=geometry(identifier)
    toxy=Transformer.from_crs(4326,32648,always_xy=True);togeo=Transformer.from_crs(32648,4326,always_xy=True)
    custom=request.get('guide_coordinates')
    if custom:
        if not isinstance(custom,list) or not 2<=len(custom)<=100:raise ValueError('Guide requires 2..100 vertices')
        for c in custom:
            if not isinstance(c,list) or len(c)!=2 or not all(isinstance(v,(float,int)) and math.isfinite(v) for v in c) or abs(c[0])>180 or abs(c[1])>90:raise ValueError('Invalid guide coordinates')
        guide=LineString([toxy.transform(*p) for p in custom]);method='user_drawn_guide_not_surveyed_thalweg'
        if request.get('saved_guide_method') in ('straight_major_axis_proxy_not_centerline','user_drawn_guide_not_surveyed_thalweg'):method=request['saved_guide_method']
    elif g.geom_type in ('LineString','MultiLineString'):
        guide=g if g.geom_type=='LineString' else max(g.geoms,key=lambda x:x.length);method='source_water_line_longest_part'
    else:
        rectangle=list(g.minimum_rotated_rectangle.exterior.coords)
        a,b=max(zip(rectangle,rectangle[1:]),key=lambda ab:Point(ab[0]).distance(Point(ab[1])))
        delta=np.array(b)-a;delta=delta/np.linalg.norm(delta);center=g.centroid;length=math.hypot(g.bounds[2]-g.bounds[0],g.bounds[3]-g.bounds[1])*1.1
        axis=LineString([np.array([center.x,center.y])-length*delta,np.array([center.x,center.y])+length*delta]);cut=axis.intersection(g)
        lines=[cut] if cut.geom_type=='LineString' else [p for p in getattr(cut,'geoms',[]) if p.geom_type=='LineString']
        if not lines:raise ValueError('No automatic straight guide; draw a guide instead')
        guide=max(lines,key=lambda x:x.length);method='straight_major_axis_proxy_not_centerline'
    if not .5<=guide.length<=20000:raise ValueError('Guide length must be 0.5..20000 m')
    half=float(request.get('cross_section_half_width_m',100))
    if not math.isfinite(half) or not 5<=half<=500:raise ValueError('Cross-section half width must be 5..500 m')
    with rasterio.open(ROOT/'assets/private/humanum_danish_edna/dtm_angkor_center.tif') as src:
        corridor=LineString(guide.coords).buffer(half)
        if not corridor.intersects(__import__('shapely').geometry.box(*src.bounds)):raise ValueError('Guide outside terrain coverage')
        longitudinal=sampled_line(src,guide);cross=[]
        for fraction in (.25,.5,.75):
            t=guide.length*fraction;p=guide.interpolate(t);a=guide.interpolate(max(0,t-2));b=guide.interpolate(min(guide.length,t+2));dx,dy=b.x-a.x,b.y-a.y;norm=math.hypot(dx,dy)
            if not norm:continue
            normal=np.array([dy,-dx])/norm;center=np.array([p.x,p.y]);section=LineString([center-half*normal,center+half*normal]);record=sampled_line(src,section)
            record['station_m']=[s-half for s in record['station_m']];record['along_guide_station_m']=t
            cut=section.intersection(g);intervals=[]
            pieces=[cut] if cut.geom_type=='LineString' else list(getattr(cut,'geoms',[]))
            for piece in pieces:
                if piece.geom_type=='LineString' and piece.length:
                    stations=[section.project(Point(x))-half for x in piece.coords];intervals.append([min(stations),max(stations)])
            record['mapped_water_intervals_m']=intervals;record['mapped_water_span_m']=sum(b-a for a,b in intervals) if intervals else None;record['mapped_span_truncated']=any(a<=-half+.5 or b>=half-.5 for a,b in intervals);record['coordinates']=[list(togeo.transform(*c)) for c in section.coords];cross.append(record)
    longitudinal['inside_mapped_water']=[bool(g.covers(Point(xy))) for xy in longitudinal['xy_m']]
    longitudinal['coordinates']=[list(togeo.transform(*c)) for c in guide.coords]
    finite=[(s,z) for s,z in zip(longitudinal['station_m'],longitudinal['elevation_m']) if z is not None]
    slope=float(np.polyfit(*np.array(finite).T,1)[0]) if len(finite)>1 else None
    return {'feature_id':identifier,'guide_method':method,'length_m':guide.length,'longitudinal':longitudinal,'cross_sections':cross,'fitted_terrain_slope':slope,
            'interpretation':'Profile direction is arbitrary, not established downstream. Present terrain is not surveyed channel bed; mapped polygon intersections are not surveyed bank stations.',
            'elevation_metadata':{'horizontal_crs':'EPSG:32648','elevation_units':'metres provisionally assumed','vertical_datum':'unconfirmed','source_grid_spacing_m':.5}}


def workspace():
    g=graph();anchor='angkor_center_features:ANG_F_09042';adj={n['id']:[] for n in g['nodes']}
    for e in g['edges']:
        if e['gap_m']<=15:adj[e['from']].append(e);adj[e['to']].append(e)
    selected={anchor};todo=[anchor]
    while todo and len(selected)<25:
        a=todo.pop(0)
        for edge in sorted(adj.get(a,[]),key=lambda e:e['gap_m']):
            b=edge['to'] if edge['from']==a else edge['from']
            if b not in selected and len(selected)<25:selected.add(b);todo.append(b)
    queue=[e['id'] for e in g['edges'] if e['from'] in selected and e['to'] in selected and e['gap_m']<=15]
    return {'anchor_feature_id':anchor,'focus_feature_ids':sorted(selected),'review_link_ids':queue,'selection_note':'Bounded candidate review workspace, not an accepted connected subnetwork','applied_review_revision':g.get('review_revision',0),'default_incision_m':json.loads((ROOT/'configs/regional_network.json').read_text())['bed_incision_m'],'state':state()}


def screen(request):
    identifier=request['link_id'];edge=next((e for e in graph()['edges'] if e['id']==identifier),None)
    if edge is None:raise ValueError('Unknown connection')
    if 'barriers' not in CACHE:
        barriers=[]
        for r in shapefile.Reader(str(ROOT/'assets/private/humanum_danish_edna/angkor_center_features')).iterShapeRecords():
            if int(r.record['TYPE']) in (3,7):
                barriers.append({'id':'angkor_center_features:'+str(r.record['FID']),'kind':'Pond Bank' if int(r.record['TYPE'])==3 else 'Raised Linear','geometry':make_valid(shape(r.shape.__geo_interface__))})
        from shapely import STRtree
        CACHE['barriers']=barriers;CACHE['barrier_tree']=STRtree([b['geometry'] for b in barriers])
    line=LineString(edge['connection_xy_m']);indices=CACHE['barrier_tree'].query(line,predicate='intersects')
    barriers=[{k:v for k,v in CACHE['barriers'][int(i)].items() if k!='geometry'} for i in indices]
    with rasterio.open(ROOT/'assets/private/humanum_danish_edna/dtm_angkor_center.tif') as src:terrain=sampled_line(src,line,max_samples=512)
    elevations=[x for x in terrain['elevation_m'] if x is not None]
    warnings=[]
    if barriers:warnings.append('Segment intersects mapped bank/raised geometry; check barrier, gate or crossing evidence.')
    if terrain['valid_fraction']<1:warnings.append('Incomplete terrain coverage along the candidate connection.')
    if edge['gap_m']<1e-7:warnings.append('Geometric contact alone does not establish a functioning hydraulic opening.')
    else:warnings.append('Unmapped gap; no channel geometry is established across this segment.')
    return {'link_id':identifier,'gap_m':edge['gap_m'],'barrier_intersections':barriers,'terrain':terrain,
            'terrain_elevation_range_m':[min(elevations),max(elevations)] if elevations else None,
            'warnings':warnings,'status':'Automated geometric screen; no historical or hydraulic acceptance decision'}


def connection_enabled(edge,accepted,rejected,records):
    decision=records.get(edge['id'],{}).get('decision')
    if decision is not None:
        if decision not in ('accepted','rejected','unresolved'):raise ValueError('Invalid saved connection decision')
        return decision=='accepted'
    return edge['id'] not in rejected and (edge['gap_m']<1e-7 or edge['id'] in accepted)


def feature_incision(records,identifier,default):
    value=records.get(identifier,{}).get('incision_m')
    result=float(default if value is None else value)
    if not math.isfinite(result) or result<0:raise ValueError('Invalid saved bed incision')
    return result


def interface_manning(records,source_a,source_b,default):
    values=[records.get(key,{}).get('manning_n') for key in (source_a,source_b)]
    if all(value is None for value in values):return None
    values=[float(default if v is None else v) for v in values]
    if not all(math.isfinite(v) and v>0 for v in values):raise ValueError('Invalid saved Manning n')
    return max(values)
