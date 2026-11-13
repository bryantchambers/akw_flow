#!/usr/bin/env python3
"""Build private multiscale face selections, not another hydraulic simulation."""
import json,sys,time
from pathlib import Path
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.transform import Affine
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.face_index import strongest,reduce_records
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/regional_native'
FACTORS=(16,64,256,1024)


def build(directory=OUT):
    source=directory/'final.tif';state={'size':source.stat().st_size,'mtime_ns':source.stat().st_mtime_ns}
    meta=directory/'face_index.json'
    if meta.exists():
        previous=json.loads(meta.read_text())
        if previous.get('source_state')==state and all((directory/f'faces_{f}.tif').exists() for f in FACTORS):return previous
    started=time.monotonic();factor=FACTORS[0]
    with rasterio.open(source) as src:
        if src.res!=(.5,.5) or src.count<3:raise ValueError('Require native regional output')
        profile=dict(driver='GTiff',height=(src.height+factor-1)//factor,width=(src.width+factor-1)//factor,count=6,dtype='float32',crs=src.crs,transform=src.transform @ Affine.scale(factor),nodata=-9999,tiled=True,blockxsize=256,blockysize=256,compress='deflate',predictor=3)
        tmp=directory/f'faces_{factor}.tmp.tif'
        with rasterio.open(tmp,'w',**profile) as dst:
            for r in range(0,src.height,1024):
                for c in range(0,src.width,1024):
                    h=min(1024,src.height-r);w=min(1024,src.width-c)
                    q=src.read((2,3),window=Window(c,r,w,h));records=[]
                    for values in q:
                        values=np.where(values==src.nodata,np.nan,values)
                        v,rr,cc=strongest(values,factor);valid=rr>=0
                        records.extend([v,np.where(valid,rr+r,-1),np.where(valid,cc+c,-1)])
                    dst.write(np.asarray(records,np.float32),window=Window(c//factor,r//factor,(w+factor-1)//factor,(h+factor-1)//factor))
                print(f'Indexed native rows {r}..{min(src.height,r+1024)} / {src.height}',flush=True)
        tmp.replace(directory/f'faces_{factor}.tif')
    for previous,factor in zip(FACTORS,FACTORS[1:]):
        with rasterio.open(directory/f'faces_{previous}.tif') as src:
            a=src.read();ratio=factor//previous
            result=np.concatenate((reduce_records(a[:3],ratio),reduce_records(a[3:],ratio)))
            profile=src.profile.copy();profile.update(height=result.shape[1],width=result.shape[2],transform=src.transform @ Affine.scale(ratio))
            tmp=directory/f'faces_{factor}.tmp.tif'
            with rasterio.open(tmp,'w',**profile) as dst:dst.write(result)
            tmp.replace(directory/f'faces_{factor}.tif')
    result={'version':1,'source_state':state,'factors':FACTORS,'source_resolution_m':.5,'meaning':'Strongest signed native face per orientation per display bin; not total flow through a coarse face.','wall_s':time.monotonic()-started}
    temporary=meta.with_suffix('.tmp');temporary.write_text(json.dumps(result,indent=2));temporary.replace(meta)
    print(json.dumps(result),flush=True);return result

if __name__=='__main__':build()
