# GPU-preferred native hydraulic solver

Implemented and tested on 13 November 2026. The regional dashboard now serves the verified `hydraulics_gpu` case. The CPU case is preserved. This improves computational performance; hydraulic regime and historical/bathymetric validation remain separate requirements.

## Slurm and the node-built environment

GPU work must run in a Slurm allocation on `dandygpun01fl`, not on the dashboard/login host. The production launcher requests one A100, 40 CPU threads, 96 GB host RAM and a two-hour limit in `compregular`.

The durable environment is `/maps/projects/caeg/people/gfx654/miniforge3/envs/qmodel-gpu-a100`. It was created and resolved on the allocated A100 node with Mamba, then CUDA/GIS/report packages were installed there. The CPU `qmodel` environment was retained. The tested GPU was an NVIDIA A100 PCIe 40 GB, compute capability 8.0, with driver 610.57.04 and CUDA 12.9 dependencies. The node reported glibc 2.28. Exact Python package versions are in `scripts/requirements-gpu-a100.lock.txt`; `environment-gpu.yml` describes the environment.

Run these commands from the project root with the ordinary CPU environment; they submit jobs rather than executing CUDA on the current host:

```bash
# Recheck GPU correctness on an allocated A100.
python scripts/submit_regional_gpu.py --validate

# Matched CPU/GPU benchmarks, including a short full-native-grid test.
python scripts/submit_regional_gpu.py --benchmark

# Full regional run into a fresh private case; verify/couple/activate afterward.
python scripts/submit_regional_gpu.py \
  --output assets/private/water_system/hydraulics_gpu_next
```

A completed output directory is never overwritten implicitly. Per-job installation, hardware, test, solver and finalization logs are under `.runtime/gpu/job-<jobid>/`. The batch job exits after its requested task, releasing the allocation. There are no indefinite marker-file waits in the production launcher.

`configs/water_system.json` uses `backend: auto`, which prefers a visible supported GPU and otherwise uses the CPU. `configs/water_system_gpu.json` explicitly requires `backend: gpu`. The regional producer CLI defaults to the GPU configuration and refuses to start outside Slurm; submit it through the helper. The lower-level `simulate` API retains CPU fallback for `auto` on CPU-only installations. A requested GPU backend fails if CUDA is unavailable or memory is insufficient; it does not silently perform the regional job on CPUs.

## Implementation and numerical behavior

`hydraulics/native_gpu.py` implements the same ordered phases as the CPU solver:

1. Momentum/fully implicit quadratic Manning friction on east and south faces.
2. Donor water-availability factors.
3. Shared-face discharge limiting, using the same factor for both adjacent cells.
4. Conservative water/upwind unit-tracer update, rainfall and infiltration losses.

Each native cell has a GPU thread. Kernels operate on flattened contiguous arrays, respecting row edges and no-data barriers. Hydraulic state, fluxes, work arrays and donor factors use float64; terrain remains source float32. Fast math is disabled. Donor factors were promoted from float32 to float64 on both backends to avoid rounding a limiting factor upward at near-empty cells.

All simulation arrays remain resident on the GPU. Block/tree reductions produce seven diagnostics; only those scalars are transferred to the CPU each timestep for the CFL policy and reporting. Final state arrays are downloaded once. Core state plus reduction storage is approximately 21 GiB for this grid, fitting the allocated 40 GB A100 with headroom. Multi-GPU decomposition, adaptive/coarse cells and active-tile skipping were not introduced. The solver still uses the original 0.5 m grid, stability timestep policy and local-inertial approximation; it still rejects unsupported groundwater and stage-boundary options.

## Measured acceptance and performance

Slurm job **23777349** built the environment, passed all ten GPU/dispatch tests, ran paired benchmarks and completed the full regional case. GPU correctness tests cover lake at rest, wetting/tracer propagation, no-data blocking, crest overtopping/multiple outlets, rain/infiltration, reverse flow and irregular array/block sizes. Both backends use the same double-precision donor factors in paired tests.

| Matched test | Solver speedup | Including allocation/setup and final array copies |
| --- | ---: | ---: |
| 1,048,576 cells, 1 simulated second | 11.54x | 5.07x |
| 16,777,216 cells, 1 simulated second | 20.28x | 7.24x |
| 372,366,336 rectangular cells, 0.5 simulated second | 24.55x | 5.08x |

Here "allocation/setup" means in-process array allocation and transfer, not Slurm queue time or environment installation. CPU runs used 40 allocated threads on the same GPU node. The full-grid short test used zero tracer; nonuniform tracer was tested in the acceptance cases and both synthetic benchmark sizes. The paired full-grid maximum absolute depth difference was about **1.42e-14 m**. These are comparisons of the same numerical equations, not independent hydraulic validation.

The full **60-second** water-present regional experiment then completed **3,498 timesteps** on the GPU:

| Component | GPU | Previous saved CPU case |
| --- | ---: | ---: |
| Solver loop | 186.91 s (3.12 min) | 5,529.61 s (92.16 min) |
| Regional build including preparation/export/display indices | 357.56 s (5.96 min) | 5,759.59 s (95.99 min) |

The earlier full CPU run used a different host and float32 donor factors; treat this full-case timing comparison as operational evidence rather than a strict hardware-isolated benchmark. The paired short tests above are the controlled comparison. Final verification, coupling and PDF production are additional CPU postprocessing and are excluded from regional-build times.

Water and unit-tracer residuals in the full GPU solve were approximately **-4.66e-10** in their respective integrated units. Native export geometry, finite/nonnegative state, wet-cell tracer bounds, conservation, source samples and executed source snapshots passed verification. All 2,801 reaches were processed, producing 8,403 cross-sections. The GeoPackage and diagnosis PDF were rebuilt.

Slurm job **23777630** independently tested the finished, marker-free launcher against its locked node environment and passed all ten GPU/dispatch tests. Both jobs completed and released their allocations. CPU-host project tests passed with the hardware-only GPU tests explicitly skipped there; those tests ran on the A100 allocations. Desktop/mobile browser checks passed with no JavaScript errors, the GPU case selected, native faces visible, and the PDF download functioning.

Evidence is retained under `assets/private/water_system/gpu_validation/` and in the GPU case manifest/verification files. The source snapshots identify the executed numerical code.

## Preferred result and dashboard routing

`assets/private/water_system/active_case.json` selects a completed, verified and coupled case. The server resolves this selection once per request, so concurrent requests cannot change another request's raster directory. Raster caches include the case directory. The viewer refreshes when the active case changes and identifies the actual backend/device.

The production Slurm workflow finalizes and activates its successful result. Activation requires matching native verification, coupling and acceptance records. A missing, changed or incomplete active case does not silently serve a stale final snapshot. The original CPU data stays under `assets/private/water_system/hydraulics/`.

## Tracer QA and remaining hydraulic limits

The earlier CPU export had one concentration excursion at a roughly 12-nanometre water depth. The verifier now applies concentration bounds to water at or above the model's existing dry-depth threshold, while recording dry-film excursions and all their mass separately. It additionally rejects appreciable excess dry-film tracer mass. No raster values are clipped or rewritten to pass this check. The GPU output has **zero** dry-film excursions and a resolved wet tracer range of **[1, 1]** for this uniform unit-tracer experiment.

The hydraulic-regime warning remains: 51,675 exported faces at least 1 cm deep exceed Froude 1. GPU acceleration does not add advective momentum, fix unverified submerged bathymetry, provide observed boundary forcing or establish archaeological accuracy. The active result is an exploratory water-present relaxation experiment, not a validated flood/drought or contaminant-hotspot forecast.

References for CUDA and comparative solver literature are in [the research assessment](gpu_hydraulics_assessment.md).
