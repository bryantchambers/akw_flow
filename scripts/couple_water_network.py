#!/usr/bin/env python3
"""Derive cross-section flux estimates from the rebuilt 2D water scenario."""
import json,sys,time
from pathlib import Path
import numpy as np,rasterio,shapefile
from shapely.geometry import shape,mapping
from shapely import transform,make_valid,union_all
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.reach_flow import section_geometry,integrate_section
from scripts.build_water_network import OUT,BASE,gpkg


def build(model_directory=None,output_directory=None):
    started=time.monotonic();model=Path(model_directory).resolve() if model_directory is not None else OUT/'hydraulics';m=json.loads((model/'manifest.json').read_text())
    if m['status']!='complete':raise ValueError('Water-driven native result is not complete')
    to_utm=Transformer.from_crs(4326,32648,always_xy=True);to_geo=Transformer.from_crs(32648,4326,always_xy=True)
    source={}
    for r in shapefile.Reader(str(BASE/'angkor_center_features')).iterShapeRecords():
        if int(r.record['TYPE']) in (2,4):source[str(r.record['FID'])]=make_valid(shape(r.shape.__geo_interface__))
    for r in shapefile.Reader(str(BASE/'angkor_center_lineartraces')).iterShapeRecords():
        if int(r.record['TYPE'])==2:source[str(r.record['FID'])]=make_valid(shape(r.shape.__geo_interface__).buffer(m['parameters'].get('water_trace_width_m',2)/2))
    destination=Path(output_directory).resolve() if output_directory is not None else OUT
    destination.mkdir(parents=True,exist_ok=True)
    data=json.loads((OUT/'reaches.geojson').read_text());sections=[];counts={}
    with rasterio.open(model/'final.tif') as result:
        for f in data['features']:
            p=f['properties'];line=transform(shape(f['geometry']),to_utm.transform,interleaved=False)
            polygon=union_all([source[sid] for sid in p['source_ids'] if sid in source]);samples=[]
            for fraction in (.2,.5,.8):
                section,tangent,capped=section_geometry(line,polygon,fraction)
                if section is None:samples.append({'valid':False,'reason':'no mapped cross-section'});continue
                sample={'valid':False,'reason':'mapped cross-section exceeds 2 km search'} if capped else integrate_section(result,section,tangent)
                sample['fraction']=fraction;samples.append(sample)
                sections.append((section,{'id':p['id']+f':s{fraction}','reach_id':p['id'],**sample}))
            usable=[v for v in samples if v.get('valid')];mid=samples[1]
            p.update(cross_sections=samples,flow_time_s=m['parameters']['duration_s'],discharge_m3_s=mid.get('discharge_m3_s'),flow_direction=0)
            if len(usable)<3:status='unresolved cross-section'
            elif any(v['wet_width_m']==0 for v in usable):status='dry or interrupted in this snapshot'
            else:
                signs=[np.sign(v['discharge_m3_s']) if abs(v['discharge_m3_s'])>m['parameters'].get('minimum_reach_discharge_m3_s',1e-5) else 0 for v in usable]
                if signs[0]!=0 and all(s==signs[0] for s in signs):status='same-direction flux at three sections';p['flow_direction']=int(signs[0])
                elif all(s==0 for s in signs):status='wet, negligible flux'
                else:status='transient or bidirectional exchange'
            p['flow_status']=status;counts[status]=counts.get(status,0)+1
            p['flow_interpretation']='Cross-section estimate from native 2D snapshot; not steady 1D discharge or verified connectivity.'
    tmp=destination/'reaches.tmp.geojson';tmp.write_text(json.dumps(data,separators=(',',':'),allow_nan=False));tmp.replace(destination/'reaches.geojson')
    layers=[]
    for name,kind in [('reaches','LINESTRING'),('nodes','POINT'),('waterbodies','POLYGON'),('ports','POINT')]:
        features=data['features'] if name=='reaches' else json.loads((OUT/(name+'.geojson')).read_text())['features']
        if name!='reaches':(destination/(name+'.geojson')).write_text(json.dumps({'type':'FeatureCollection','features':features},separators=(',',':')))
        layers.append((name,kind,[(transform(shape(f['geometry']),to_utm.transform,interleaved=False),f['properties']) for f in features]))
    layers.append(('cross_sections','LINESTRING',sections));tmp=destination/'water_network.tmp.gpkg';gpkg(tmp,layers);tmp.replace(destination/'water_network.gpkg')
    section_geo={'type':'FeatureCollection','features':[{'type':'Feature','geometry':mapping(transform(g,to_geo.transform,interleaved=False)),'properties':p} for g,p in sections]}
    (destination/'cross_sections.geojson').write_text(json.dumps(section_geo,separators=(',',':'),allow_nan=False))
    coupling={'model_directory':model.name,'status':'complete','time_s':m['parameters']['duration_s'],'flow_status_counts':counts,'sections':len(sections),'wall_s':time.monotonic()-started,'model_source_state':{f.name:{'size':f.stat().st_size,'mtime_ns':f.stat().st_mtime_ns} for f in (model/'manifest.json',model/'final.tif')},'limits':['No measured inflows or levels. Water-present relaxation is exploratory.','Three section checks do not prove hydraulic continuity between sections. Native 2D cell flows remain authoritative.','Positive reach flux is from_node toward to_node. Negative is reverse.','Flux across a geometric cross-section can include lateral/overbank exchange. It is not a calibrated 1D link.']}
    (destination/'coupling.json').write_text(json.dumps(coupling,indent=2));print(json.dumps(coupling,indent=2));return coupling

if __name__=='__main__':build()
