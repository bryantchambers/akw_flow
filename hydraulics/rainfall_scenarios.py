"""Rainfall experiment definitions and comparisons; no seasonal-frequency claims."""
import json,math,re
from pathlib import Path
import numpy as np,rasterio
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'assets/private/water_system'


def validate(config):
    duration=float(config['duration_s']);rates=[float(v) for v in config['rainfall_intensities_mm_hr']]
    if not math.isfinite(duration) or duration<=0 or duration>86400:raise ValueError('Duration must be positive and at most one day')
    if not rates or any(not math.isfinite(v) or v<0 or v>300 for v in rates) or len(set(rates))!=len(rates) or rates!=sorted(rates) or rates[0]!=0:raise ValueError('Use unique increasing rates starting with the zero-rain control, up to 300 mm/h')
    if not math.isfinite(float(config['infiltration_mm_hr'])) or config['infiltration_mm_hr']<0:raise ValueError('Invalid infiltration')
    for key in ('minimum_face_discharge_m3_s','minimum_face_depth_m','minimum_reach_discharge_m3_s'):
        if not math.isfinite(float(config[key])) or config[key]<=0:raise ValueError('Positive flow thresholds required')
    if any(not math.isfinite(v) or v<=0 for v in config['comparison_depth_thresholds_m']):raise ValueError('Invalid depth thresholds')
    return duration,rates


def atomic_json(path,data):
    tmp=path.with_suffix('.tmp.json');tmp.write_text(json.dumps(data,indent=2,allow_nan=False));tmp.replace(path)


def reach_comparison(features,control,threshold=1e-5):
    previous={f['properties']['id']:f['properties'] for f in control}
    counts={'newly_directional':0,'lost_directional':0,'reversed_direction':0,'unresolved':0};changes=[]
    if len(previous)!=len(control):raise ValueError('Duplicate control reach IDs')
    for f in features:
        p=f['properties'];old=previous.get(p['id'])
        if old is None:raise ValueError('Unmatched reach ID in comparison')
        q=p.get('discharge_m3_s');before=old.get('discharge_m3_s');direction=p.get('flow_direction',0) if q is not None and abs(q)>threshold else 0;prior=old.get('flow_direction',0) if before is not None and abs(before)>threshold else 0
        if q is None or before is None:label='unresolved';counts['unresolved']+=1
        elif direction and not prior:label='newly directional';counts['newly_directional']+=1
        elif prior and not direction:label='lost consistent direction';counts['lost_directional']+=1
        elif direction and prior and direction!=prior:label='reversed direction';counts['reversed_direction']+=1
        else:label='same direction class'
        p.update(control_discharge_m3_s=before,delta_discharge_m3_s=None if q is None or before is None else q-before,rainfall_comparison=label)
        if q is not None and before is not None:changes.append({'reach_id':p['id'],'q_m3_s':q,'control_q_m3_s':before,'delta_q_m3_s':q-before,'class':label})
    return {'directional_class_changes':counts,'largest_midsection_discharge_changes':sorted(changes,key=lambda r:abs(r['delta_q_m3_s']),reverse=True)[:30],
        'interpretation':'Direction classes use the three-section consistency check. New directionality is a candidate connection change, not proof of a new surveyed channel or spillway.'}


def raster_comparison(model,control,config):
    thresholds=config['comparison_depth_thresholds_m'];result={'area_at_or_above_depth_m_m2':{str(v):0. for v in thresholds},'maximum_depth_m':0.,'newly_flowing_faces':0,'reversed_faces':0,'qualifying_faces':0,'maximum_depth_increase_m':0.,'maximum_depth_decrease_m':0.}
    qmin=config['minimum_face_discharge_m3_s'];hmin=config['minimum_face_depth_m'];delta_sum=0.;delta_sq=0.;valid_count=0
    with rasterio.open(model/'final.tif') as src,rasterio.open(control/'final.tif') as ref:
        if src.shape!=ref.shape or src.transform!=ref.transform or src.crs!=ref.crs:raise ValueError('Scenario and control grids differ')
        area=abs(src.transform.a*src.transform.e);dx=src.res[0]
        for _,w in src.block_windows(1):
            a=src.read((1,2,3,5,6),window=w).astype(float);b=ref.read((1,2,3,5,6),window=w).astype(float);valid=(a[0]>=0)&(b[0]>=0)
            if not valid.any():continue
            delta=a[0,valid]-b[0,valid];delta_sum+=float(delta.sum());delta_sq+=float(np.sum(delta*delta));valid_count+=int(valid.sum())
            result['maximum_depth_m']=max(result['maximum_depth_m'],float(a[0,valid].max()))
            result['maximum_depth_increase_m']=max(result['maximum_depth_increase_m'],float(delta.max()));result['maximum_depth_decrease_m']=min(result['maximum_depth_decrease_m'],float(delta.min()))
            for h in thresholds:result['area_at_or_above_depth_m_m2'][str(h)]+=float(np.count_nonzero(valid&(a[0]>=h))*area)
            for qb,vb in ((1,3),(2,4)):
                fa=np.divide(abs(a[qb]),abs(a[vb]),out=np.zeros_like(a[0]),where=abs(a[vb])>1e-12)
                fb=np.divide(abs(b[qb]),abs(b[vb]),out=np.zeros_like(b[0]),where=abs(b[vb])>1e-12)
                aa=valid&(abs(a[qb])*dx>qmin)&(fa>=hmin);bb=valid&(abs(b[qb])*dx>qmin)&(fb>=hmin)
                result['qualifying_faces']+=int(aa.sum());result['newly_flowing_faces']+=int((aa&~bb).sum());result['reversed_faces']+=int((aa&bb&(a[qb]*b[qb]<0)).sum())
    result.update(mean_depth_difference_m=delta_sum/max(valid_count,1),rms_depth_difference_m=math.sqrt(delta_sq/max(valid_count,1)),minimum_face_discharge_m3_s=qmin,minimum_predictor_face_depth_m=hmin)
    return result


def status():
    pointer=BASE/'rainfall_suite.json'
    if not pointer.exists():return {'suite':None}
    ref=json.loads(pointer.read_text());suite_path=BASE/'rainfall_suites'/ref['id']/'suite.json'
    if not re.fullmatch(r'[A-Za-z0-9_-]+',ref['id']):raise ValueError('Invalid suite identifier')
    data=json.loads(suite_path.read_text())
    if data.get('current_case'):
        p=BASE/data['current_case']/'progress.json'
        if p.exists():data['current_progress']=json.loads(p.read_text())
    return {'suite':data}
