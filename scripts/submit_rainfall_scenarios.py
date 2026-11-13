#!/usr/bin/env python3
"""Prepare a reproducible rainfall experiment and submit one sequential GPU job."""
import argparse,json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.run_rainfall_scenarios import prepare
from hydraulics.rainfall_scenarios import atomic_json,BASE


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'configs/rainfall_scenarios.json'));p.add_argument('--suite-id');p.add_argument('--resume')
    args=p.parse_args();(ROOT/'.runtime/gpu').mkdir(parents=True,exist_ok=True)
    if args.resume:
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]+',args.resume):raise ValueError('Invalid suite ID')
        directory=BASE/'rainfall_suites'/args.resume
    else:directory=prepare(args.config,args.suite_id or 'rain_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))
    data=json.loads((directory/'suite.json').read_text())
    if data.get('slurm_job_id'):
        result=subprocess.run(['squeue','-h','-j',str(data['slurm_job_id']),'-o','%T'],capture_output=True,text=True,check=True)
        if result.stdout.strip():raise RuntimeError('Suite already has a live Slurm job')
    command=['sbatch','--parsable','--chdir',str(ROOT),str(ROOT/'scripts/slurm/rainfall_scenarios.sbatch'),str(directory)]
    if args.resume:command.append('--resume')
    result=subprocess.run(command,capture_output=True,text=True,check=True);data['slurm_job_id']=result.stdout.strip().split(';')[0];data['status']='submitted';atomic_json(directory/'suite.json',data)
    print(json.dumps({'suite_id':data['id'],'slurm_job_id':data['slurm_job_id'],'duration_s':data['configuration']['duration_s'],'cases':len(data['cases'])}))

if __name__=='__main__':main()
