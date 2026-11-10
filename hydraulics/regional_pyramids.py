"""Display-only raster pyramids. Native solver/output grid is never replaced."""
import rasterio
from rasterio.enums import Resampling

FACTORS=[2,4,8,16,32,64,128]

def build_pyramids(directory,callback=None):
    build_native_hillshade(directory)
    for name in ('initial.tif','terrain.tif','final.tif'):
        if callback:callback(name)
        with rasterio.Env(GDAL_NUM_THREADS='8',COMPRESS_OVERVIEW='DEFLATE',PREDICTOR_OVERVIEW='3',ZLEVEL_OVERVIEW='1',GDAL_TIFF_OVR_BLOCKSIZE='256'):
            with rasterio.open(directory/name,'r+',NUM_THREADS='8') as src:
                if src.overviews(1)!=FACTORS:src.build_overviews(FACTORS,Resampling.nearest)
                src.update_tags(ns='rio_overview',resampling='nearest',purpose='display only; native 0.5 m base grid retained')


def build_native_hillshade(directory):
    """Shade at native spacing before display resampling; one-pixel halo at tile edges."""
    import json
    import numpy as np
    from rasterio.windows import Window
    state=(directory/'terrain_source_state.json').read_text()
    cache=directory/'hillshade_source_state.json'
    if (directory/'hillshade.tif').exists() and cache.exists() and cache.read_text()==state:return
    with rasterio.open(directory/'terrain.tif') as src:
        profile=src.profile.copy();profile.update(count=1,dtype='uint8',nodata=0,predictor=2,NUM_THREADS='8')
        tmp=directory/'hillshade.tmp.tif'
        with rasterio.open(tmp,'w',**profile) as dst:
            for _,w in dst.block_windows(1):
                halo=Window(w.col_off-1,w.row_off-1,w.width+2,w.height+2)
                z=src.read(1,window=halo,boundless=True,masked=True).filled(np.nan)
                gy,gx=np.gradient(z,src.res[0]);light=(gx*.5+gy*.5+np.sqrt(.5))/np.sqrt(1+gx*gx+gy*gy)
                light=light[1:-1,1:-1];shade=(1+254*np.nan_to_num(np.clip(.2+.8*light,0,1))).astype('uint8');shade[~np.isfinite(light)]=0
                dst.write(shade,1,window=w)
            dst.build_overviews(FACTORS,Resampling.nearest)
            dst.update_tags(native_spacing_m='0.5',purpose='Hillshade calculated at native spacing before display resampling')
        tmp.replace(directory/'hillshade.tif');cache.write_text(state)
