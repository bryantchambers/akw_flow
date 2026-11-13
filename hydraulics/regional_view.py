"""Allowlisted, windowed regional raster derivatives; original downloads stay private."""
import io,json,math
from functools import lru_cache
from contextvars import ContextVar
from pathlib import Path
import numpy as np
import rasterio
from rasterio.vrt import WarpedVRT
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from pyproj import Transformer
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
from .water_case import active_directory
OUT=active_directory() if (ROOT/'assets/private/water_system/hydraulics/manifest.json').exists() else ROOT/'assets/private/regional_native'
TOUTM=Transformer.from_crs(4326,32648,always_xy=True)
TOGEO=Transformer.from_crs(32648,4326,always_xy=True)


CASE_DIRECTORY=ContextVar('regional_case_directory',default=None)


def output_directory():
    return CASE_DIRECTORY.get() or OUT


def status():
    result={'case':output_directory().name}
    for key in ('manifest','progress','verification'):
        file=output_directory()/(key+'.json')
        result[key]=json.loads(file.read_text()) if file.exists() else None
    return result


def raster_path(layer,snapshot):
    if layer not in ('height','hillshade','depth','tracer'):raise ValueError('Unknown raster layer')
    if snapshot not in ('initial','final'):raise ValueError('Unknown snapshot')
    if snapshot=='final' and layer not in ('height','hillshade'):
        file=output_directory()/'manifest.json'
        if not file.exists() or json.loads(file.read_text()).get('status')!='complete':raise FileNotFoundError('Current final state is not available')
    if layer=='hillshade' and (output_directory()/'hillshade.tif').exists():return output_directory()/'hillshade.tif'
    return output_directory()/('terrain.tif' if layer in ('height','hillshade') else snapshot+'.tif')


def tile(layer,snapshot,zoom,x,y):
    if not 4<=zoom<=22 or not 0<=x<2**zoom or not 0<=y<2**zoom:raise ValueError('Invalid tile coordinates')
    path=raster_path(layer,snapshot)
    if not path.exists():raise FileNotFoundError('Snapshot unavailable')
    return _tile(layer,snapshot,zoom,x,y,path.stat().st_mtime_ns,str(output_directory()))


@lru_cache(maxsize=256)
def _tile(layer,snapshot,zoom,x,y,mtime,case_directory):
    path=raster_path(layer,snapshot)
    world=40075016.68557849;size=world/2**zoom
    tf=from_origin(-world/2+x*size,world/2-y*size,size/256,size/256)
    band=4 if layer=='tracer' and snapshot=='final' else 1
    cached_shade=layer=='hillshade' and path.name=='hillshade.tif'
    halo=1 if layer=='hillshade' and not cached_shade else 0
    sample_tf=tf @ rasterio.Affine.translation(-halo,-halo)
    with rasterio.open(path) as src, WarpedVRT(src,crs='EPSG:3857',transform=sample_tf,width=256+2*halo,height=256+2*halo,resampling=Resampling.nearest,nodata=-9999.,dtype='float32') as vrt:
        values=vrt.read(band,masked=True).filled(np.nan)
        wet_depth=vrt.read(1,masked=True).filled(np.nan) if layer=='tracer' else None
    if cached_shade:
        rgba=np.zeros((256,256,4),np.uint8);rgba[:,:,:3]=np.nan_to_num(values)[:,:,None].astype('uint8');rgba[:,:,3]=np.isfinite(values)*255
        buffer=io.BytesIO();Image.fromarray(rgba).save(buffer,format='PNG');return buffer.getvalue()
    if layer=='hillshade':
        latitude=math.atan(math.sinh((world/2-(y+.5)*size)/6378137))
        pixel=size/256*math.cos(latitude)
        gy,gx=np.gradient(values,pixel)
        illumination=(-gx*(-.5)+gy*.5+math.sqrt(.5))/np.sqrt(1+gx*gx+gy*gy)
        shade=np.nan_to_num(np.clip(.2+.8*illumination,0,1)[1:-1,1:-1]*255).astype('uint8')
        rgba=np.zeros((256,256,4),np.uint8);rgba[:,:,:3]=shade[:,:,None]
        rgba[:,:,3]=np.isfinite(illumination[1:-1,1:-1])*255
        buffer=io.BytesIO();Image.fromarray(rgba).save(buffer,format='PNG');return buffer.getvalue()
    valid=np.isfinite(values)
    if layer=='tracer':valid &= wet_depth>=.001
    rgba=np.zeros((256,256,4),np.uint8)
    if layer=='height':
        v=np.clip((values-15)/45,0,1)
        rgba[:,:,0]=np.nan_to_num(45+175*v).astype('uint8');rgba[:,:,1]=np.nan_to_num(100+105*v).astype('uint8');rgba[:,:,2]=np.nan_to_num(85+65*v).astype('uint8');rgba[:,:,3]=valid*255
    else:
        if layer=='tracer' and snapshot=='initial':
            cfg=json.loads((output_directory()/'manifest.json').read_text())['parameters']
            values=np.where(values>0,cfg['initial_unit_tracer_concentration'],0)
        if layer=='depth':v=np.sqrt(np.clip(values,0,1))
        else:v=np.clip(values,0,1)
        rgba[:,:,0]=np.nan_to_num(220-190*v if layer=='depth' else 245-125*v).astype('uint8')
        rgba[:,:,1]=np.nan_to_num(240-160*v if layer=='depth' else 235-205*v).astype('uint8')
        rgba[:,:,2]=np.nan_to_num(255-90*v if layer=='depth' else 250-70*v).astype('uint8')
        # Visibility threshold is display-only; exact values remain available at a clicked cell.
        rgba[:,:,3]=(valid & (values>=.001))*230
    buffer=io.BytesIO();Image.fromarray(rgba).save(buffer,format='PNG');return buffer.getvalue()


def point(lon,lat,snapshot):
    if not np.isfinite([lon,lat]).all() or not -180<=lon<=180 or not -85<=lat<=85:raise ValueError('Invalid longitude/latitude')
    if snapshot not in ('initial','final'):raise ValueError('Unknown snapshot')
    x,y=TOUTM.transform(lon,lat)
    with rasterio.open(output_directory()/'terrain.tif') as src:
        row,col=src.index(x,y)
        if not 0<=row<src.height or not 0<=col<src.width:raise ValueError('Outside supplied survey footprint')
        z=float(src.read(1,window=((row,row+1),(col,col+1)))[0,0]);center=src.xy(row,col)
    if z==-9999 or not math.isfinite(z):raise ValueError('No valid survey elevation at this location')
    with rasterio.open(raster_path('depth',snapshot)) as src:
        values=src.read(window=((row,row+1),(col,col+1)))[:,0,0].astype(float)
    if values[0]<0:raise ValueError('No model support here')
    c=values[3] if snapshot=='final' else json.loads((output_directory()/'manifest.json').read_text())['parameters']['initial_unit_tracer_concentration'] if values[0]>0 else 0
    return {'row':row,'col':col,'center_utm_m':list(center),'center_lonlat':list(TOGEO.transform(*center)),'solver_spacing_m':.5,
        'terrain_elevation_m':z,'water_depth_m':float(values[0]),'water_stage_m':z+float(values[0]),
        'east_face_discharge_m3_s':float(values[1]*.5) if snapshot=='final' else 0.,
        'south_face_discharge_m3_s':float(values[2]*.5) if snapshot=='final' else 0.,'unit_tracer_concentration':float(c)}


def vectors(bounds,snapshot):
    if snapshot!='final':return []
    if len(bounds)!=4 or not np.isfinite(bounds).all():raise ValueError('Invalid bounds')
    west,south,east,north=map(float,bounds)
    if not -180<=west<east<=180 or not -85<=south<north<=85:raise ValueError('Invalid geographic bounds')
    x0,y0=TOUTM.transform(west,south);x1,y1=TOUTM.transform(east,north)
    with rasterio.open(raster_path('depth','final')) as src:
        x0=max(x0,src.bounds.left);x1=min(x1,src.bounds.right);y0=max(y0,src.bounds.bottom);y1=min(y1,src.bounds.top)
        if x0>=x1 or y0>=y1:return []
        window=from_bounds(x0,y0,x1,y1,src.transform)
        vals=src.read((1,5,6),window=window,out_shape=(3,20,28),resampling=Resampling.nearest)
    out=[]
    for r in range(20):
        for c in range(28):
            h,ux,vs=map(float,vals[:,r,c])
            if h<.001 or not np.isfinite([h,ux,vs]).all():continue
            uy=-vs
            if math.hypot(ux,uy)<1e-5:continue
            x=x0+(c+.5)*(x1-x0)/28;y=y1-(r+.5)*(y1-y0)/20
            out.append({'lonlat':list(TOGEO.transform(x,y)),'east_m_s':ux,'north_m_s':uy,'depth_m':h})
    return out


def comparison():
    file=output_directory()/'view_comparison.json'
    if not file.exists():raise FileNotFoundError('Saved comparison unavailable')
    data=json.loads(file.read_text());current=True
    for name,expected in data['source_states'].items():
        path=ROOT/name
        if not path.exists() or {'size':path.stat().st_size,'mtime_ns':path.stat().st_mtime_ns}!=expected:current=False
    data['current']=current
    return data


def cells(bounds,snapshot='final'):
    """Actual native-cell polygons/values for a small GIS inspection window."""
    if snapshot not in ('initial','final'):raise ValueError('Unknown snapshot')
    if len(bounds)!=4 or not np.isfinite(bounds).all():raise ValueError('Invalid bounds')
    west,south,east,north=map(float,bounds)
    if not -180<=west<east<=180 or not -85<=south<north<=85:raise ValueError('Invalid bounds')
    xs,ys=TOUTM.transform([west,east,east,west],[south,south,north,north])
    with rasterio.open(raster_path('depth',snapshot)) as src,rasterio.open(output_directory()/'terrain.tif') as terrain:
        x0=max(min(xs),src.bounds.left);x1=min(max(xs),src.bounds.right);y0=max(min(ys),src.bounds.bottom);y1=min(max(ys),src.bounds.top)
        if x0>=x1 or y0>=y1:return {'type':'FeatureCollection','features':[]}
        w=from_bounds(x0,y0,x1,y1,src.transform)
        c0=max(0,math.floor(w.col_off));r0=max(0,math.floor(w.row_off));c1=min(src.width,math.ceil(w.col_off+w.width));r1=min(src.height,math.ceil(w.row_off+w.height))
        if (r1-r0)*(c1-c0)>10000:raise ValueError('Zoom to 0.5 m cells before exporting; maximum 10,000 cells per window')
        from rasterio.windows import Window
        window=Window(c0,r0,c1-c0,r1-r0);h=src.read(1,window=window);z=terrain.read(1,window=window)
        flux=src.read((2,3),window=window) if snapshot=='final' else np.zeros((2,*h.shape))
        features=[]
        for r,c in zip(*np.nonzero(h>=0)):
            row=r0+int(r);col=c0+int(c);ring=[list(TOGEO.transform(*(src.transform @ p))) for p in [(col,row),(col+1,row),(col+1,row+1),(col,row+1),(col,row)]]
            features.append({'type':'Feature','geometry':{'type':'Polygon','coordinates':[ring]},'properties':{'id':f'cell:r{row}c{col}','row':row,'col':col,'spacing_m':.5,'area_m2':.25,'depth_m':float(h[r,c]),'terrain_m':float(z[r,c]),'stage_m':float(z[r,c])+float(h[r,c]),'east_face_discharge_m3_s':float(flux[0,r,c])*.5,'south_face_discharge_m3_s':float(flux[1,r,c])*.5,'snapshot':snapshot}})
        return {'type':'FeatureCollection','features':features}
