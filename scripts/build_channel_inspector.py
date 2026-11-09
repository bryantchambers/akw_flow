#!/usr/bin/env python3
"""Prepare private, explicitly served inspection derivatives; source files stay blocked."""
import json,math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject,transform_bounds,Resampling
from rasterio.transform import from_bounds
from rasterio.windows import Window
from scipy import ndimage
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/private/channel_inspector'


def png(path,arr,valid,low,high,colors):
    t=np.clip((arr-low)/max(high-low,1e-9),0,1);t=np.nan_to_num(t)
    rgb=np.array(colors)[np.minimum((t*(len(colors)-1)).astype(int),len(colors)-1)]
    rgba=np.dstack([rgb,np.where(valid,255,0)]).astype('uint8')
    with rasterio.open(path,'w',driver='PNG',height=arr.shape[0],width=arr.shape[1],count=4,dtype='uint8') as dst:
        dst.write(rgba.transpose(2,0,1))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inventory=json.loads((ROOT/'assets/private/humanum_channels/mapped_water_features.json').read_text())
    pilot=json.loads((ROOT/'assets/private/humanum_channels/balanced_network.json').read_text())
    togeo=Transformer.from_crs(32648,4326,always_xy=True)
    features=[]
    for f in inventory['features']:
        if f['classification'] not in ('Canal','Water','Temple Moat','Pond','Pond Bank','Raised Linear'):continue
        features.append({'type':'Feature','geometry':{'type':'MultiLineString','coordinates':[[list(togeo.transform(*xy)) for xy in part] for part in f['parts_xy_m']]},'properties':{'id':f['id'],'kind':f['classification'],'fid':f['source_fid']}})
    data={'features':features,'terrains':{},'height_units':'metres provisionally assumed; vertical datum unconfirmed',
          'depth_status':'No measured water depth. Depression is local mean terrain minus elevation, clipped at zero; not bathymetry.',
          'imagery_attribution':'Source: Esri, Vantor, Earthstar Geographics, and the GIS User Community'}
    with rasterio.open(ROOT/'assets/private/humanum_danish_edna/dtm_angkor_center.tif') as src:
        row,col=pilot['provenance']['window_row_col'];h,w=pilot['provenance']['window_shape']
        for name,bounds,limit in [('overview',tuple(src.bounds),1024),('detail',rasterio.windows.bounds(Window(col,row,w,h),src.transform),768)]:
            b=transform_bounds(src.crs,3857,*bounds,densify_pts=21)
            dx,dy=b[2]-b[0],b[3]-b[1];width=limit;height=max(1,round(limit*dy/dx))
            if name=='detail':width=w;height=h
            tf=from_bounds(*b,width,height);z=np.full((height,width),np.nan,dtype='float32')
            reproject(rasterio.band(src,1),z,src_transform=src.transform,src_crs=src.crs,src_nodata=src.nodata,
                      dst_transform=tf,dst_crs=3857,dst_nodata=np.nan,resampling=Resampling.bilinear)
            valid=np.isfinite(z);low,high=np.percentile(z[valid],[2,98]);pixel=dx/width*math.cos(math.radians(13.4))
            size=max(3,2*int(math.ceil(5/pixel))+1);support=ndimage.minimum_filter(valid.astype('uint8'),size=size,mode='constant',cval=0).astype(bool)
            mean=ndimage.uniform_filter(np.where(valid,z,0),size=size,mode='constant',cval=0)
            depression=np.maximum(0,mean-z);depthmax=max(.1,float(np.percentile(depression[support],99))) if support.any() else .1
            png(OUT/(name+'_height.png'),z,valid,low,high,[[45,89,73],[102,142,94],[179,185,122],[204,169,112],[244,228,197]])
            png(OUT/(name+'_depression.png'),depression,support,0,depthmax,[[238,248,249],[165,216,230],[71,156,196],[25,90,160],[10,40,100]])
            ll=transform_bounds(3857,4326,*b)
            data['terrains'][name]={'bounds':[[ll[1],ll[0]],[ll[3],ll[2]]],'shape':[height,width],
                'display_pixel_m':pixel,'height_range':[float(low),float(high)],'depression_range':[0,depthmax],
                'relief_neighbourhood_m':size*pixel,'note':'Regional decimated view' if name=='overview' else 'Native-spacing pilot near a mapped canal; not the complete study area'}
    (OUT/'inspector.json').write_text(json.dumps(data,separators=(',',':'),allow_nan=False))
    print(json.dumps({'features':len(features),'terrains':data['terrains']}))
if __name__=='__main__':main()
