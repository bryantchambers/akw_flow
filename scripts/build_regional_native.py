#!/usr/bin/env python3
"""Full native 0.5 m regional raster model. Private inputs and derivatives only."""
import argparse,json,time,sys,hashlib,os
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import rasterio,shapefile
from rasterio.features import rasterize
from rasterio.windows import Window
from pyproj import Transformer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.native_grid import simulate
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/private/regional_native'
SOURCE=ROOT/'assets/private/humanum_danish_edna/dtm_angkor_center.tif'


def write_json(path,value):
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,allow_nan=False,indent=2));tmp.replace(path)


def build(config):
    OUT.mkdir(parents=True,exist_ok=True)
    lock=OUT/'build.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise ValueError('Regional build lock exists; check the recorded PID before removing a stale lock')
    os.write(fd,str(os.getpid()).encode());os.close(fd)
    started=time.monotonic()
    def progress(stage,**kwargs):
        record={'stage':stage,'updated_utc':datetime.now(timezone.utc).isoformat(),'wall_s':time.monotonic()-started,'pid':os.getpid(),**kwargs}
        write_json(OUT/'progress.json',record);print(json.dumps(record),flush=True)
    try:
        if float(config['spacing_m'])!=.5:raise ValueError('This build preserves native 0.5 m solver spacing')
        if config.get('initialization','connected_mapped_water_minimum_plus_offset')!='connected_mapped_water_minimum_plus_offset':raise ValueError('Unknown regional initialization mode')
        progress('preparing',message='Reading full native terrain and mapped water inventory')
        with rasterio.open(SOURCE) as src:
            if src.crs.to_epsg()!=32648 or src.res!=(.5,.5):raise ValueError('Require native EPSG:32648, 0.5 m terrain')
            z=src.read(1);z[(z==src.nodata)|~np.isfinite(z)]=np.nan
            profile=src.profile.copy();bounds=list(src.bounds);tf=src.transform;crs=src.crs
        from hydraulics.fixed_geometry import apply_fixed_edits,apply_initial_levels
        edits=config.get('terrain_modifications',[])
        apply_fixed_edits(z,tf,edits)
        valid=np.isfinite(z);validcount=int(valid.sum())
        shapes=[]
        base=SOURCE.parent
        for rec in shapefile.Reader(str(base/'angkor_center_features')).iterShapeRecords():
            if rec.record['TYPE'] in (1,2,4):shapes.append((rec.shape.__geo_interface__,1))
        for rec in shapefile.Reader(str(base/'angkor_center_lineartraces')).iterShapeRecords():
            if rec.record['TYPE']==2:
                from shapely.geometry import shape,mapping
                shapes.append((mapping(shape(rec.shape.__geo_interface__).buffer(1.)),1))
        with rasterio.Env(GDAL_CACHEMAX=256*1024**2):water=rasterize(shapes,out_shape=z.shape,transform=tf,dtype='uint8')
        water[~valid]=0;wetcount=int(water.sum())
        depth=float(config['initial_mapped_water_depth_m']);concentration=float(config['initial_unit_tracer_concentration'])
        if not np.isfinite([depth,concentration]).all() or min(depth,concentration)<0:raise ValueError('Invalid initial water / tracer')
        from scipy.ndimage import label, minimum
        progress('preparing',message='Computing level low-water starts within connected mapped waterbodies')
        labels,components=label(water)
        minima=minimum(z,labels=labels,index=np.arange(1,components+1))
        levels=np.zeros(components+1,dtype=np.float64);levels[1:]=minima+depth
        initial=np.maximum(levels[labels]-z,0.)
        initial[water==0]=0;initial[~valid]=0
        wetcount=int(np.count_nonzero(initial>0))
        del labels,minima,levels
        apply_initial_levels(initial,z,water,tf,config.get('initial_water_levels',[]))
        wetcount=int(np.count_nonzero(initial>0))
        profile.update(driver='GTiff',count=1,dtype='float32',nodata=-9999.,tiled=True,blockxsize=512,blockysize=512,compress='deflate',predictor=3,zlevel=1,BIGTIFF='IF_SAFER',NUM_THREADS='4')
        profile.pop('interleave',None)
        # Reblock the striped source for efficient native-scale viewport reads.
        source_state={'size':SOURCE.stat().st_size,'mtime_ns':SOURCE.stat().st_mtime_ns}
        if edits:source_state['fixed_edits_sha256']=hashlib.sha256(json.dumps(edits,sort_keys=True).encode()).hexdigest()
        prior=OUT/'terrain_source_state.json'
        if not (OUT/'terrain.tif').exists() or not prior.exists() or json.loads(prior.read_text())!=source_state:
            progress('preparing',message='Writing native tiled terrain cache; no resampling',valid_cells=validcount)
            temporary=OUT/'terrain.tmp.tif'
            with rasterio.open(temporary,'w',**profile) as dst:
                for _,window in dst.block_windows(1):
                    r,c=int(window.row_off),int(window.col_off);h,w=int(window.height),int(window.width)
                    tile=z[r:r+h,c:c+w];dst.write(np.where(np.isfinite(tile),tile,-9999).astype('float32'),1,window=window)
            temporary.replace(OUT/'terrain.tif');write_json(prior,source_state)
        progress('preparing',message='Writing initial native mapped-water raster',valid_cells=validcount,initial_wet_cells=wetcount)
        temporary=OUT/'initial.tmp.tif'
        with rasterio.open(temporary,'w',**profile) as dst:
            dst.set_band_description(1,'hypothetical initial mapped-water depth, metres')
            for _,window in dst.block_windows(1):
                r,c=int(window.row_off),int(window.col_off);h,w=int(window.height),int(window.width)
                tile=initial[r:r+h,c:c+w].astype('float32')
                tile[~valid[r:r+h,c:c+w]]=-9999
                dst.write(tile,1,window=window)
        temporary.replace(OUT/'initial.tif')
        geo=Transformer.from_crs(crs,4326,always_xy=True)
        west,south=geo.transform(bounds[0],bounds[1]);east,north=geo.transform(bounds[2],bounds[3])
        manifest={'version':1,'model':'Continuous native-grid 2D local-inertial regional model','status':'prepared','parameters':config,
            'terrain_resolution_m':.5,'solver_spacing_m':.5,'shape':list(z.shape),'grid_cells':int(z.size),'valid_cells':validcount,
            'valid_area_km2':validcount*.25/1e6,'footprint_area_km2':z.size*.25/1e6,'initial_mapped_water_cells':wetcount,
            'bounds_lonlat':[[south,west],[north,east]],'bounds_projected_m':bounds,'transform':list(tf)[:6],
            'source':str(SOURCE),'source_state':source_state,'snapshots':[{'key':'initial','time_s':0}],
            'scope':'Entire supplied high-resolution survey footprint; not all Greater Angkor or automatically both Barays.',
            'assumptions':['Actual 0.5 m solver cells, no coarsening or storage quantiles.',
                'Continuous hydraulic raster; output/display tiling introduces no internal closed boundaries.',
                'Fixed terrain; no erosion, automatic channel burning, breach development or sediment. Evidence-labelled fixed edits, if configured, are scenario assumptions.',
                'Current DTM is not verified submerged bathymetry; vertical metres/datum/accuracy unverified.',
                'Low-water initialization: each mapped connected component starts at its minimum DTM elevation plus configured depth offset; higher pixels are dry. Not observed water levels.',
                'Closed survey perimeter and impermeable no-data cells; no regional inflow/outflow calibration.',
                'Local-inertial wide-flow approximation omits advective momentum and explicit structure equations.',
                'Conservative unit tracer starts in mapped water; rainfall has zero tracer. Not a pathogen model.',
                'No regional groundwater coupling. Infiltration, if configured, exports dissolved tracer.',
                'Native raster outputs are float32; solver state and conservation sums use float64.'],
            'friction_treatment':'fully implicit quadratic Manning friction','velocity_depth_timing':'Face velocity uses the predictor depth used for final-step discharge; depth raster is end-of-step.',
            'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'hydraulics/native_grid.py',ROOT/'hydraulics/fixed_geometry.py']}}
        snapshots=OUT/'code_snapshots';snapshots.mkdir(exist_ok=True)
        for source in [Path(__file__),ROOT/'hydraulics/native_grid.py',ROOT/'hydraulics/fixed_geometry.py']:
            (snapshots/(manifest['code_sha256'][source.name]+'_'+source.name)).write_bytes(source.read_bytes())
        write_json(OUT/'manifest.json',manifest)
        h=initial
        del initial
        progress('solving',message='Running continuous native-grid startup scenario',valid_cells=validcount)
        result=simulate(z,h,config,initial_concentration=water.astype(np.float32)*concentration,
            callback=lambda record:progress('solving',simulation=record,valid_cells=validcount))
        del h,water,valid
        progress('exporting',message='Writing native final depth, unit-width fluxes and tracer concentration',simulation=result['history'][-1])
        profile.update(count=6)
        temporary=OUT/'final.tmp.tif'
        with rasterio.open(temporary,'w',**profile) as dst:
            for band,name in enumerate(('depth_m','east_flux_m2_s','south_flux_m2_s','unit_tracer_concentration','east_face_velocity_m_s','south_face_velocity_m_s'),1):dst.set_band_description(band,name)
            for _,window in dst.block_windows(1):
                r,c=int(window.row_off),int(window.col_off);h,w=int(window.height),int(window.width);s=np.s_[r:r+h,c:c+w]
                validtile=np.isfinite(z[s]);hh=result['depth'][s]
                cc=np.divide(result['mass_per_area'][s],hh,out=np.zeros_like(hh),where=hh>1e-12)
                ux=np.zeros_like(hh);uy=np.zeros_like(hh)
                nc=min(w,z.shape[1]-c-1);nr=min(h,z.shape[0]-r-1)
                if nc>0:
                    sa=np.s_[r:r+h,c:c+nc];sb=np.s_[r:r+h,c+1:c+nc+1]
                    df=np.maximum(z[sa]+result['momentum_depth'][sa],z[sb]+result['momentum_depth'][sb])-np.maximum(z[sa],z[sb])
                    ux[:,:nc]=np.divide(result['qx_per_width'][sa],df,out=np.zeros_like(df),where=np.isfinite(df)&(df>1e-6))
                if nr>0:
                    sa=np.s_[r:r+nr,c:c+w];sb=np.s_[r+1:r+nr+1,c:c+w]
                    df=np.maximum(z[sa]+result['momentum_depth'][sa],z[sb]+result['momentum_depth'][sb])-np.maximum(z[sa],z[sb])
                    uy[:nr,:]=np.divide(result['qy_per_width'][sa],df,out=np.zeros_like(df),where=np.isfinite(df)&(df>1e-6))
                for band,tile in enumerate((hh,result['qx_per_width'][s],result['qy_per_width'][s],cc,ux,uy),1):
                    dst.write(np.where(validtile,tile,-9999).astype('float32'),band,window=window)
        temporary.replace(OUT/'final.tif')
        from hydraulics.regional_pyramids import build_pyramids
        progress('preparing_display',message='Building display-only pyramids; native grid retained')
        build_pyramids(OUT)
        manifest.update(status='complete',display_pyramid_factors=[2,4,8,16,32,64,128],snapshots=[{'key':'initial','time_s':0},{'key':'final','time_s':float(config['duration_s'])}],
            budget=result['budget'],tracer_budget=result['tracer_budget'],history=result['history'],steps=result['steps'],wall_s=time.monotonic()-started,
            maximum_depth_m=float(np.max(result['depth'])))
        write_json(OUT/'manifest.json',manifest);progress('complete',budget=result['budget'],tracer_budget=result['tracer_budget'],steps=result['steps'])
        return manifest
    except BaseException as exc:
        progress('failed',error=str(exc));raise
    finally:lock.unlink(missing_ok=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'configs/regional_native.json'));args=p.parse_args()
    build(json.loads(Path(args.config).read_text()))
