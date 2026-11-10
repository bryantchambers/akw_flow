# Durable project environment

The continuing project environment belongs at:

`/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel`

Activate it with `mamba activate qmodel`. Create it from the repository root using `mamba env create -f environment.yml`. Mamba manages Python and the environment prefix; the pinned scientific, GIS, report and browser packages use the versions captured from the tested project environment in `scripts/requirements-qmodel.lock.txt`.

The prior `/tmp/qmodel-gis-env` was temporary setup infrastructure. It is not the intended ongoing environment. Do not create new durable project environments under `/tmp`.

The dashboard uses the interpreter that starts `scripts/restart_dashboard.py`, so launch it from the activated environment or with its absolute interpreter path. The restart helper verifies this checkout's managed PID and HTTP readiness.

## CPU resources

Up to **40 threads** are authorized for regional modelling. Set `threads` in `configs/regional_native.json`; the default is now 40. Launch with `NUMBA_NUM_THREADS=40 python scripts/build_regional_native.py` so the Numba runtime's upper limit also permits 40. A previously started 32-thread calculation can finish without restarting solely for this increase.

## Temporary files

The project-related `/tmp` inventory contained:

- The 1.1 GB temporary Python environment used by the dashboard and active calculation.
- Scratch/edit/verification scripts, TOPSAR probe/reference files and downloaded C format references.
- An effectively empty legacy browser-testing directory.

Fourteen scratch/reference files were copied with SHA-256 records into `assets/private/maintenance/tmp_recovery/`. These are recovery copies, not canonical source code or runtime dependencies. The actual implemented scripts live in `scripts/` and `hydraulics/`.

Primary survey data, acquired datasets and model results remain under `assets/` (restricted spatial files under ignored `assets/private/`). Review screenshots/PDFs remain under `knowledge/`. Runtime logs and browser screenshots are under ignored `.runtime/` in the workspace.

Unrelated projects, user upload directories and live sockets/browser caches in `/tmp` were left alone. Temporary IPC sockets and short-lived test directories are appropriate uses of `/tmp`; scientific environments, datasets and final outputs are not.

Keep the old environment available until any calculation using it has finished and the durable replacement passes validation. Do not remove an environment while its processes are active.

## Migration verification

The durable environment passed all 101 tests. A native solver smoke test accepted 40 threads. The managed dashboard was restarted with the Miniforge interpreter and its HTTP health check passed. The already-running 32-thread regional calculation was preserved until completion; its original interpreter/version remain part of that run's provenance.

Migration is complete: the retired `/tmp/qmodel-gis-env` was removed after its final process exited. The fourteen checksum-verified scratch originals were removed after recovery. The active dashboard and validation tools use Miniforge; unrelated temporary files were preserved.
