#!/usr/bin/env python3
"""Decode TOPSAR ts1260 and prepare independently selectable, provisional terrain previews.
Uses the published AIRSAR SCH coordinate definition via PROJ, not a corner-fitted UTM transform.
No registration shift, geoid correction, pit filling or hydrological simulation is applied.
"""
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pyproj
import rasterio
from affine import Affine
from rasterio.transform import from_bounds
from rasterio.warp import reproject, Resampling

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'assets/data/context'
OUT=DATA/'topsar'
NODATA=-9999.0
REFERENCE_URLS=[
 'https://airsar.jpl.nasa.gov/data/data_format.pdf',
 'https://airsar.jpl.nasa.gov/data/getting_started.html',
 'https://ntrs.nasa.gov/api/citations/19980045325/downloads/19980045325.pdf',
 'https://proj.org/en/stable/operations/projections/sch.html',
]


def field(blob,key):
    pattern=re.escape(key.encode())+rb'\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))'
    match=re.search(pattern,blob)
    if not match:raise ValueError('Missing header field: '+key)
    return float(match.group(1))


def transforms(lat,lon,heading):
    crs=pyproj.CRS.from_proj4(f'+proj=sch +plat_0={lat} +plon_0={lon} +phdg_0={heading} +ellps=WGS84 +units=m +type=crs')
    to_geo=pyproj.Transformer.from_crs(crs,4979,always_xy=True)
    from_geo=pyproj.Transformer.from_crs(4979,crs,always_xy=True)
    return crs,to_geo,from_geo


def save_scene(name,arr,transform,source_meta,base):
    h,w=arr.shape
    valid=np.isfinite(arr)&(arr!=NODATA)
    assert valid.any()
    bounds=rasterio.transform.array_bounds(h,w,transform)
    selected=[]
    for feature in base['waterways']['features']:
        coords=feature['geometry']['coordinates']
        if feature['geometry']['type']=='Polygon':coords=[p for ring in coords for p in ring]
        if any(bounds[0]<=lon<=bounds[2] and bounds[1]<=lat<=bounds[3] for lon,lat in coords):selected.append(feature)
    latitude=(bounds[1]+bounds[3])/2
    spacing=[math.radians(transform.a)*6371000*math.cos(math.radians(latitude)),math.radians(-transform.e)*6371000]
    scene={
      'generated_utc':datetime.now(timezone.utc).isoformat(),'terrain_id':name,
      'bbox_wsen':list(bounds),'grid_bbox_wsen':[bounds[0]+transform.a/2,bounds[1]-transform.e/2,bounds[2]-transform.a/2,bounds[3]+transform.e/2],'fence_description':'Terrain-preview extent; not an archaeological boundary or delineated catchment.',
      'width':w,'height':h,'elevation_m':[round(float(x),2) if ok else None for x,ok in zip(arr.ravel(),valid.ravel())],
      'screening_area_km2':None,
      'terrain':dict(source_meta,source='NASA/JPL TOPSAR C-band ts1260 (21 Sep 2000)',
        horizontal_crs='EPSG:4326',vertical_reference='WGS84 ellipsoidal metres, derived from AIRSAR SCH spherical heights; no EGM2008 correction',
        native_pixel_metres_approx=[5,5],display_pixel_metres_approx=spacing,
        aggregation='Nearest-neighbour geocoded sampling. Missing data remain holes; no Copernicus infill.',
        min_m=float(arr[valid].min()),max_m=float(arr[valid].max()),valid_fraction=float(valid.mean()),
        source_url='https://airsar.asf.alaska.edu/data/ts/ts1260/ts1260_c.demi2'),
      'screening':None,'waterways':{'type':'FeatureCollection','features':selected},'osm_snapshot':base['osm_snapshot'],
      'osm_attribution':base['osm_attribution'],'hotspots':[],'model_outputs':[],
      'landmarks':[x for x in base['landmarks'] if bounds[0]<=x['lon']<=bounds[2] and bounds[1]<=x['lat']<=bounds[3]]}
    destination=OUT/f'viewer_{name}.json'
    destination.write_text(json.dumps(scene,separators=(',',':'),allow_nan=False)+'\n')
    return {'path':str(destination.relative_to(ROOT/'assets')),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
       'bytes':destination.stat().st_size,'shape':[h,w],'bbox_wsen':list(bounds),'valid_fraction':float(valid.mean()),'display_spacing_m':spacing}


def main():
    rawpath=OUT/'ts1260_c.demi2'
    raw_sha=hashlib.sha256(rawpath.read_bytes()).hexdigest()
    acquired=json.loads((OUT/'acquisition.json').read_text())
    assert raw_sha==acquired['sha256'], 'Raw file differs from acquired source'
    with rawpath.open('rb') as stream:header=stream.read(18640)
    rows=int(field(header,'NUMBER OF LINES IN IMAGE ='))
    cols=int(field(header,'NUMBER OF SAMPLES PER RECORD ='))
    offset=int(field(header,'BYTE OFFSET OF FIRST DATA RECORD ='))
    assert rawpath.stat().st_size==offset+rows*cols*2
    s0=field(header,'ALONG-TRACK OFFSET S0 (M) =');c0=field(header,'CROSS-TRACK OFFSET C0 (M) =')
    dx=field(header,'X-DIRECTION POST SPACING (M) =');dy=field(header,'Y-DIRECTION POST SPACING (M) =')
    lat=field(header,'LATITUDE OF PEG POINT =');lon=field(header,'LONGITUDE OF PEG POINT =');heading=field(header,'HEADING AT PEG POINT (DEGREES) =')
    increment=field(header,'ELEVATION INCREMENT (M) =');offset_m=field(header,'ELEVATION OFFSET (M) =')
    crs,to_geo,from_geo=transforms(lat,lon,heading)
    geod=pyproj.Geod(ellps='WGS84');checks=[]
    for index,(r,c) in enumerate([(0,0),(0,cols-1),(rows-1,cols-1),(rows-1,0)],1):
        x,y,h=to_geo.transform(s0+r*dy,c0+c*dx,0)
        refx=field(header,f'LONGITUDE OF CORNER {index} =');refy=field(header,f'LATITUDE OF CORNER {index} =')
        distance=geod.inv(x,y,refx,refy)[2]
        assert distance<2,('Header-corner mismatch',index,distance)
        checks.append({'corner':index,'computed_lon':x,'computed_lat':y,'header_lon':refx,'header_lat':refy,'residual_m':distance})
    raw=np.memmap(rawpath,mode='r',dtype='>i2',offset=offset,shape=(rows,cols))
    # Conservative DISPLAY mask: repeated -16384 is a suspected fill/saturation code.
    # It is not claimed to be a fully validated product-wide NoData convention.
    suspected_fill_count=int(np.count_nonzero(raw==-16384))
    source_transform=Affine(0,dy,s0-dy/2,dx,0,c0-dx/2)
    decoded=OUT/'ts1260_sch_decoded.tif'
    reuse=False
    if decoded.exists():
        with rasterio.open(decoded) as cached:reuse=cached.tags().get('source_sha256')==raw_sha and cached.tags().get('decoder_version')=='1'
    if not reuse:
        with rasterio.open(decoded,'w',driver='GTiff',width=cols,height=rows,count=1,dtype='float32',crs=crs.to_wkt(),
            transform=source_transform,nodata=NODATA,tiled=True,compress='deflate',predictor=3) as dst:
            for row in range(0,rows,256):
                end=min(row+256,rows);dn=np.asarray(raw[row:end,:]);heights=dn.astype(np.float64)*increment+offset_m
                along=np.broadcast_to(s0+np.arange(row,end)[:,None]*dy,heights.shape)
                cross=np.broadcast_to(c0+np.arange(cols)[None,:]*dx,heights.shape)
                _,_,ellipsoidal=to_geo.transform(along,cross,heights)
                values=np.asarray(ellipsoidal,dtype=np.float32);values[dn==-16384]=NODATA
                dst.write(values,1,window=rasterio.windows.Window(0,row,cols,end-row))
            dst.update_tags(source_sha256=raw_sha,decoder_version='1',vertical_reference='WGS84 ellipsoidal heights from SCH spherical heights; no geoid correction',
                horizontal_method='AIRSAR SCH, peg/heading and sample offsets; source UTM label is not an implemented map projection',
                suspected_fill_policy='DN -16384 provisionally masked for display, raw retained unchanged; other quality flags unresolved')
    base=json.loads((DATA/'viewer_scene.json').read_text())
    common={'status':'Provisional metadata-georeferenced preview; not independently ground-validated',
      'acquisition_date':'2000-09-21','nominal_azimuth_resolution_m':10.8,
      'geolocation_method':'PROJ SCH using source peg/heading/S0/C0; header-corner agreement checked; no fitted registration shift.',
      'geolocation_check_max_residual_m':max(x['residual_m'] for x in checks),
      'quality_note':'5 m post spacing is not positional or vertical accuracy. Radar surface effects and outliers remain.',
      'mask_note':'Repeated DN -16384 provisionally excluded from display. NoData convention and product quality flags remain incompletely verified.'}
    centre=(103.86699,13.41247)
    # 2km local tile: ~5m display without forcing 28 million source posts into the browser.
    half_lon=1000/(111320*math.cos(math.radians(centre[1])));half_lat=1000/111320
    detail_bounds=[centre[0]-half_lon,centre[1]-half_lat,centre[0]+half_lon,centre[1]+half_lat]
    corners=[(field(header,f'LONGITUDE OF CORNER {i} ='),field(header,f'LATITUDE OF CORNER {i} =')) for i in range(1,5)]
    overview_bounds=[min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners)]
    products=[]
    with rasterio.open(decoded) as source:
        for name,bounds,spacing in [('topsar_detail',detail_bounds,5),('topsar_overview',overview_bounds,80)]:
            midlat=(bounds[1]+bounds[3])/2
            w=math.ceil((bounds[2]-bounds[0])*111320*math.cos(math.radians(midlat))/spacing)
            h=math.ceil((bounds[3]-bounds[1])*111320/spacing)
            transform=from_bounds(*bounds,w,h)
            target=np.full((h,w),NODATA,dtype=np.float32)
            reproject(source=rasterio.band(source,1),destination=target,src_transform=source.transform,src_crs=source.crs,
              src_nodata=NODATA,dst_transform=transform,dst_crs='EPSG:4326',dst_nodata=NODATA,
              resampling=Resampling.nearest,num_threads=2,warp_mem_limit=128)
            with rasterio.open(OUT/f'{name}_geocoded.tif','w',driver='GTiff',width=w,height=h,count=1,dtype='float32',
              crs='EPSG:4326',transform=transform,nodata=NODATA,compress='deflate',predictor=3,tiled=True) as dest:
                dest.write(target,1);dest.update_tags(vertical_reference='WGS84 ellipsoidal; not EGM2008',status=common['status'])
            products.append(save_scene(name,target,transform,common,base))
            print('Prepared',name,w,h,'valid',products[-1]['valid_fraction'],flush=True)
    # A coordinate transform round trip is a numerical check, not an external accuracy assessment.
    test_s=np.array([s0,s0+30000,s0+(rows-1)*dy]);test_c=np.array([c0,c0+5000,c0+(cols-1)*dx]);test_h=np.array([0,25,100])
    coords=to_geo.transform(test_s,test_c,test_h);back=from_geo.transform(*coords)
    roundtrip=max(float(np.max(np.abs(actual-expected))) for actual,expected in zip(back,(test_s,test_c,test_h)))
    assert roundtrip<1e-5
    provenance={'generated_utc':datetime.now(timezone.utc).isoformat(),'script':'scripts/build_topsar_scenes.py',
      'source_sha256':raw_sha,'source_file':str(rawpath.relative_to(ROOT)),
      'byte_order':'Big-endian signed 16-bit (SUN-compatible documented product)',
      'raw_shape':[rows,cols],'header_offset_bytes':offset,'sphere_height_formula':f'DN * {increment} + ({offset_m})',
      'horizontal_source_crs_wkt':crs.to_wkt(),'horizontal_source_crs':f'+proj=sch +plat_0={lat} +plon_0={lon} +phdg_0={heading} +ellps=WGS84 +units=m','horizontal_pixel_transform':list(source_transform)[:6],
      'height_conversion':'AIRSAR sphere -> WGS84 ellipsoidal height via PROJ SCH; no orthometric/geoid conversion or empirical offset applied.',
      'suspected_fill_dn':-16384,'suspected_fill_count':suspected_fill_count,'mask_policy_is_provisional':True,
      'corner_checks':checks,'roundtrip_max_error_m':roundtrip,'references':REFERENCE_URLS,'products':products,
      'limitations':['Header agreement is not an independent ground-control accuracy test.','No hydrological screening computed from this provisional TOPSAR preview.','No Copernicus heights or EGM2008 datum blended into TOPSAR.','Preview gaps remain holes; source quality/outliers are not comprehensively corrected.']}
    (OUT/'conversion_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(json.dumps({'corner_max_residual_m':max(x['residual_m'] for x in checks),'roundtrip_max_error_m':roundtrip,'products':products},indent=2))


if __name__=='__main__':main()
