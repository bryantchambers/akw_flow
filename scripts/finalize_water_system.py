#!/usr/bin/env python3
"""Verify completed native case, couple reaches, then publish a local acceptance record."""
import argparse,json,sys,time,traceback,os
from datetime import datetime,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/private/water_system';MODEL=OUT/'hydraulics'


def write(value):
    tmp=OUT/'acceptance.tmp.json';tmp.write_text(json.dumps(value,indent=2));tmp.replace(OUT/'acceptance.json');print(json.dumps(value),flush=True)


def finalize(wait=False,model_directory=None,activate=False):
    global MODEL
    if model_directory is not None:MODEL=Path(model_directory).resolve()
    lock=OUT/'finalize.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
    try:
        while True:
            m=json.loads((MODEL/'manifest.json').read_text()) if (MODEL/'manifest.json').exists() else {}
            p=json.loads((MODEL/'progress.json').read_text()) if (MODEL/'progress.json').exists() else {}
            if m.get('status')=='complete':break
            if p.get('stage')=='failed':raise RuntimeError('Native calculation failed: '+p.get('error','unknown'))
            if not wait:raise RuntimeError('Native calculation is still running; use --wait for automatic finalization')
            time.sleep(5)
        write({'stage':'verifying native output','updated_utc':datetime.now(timezone.utc).isoformat()})
        from scripts.verify_regional_native import verify
        native=verify(MODEL)
        from scripts.build_regional_view_comparison import build as compare
        compare(MODEL)
        from scripts.couple_water_network import build as couple
        coupling=couple(MODEL)
        from scripts.verify_water_network import verify as verify_network
        network=verify_network()
        from scripts.build_water_diagnosis import build as diagnosis
        report=diagnosis(MODEL)
        write({'model_directory':MODEL.name,'execution':m.get('execution'),'stage':'complete','implementation_and_gis_checks':'passed','scientific_validation':'not validated','hydraulic_regime_review_required':native['faces_with_froude_over_one_and_face_depth_at_least_1cm']>0,
            'native_cells':native['valid_native_cells'],'network_layers':network['gis_layers'],'coupling':coupling['flow_status_counts'],'report':str(report.relative_to(ROOT)),
            'updated_utc':datetime.now(timezone.utc).isoformat(),'limits':'Exploratory water-present relaxation, not the original pilot hydrograph, a calibrated flood/drought case, or a contaminant hotspot prediction.'})
        if activate:
            from hydraulics.water_case import activate as activate_case
            activate_case(MODEL)
    except BaseException as exc:
        write({'stage':'failed','error':str(exc),'updated_utc':datetime.now(timezone.utc).isoformat()});raise
    finally:lock.unlink(missing_ok=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wait',action='store_true');p.add_argument('--model-dir');p.add_argument('--activate',action='store_true');args=p.parse_args();finalize(args.wait,args.model_dir,args.activate)
