# GPU acceleration assessment for the Angkor fixed-terrain model

Assessment date: 13 November 2026. **Implemented since this assessment:** see [the GPU backend and measured results](gpu_backend.md). This is a code/timing audit and literature review, not a measured GPU benchmark. No GPU job, software installation or hydraulic rerun was launched for this assessment.

## Recommendation

A GPU implementation is worth benchmarking. The current solver repeatedly applies nearest-neighbour raster operations to 372 million native cells, which is a suitable parallel workload. Start with a single A100 and unchanged 0.5 m geometry, arithmetic precision, face limiting, wetting/drying and transport rules. Measure accuracy and elapsed time against the 40-thread CPU reference before choosing an acceleration target. GPU execution will not resolve missing bathymetry, forcing data or hydraulic-regime limitations.

## Evidence from this checkout

The completed regional calculation used 372,366,336 rectangular grid cells, of which 372,327,658 have valid terrain. It simulated 60 seconds in 3,498 timesteps:

| Measured component | Time |
| --- | ---: |
| Solver loop | 92.16 minutes |
| Preparation, export and display work outside the recorded solver loop | 3.83 minutes |
| Build total | 95.99 minutes |
| Mean solver cost per timestep | 1.581 seconds |

These figures come from `assets/private/water_system/hydraulics/manifest.json`; they do not include the downstream finalizer, which stopped at its tracer-range check. About 96% of the build time was spent in the solver, so a faster solver can materially affect total runtime. The code is CPU Numba (`@njit(parallel=True)` and `prange`), not CUDA; installing CUDA alone will not accelerate it.

The current host exposes no CUDA device: `nvidia-smi` is absent, `/dev/nvidia*` is absent, and PCI enumeration reports a Matrox display controller. Slurm reports node `dandygpun01fl` in `compregular`, advertising `gpu:a100:2` with a mixed allocation state. This establishes scheduler-advertised hardware, not a guaranteed free allocation or confirmed GPU memory size. A scheduled GPU job must verify driver, toolkit, actual VRAM and access before benchmarking.

## Published evidence and alternatives

- **LISFLOOD-FP 8.1 (Sharifian et al., 2023)** is the closest comparison: its uniform-grid GPU ACC solver uses a local-inertial formulation. It reports GPU/CPU speedups around 2–28 across cases, with small cases sometimes showing little benefit. Its CPU reference used 12 threads, so those ratios cannot be applied to our 40-thread baseline. Much larger reported gains combine GPU execution with grid coarsening. [Paper](https://gmd.copernicus.org/articles/16/2391/2023/).
- **LISFLOOD-FP 8.0 (Shaw et al., 2021)** provides GPU finite-volume and discontinuous-Galerkin shallow-water solvers, useful reference engines if fast/transcritical flows require advective momentum. Its results also show that timestep restrictions and thin overland flow can limit runtime despite GPU execution. Switching engines would require geometry/forcing import, transport/output integration and validation. [Paper](https://gmd.copernicus.org/articles/14/3577/2021/).
- **LISFLOOD-FP 8.2 (Chowdhury and Kesserwani, 2025)** adds GPU dynamic resolution adaptation to DG2. This is a potential later optimization, but it changes which cells remain at the finest spacing. It is not evidence for achieving the same speedup on an everywhere-0.5 m grid. [Paper](https://gmd.copernicus.org/articles/18/9827/2025/).
- **HEC-RAS 2025 GPU solver:** USACE reports CUDA-based explicit solving and example speedups above 10x, with different hardware, meshes and CPU baselines. Its documented Windows/NVIDIA workflow is an alternative platform rather than a drop-in backend for this Linux/Python model. [Official documentation](https://www.hec.usace.army.mil/confluence/hecras/latest/gpu-solver).
- **FIP/RMG (2024):** a primary study of GPU kernel optimization for structured-grid shallow-water simulation. It demonstrates that data access and instruction throughput matter, beyond merely moving code to a GPU. [Paper](https://doi.org/10.1016/j.envsoft.2024.106030).

The first three open-access papers have been downloaded into `assets/manuscripts/` and registered in the acquisition and PDF-validation manifests.

## Memory and implementation requirements

At the initial assessment, the core arrays needed approximately **56 bytes per rectangular cell**: float32 terrain and donor scale, plus six float64 depth/mass/flux/work fields. That was **19.42 GiB**. The implemented GPU/CPU backends now use float64 donor factors, increasing core storage to about **20.81 GiB**, excluding GPU reduction scratch space, staging, masks, library overhead and retained output state. This is an array accounting estimate, not a measured GPU allocation.

A 24 GB GPU would have limited headroom for a direct full-domain port. A 40 GB or larger device is a more practical starting point; verify the advertised A100's capacity. Each additional float64 scalar raster adds about 2.77 GiB; a double-buffered constituent adds about 5.55 GiB before other work arrays. Changing everything to float32 could reduce core storage to roughly 11.10 GiB, but requires separate numerical validation, particularly at wet/dry fronts and for transport.

For a Python CUDA backend, use NVIDIA's maintained `numba-cuda` package. Numba's built-in CUDA target is deprecated. Explicit CUDA kernels and GPU memory management are still required; existing CPU decorators do not convert automatically. [NVIDIA installation guide](https://nvidia.github.io/numba-cuda/user/installation.html), [Numba deprecation notice](https://numba.readthedocs.io/en/stable/reference/deprecation.html#deprecation-of-the-built-in-cuda-target).

Keep terrain and hydraulic state on the GPU throughout a run. Preserve the ordered momentum, donor-scale, shared-face limiting and state-update phases. Synchronize phases correctly; kernel fusion must not introduce neighbour-dependent races. Use GPU reductions for CFL and diagnostics. Transfer saved snapshots rather than the complete domain on every step. Profile memory throughput, Manning/friction arithmetic, reductions and host synchronization instead of assuming one bottleneck.

## Further gains without reducing the 0.5 m cell size

Only about 15.4% of valid cells were above the run's 1 mm wet-cell reporting threshold at the final time. This suggests investigating dynamically active tiles. It does not justify dropping the other cells: thin water films, rainfall, wetting fronts and new spill paths can activate them. Any active-tile method must include neighbouring faces/halos, reactivate tiles dynamically and exchange fluxes conservatively. Tiles must never become isolated hydraulic basins.

Cache static terrain and geometry between scenario runs. GPU execution still obeys stability timestep restrictions; do not increase the timestep or remove deep cells simply to obtain a speedup. Adaptive/coarser floodplain meshes and local timestepping are separate numerical changes that require explicit tests of banks, narrow channels and multiple outlets.

## What a speedup would mean

Keeping the measured 3.83 minutes of non-solver work unchanged gives these illustrative arithmetic scenarios:

| Hypothetical solver speedup | Estimated total build time |
| --- | ---: |
| 3x | 34.6 minutes |
| 5x | 22.3 minutes |
| 10x | 13.0 minutes |
| 20x | 8.4 minutes |

These are not GPU predictions. They exclude queueing, additional downstream processing and any changed output costs. The last run simulated only one minute of physical time; hour/day scenarios remain a large workload even after substantial acceleration.

## Benchmark and acceptance plan

1. Resolve the CPU reference's tracer QA handling and review its supercritical-flow limitations.
2. Obtain one GPU allocation, query its actual hardware/driver, and profile the existing CPU kernels on matched test domains.
3. Implement a separate GPU backend in the durable Miniforge environment, retaining the CPU backend and existing artifacts.
4. Compare lake-at-rest, bank blocking/overtopping, multiple outlets, wet/dry propagation, reversal and water/tracer conservation on identical inputs. Include source/no-data boundaries and cross-tile exchange if tiling is introduced.
5. Benchmark a small native pilot, a medium multi-million-cell crop and then the full source grid. Record precision, GPU memory peak, timesteps, kernel/transfer/output times and end-to-end wall time. GPU and CPU runs must use the same physical duration, forcing, numerical method and timestep policy.
6. Accept acceleration only if differences in water levels, wet areas, outlet activation, reach fluxes and conservative transport are within predeclared tolerances. Test any later mixed precision or adaptive resolution as separate changes.

### CPU reference QA finding

The solver completed, but the finalizer rejected one exported concentration value of approximately 1.0000713 (initial maximum 1). A read-only scan found that cell's depth was approximately **1.21e-8 m**, representing about **3.03e-9 m³** of water. Concentration stayed at or below 1 in all cells at least 1 mm deep. This points to a dry-film/near-zero-denominator numerical issue, not demonstrated bulk tracer instability. Its cause and appropriate dry-cell reporting/validation convention still need correction; the failed acceptance has not been silently waived. Details are retained in `assets/private/water_system/tracer_bound_diagnosis.json`.
