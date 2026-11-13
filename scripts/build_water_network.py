#!/usr/bin/env python3
"""Native-resolution conduit reach graph, separate storage geometry and GIS exports."""
import json,sys,time,hashlib,sqlite3,struct
from pathlib import Path
import numpy as np,rasterio,shapefile
from rasterio.features import rasterize
from shapely.geometry import shape,mapping,LineString,Point
from shapely import make_valid,STRtree
from pyproj import Transformer
from skimage.morphology import skeletonize
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.reach_extraction import skeleton_paths,subdivide_path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/water_system';BASE=ROOT/'assets/private/humanum_danish_edna'


def parts(g):
    if g.geom_type=='Polygon':yield g
    elif hasattr(g,'geoms'):
        for p in g.geoms:yield from parts(p)


def feature(geometry,properties):return {'type':'Feature','geometry':geometry,'properties':properties}


def gpkg(path,layers):
    """Minimal OGC GeoPackage, EPSG:32648; standard GIS geometries, not JSON blobs."""
    if path.exists():path.unlink()
    db=sqlite3.connect(path)
    db.executescript('PRAGMA application_id=1196444487; PRAGMA user_version=10300; CREATE TABLE gpkg_spatial_ref_sys(srs_name TEXT NOT NULL,srs_id INTEGER PRIMARY KEY,organization TEXT NOT NULL,organization_coordsys_id INTEGER NOT NULL,definition TEXT NOT NULL,description TEXT); CREATE TABLE gpkg_contents(table_name TEXT PRIMARY KEY,data_type TEXT NOT NULL,identifier TEXT UNIQUE,description TEXT DEFAULT "",last_change DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,min_x DOUBLE,min_y DOUBLE,max_x DOUBLE,max_y DOUBLE,srs_id INTEGER); CREATE TABLE gpkg_geometry_columns(table_name TEXT,column_name TEXT,geometry_type_name TEXT,srs_id INTEGER,z INTEGER,m INTEGER,PRIMARY KEY(table_name,column_name));')
    from pyproj import CRS
    for sid,name,org,definition in [(-1,'Undefined Cartesian','NONE','undefined'),(0,'Undefined geographic','NONE','undefined'),(4326,'WGS84','EPSG',CRS.from_epsg(4326).to_wkt()),(32648,'WGS84 UTM48N','EPSG',CRS.from_epsg(32648).to_wkt())]:db.execute('INSERT INTO gpkg_spatial_ref_sys VALUES(?,?,?,?,?,?)',(name,sid,org,sid,definition,''))
    for name,kind,records in layers:
        keys=sorted({k for _,p in records for k in p})
        types={k:('REAL' if any(isinstance(p.get(k),(int,float)) and not isinstance(p.get(k),bool) for _,p in records) else 'TEXT') for k in keys}
        db.execute(f'CREATE TABLE "{name}" (fid INTEGER PRIMARY KEY AUTOINCREMENT,'+','.join(['geom BLOB',*[f'"{k}" {types[k]}' for k in keys]])+')')
        from datetime import datetime,timezone
        db.execute('INSERT INTO gpkg_contents(table_name,data_type,identifier,srs_id,last_change) VALUES(?,?,?,?,?)',(name,'features',name,32648,datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')))
        db.execute('INSERT INTO gpkg_geometry_columns VALUES(?,?,?,?,?,?)',(name,'geom',kind,32648,0,0))
        sql=f'INSERT INTO "{name}" ('+','.join(['geom',*['"'+k+'"' for k in keys]])+') VALUES('+','.join('?' for _ in range(len(keys)+1))+')'
        for g,p in records:
            blob=b'GP'+bytes([0,1])+struct.pack('<i',32648)+g.wkb
            vals=[json.dumps(p[k]) if isinstance(p.get(k),(list,dict)) else str(p[k]) if isinstance(p.get(k),bool) else p.get(k) for k in keys]
            db.execute(sql,[blob,*vals])
    db.commit();db.close()


def write_layers(layers):
    from shapely import transform
    togeo=Transformer.from_crs(32648,4326,always_xy=True)
    for name,(_,records) in layers.items():
        temporary=OUT/(name+'.tmp.geojson')
        temporary.write_text(json.dumps({'type':'FeatureCollection','features':[feature(mapping(transform(g,togeo.transform,interleaved=False)),p) for g,p in records]},allow_nan=False,separators=(',',':')))
        temporary.replace(OUT/(name+'.geojson'))
    temporary=OUT/'water_network.tmp.gpkg'
    gpkg(temporary,[(name,kind,records) for name,(kind,records) in layers.items()])
    temporary.replace(OUT/'water_network.gpkg')


def build():
    OUT.mkdir(parents=True,exist_ok=True);cfg=json.loads((ROOT/'configs/water_system.json').read_text());started=time.monotonic()
    with rasterio.open(BASE/'dtm_angkor_center.tif') as src:
        tf=src.transform;dims=src.shape;spacing=src.res[0]
        if spacing!=cfg['extraction_spacing_m'] or src.crs.to_epsg()!=32648:raise ValueError('Extraction must use native georeferenced source')
    conduits=[];bodies=[]
    for r in shapefile.Reader(str(BASE/'angkor_center_features')).iterShapeRecords():
        typ=int(r.record['TYPE']);fid=str(r.record['FID'])
        if typ not in (1,2,4):continue
        for i,g in enumerate(parts(make_valid(shape(r.shape.__geo_interface__)))):
            rec={'id':fid+f':part{i}','source_id':fid,'kind':{1:'Pond/reservoir',2:'Canal',4:'Moat'}[typ],'geom':g}
            if typ in (2,4):conduits.append(rec)
            if typ in (1,4):bodies.append(rec)
    for r in shapefile.Reader(str(BASE/'angkor_center_lineartraces')).iterShapeRecords():
        if int(r.record['TYPE'])==2:
            conduits.append({'id':str(r.record['FID'])+':trace','source_id':str(r.record['FID']),'kind':'Water trace','geom':make_valid(shape(r.shape.__geo_interface__).buffer(cfg['water_trace_width_m']/2))})
    print('Rasterizing conduits at 0.5 m',len(conduits),flush=True)
    mask=rasterize([(mapping(c['geom']),1) for c in conduits],out_shape=dims,transform=tf,dtype='uint8').astype(bool)
    with rasterio.open(BASE/'dtm_angkor_center.tif') as src:
        # Coverage validity only; terrain is not lowered to force connectivity.
        z=src.read(1);mask &= np.isfinite(z)&(z!=src.nodata)
    print('Skeletonizing native conduit mask',int(mask.sum()),flush=True);skel=np.load(OUT/'conduit_skeleton.npy') if (OUT/'conduit_skeleton.npy').exists() else skeletonize(mask)
    np.save(OUT/'conduit_skeleton.npy',skel)
    print('Tracing branches and loops',int(skel.sum()),flush=True);paths=skeleton_paths(skel,mask);del skel
    tree=STRtree([c['geom'] for c in conduits]);reaches=[];nodes={};short=[]
    def coordinate(p):return tf @ (p[1]+.5,p[0]+.5)
    def node(p):
        key=f'n:r{p[0]}c{p[1]}'
        if key not in nodes:nodes[key]={'id':key,'row':p[0],'col':p[1],'terrain_m':float(z[p]),'coordinates_utm':coordinate(p)}
        return key
    for path in paths:
        for part in subdivide_path(path,spacing,cfg['maximum_reach_length_m']):
            g=LineString([coordinate(p) for p in part]);length=g.length
            if length<cfg['minimum_reach_length_m']:
                short.append({'length_m':length,'start_rc':part[0],'end_rc':part[-1]})
                # Retain short junction connectors for topological integrity.
            sources=[conduits[int(i)] for i in tree.query(g,predicate='intersects')]
            simplified=g.simplify(cfg['geometry_simplification_m'],preserve_topology=True)
            rec={'id':f'reach:{len(reaches):06d}','from_node':node(part[0]),'to_node':node(part[-1]),'length_m':length,
                'source_ids':sorted({s['source_id'] for s in sources}),'kind':'Moat' if any(s['kind']=='Moat' for s in sources) else 'Channel',
                'terrain_start_m':float(z[part[0]]),'terrain_end_m':float(z[part[-1]]),
                'flow_status':'Geometry extracted; flow requires the rebuilt water-driven case','discharge_m3_s':None,'geom':simplified}
            reaches.append(rec)
    degree={k:0 for k in nodes}
    for r in reaches:degree[r['from_node']]+=1;degree[r['to_node']]+=1
    for k,n in nodes.items():n['degree']=degree[k];n['role']='terminal' if degree[k]==1 else 'junction' if degree[k]>2 else 'reach_station'
    # Report connected components without inventing edges across unmapped gaps.
    parent={k:k for k in nodes}
    def root(k):
        while parent[k]!=k:parent[k]=parent[parent[k]];k=parent[k]
        return k
    for reach in reaches:
        a,b=root(reach['from_node']),root(reach['to_node']);parent[b]=a
    components={};component_ids={}
    for key in sorted(nodes):
        r=root(key)
        if r not in component_ids:component_ids[r]=f'component:{len(component_ids):04d}'
        cid=component_ids[r];nodes[key]['component_id']=cid
        components.setdefault(cid,{'id':cid,'nodes':0,'reaches':0,'length_m':0.})['nodes']+=1
    for reach in reaches:
        cid=nodes[reach['from_node']]['component_id'];reach['component_id']=cid
        components[cid]['reaches']+=1;components[cid]['length_m']+=reach['length_m']
    print('Building explicit channel/storage contact ports',flush=True)
    ports=[];body_tree=STRtree([b['geom'] for b in bodies])
    reach_tree=STRtree([r['geom'] for r in reaches])
    for conduit in conduits:
        if conduit['kind']=='Moat':continue
        for index in body_tree.query(conduit['geom'],predicate='intersects'):
            body=bodies[int(index)]
            contact=conduit['geom'].intersection(body['geom'].boundary)
            pieces=list(contact.geoms) if hasattr(contact,'geoms') else [contact]
            for piece in pieces:
                if piece.is_empty:continue
                point=piece.interpolate(.5,normalized=True) if piece.geom_type in ('LineString','MultiLineString') else piece.representative_point()
                nearest=reach_tree.query_nearest(point,all_matches=False)
                reach=reaches[int(nearest[0])] if len(nearest) else None
                linked=reach is not None and conduit['source_id'] in reach['source_ids']
                row,col=rasterio.transform.rowcol(tf,point.x,point.y)
                elevation=float(z[row,col]) if 0<=row<z.shape[0] and 0<=col<z.shape[1] and np.isfinite(z[row,col]) else None
                ports.append({'id':f'port:{len(ports):05d}','storage_id':body['id'],'source_conduit_id':conduit['source_id'],
                    'reach_id':reach['id'] if linked else None,'reach_distance_m':float(point.distance(reach['geom'])) if linked else None,
                    'contact_length_m':float(piece.length),'terrain_sample_m':elevation,'crest_status':'Unverified: contact is geometry, not a surveyed spillway crest',
                    'geom':point})
    layers={'reaches':('LINESTRING',[(r['geom'],{k:v for k,v in r.items() if k!='geom'}) for r in reaches]),
        'nodes':('POINT',[(Point(n['coordinates_utm']),{k:v for k,v in n.items() if k!='coordinates_utm'}) for n in nodes.values()]),
        'waterbodies':('POLYGON',[(b['geom'],{k:v for k,v in b.items() if k!='geom'}) for b in bodies]),
        'ports':('POINT',[(p['geom'],{k:v for k,v in p.items() if k!='geom'}) for p in ports])}
    write_layers(layers)
    report={'source_resolution_m':spacing,'extraction_resolution_m':spacing,'reaches':len(reaches),'nodes':len(nodes),'components':len(components),'ports':len(ports),'component_summary':list(components.values()),'junctions':sum(n['degree']>2 for n in nodes.values()),'waterbodies':len(bodies),'conduit_pixels':int(mask.sum()),'short_connectors_retained':len(short),
        'source_files':{f.name:{'size':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns} for f in [BASE/'dtm_angkor_center.tif',*[BASE/(stem+ext) for stem in ('angkor_center_features','angkor_center_lineartraces') for ext in ('.shp','.shx','.dbf','.prj')]]},'wall_s':time.monotonic()-started,'configuration':cfg,'limits':['Mapped conduit skeletons are candidate centreline geometry, not surveyed thalwegs.','No proximity gap merging, reservoir centroid spokes, global sink filling or terrain burn-in.','Large storage polygons stay separate resolved waterbodies.','Topology follows native raster contact; true structures and hidden culverts require evidence.','No hydraulic flow is inferred from slope or drawn merely to fill a channel.']}
    (OUT/'network_manifest.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ('component_summary','configuration')}),flush=True)
    return report

if __name__=='__main__':build()
