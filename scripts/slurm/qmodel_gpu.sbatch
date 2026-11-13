#!/usr/bin/env bash
#SBATCH --job-name=qmodel-gpu
#SBATCH --partition=compregular
#SBATCH --nodelist=dandygpun01fl
#SBATCH --gres=gpu:a100:1
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=40
#SBATCH --mem=96G
#SBATCH --time=02:00:00
#SBATCH --output=.runtime/gpu/slurm-%j.log
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:?}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}" NUMBA_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export PYTHONUNBUFFERED=1
export QMODEL_GPU_ENV=/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel-gpu-a100
export QMODEL_MAMBA=/maps/projects/caeg/people/gfx654/miniforge3/bin/mamba
task=${1:-regional}
case "$task" in benchmark|regional|validate) ;; *) echo 'Task must be benchmark, validate or regional' >&2; exit 2 ;; esac
run_dir="$PWD/.runtime/gpu/job-${SLURM_JOB_ID}"
mkdir -p "$run_dir"
printf '%s\n' "$run_dir" > .runtime/gpu/current-job-path
hostname > "$run_dir/hostname.txt"
getconf GNU_LIBC_VERSION > "$run_dir/glibc.txt"
nvidia-smi --query-gpu=name,uuid,memory.total,driver_version --format=csv > "$run_dir/hardware.csv"
# Environment creation and binary resolution must happen on this allocated node.
if [[ ! -x "$QMODEL_GPU_ENV/bin/python" ]]; then
 "$QMODEL_MAMBA" create -y -p "$QMODEL_GPU_ENV" -c conda-forge python=3.12 pip
fi
if [[ -f scripts/requirements-gpu-a100.lock.txt ]]; then
 "$QMODEL_GPU_ENV/bin/python" -m pip install -r scripts/requirements-gpu-a100.lock.txt > "$run_dir/install.log" 2>&1
else
 "$QMODEL_GPU_ENV/bin/python" -m pip install -r scripts/requirements-gis.txt -r scripts/requirements-native.txt -r scripts/requirements-reports.txt -r scripts/requirements-gpu.txt > "$run_dir/install.log" 2>&1
fi
"$QMODEL_GPU_ENV/bin/python" -m pip freeze > "$run_dir/requirements.lock.txt"
"$QMODEL_GPU_ENV/bin/python" -c 'from numba import cuda; print(cuda.detect()); assert cuda.is_available()' > "$run_dir/cuda-detect.txt"
touch "$run_dir/environment-ready"
if [[ "$task" == validate ]]; then
 srun --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK}" "$QMODEL_GPU_ENV/bin/python" -m unittest tests.test_native_gpu > "$run_dir/acceptance-tests.log" 2>&1
elif [[ "$task" == benchmark ]]; then
 srun --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK}" "$QMODEL_GPU_ENV/bin/python" scripts/benchmark_gpu.py --output "$run_dir/benchmark.json" > "$run_dir/benchmark.log" 2>&1
else
 output=${2:-assets/private/water_system/hydraulics_gpu}
 # Do not silently overwrite a previous completed GPU case.
 if [[ -f "$output/manifest.json" ]]; then
  echo 'Output already exists; supply a fresh output directory or archive it explicitly' >&2; exit 2
 fi
 srun --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK}" "$QMODEL_GPU_ENV/bin/python" -m unittest tests.test_native_gpu > "$run_dir/acceptance-tests.log" 2>&1
 srun --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK}" "$QMODEL_GPU_ENV/bin/python" scripts/build_regional_native.py --config configs/water_system_gpu.json --output "$output" > "$run_dir/regional.log" 2>&1
 srun --ntasks=1 --cpus-per-task="${SLURM_CPUS_PER_TASK}" "$QMODEL_GPU_ENV/bin/python" scripts/finalize_water_system.py --model-dir "$output" --activate > "$run_dir/finalization.log" 2>&1
fi
