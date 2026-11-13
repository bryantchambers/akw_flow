#!/usr/bin/env python3
"""Check full native exports and provenance without treating budgets as site validation."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import rasterio
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/regional_native'


def tracer_tile_quality(h,c,maximum,dry_depth,area=.25):
    """Bounds apply to resolved wet cells; retain and quantify all dry-film mass."""
    wet=h>=max(float(dry_depth),1e-12)
    outside=(c<0)|(c>maximum+1e-5)
    if np.any(wet&outside):raise ValueError('Tracer outside initial concentration range in wet cells')
    dry_outside=(~wet)&outside
    excess=np.maximum(c-maximum,0.)+np.maximum(-c,0.)
    return {'dry_excursion_cells':int(dry_outside.sum()),
        'dry_excursion_water_volume_m3':float(h[dry_outside].sum()*area),
        'dry_excess_mass':float((h[~wet]*excess[~wet]).sum()*area),
        'wet_min':float(c[wet].min()) if wet.any() else None,
        'wet_max':float(c[wet].max()) if wet.any() else None}


def verify(output_directory=None):
    global OUT
    if output_directory is not None:OUT=Path(output_directory)
    m=json.loads((OUT/'manifest.json').read_text())
    if m['status']!='complete':raise ValueError('Regional export not complete')
    totals=np.zeros(2);maxdepth=0.;maxc=0.;minc=1.;validcount=0;maxvelocity=0.;highfr=0;highfr_deep=0;maxvelocity_deep=0.
    dry_count=0;dry_volume=0.;dry_excess=0.;wet_min=None;wet_max=None
    with rasterio.open(OUT/'terrain.tif') as terrain,rasterio.open(OUT/'final.tif') as result:
        if result.shape!=tuple(m['shape']) or result.res!=(.5,.5) or result.transform!=terrain.transform or result.count!=6:raise ValueError('Native output geometry mismatch')
        for _,window in result.block_windows(1):
            a=result.read(window=window).astype(float);valid=a[0]!=result.nodata
            if not np.isfinite(a[:,valid]).all() or np.any(a[0,valid]<0):raise ValueError('Nonfinite/negative exported state')
            if not valid.any():continue
            h=a[0,valid];c=a[3,valid]
            quality=tracer_tile_quality(h,c,m['parameters']['initial_unit_tracer_concentration'],m['parameters']['dry_depth_m'])
            dry_count+=quality['dry_excursion_cells'];dry_volume+=quality['dry_excursion_water_volume_m3'];dry_excess+=quality['dry_excess_mass']
            if quality['wet_min'] is not None:
                wet_min=quality['wet_min'] if wet_min is None else min(wet_min,quality['wet_min'])
                wet_max=quality['wet_max'] if wet_max is None else max(wet_max,quality['wet_max'])
            totals[0]+=h.sum()*.25;totals[1]+=(h*c).sum()*.25
            validcount+=int(valid.sum());maxdepth=max(maxdepth,float(h.max()));maxc=max(maxc,float(c.max()));minc=min(minc,float(c.min()))
            for flux,velocity in ((a[1,valid],a[4,valid]),(a[2,valid],a[5,valid])):
                maxvelocity=max(maxvelocity,float(abs(velocity).max()))
                active=(abs(velocity)>1e-6)&(abs(flux)>1e-10)
                hf=np.abs(flux[active]/velocity[active]);fr=abs(velocity[active])/np.sqrt(9.80665*np.maximum(hf,1e-12))
                highfr+=int(np.count_nonzero(fr>1))
                deep=hf>=.01
                highfr_deep+=int(np.count_nonzero((fr>1)&deep))
                if deep.any():maxvelocity_deep=max(maxvelocity_deep,float(abs(velocity[active][deep]).max()))
        rng=np.random.default_rng(20261110)
        source=Path(m['source'])
        if source.stat().st_size!=m['source_state']['size'] or source.stat().st_mtime_ns!=m['source_state']['mtime_ns']:raise ValueError('Source file state changed')
        with rasterio.open(source) as original:
            if original.transform!=terrain.transform or original.shape!=terrain.shape:raise ValueError('Source grid changed')
            for _ in range(16):
                r=int(rng.integers(0,original.height-64));c=int(rng.integers(0,original.width-64));w=rasterio.windows.Window(c,r,64,64)
                a=original.read(1,window=w,masked=True);b=terrain.read(1,window=w,masked=True)
                from hydraulics.fixed_geometry import apply_fixed_edits
                expected=a.filled(np.nan)
                apply_fixed_edits(expected,original.window_transform(w),m['parameters'].get('terrain_modifications',[]))
                if not np.array_equal(expected,b.filled(np.nan),equal_nan=True):raise ValueError('Scenario terrain differs from expected native source/edits')
    if validcount!=m['valid_cells']:raise ValueError('Native support count changed')
    for name,sha in m['code_sha256'].items():
        path=OUT/'code_snapshots'/(sha+'_'+name)
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Missing executed source snapshot')
    waterdiff=float(totals[0]-m['budget']['final_volume_m3']);massdiff=float(totals[1]-m['tracer_budget']['final_mass'])
    if abs(waterdiff)>max(.001,abs(totals[0])*1e-6) or abs(massdiff)>max(.001,abs(totals[1])*1e-6):raise ValueError('Excess float32 export discrepancy')
    for name,expected in m.get('initialization_inputs',{}).items():
        path=Path(name)
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected['sha256']:raise ValueError('Initialization source changed')
    if dry_excess>max(1e-9,abs(m['tracer_budget']['initial_mass'])*1e-12):raise ValueError('Dry-film excess tracer mass exceeds tolerance')
    relative_residual=abs(m['budget']['residual_m3'])/max(1.,m['budget']['initial_volume_m3']+m['budget']['rainfall_m3'])
    if relative_residual>1e-7:raise ValueError('Solver water conservation residual exceeds tolerance')
    report={'solver_water_relative_residual':relative_residual,'status':'passed','valid_native_cells':validcount,'solver_spacing_m':.5,'exported_water_volume_m3':float(totals[0]),'export_water_rounding_difference_m3':waterdiff,
        'exported_unit_tracer_mass':float(totals[1]),'export_tracer_rounding_difference':massdiff,'maximum_depth_m':maxdepth,
        'wet_unit_tracer_range':[wet_min,wet_max],'dry_film_excursion_cells':dry_count,'dry_film_excursion_volume_m3':dry_volume,'dry_film_excess_tracer_mass':dry_excess,'tracer_wet_depth_threshold_m':m['parameters']['dry_depth_m'],'unit_tracer_range':[minc,maxc],'maximum_exported_face_velocity_m_s':maxvelocity,'faces_with_froude_over_one':highfr,'faces_with_froude_over_one_and_face_depth_at_least_1cm':highfr_deep,'maximum_face_velocity_at_depth_at_least_1cm_m_s':maxvelocity_deep,
        'terrain_cache_sample_windows_matching_source':16,'code_snapshots_verified':True,
        'interpretation':'Implementation/export check only. Any high-Froude faces require review; local-inertial approximation is not validated for those regimes.'}
    (OUT/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2));return report

if __name__=='__main__':verify()
