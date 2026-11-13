#!/usr/bin/env python3
"""Sequential Slurm GPU rainfall sweep with independent, immutable case outputs."""
import argparse,copy,hashlib,json,math,os,shutil,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hydraulics.rainfall_scenarios import BASE,ROOT,validate,atomic_json,reach_comparison,raster_comparison


def prepare(config_path,suite_id):
    import re
    if not re.fullmatch(r'[A-Za-z0-9_-]+',suite_id):raise ValueError('Invalid suite ID')
    config=json.loads(Path(config_path).read_text());duration,rates=validate(config)
    directory=BASE/'rainfall_suites'/suite_id
    if directory.exists():raise ValueError('Suite already exists; choose a new ID')
    directory.mkdir(parents=True)
    base=json.loads((ROOT/config['base_configuration']).read_text());base['backend']='gpu'
    cases=[]
    for rate in rates:
        key=('r'+format(rate,'g').replace('.','p'));name='hydraulics_gpu_'+suite_id+'_'+key
        p=copy.deepcopy(base);p.update(duration_s=duration,rainfall_mm_hr=rate,infiltration_mm_hr=config['infiltration_mm_hr'],max_steps=1000000,
            rainfall_suite_id=suite_id,rainfall_case_id=key,minimum_reach_discharge_m3_s=config['minimum_reach_discharge_m3_s'],
            scenario_label=f'Rainfall-only sensitivity: {rate:g} mm/h for {duration/60:g} min ({rate*duration/3600:g} mm); hypothetical initial storage, no infiltration or external inflows')
        (directory/(key+'.json')).write_text(json.dumps(p,indent=2))
        cases.append({'id':key,'directory':name,'rainfall_mm_hr':rate,'duration_s':duration,'total_rainfall_mm':rate*duration/3600,'status':'queued'})
    data={'id':suite_id,'status':'prepared','created_utc':datetime.now(timezone.utc).isoformat(),'configuration':config,'cases':cases,'current_case':None,'slurm_job_id':None}
    atomic_json(directory/'suite.json',data);atomic_json(BASE/'rainfall_suite.json',{'id':suite_id});return directory


def run(directory,resume=False):
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Rainfall cases require a Slurm GPU allocation')
    from hydraulics.native_grid import gpu_available
    if not gpu_available():raise RuntimeError('No allocated CUDA GPU available')
    from scripts.build_regional_native import build
    from scripts.verify_regional_native import verify
    from scripts.couple_water_network import build as couple
    directory=Path(directory).resolve();data=json.loads((directory/'suite.json').read_text());data.update(status='running',slurm_job_id=os.environ['SLURM_JOB_ID'])
    atomic_json(directory/'suite.json',data)
    frozen={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/name for name in ('hydraulics/native_grid.py','hydraulics/native_gpu.py','hydraulics/water_initialization.py','hydraulics/fixed_geometry.py','scripts/build_regional_native.py','scripts/couple_water_network.py','hydraulics/reach_flow.py','scripts/verify_regional_native.py')]}
    source_record=directory/'executed_source_states.json'
    if source_record.exists() and json.loads(source_record.read_text())!=frozen:raise RuntimeError('Numerical source changed; prepare a new suite to avoid mixing versions')
    atomic_json(source_record,frozen)
    control=BASE/data['cases'][0]['directory'];initial_volume=None
    try:
        for item in data['cases']:
            for path,digest in frozen.items():
                if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:raise RuntimeError('Numerical source changed during suite: '+path)
            model=BASE/item['directory']
            if item['status']=='complete':
                if not (model/'scenario_summary.json').exists():raise RuntimeError('Completed-case summary missing')
                if initial_volume is None:initial_volume=json.loads((model/'scenario_summary.json').read_text())['initial_volume_m3']
                continue
            data['current_case']=item['directory'];item['status']='running';atomic_json(directory/'suite.json',data)
            config=json.loads((directory/(item['id']+'.json')).read_text())
            if (model/'manifest.json').exists():
                if not resume:raise ValueError('Refuse to overwrite an existing case; use --resume to archive and restart the interrupted case')
                model.rename(model.with_name(model.name+'_partial_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')))
            model.mkdir(exist_ok=True)
            # Copy the tiled geometry cache. Case outputs never modify the reference.
            reference=BASE/'hydraulics_gpu'
            for name in ('terrain.tif','terrain_source_state.json'):
                if (reference/name).exists():shutil.copyfile(reference/name,model/name)
            manifest=build(config,model)
            if initial_volume is None:initial_volume=manifest['budget']['initial_volume_m3']
            if not math.isclose(initial_volume,manifest['budget']['initial_volume_m3'],rel_tol=1e-12,abs_tol=1e-8):raise AssertionError('Initial conditions differ between rainfall cases')
            expected=item['rainfall_mm_hr']/3.6e6*item['duration_s']*manifest['valid_cells']*.25
            if not math.isclose(expected,manifest['budget']['rainfall_m3'],rel_tol=1e-9,abs_tol=1e-6):raise AssertionError('Rainfall volume differs from intensity x duration x area')
            verification=verify(model)
            network=model/'network';coupling=couple(model,network)
            features=json.loads((network/'reaches.geojson').read_text())
            reference_features=json.loads((control/'network/reaches.geojson').read_text())['features']
            reach_stats=reach_comparison(features['features'],reference_features,data['configuration']['minimum_reach_discharge_m3_s'])
            atomic_json(network/'reaches.geojson',features)
            # Keep GeoPackage reach attributes identical to the inspected GeoJSON.
            import sqlite3
            db=sqlite3.connect(network/'water_network.gpkg')
            present={row[1] for row in db.execute('PRAGMA table_info(reaches)')}
            for name,typ in [('control_discharge_m3_s','REAL'),('delta_discharge_m3_s','REAL'),('rainfall_comparison','TEXT')]:
                if name not in present:db.execute('ALTER TABLE reaches ADD COLUMN '+name+' '+typ)
            for f in features['features']:
                p=f['properties'];db.execute('UPDATE reaches SET control_discharge_m3_s=?,delta_discharge_m3_s=?,rainfall_comparison=? WHERE id=?',(p['control_discharge_m3_s'],p['delta_discharge_m3_s'],p['rainfall_comparison'],p['id']))
            db.commit();db.close()
            raster_stats=raster_comparison(model,control,data['configuration'])
            summary={'status':'complete','model_directory':model.name,'suite_id':data['id'],'rainfall_mm_hr':item['rainfall_mm_hr'],'duration_s':item['duration_s'],'total_rainfall_mm':item['total_rainfall_mm'],
                'control_directory':control.name,'initial_volume_m3':initial_volume,'budget':manifest['budget'],'tracer_budget':manifest['tracer_budget'],'coupling':coupling['flow_status_counts'],
                'reach_comparison':reach_stats,'raster_comparison':raster_stats,'regime_review_faces':verification['faces_with_froude_over_one_and_face_depth_at_least_1cm'],
                'interpretation':data['configuration']['interpretation'],'limits':data['configuration']['limits']}
            atomic_json(model/'scenario_summary.json',summary)
            atomic_json(model/'acceptance.json',{'stage':'complete','model_directory':model.name,'implementation_checks':'passed','scientific_validation':'not validated'})
            item.update(status='complete',summary=summary,completed_utc=datetime.now(timezone.utc).isoformat());atomic_json(directory/'suite.json',data)
        data.update(status='complete',current_case=None,completed_utc=datetime.now(timezone.utc).isoformat());atomic_json(directory/'suite.json',data)
        import csv
        with (directory/'comparison.csv').open('w') as stream:
            levels=data['configuration']['comparison_depth_thresholds_m']
            writer=csv.writer(stream);writer.writerow(['case','rain_mm_hr','duration_s','rain_total_mm','rain_volume_m3','final_water_volume_m3',*['area_depth_ge_'+str(v)+'m_m2' for v in levels],'newly_directional_reaches','reversed_direction_reaches','newly_flowing_faces'])
            for case in data['cases']:
                s=case['summary'];writer.writerow([case['id'],case['rainfall_mm_hr'],case['duration_s'],case['total_rainfall_mm'],s['budget']['rainfall_m3'],s['budget']['final_volume_m3'],*[s['raster_comparison']['area_at_or_above_depth_m_m2'][str(v)] for v in levels],s['reach_comparison']['directional_class_changes']['newly_directional'],s['reach_comparison']['directional_class_changes']['reversed_direction'],s['raster_comparison']['newly_flowing_faces']])
    except BaseException as exc:
        data.update(status='failed',error=str(exc));atomic_json(directory/'suite.json',data);raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare');p.add_argument('--suite-id');p.add_argument('--run');p.add_argument('--resume',action='store_true');args=p.parse_args()
    if args.prepare:print(prepare(args.prepare,args.suite_id))
    elif args.run:run(args.run,args.resume)
    else:p.error('Use --prepare with --suite-id, or --run')
