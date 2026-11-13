"""Explicit, uncalibrated mapped-storage and conduit initial-water scenarios.

Storage bodies start level independently. Conduits outside storage start with a
locally estimated water surface, not constant depth on high banks or one elevation spanning the whole graph.
No terrain modification, boundary-stage forcing, or connectivity inference.
"""
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds,Window
import shapefile
from shapely.geometry import shape,mapping
from shapely import make_valid


def polygon_parts(g):
    if g.geom_type=='Polygon':yield g
    elif hasattr(g,'geoms'):
        for child in g.geoms:yield from polygon_parts(child)


def storage_depth(z,mask,percentile,offset):
    valid=mask & np.isfinite(z)
    if not valid.any():return np.zeros_like(z,dtype=float),None
    stage=float(np.percentile(z[valid],percentile))+offset
    return np.where(valid,np.maximum(stage-z.astype(float),0.),0.),stage


def initialize_mapped_water(z,tf,base,config):
    percentile=float(config['initial_stage_percentile']);offset=float(config['initial_stage_offset_m'])
    if not np.isfinite([percentile,offset]).all() or not 0<=percentile<=100 or offset<0:raise ValueError('Invalid mapped-water initial conditions')
    initial=np.zeros(z.shape,dtype=np.float64);covered=np.zeros(z.shape,bool);conduits=[];bodies=[]
    for r in shapefile.Reader(str(base/'angkor_center_features')).iterShapeRecords():
        typ=int(r.record['TYPE'])
        if typ not in (1,2,4):continue
        for i,g in enumerate(polygon_parts(make_valid(shape(r.shape.__geo_interface__)))):
            if typ==2:conduits.append((mapping(g),1));continue
            win=from_bounds(*g.bounds,tf)
            c0=max(0,int(np.floor(win.col_off)));r0=max(0,int(np.floor(win.row_off)))
            c1=min(z.shape[1],int(np.ceil(win.col_off+win.width)));r1=min(z.shape[0],int(np.ceil(win.row_off+win.height)))
            if c1<=c0 or r1<=r0:continue
            sl=np.s_[r0:r1,c0:c1];local_tf=rasterio.windows.transform(Window(c0,r0,c1-c0,r1-r0),tf)
            mask=rasterize([(mapping(g),1)],out_shape=(r1-r0,c1-c0),transform=local_tf,dtype='uint8').astype(bool)
            depth,stage=storage_depth(z[sl],mask,percentile,offset)
            initial[sl]=np.maximum(initial[sl],depth);covered[sl]|=mask
            bodies.append({'source_id':str(r.record['FID']),'part':i,'kind':'Moat' if typ==4 else 'Pond/reservoir','stage_m':stage,'wet_cells':int(np.count_nonzero(depth>0)),'volume_m3':float(depth.sum()*abs(tf.a*tf.e))})
    for r in shapefile.Reader(str(base/'angkor_center_lineartraces')).iterShapeRecords():
        if int(r.record['TYPE'])==2:conduits.append((mapping(shape(r.shape.__geo_interface__).buffer(float(config.get('water_trace_width_m',2))/2)),1))
    conduit_mask=rasterize(conduits,out_shape=z.shape,transform=tf,dtype='uint8').astype(bool)
    valid=conduit_mask & ~covered & np.isfinite(z)
    from pathlib import Path
    stage_path=Path(__file__).resolve().parents[1]/config['conduit_stage_file']
    with rasterio.open(stage_path) as src:
        if src.shape!=z.shape or src.transform!=tf or src.crs.to_epsg()!=32648:raise ValueError('Conduit stage raster does not match native terrain')
        stage=src.read(1)
        valid &= np.isfinite(stage)&(stage!=src.nodata)
        initial[valid]=np.maximum(stage[valid].astype(float)-z[valid].astype(float),0.)
    initial[~np.isfinite(z)]=0
    return initial,{'method':'Independent hydrostatic storage levels; local cross-section stages on conduits outside storage polygons',
        'storage_stage_percentile':percentile,'storage_stage_offset_m':offset,'conduit_stage_source':str(stage_path),
        'storage_bodies':bodies,'conduit_cells_outside_storage':int(valid.sum()),'initial_wet_cells':int(np.count_nonzero(initial>0)),
        'volume_m3':float(initial.sum()*abs(tf.a*tf.e)),
        'interpretation':'Hypothetical water-present relaxation experiment. Initial conduit surfaces need not be in equilibrium. Closed perimeter, no observed inflows, no claim of historical or steady flow. No terrain burning.'}
