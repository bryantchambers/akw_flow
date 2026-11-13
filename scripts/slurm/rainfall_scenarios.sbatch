#!/usr/bin/env bash
#SBATCH --job-name=qmodel-rain
#SBATCH --partition=compregular
#SBATCH --nodelist=dandygpun01fl
#SBATCH --gres=gpu:a100:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=96G
#SBATCH --time=12:00:00
#SBATCH --output=.runtime/gpu/rain-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
suite=${1:?Pass the prepared suite directory}
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}" NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export NUMBA_ENABLE_CUDASIM=0 PYTHONUNBUFFERED=1
prefix=/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel-gpu-a100
mamba_bin=/maps/projects/caeg/people/gfx654/miniforge3/bin/mamba
logdir="$suite/slurm-${SLURM_JOB_ID}"
mkdir -p "$logdir"
hostname > "$logdir/hostname.txt"
nvidia-smi --query-gpu=name,uuid,memory.total,driver_version --format=csv > "$logdir/hardware.csv"
# Any environment creation or package resolution takes place on the A100 host.
if [[ ! -x "$prefix/bin/python" ]]; then "$mamba_bin" create -y -p "$prefix" -c conda-forge python=3.12 pip; fi
"$prefix/bin/python" -m pip install -r scripts/requirements-gpu-a100.lock.txt > "$logdir/environment.log" 2>&1
"$prefix/bin/python" -m pip freeze > "$logdir/requirements.lock.txt"
srun --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK}" "$prefix/bin/python" -m unittest tests.test_native_gpu > "$logdir/gpu-tests.log" 2>&1
srun --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK}" "$prefix/bin/python" scripts/run_rainfall_scenarios.py --run "$suite" ${2:-} > "$logdir/run.log" 2>&1
