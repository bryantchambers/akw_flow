#!/usr/bin/env python3
"""Allocated-GPU acceptance, matched CPU/GPU benchmarks and full-grid short test."""
import argparse,json,os,platform,sys,time,unittest,hashlib
from pathlib import Path
import numpy as np,rasterio
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hydraulics.native_grid import simulate,gpu_available


def write(path,data):
    temp=path.with_suffix('.tmp.json');temp.write_text(json.dumps(data,indent=2,allow_nan=False));temp.replace(path)


def metrics(a,b):
    fields={}
    for k in ('depth','mass_per_area','qx_per_width','qy_per_width'):
        delta=b[k]-a[k]
        fields[k]={'max_absolute':float(abs(delta).max()),'rmse':float(np.sqrt(np.mean(delta*delta)))}
        if not np.allclose(b[k],a[k],atol=1e-8,rtol=1e-7):raise AssertionError('CPU/GPU divergence: '+k+' '+str(fields[k]))
    if a['steps']!=b['steps']:raise AssertionError('Different timestep count')
    return fields


def run_case(name,z,h,c,config):
    records={};results={}
    # Warm compilation separately; timing records identify setup and output copies.
    for backend in ('cpu','gpu'):
        print('BENCHMARK',name,backend,z.shape,flush=True)
        start=time.monotonic();r=simulate(z,h,{**config,'backend':backend},c)
        records[backend]={'wall_s':time.monotonic()-start,'execution':r['execution'],'steps':r['steps'],'budget':r['budget'],'tracer_budget':r['tracer_budget']};results[backend]=r
    fields=metrics(results['cpu'],results['gpu'])
    record={'name':name,'shape':list(z.shape),'cells':z.size,'duration_s':config['duration_s'],'cpu_threads':config['threads'],'runs':records,'comparison':fields,
        'solver_speedup':records['cpu']['execution']['solver_s']/records['gpu']['execution']['solver_s'],
        'end_to_end_speedup':records['cpu']['wall_s']/records['gpu']['wall_s']}
    print(json.dumps(record),flush=True);return record


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();output=args.output
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Run this test through Slurm')
    if not gpu_available():raise RuntimeError('A real allocated GPU is required; no simulator or CPU fallback')
    from numba import cuda
    if os.environ.get('NUMBA_ENABLE_CUDASIM')=='1':raise RuntimeError('CUDA simulator is not a performance test')
    report={'status':'running','host':platform.node(),'slurm_job_id':os.environ['SLURM_JOB_ID'],'cuda_visible_devices':os.environ.get('CUDA_VISIBLE_DEVICES'),'python':sys.version,'prefix':sys.prefix,'benchmarks':[],
        'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ('hydraulics/native_grid.py','hydraulics/native_gpu.py','scripts/benchmark_gpu.py')}}
    write(output,report)
    suite=unittest.TestLoader().loadTestsFromName('tests.test_native_gpu')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:raise AssertionError('GPU acceptance failed or skipped')
    report['acceptance_tests']=result.testsRun;write(output,report)
    cfg=dict(spacing_m=.5,duration_s=1,dt_max_s=.02,threads=min(40,int(os.environ.get('SLURM_CPUS_PER_TASK','1'))),manning_n=.05,cfl=.35,progress_interval_wall_s=1000)
    for size in (1024,4096):
        rr,cc=np.indices((size,size),dtype=np.float32)
        z=(.005*np.sin(cc/100)+.003*np.cos(rr/100)).astype(np.float32)
        h=np.maximum(.1-z.astype(float),0.);h[size//3:size//2,size//3:size//2]+=.05
        c=np.zeros(z.shape,np.float32);c[size//3:size//2,size//3:size//2]=1
        report['benchmarks'].append(run_case('synthetic_'+str(size),z,h,c,cfg));write(output,report)
    del rr,cc,z,h,c
    base=ROOT/'assets/private/water_system/hydraulics'
    if not (base/'terrain.tif').exists():raise FileNotFoundError('Native regional test inputs missing')
    with rasterio.open(base/'terrain.tif') as src:z=src.read(1);z[z==src.nodata]=np.nan
    with rasterio.open(base/'initial.tif') as src:h=src.read(1).astype(float);h[h==src.nodata]=0
    # Zero tracer is valid for this short full-grid memory/performance test.
    # Nonuniform tracer is exercised in the preceding acceptance and medium tests.
    report['benchmarks'].append(run_case('full_native_region_0.5m',z,h,None,{**cfg,'duration_s':.5,'dt_max_s':.1}));write(output,report)
    report['status']='passed';write(output,report)

if __name__=='__main__':main()
