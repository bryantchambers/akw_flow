#!/usr/bin/env python3
"""Preferred GPU workflow: request Slurm resources, then build/run on the A100."""
import argparse,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--benchmark',action='store_true')
    mode.add_argument('--validate',action='store_true')
    p.add_argument('--output',default='assets/private/water_system/hydraulics_gpu')
    args=p.parse_args();(ROOT/'.runtime/gpu').mkdir(parents=True,exist_ok=True)
    output=Path(args.output)
    if not output.is_absolute():output=ROOT/output
    if not output.resolve().is_relative_to((ROOT/'assets/private/water_system').resolve()):raise ValueError('Survey derivatives must stay under assets/private')
    if not args.benchmark and not args.validate and (output/'manifest.json').exists():raise ValueError('Output exists; provide a fresh --output directory')
    cmd=['sbatch','--parsable','--chdir',str(ROOT),str(ROOT/'scripts/slurm/qmodel_gpu.sbatch'),'benchmark' if args.benchmark else 'validate' if args.validate else 'regional']
    if not args.benchmark and not args.validate:cmd.append(str(output))
    subprocess.run(cmd,check=True,cwd=ROOT)

if __name__=='__main__':main()
